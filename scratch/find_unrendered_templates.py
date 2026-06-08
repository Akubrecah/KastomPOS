import os
import re

def find_unrendered():
    templates_dir = "/Users/Akubrecah/Desktop/KastomPOS/templates"
    templates = [f for f in os.listdir(templates_dir) if f.endswith(".html") and not f.startswith("_")]
    
    main_path = "/Users/Akubrecah/Desktop/KastomPOS/main.py"
    with open(main_path) as f:
        main_content = f.read()
        
    html_references = re.findall(r'[\"\']([^\"\']+\.html)[\"\']', main_content)
    
    unrendered = []
    for t in templates:
        if t not in html_references:
            unrendered.append(t)
            
    print(f"Total templates: {len(templates)}")
    print(f"Referenced in main.py: {len(set(html_references))}")
    print(f"Unrendered templates ({len(unrendered)}):")
    for t in sorted(unrendered):
        print(f"  - {t}")

if __name__ == "__main__":
    find_unrendered()
