import re

with open('Bot/bot.py', 'r', encoding='utf-8') as f:
    text = f.read()

deload_logic = '''
    if "weekly_damage" not in user: user["weekly_damage"] = 0
    user["weekly_damage"] += dmg
    if user["weekly_damage"] > 50000 and not user.get("deload_warned"):
        user["deload_warned"] = True
        special_t += "\\n\\n⚠️ *SİSTEM UYARISI:* Bu hafta toplam kaldırdığın ağırlık 50 Tonu aştı! Merkezi sinir sistemini korumak için önümüzdeki hafta 'Deload' (Dinlenme/Hafif Ağırlık) yapman önerilir."
'''

text = text.replace('    if mk_key == "bench_press" and w >= 100', deload_logic.strip() + '\\n\\n    if mk_key == "bench_press" and w >= 100')

with open('Bot/bot.py', 'w', encoding='utf-8') as f:
    f.write(text)