import re

with open('Bot/bot.py', 'r', encoding='utf-8') as f:
    text = f.read()

# I will replace the log_set logic to include 1RM
old_code = '''
    # Detaylı istatistik takibi
    if "exercise_stats" not in user: user["exercise_stats"] = {}
    if mk_key not in user["exercise_stats"]: user["exercise_stats"][mk_key] = {"sets": 0, "reps": 0, "volume": 0}
    user["exercise_stats"][mk_key]["sets"] += 1
    user["exercise_stats"][mk_key]["reps"] += r
    user["exercise_stats"][mk_key]["volume"] += dmg
    
    # Derin Loglama
'''

new_code = '''
    # Detaylı istatistik takibi
    if "exercise_stats" not in user: user["exercise_stats"] = {}
    if mk_key not in user["exercise_stats"]: user["exercise_stats"][mk_key] = {"sets": 0, "reps": 0, "volume": 0}
    user["exercise_stats"][mk_key]["sets"] += 1
    user["exercise_stats"][mk_key]["reps"] += r
    user["exercise_stats"][mk_key]["volume"] += dmg
    
    # --- 1RM HESAPLAMA (Brzycki Formülü) ---
    if "pr_records" not in user: user["pr_records"] = {}
    pr_msg = ""
    if r <= 30 and w > 0:
        orm = int(w * (36 / (37 - r)))
        current_pr = user["pr_records"].get(mk_key, 0)
        if orm > current_pr:
            user["pr_records"][mk_key] = orm
            xp_reward = 100
            user["xp"] += xp_reward
            pr_msg = f"\\n\\n🏆 *YENİ REKOR (PR)!*\\n{orm}kg Tahmini 1RM gücüne ulaştın! (+{xp_reward} XP)"
    
    # Derin Loglama
'''

text = text.replace(old_code.strip(), new_code.strip())

# And we need to add pr_msg to the bot.edit_message_text
old_reply = '''
    if special_t: t+=special_t
    bot.edit_message_text(t, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
'''

new_reply = '''
    if special_t: t+=special_t
    t += pr_msg
    bot.edit_message_text(t, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
'''

text = text.replace(old_reply.strip(), new_reply.strip())

with open('Bot/bot.py', 'w', encoding='utf-8') as f:
    f.write(text)