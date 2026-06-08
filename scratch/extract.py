import json

transcript_path = "/Users/Akubrecah/.gemini/antigravity-ide/brain/b02e7334-3c36-454a-8cd9-07e94da4959e/.system_generated/logs/transcript.jsonl"
output_path = "/Users/Akubrecah/Desktop/KastomPOS/scratch/prompt_content.txt"

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            if data.get("step_index") == 1050 or data.get("step_index") == 1106:
                content = data.get("content", "")
                with open(output_path, 'w', encoding='utf-8') as out:
                    out.write(content)
                print(f"Successfully extracted step {data.get('step_index')}!")
                break
        except Exception as e:
            print(f"Error parsing line: {e}")
