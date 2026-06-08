import json

log_path = "/Users/Akubrecah/.gemini/antigravity-ide/brain/b02e7334-3c36-454a-8cd9-07e94da4959e/.system_generated/logs/transcript.jsonl"

with open(log_path, "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        try:
            data = json.loads(line)
            if data.get("source") == "USER_EXPLICIT" and "on the item purchase report" in data.get("content", ""):
                print(f"Line {i} matches!")
                content = data.get("content", "")
                print(f"Length of content: {len(content)}")
                # Save the full content to a file
                with open("/Users/Akubrecah/Desktop/KastomPOS/scratch/full_user_msg.txt", "w", encoding="utf-8") as out:
                    out.write(content)
                print("Saved full content to scratch/full_user_msg.txt")
        except Exception as e:
            pass
