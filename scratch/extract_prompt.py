import json

log_path = "/Users/Akubrecah/.gemini/antigravity-ide/brain/b02e7334-3c36-454a-8cd9-07e94da4959e/.system_generated/logs/transcript.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            # Find the user requests
            if data.get("source") == "USER_EXPLICIT" or data.get("type") == "USER_INPUT":
                content = data.get("content", "")
                if "still it does not match the page source provided this" in content:
                    print("FOUND LATEST PROMPT")
                    with open("/Users/Akubrecah/Desktop/KastomPOS/scratch/extracted_latest_prompt.txt", "w", encoding="utf-8") as out:
                        out.write(content)
                elif "bookings summary use this" in content:
                    print("FOUND BOOKINGS SUMMARY PROMPT")
                    with open("/Users/Akubrecah/Desktop/KastomPOS/scratch/extracted_bookings_summary_prompt.txt", "w", encoding="utf-8") as out:
                        out.write(content)
                elif "change the name of Room Booking Summaries to Room Sales" in content:
                    print("FOUND ROOM SALES PROMPT")
                    with open("/Users/Akubrecah/Desktop/KastomPOS/scratch/extracted_room_sales_prompt.txt", "w", encoding="utf-8") as out:
                        out.write(content)
        except Exception as e:
            print("Error parsing line:", e)
