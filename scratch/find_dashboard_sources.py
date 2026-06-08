import json
import re

transcript_path = "/Users/Akubrecah/.gemini/antigravity-ide/brain/b02e7334-3c36-454a-8cd9-07e94da4959e/.system_generated/logs/transcript.jsonl"

print("Searching transcript for Dashboard or Index pages...")
with open(transcript_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        try:
            data = json.loads(line)
            content = data.get("content", "")
            if not content:
                continue
            
            # Check for title tag or other cues
            if "Dashboard | JiPOS" in content or "Home | JiPOS" in content or "/sys/index" in content:
                print(f"Line {i}: step_index={data.get('step_index')}, source={data.get('source')}, content_len={len(content)}")
                # If there's html, print some stats
                html_start = content.find("<!DOCTYPE html>")
                if html_start != -1:
                    print(f"  -> Contains <!DOCTYPE html> at position {html_start}")
                    # Print first 200 chars and last 200 chars of HTML
                    html_snippet = content[html_start:html_start+300]
                    print(f"  -> Snippet: {html_snippet!r}")
        except Exception as e:
            pass
