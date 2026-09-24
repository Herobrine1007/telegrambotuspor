with open('Bot/bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.startswith('if "weekly_damage" not in user:'):
        lines[i] = '    ' + line

with open('Bot/bot.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)