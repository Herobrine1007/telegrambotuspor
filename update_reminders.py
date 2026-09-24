import re

with open('Bot/bot.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_func = '''
def reminder_thread():
    while True:
        time.sleep(3600)  # Her saat başı kontrol
        try:
            data = load_data()
            now = datetime.now()
            # Sadece akşam 18 - 21 arası hatırlat
            if 18 <= now.hour <= 21:
                for uid, u in data.items():
                    d = u.get("daily", {})
                    # Bugün hiç antrenman set girmemişse ve bugün hatırlatılmamışsa
                    if d.get("sets", 0) == 0 and not u.get("reminded_today", False) and not u.get("streak_freeze"):
                        msg = "🔸 *Savaşçı, bugün kılıcını (ağırlıkları) kaldırmadın!*\\n"
                        if u.get("measurements"):
                            msg += f"Vücut Ölçülerin ({u['measurements']}) gerilemesin! Evde yapabileceğin 10 dakikalık şınav/mekik veya squat setleriyle bile günü kurtarabilirsin.\\n"
                        else:
                            msg += "Evde yapabileceğin 10 dakikalık şınav/mekik veya squat setleriyle bile günü kurtarabilirsin.\\n"
                        msg += "\\nUnutma, hiç yapmamaktansa yarım yapmak daha iyidir. Asistan butonuna basıp sana özel bir antrenman önermemi isteyebilirsin!"
                        try:
                            bot.send_message(int(uid), msg, parse_mode="Markdown")
                            u["reminded_today"] = True
                            save_user(uid, u)
                        except:
                            pass
            
            # Gece 02:00 gibi reminder state sıfırla
            if now.hour == 2:
                for uid, u in data.items():
                    if u.get("reminded_today"):
                        u["reminded_today"] = False
                        save_user(uid, u)
                        
        except Exception as e:
            print(f"Reminder Error: {e}")
'''

new_func = '''
def reminder_thread():
    while True:
        time.sleep(3600)  # Her saat başı kontrol
        try:
            data = load_data()
            now = datetime.now()
            
            for uid, u in data.items():
                d = u.get("daily", {})
                t = u.get("targets", {})
                
                # Sadece akşam 18 - 21 arası hatırlat (Antrenman)
                if 18 <= now.hour <= 21:
                    if d.get("sets", 0) == 0 and not u.get("reminded_today", False) and not u.get("streak_freeze"):
                        msg = "🔸 *Savaşçı, bugün kılıcını (ağırlıkları) kaldırmadın!*\\n"
                        if u.get("measurements"):
                            msg += f"Vücut Ölçülerin ({u['measurements']}) gerilemesin! Evde yapabileceğin 10 dakikalık şınav/mekik setleriyle bile günü kurtarabilirsin.\\n"
                        else:
                            msg += "Evde yapabileceğin 10 dakikalık şınav/mekik setleriyle bile günü kurtarabilirsin.\\n"
                        msg += "\\nUnutma, hiç yapmamaktansa yarım yapmak daha iyidir!"
                        try:
                            bot.send_message(int(uid), msg, parse_mode="Markdown")
                            u["reminded_today"] = True
                            save_user(uid, u)
                        except: pass

                # 20:00 ve 22:00 Makro Açığı Uyarıları
                if now.hour in [20, 22] and not u.get(f"macro_reminded_{now.hour}", False):
                    protein_left = t.get("protein", 0) - d.get("protein", 0)
                    kcal_left = t.get("kcal", 0) - d.get("kcal", 0)
                    if protein_left > 20:
                        msg = f"🍗 *Dikkat Savaşçı!* Hedefinden {int(protein_left)}g protein geridesin.\\nKaslarını beslemek için bir porsiyon tavuk, lor peyniri veya yumurta yemelisin! Yoksa bugünkü XP kazanımın düşecek."
                        try:
                            bot.send_message(int(uid), msg, parse_mode="Markdown")
                            u[f"macro_reminded_{now.hour}"] = True
                            save_user(uid, u)
                        except: pass
                    elif kcal_left > 500:
                        msg = f"🔥 *Kalori Açığı Çok Yüksek!* Bugün daha {int(kcal_left)} kcal kalori alman lazım.\\nBu şekilde uyursan kas kaybedebilirsin!"
                        try:
                            bot.send_message(int(uid), msg, parse_mode="Markdown")
                            u[f"macro_reminded_{now.hour}"] = True
                            save_user(uid, u)
                        except: pass

            # Gece 02:00 gibi reminder state sıfırla
            if now.hour == 2:
                for uid, u in data.items():
                    u["reminded_today"] = False
                    u["macro_reminded_20"] = False
                    u["macro_reminded_22"] = False
                    save_user(uid, u)
                        
        except Exception as e:
            pass
'''

text = text.replace(old_func.strip(), new_func.strip())

with open('Bot/bot.py', 'w', encoding='utf-8') as f:
    f.write(text)