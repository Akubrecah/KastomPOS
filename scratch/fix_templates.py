import re

def fix_template_responses(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # Regex to find: templates.TemplateResponse("name.html", {"request": request, ...})
    # and convert to: templates.TemplateResponse(request=request, name="name.html", context={...})
    
    # This is tricky because context can be a variable or a literal dictionary
    # Let's target the most common problematic pattern:
    # templates.TemplateResponse("name.html", {"request": request, ...})
    
    def replacement(match):
        full_match = match.group(0)
        args_str = match.group(1)
        
        # Split args by comma, but be careful with nested commas in dicts
        # For simplicity, if it's already using keyword arguments, skip it.
        if 'request=' in args_str and 'name=' in args_str:
            return full_match
            
        # Try to find request in the second argument
        # Pattern: TemplateResponse("filename", {"request": request, ...})
        m = re.match(r'"([^"]+)",\s*(\{.*"request":\s*request.*\})', args_str, re.DOTALL)
        if m:
            name = m.group(1)
            context = m.group(2)
            return f'templates.TemplateResponse(request=request, name="{name}", context={context})'
            
        # Pattern: TemplateResponse("filename", context_var)
        m = re.match(r'"([^"]+)",\s*([a-zA-Z0-9_]+)', args_str)
        if m:
            name = m.group(1)
            context_var = m.group(2)
            return f'templates.TemplateResponse(request=request, name="{name}", context={context_var})'

        return full_match

    # Simple regex for the call and its arguments
    new_content = re.sub(r'templates\.TemplateResponse\((.*?)\)', replacement, content, flags=re.DOTALL)
    
    with open(file_path, 'w') as f:
        f.write(new_content)

if __name__ == "__main__":
    fix_template_responses('main.py')
