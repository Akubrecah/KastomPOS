import json

log_path = "/Users/Akubrecah/.gemini/antigravity-ide/brain/b02e7334-3c36-454a-8cd9-07e94da4959e/.system_generated/logs/transcript.jsonl"

print("Reading latest steps...")
with open(log_path, 'r', encoding='utf-8') as f:
    lines = list(f)

# Let's print the last 15 steps
start_idx = max(0, len(lines) - 20)
for idx in range(start_idx, len(lines)):
    try:
        data = json.loads(lines[idx])
        step = data.get("step_index")
        source = data.get("source")
        type_ = data.get("type")
        content = data.get("content", "")
        print(f"\n--- STEP {step} | Source: {source} | Type: {type_} ---")
        if content:
            print(content[:600] + ("..." if len(content) > 600 else ""))
        if "tool_calls" in data and data["tool_calls"]:
            print("Tool calls:", json.dumps(data["tool_calls"], indent=2)[:300])
    except Exception as e:
        print(f"Error reading step {idx}: {e}")
