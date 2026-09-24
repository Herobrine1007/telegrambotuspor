with open('Bot/bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'yapman önerilir."\\n\\n    if mk_key' in line:
        lines[i] = line.replace('yapman önerilir."\\n\\n    if mk_key', 'yapman önerilir."\n\n    if mk_key')

with open('Bot/bot.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)