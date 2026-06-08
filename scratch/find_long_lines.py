import json

transcript_path = "/Users/Akubrecah/.gemini/antigravity-ide/brain/b02e7334-3c36-454a-8cd9-07e94da4959e/.system_generated/logs/transcript.jsonl"

print("Finding long lines in transcript...")
with open(transcript_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if len(line) > 10000:
            print(f"Line {i} is {len(line)} characters long.")
            try:
                data = json.loads(line)
                print(f"  step_index: {data.get('step_index')}, type: {data.get('type')}, source: {data.get('source')}")
                content = data.get("content", "")
                print(f"  content length: {len(content)}")
                # Find other fields
                for k, v in data.items():
                    if isinstance(v, str) and len(v) > 5000:
                        print(f"    String key '{k}' has length {len(v)}")
                    elif isinstance(v, list):
                        print(f"    List key '{k}' has length {len(v)}")
            except Exception as e:
                print(f"  Failed to parse JSON: {e}")
