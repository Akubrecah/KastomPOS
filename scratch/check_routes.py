import re
import os

def check_routes():
    # Read all hrefs from _sidebar.html
    sidebar_path = "/Users/Akubrecah/Desktop/KastomPOS/templates/_sidebar.html"
    if not os.path.exists(sidebar_path):
        print("Sidebar not found")
        return
        
    with open(sidebar_path) as f:
        content = f.read()
        
    hrefs = set(re.findall(r'href="([^"#]+)"', content))
    print(f"Found {len(hrefs)} unique links in sidebar.")
    
    # Read main.py to find defined routes
    main_path = "/Users/Akubrecah/Desktop/KastomPOS/main.py"
    with open(main_path) as f:
        main_content = f.read()
        
    # Simple regex to find @app.get("...") or @app.post("...")
    routes = set(re.findall(r'@app\.(?:get|post|put|delete|patch)\(\"([^\"]+)\"', main_content))
    print(f"Found {len(routes)} routes in main.py.")
    
    missing = []
    found = []
    
    for href in sorted(hrefs):
        if href == "/":
            found.append(href)
            continue
            
        # Check direct match
        matched = False
        for route in routes:
            # Handle path parameters or fast matches
            route_regex = re.sub(r'\{[^\}]+\}', r'[^/]+', route)
            if re.match(f"^{route_regex}/?$", href):
                matched = True
                break
        if matched:
            found.append(href)
        else:
            missing.append(href)
            
    print("\n--- LINK STATUS ---")
    print(f"✅ Active/Matched Links ({len(found)}):")
    for link in found:
        print(f"  - {link}")
        
    print(f"\n❌ Missing/Broken Links ({len(missing)}):")
    for link in missing:
        print(f"  - {link}")

if __name__ == "__main__":
    check_routes()
