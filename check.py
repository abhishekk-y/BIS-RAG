import fitz
doc = fitz.open('d:/STUFF/BIS/Assets/dataset.pdf')
text = ""
for i in range(100, 150):
    text += doc[i].get_text()

import re
summary_pattern = re.compile(
    r'(?:SUMMARY\s+OF\s*\n\s*)?^IS\s+'
    r'(\d+(?:\s*\(Part\s*\d+\))?)\s*'
    r'[:\-]\s*'
    r'(\d{4})\s+'
    r'([A-Z][^\n]*)',
    re.IGNORECASE | re.MULTILINE
)
matches = summary_pattern.finditer(text)
for m in matches:
    print(m.group(0).strip())
