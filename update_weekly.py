import re

with open('Bot/bot.py', 'r', encoding='utf-8') as f:
    text = f.read()

reset_logic = '''
    if old_date and user.get("daily"):
        # Haftalık Reset (Pazartesi ise)
        today_obj = datetime.strptime(today, "%Y-%m-%d").date()
        if today_obj.weekday() == 0:  # Pazartesi
            user["weekly_damage"] = 0
            user["deload_warned"] = False
'''

text = text.replace('    if old_date and user.get("daily"):', reset_logic.strip())

with open('Bot/bot.py', 'w', encoding='utf-8') as f:
    f.write(text)