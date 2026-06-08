import json
import re

transcript_path = "/Users/Akubrecah/.gemini/antigravity-ide/brain/b02e7334-3c36-454a-8cd9-07e94da4959e/.system_generated/logs/transcript.jsonl"

print("Searching transcript for Room Sale Report...")
found = False

with open(transcript_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        try:
            data = json.loads(line)
            content = data.get("content", "")
            if not content:
                # Also check tool_calls or other fields in step if content is empty
                continue
            
            if "Room Sale Report | JiPOS" in content:
                print(f"Match found at line {i}, step_index: {data.get('step_index')}, type: {data.get('type')}, source: {data.get('source')}")
                print(f"Content length: {len(content)}")
                
                # Let's extract the HTML portion
                html_start = content.find("<!DOCTYPE html>")
                if html_start != -1:
                    html_content = content[html_start:]
                    # If there are trailing tags or markdown wrappers, keep it clean
                    html_end = html_content.rfind("</html>")
                    if html_end != -1:
                        html_content = html_content[:html_end+7]
                    
                    output_file = "/Users/Akubrecah/Desktop/KastomPOS/scratch/extracted_jipos_page.html"
                    with open(output_file, 'w', encoding='utf-8') as out:
                        out.write(html_content)
                    print(f"Successfully saved clean HTML to {output_file} (length: {len(html_content)})")
                    found = True
        except Exception as e:
            pass

if not found:
    print("No direct content match found in 'content' field. Searching all values recursively...")
    # Let's search inside any string value in the JSON
    with open(transcript_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if "Room Sale Report | JiPOS" in line:
                print(f"Found 'Room Sale Report | JiPOS' raw substring on line {i} of transcript!")
                try:
                    data = json.loads(line)
                    # Let's pretty print the keys and structure
                    print(f"Keys: {list(data.keys())}")
                    # Let's find where the HTML is
                    raw_str = json.dumps(data)
                    html_start = raw_str.find("<!DOCTYPE html>")
                    if html_start != -1:
                        # unescape or get raw
                        # We can extract the HTML from the raw line using regex
                        matches = re.findall(r'<!DOCTYPE html>.*?</html>', raw_str)
                        if matches:
                            html_content = matches[-1] # take the last one or the longest
                            # Decode escape sequences if needed
                            html_content = html_content.encode().decode('unicode-escape')
                            output_file = "/Users/Akubrecah/Desktop/KastomPOS/scratch/extracted_jipos_page.html"
                            with open(output_file, 'w', encoding='utf-8') as out:
                                out.write(html_content)
                            print(f"Successfully regex extracted clean HTML to {output_file} (length: {len(html_content)})")
                            found = True
                            break
                except Exception as e:
                    print(f"Error parsing line {i}: {e}")
