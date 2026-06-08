with open("scratch/prompt_content.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines in extracted content: {len(lines)}")

# Let's find key sections: form, table, main-header, etc.
body_start = -1
body_end = -1
for i, line in enumerate(lines):
    if "<body" in line:
        body_start = i
    if "</body" in line:
        body_end = i

print(f"Body start line: {body_start}, Body end line: {body_end}")

# Print around body start
print("--- BODY START ---")
for line in lines[body_start:body_start+40]:
    print(line.strip())

# Find card-body or table or form tags and print around them
print("--- SEARCHING FOR FORMS AND TABLES ---")
for i, line in enumerate(lines):
    if "<form" in line or "<table" in line or "tb_title" in line or "small-box" in line:
        print(f"Line {i}: {line.strip()[:100]}")
