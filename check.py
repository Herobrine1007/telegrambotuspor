import re
with open('Bot/bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'print(' in line:
        # Very simple: remove common emojis from print statements
        line = line.replace('\u2694\ufe0f', '')
        line = line.replace('\u2694', '')
        line = line.replace('\ufe0f', '')
        # Remove any non-ascii from print statements just to be safe
        line = re.sub(r'[^\x00-\x7F]+', '', line)
    new_lines.append(line)

with open('Bot/bot.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)