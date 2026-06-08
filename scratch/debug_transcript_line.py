import json

log_path = "/Users/Akubrecah/.gemini/antigravity-ide/brain/b02e7334-3c36-454a-8cd9-07e94da4959e/.system_generated/logs/transcript.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        try:
            data = json.loads(line)
            step_idx = data.get("step_index")
            if step_idx == 39:
                print("Keys in line:", list(data.keys()))
                print("Content length:", len(data.get("content", "")))
                print("Content starts with:")
                print(data.get("content", "")[:500])
                print("Content ends with:")
                print(data.get("content", "")[-500:])
                break
        except Exception as e:
            pass
