with open('Bot/bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.startswith('if old_date and user.get("daily"):'):
        lines[i] = '    ' + line

with open('Bot/bot.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)