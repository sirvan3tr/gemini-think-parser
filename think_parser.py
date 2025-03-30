# -*- coding: utf-8 -*-
import re
import sys
from bs4 import BeautifulSoup, NavigableString, Tag

# --- Configuration ---
LATEX_PREAMBLE = r"""\documentclass{article}
\usepackage{amsmath} % For math environments like align, used by KaTeX
\usepackage{amssymb} % For math symbols
\usepackage{amsfonts} % For math fonts
\usepackage{ulem}    % For \underline, if needed (used by KaTeX underline)

% Optional: Adjust margins if needed
\usepackage[margin=1in]{geometry}

% Improve spacing around math environments and lists if needed
%\usepackage{parskip} 

\begin{document}
"""

LATEX_POSTAMBLE = r"""
\end{document}
"""

# --- LaTeX Conversion Logic ---

def clean_text(text):
    """Cleans up excessive whitespace from text nodes."""
    # Replace multiple spaces/newlines with a single space
    text = re.sub(r'\s+', ' ', text)
    return text.strip() # Remove leading/trailing whitespace

def html_to_latex(element):
    """Recursively converts a BeautifulSoup element (and its children) to LaTeX."""
    latex_string = ""

    if isinstance(element, NavigableString):
        # Handle plain text nodes
        cleaned = clean_text(str(element))
        # Basic LaTeX escaping (add more if needed)
        cleaned = cleaned.replace('%', '\\%')
        cleaned = cleaned.replace('&', '\\&')
        cleaned = cleaned.replace('_', '\\_')
        cleaned = cleaned.replace('#', '\\#')
        cleaned = cleaned.replace('$', '\\$')
        # Add space if the string is not empty and the previous char wasn't whitespace or start
        if cleaned:
             latex_string += cleaned + " " # Add a space after text chunks
        return latex_string

    if not isinstance(element, Tag):
        return "" # Should not happen with BS4 typical usage

    # --- Handle specific HTML tags ---
    tag_name = element.name.lower()

    if tag_name == 'p':
        # Paragraphs: process children and add paragraph break
        inner_latex = ""
        for child in element.children:
            inner_latex += html_to_latex(child)
        latex_string += inner_latex.strip() + "\n\n" # Double newline for paragraph

    elif tag_name == 'span':
        # Spans usually just contain text or other inline elements
        inner_latex = ""
        for child in element.children:
            inner_latex += html_to_latex(child)
        latex_string += inner_latex # Keep spans inline

    elif tag_name == 'ms-katex':
        # KaTeX math elements
        # Try finding the annotation tag first (most reliable)
        annotation_tag = element.find('annotation', encoding='application/x-tex')
        if annotation_tag and annotation_tag.string:
            math_content = annotation_tag.string.strip()
            # Decide inline vs display based on class or structure (heuristic)
            if 'inline' in element.get('class', []):
                 # Add space before if previous text didn't end with space
                latex_string += f"${math_content}$ "
            else:
                # Assume display math if not explicitly inline
                latex_string += f"\\[\n{math_content}\n\\]\n\n"
        else:
             # Fallback: try finding code tag directly (less reliable)
             code_tag = element.find('code')
             if code_tag and code_tag.string:
                 math_content = code_tag.string.strip()
                 latex_string += f"${math_content}$ " # Default to inline as fallback
             else:
                 print(f"Warning: Could not extract LaTeX from <ms-katex>: {element}", file=sys.stderr)
        # Add trailing space for inline math

    elif tag_name == 'br':
        # Line break
        latex_string += "\n"

    elif tag_name == 'ol':
        # Ordered list
        latex_string += "\\begin{enumerate}\n"
        inner_latex = ""
        for child in element.children:
            inner_latex += html_to_latex(child)
        latex_string += inner_latex.strip() # Remove potential trailing spaces before end env
        latex_string += "\n\\end{enumerate}\n\n"

    elif tag_name == 'li':
        # List item
        latex_string += "  \\item "
        inner_latex = ""
        for child in element.children:
            inner_latex += html_to_latex(child)
        # Handle potential nested paragraphs inside <li> which add extra newlines
        inner_latex = inner_latex.strip() # Remove leading/trailing whitespace/newlines
        inner_latex = re.sub(r'\n\n+', '\n', inner_latex) # Reduce multiple newlines inside item
        latex_string += inner_latex + "\n" # Newline after each item

    elif tag_name == 'div' and 'mat-expansion-panel-body' in element.get('class', []):
        # Process the content of the main container div, but don't add div tags
        inner_latex = ""
        for child in element.children:
            inner_latex += html_to_latex(child)
        latex_string += inner_latex

    elif tag_name in ['ms-text-chunk', 'ms-cmark-node', 'div', 'pre', 'code', 'math', 'semantics']:
        # Process children of structural/intermediate tags without adding the tags themselves
        # Note: We specifically handle the 'annotation' tag inside 'ms-katex' already.
        # 'code' inside 'ms-katex' is handled via fallback, but generic 'code' might need specific handling if used differently.
        inner_latex = ""
        for child in element.children:
            inner_latex += html_to_latex(child)
        latex_string += inner_latex

    # Add more tag handlers here if needed (e.g., <em> -> \emph{}, <strong> -> \textbf{}, <a> -> \href{})

    else:
        # Default: Process children for unknown tags, print a warning
        print(f"Warning: Unhandled tag <{tag_name}>. Processing children.", file=sys.stderr)
        inner_latex = ""
        for child in element.children:
            inner_latex += html_to_latex(child)
        latex_string += inner_latex

    return latex_string

def post_process_latex(latex_code):
    """Apply final cleanup rules to the generated LaTeX."""
    # Remove spaces before punctuation that might occur due to added spaces
    latex_code = re.sub(r'\s+([.,;:!?])', r'\1', latex_code)
    # Remove space before line breaks
    latex_code = re.sub(r'\s+\n$', r'\n', latex_code, flags=re.MULTILINE)
    # Remove space immediately before enumerate/itemize items
    latex_code = re.sub(r'\s+\\item', r'\\item', latex_code)
     # Remove space immediately before math mode start $
    #latex_code = re.sub(r'\s+\$', r'$', latex_code)
    # Remove space immediately after math mode end $ (if followed by punctuation/newline)
    #latex_code = re.sub(r'\$\s+([.,;:!?\n])', r'$\1', latex_code)
    # Consolidate multiple paragraph breaks
    latex_code = re.sub(r'(\n\s*){3,}', '\n\n', latex_code)
    # Remove leading/trailing whitespace from the whole result
    latex_code = latex_code.strip()
    return latex_code

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python think_parser.py <input_html_file> <output_latex_file>")
        sys.exit(1)

    input_html_file = sys.argv[1]
    output_latex_file = sys.argv[2]

    print(f"Reading HTML from: {input_html_file}")
    try:
        with open(input_html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"Error: Input file '{input_html_file}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading input file: {e}")
        sys.exit(1)

    print("Parsing HTML...")
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find the main content div (adjust selector if needed)
    # Using a more general search if the exact class isn't always present
    # Prioritize the specific class if found
    content_div = soup.find('div', class_='mat-expansion-panel-body')
    if not content_div:
         # Fallback: try finding the first div or body if the specific one isn't there
         content_div = soup.find('div') or soup.find('body')

    if not content_div:
        print("Error: Could not find main content container in HTML.")
        sys.exit(1)

    print("Converting to LaTeX...")
    latex_body = html_to_latex(content_div)
    latex_body_cleaned = post_process_latex(latex_body)

    print(f"Writing LaTeX to: {output_latex_file}")
    try:
        with open(output_latex_file, 'w', encoding='utf-8') as f:
            #f.write(LATEX_PREAMBLE)
            f.write(latex_body_cleaned)
            #f.write(LATEX_POSTAMBLE)
    except Exception as e:
        print(f"Error writing output file: {e}")
        sys.exit(1)

    print("Conversion complete.")