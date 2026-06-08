import json

log_path = "/Users/Akubrecah/.gemini/antigravity-ide/brain/b02e7334-3c36-454a-8cd9-07e94da4959e/.system_generated/logs/transcript.jsonl"

steps_to_read = [1227, 1228, 1229, 1230, 1310, 1311, 1312, 1444, 1445]

with open(log_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        try:
            data = json.loads(line)
            step_idx = data.get("step_index")
            if step_idx in steps_to_read or (step_idx >= 1220 and step_idx <= 1240) or (step_idx >= 1300 and step_idx <= 1320):
                print(f"\n================ STEP {step_idx} ({data.get('source')} - {data.get('type')}) ================")
                content = data.get("content", "")
                print(content[:2000])
                if len(content) > 2000:
                    print("...[TRUNCATED IN PRINT]...")
        except Exception as e:
            pass
