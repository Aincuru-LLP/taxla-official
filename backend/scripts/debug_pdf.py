import fitz
import sys

def debug_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    page = doc[35] # Page 36 in PDF reader
    text = page.get_text("text")
    print("PAGE 36 TEXT:")
    print(repr(text[:500]))
    
    page = doc[36] # Page 37 in PDF reader
    text = page.get_text("text")
    print("\nPAGE 37 TEXT:")
    print(repr(text[:500]))

if __name__ == "__main__":
    debug_pdf(sys.argv[1])
