import re
import os

def check_files_and_routes():
    templates_dir = "/Users/Akubrecah/Desktop/KastomPOS/templates"
    templates = os.listdir(templates_dir)
    
    # Read _sidebar.html
    sidebar_path = os.path.join(templates_dir, "_sidebar.html")
    with open(sidebar_path) as f:
        content = f.read()
    hrefs = sorted(list(set(re.findall(r'href="([^"#]+)"', content))))
    
    # Read main.py routes
    main_path = "/Users/Akubrecah/Desktop/KastomPOS/main.py"
    with open(main_path) as f:
        main_content = f.read()
    routes = set(re.findall(r'@app\.(?:get|post|put|delete|patch)\(\"([^\"]+)\"', main_content))
    
    print(f"{'Link':<50} | {'Route in main.py?':<20} | {'Matching Template?':<30}")
    print("-" * 105)
    
    for href in hrefs:
        if href == "/":
            continue
            
        # Check route
        has_route = False
        for route in routes:
            route_regex = re.sub(r'\{[^\}]+\}', r'[^/]+', route)
            if re.match(f"^{route_regex}/?$", href):
                has_route = True
                break
                
        # Check template file by analyzing the suffix or guessing the name
        # E.g. /admin/config/categories -> categories.html
        # E.g. /admin/reports/general-sales -> general_sales.html or similar
        parts = href.strip("/").split("/")
        candidate_names = []
        if len(parts) >= 1:
            candidate_names.append(f"{parts[-1]}.html")
            candidate_names.append(f"{'_'.join(parts[1:])}.html")
            candidate_names.append(f"{'_'.join(parts)}.html")
            candidate_names.append(f"{parts[-1].replace('-', '_')}.html")
            candidate_names.append(f"{'_'.join(parts[1:]).replace('-', '_')}.html")
            candidate_names.append(f"{'_'.join(parts).replace('-', '_')}.html")
            
        matching_template = "None"
        for cand in candidate_names:
            if cand in templates:
                matching_template = cand
                break
                
        route_str = "✅ Yes" if has_route else "❌ No"
        temp_str = f"✅ {matching_template}" if matching_template != "None" else "❌ No"
        
        if not has_route or matching_template == "None":
            print(f"{href:<50} | {route_str:<20} | {temp_str:<30}")

if __name__ == "__main__":
    check_files_and_routes()
