import json

log_path = "/Users/Akubrecah/.gemini/antigravity-ide/brain/b02e7334-3c36-454a-8cd9-07e94da4959e/.system_generated/logs/transcript.jsonl"

print("Scanning all transcript steps for HTML tags in 'Room Sale Report | JiPOS' context:")
with open(log_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if "Room Sale Report" in line or "Room Booking Summaries" in line:
            try:
                data = json.loads(line)
                content = data.get("content", "")
                if not content:
                    continue
                step_idx = data.get("step_index")
                source = data.get("source")
                # Count tags
                tables = content.count("<table")
                forms = content.count("<form")
                divs = content.count("<div")
                print(f"Step {step_idx} ({source}): len={len(content)} | tables={tables}, forms={forms}, divs={divs}")
            except Exception as e:
                pass
