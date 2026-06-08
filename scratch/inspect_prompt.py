import re

with open("scratch/prompt_content.txt", "r", encoding="utf-8") as f:
    content = f.read()

# Let's find all CSS class declarations in <style>
style_block = re.findall(r'<style>(.*?)</style>', content, re.DOTALL)
if style_block:
    print("--- STYLE BLOCK ---")
    print(style_block[0])

# Let's find some key components or text in the HTML body
print("\n--- BODY SCRAPING ---")
# Print the first 10 occurrences of class="..."
classes = re.findall(r'class="([^"]+)"', content)
print(f"Total CSS class references: {len(classes)}")
print("Unique classes found in user prompt:")
print(sorted(list(set(classes)))[:30])

# Let's search for table, form, input or any other key structures
print("\n--- KEY TAGS ---")
for tag in ['table', 'thead', 'form', 'select', 'tbody', 'card', 'box']:
    matches = re.findall(rf'<{tag}[^>]*>', content, re.IGNORECASE)
    print(f"Tag <{tag}>: found {len(matches)} times. Examples:")
    for m in matches[:3]:
        print(f"  {m}")
