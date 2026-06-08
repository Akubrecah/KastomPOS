import os
import re

templates_dir = "/Users/Akubrecah/Desktop/KastomPOS/templates"
files_checked = 0
violations = []

# Exclude URLs from check
for root, dirs, files in os.walk(templates_dir):
    for file in files:
        if file.endswith('.html'):
            files_checked += 1
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Remove all tags and URLs
            clean_content = re.sub(r'<[^>]+>', ' ', content)
            clean_content = re.sub(r'https?://[^\s]+', ' ', clean_content)
            
            if "jipos" in clean_content.lower():
                # Find matching lines
                lines = content.split('\n')
                for idx, line in enumerate(lines):
                    if "jipos" in line.lower() and "demo1.jipos.co" not in line.lower():
                        violations.append((file, idx + 1, line.strip()))

print(f"Checked {files_checked} templates.")
if violations:
    print(f"Found {len(violations)} legacy branding violations:")
    for file, line_num, text in violations:
        print(f"  - {file}:{line_num}: {text}")
else:
    print("No legacy branding violations found! Branding is clean.")
