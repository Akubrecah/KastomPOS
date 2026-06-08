import json

log_path = "/Users/Akubrecah/.gemini/antigravity-ide/brain/b02e7334-3c36-454a-8cd9-07e94da4959e/.system_generated/logs/transcript.jsonl"
target_step = 3412

with open(log_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i == target_step:
            try:
                data = json.loads(line)
                content = data.get("content", "")
                with open("scratch/latest_user_request.txt", "w", encoding="utf-8") as out:
                    out.write(content)
                print(f"Successfully wrote {len(content)} characters to scratch/latest_user_request.txt")
            except Exception as e:
                print(f"Error parsing json: {e}")
            break
