import json

log_path = "/Users/Akubrecah/.gemini/antigravity-ide/brain/b02e7334-3c36-454a-8cd9-07e94da4959e/.system_generated/logs/transcript.jsonl"

print("Reading user requests...")
with open(log_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        try:
            data = json.loads(line)
            if data.get("source") == "USER_EXPLICIT" or data.get("type") == "USER_INPUT":
                content = data.get("content", "")
                snippet = content[:150].replace('\n', ' ')
                print(f"Step {i}: len={len(content)} | snippet: {snippet}")
        except Exception as e:
            pass
