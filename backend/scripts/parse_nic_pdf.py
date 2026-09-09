import re
import json
import pymupdf
import sys

def parse_pdf(pdf_path, output_json):
    doc = pymupdf.open(pdf_path)
    
    codes = []
    
    pattern_5digit = re.compile(r'^(\d{5})$')
    pattern_5digit_with_desc = re.compile(r'^(\d{5})\s+(.+)$')
    
    current_code = None
    current_desc = []
    
    def save_current():
        nonlocal current_code, current_desc
        if current_code:
            desc_str = " ".join(current_desc).strip()
            if desc_str:
                codes.append({
                    "nic_2digit": current_code[:2],
                    "nic_4digit": current_code[:4],
                    "nic_5digit": current_code,
                    "description": desc_str
                })
        current_code = None
        current_desc = []

    for i in range(35, 138): 
        if i >= len(doc):
            break
        page = doc[i]
        text = page.get_text("text")
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip page numbers which are usually 1-3 digits alone
            if re.match(r'^\d{1,3}$', line):
                continue
            
            # Check if line is a 5 digit code with description inline
            match_inline = pattern_5digit_with_desc.match(line)
            if match_inline:
                save_current()
                current_code = match_inline.group(1)
                current_desc.append(match_inline.group(2))
                save_current() # usually it's one line if it's inline, but we can just save it immediately
                continue
                
            # Check if line is exactly a 5 digit code
            match_exact = pattern_5digit.match(line)
            if match_exact:
                save_current()
                current_code = match_exact.group(1)
                continue
            
            # If it's a 3 or 4 digit code alone, or heading, we can stop accumulating description
            if re.match(r'^\d{3,4}$', line) or line.isupper() or line.startswith("This class"):
                if current_code:
                    save_current()
                continue
            
            # Otherwise, it might be part of the description
            if current_code:
                current_desc.append(line)
    
    # Save the last one
    save_current()
    
    # Remove duplicates preserving order
    seen = set()
    unique_codes = []
    for c in codes:
        if c['nic_5digit'] not in seen:
            seen.add(c['nic_5digit'])
            unique_codes.append(c)

    print(f"Extracted {len(unique_codes)} NIC codes.")
    
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(unique_codes, f, indent=2, ensure_ascii=False)
    print(f"Saved to {output_json}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python parse_nic_pdf.py <pdf_path> <output_json>")
        sys.exit(1)
    parse_pdf(sys.argv[1], sys.argv[2])
