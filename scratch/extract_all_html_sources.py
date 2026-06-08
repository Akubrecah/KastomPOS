import json
import os

log_path = "/Users/Akubrecah/.gemini/antigravity-ide/brain/b02e7334-3c36-454a-8cd9-07e94da4959e/.system_generated/logs/transcript.jsonl"
output_dir = "/Users/Akubrecah/Desktop/KastomPOS/scratch/extracted_html"
os.makedirs(output_dir, exist_ok=True)

print("Scanning transcript.jsonl for all HTML payloads...")
with open(log_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        try:
            data = json.loads(line)
            step_idx = data.get("step_index")
            source = data.get("source")
            content = data.get("content", "")
            
            if not content:
                continue
            
            # Look for DOCTYPE or standard HTML patterns in USER messages
            if "html" in content.lower() and "<head" in content.lower() and source == "USER_EXPLICIT":
                title_match = None
                title_idx = content.find("<title>")
                if title_idx != -1:
                    end_title_idx = content.find("</title>", title_idx)
                    if end_title_idx != -1:
                        title_match = content[title_idx+7:end_title_idx].strip()
                
                print(f"Step {step_idx}: source={source}, len={len(content)}, title={title_match}")
                
                # Save the full content to a file in extracted_html
                sanitized_title = "".join([c if c.isalnum() else "_" for c in str(title_match or "page")])
                filename = f"step_{step_idx}_{sanitized_title}.html"
                filepath = os.path.join(output_dir, filename)
                with open(filepath, 'w', encoding='utf-8') as out_f:
                    out_f.write(content)
                print(f"  -> Saved to {filename}")
        except Exception as e:
            pass
print("Scan completed.")
