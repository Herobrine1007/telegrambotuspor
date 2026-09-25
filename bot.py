# -*- coding: utf-8 -*-
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import json
import os
import re
import math
from datetime import datetime, date, timedelta
from difflib import SequenceMatcher
import google.generativeai as genai

TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']

bot = telebot.TeleBot(TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../Data/database.json')
FOODS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../Data/foods.json')

def load_foods():
    try:
        with open(FOODS_FILE, 'r', encoding='utf-8') as f:
            d = json.load(f)
            return d.get('FOODS', {}), d.get('FCAT', {})
    except Exception as e:
        print(f"foods.json yklenirken hata: {e}")
        return {}, {}

def load_workouts():
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../Data/workouts.json'), 'r', encoding='utf-8') as f:
            d = json.load(f)
            return d.get('EXERCISES', {}), d.get('WORKOUT_PROGRAMS', {})
    except Exception as e:
        print(f"workouts.json yklenirken hata: {e}")
        return {}, {}

FOODS, FCAT = load_foods()
EXERCISES, WORKOUT_PROGRAMS = load_workouts()

def save_foods():
    try:
        lines = ["{", '    "FOODS": {']
        food_items = []
        for k, v in FOODS.items():
            # Tam kullanıcının istediği gibi: boşluksuz, tek satır!
            v_str = '{' + ','.join(f'"{ik}":{iv}' if isinstance(iv, (int, float)) else f'"{ik}":"{iv}"' for ik, iv in v.items()) + '}'
            food_items.append(f'        "{k}": {v_str}')
        lines.append(",\n".join(food_items))
        lines.append('    },')
        
        lines.append('    "FCAT": {')
        fcat_items = []
        for k, v in FCAT.items():
            v_str = json.dumps(v, ensure_ascii=False).replace(', ', ',').replace(': ', ':')
            fcat_items.append(f'        "{k}": {v_str}')
        lines.append(",\n".join(fcat_items))
        lines.append('    }')
        lines.append("}")
        
        with open(FOODS_FILE, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
    except Exception as e:
        print(f"foods.json kaydedilirken hata: {e}")

# ══════════════════════════════════════════════════════════════
#                        VERİTABANI
# ══════════════════════════════════════════════════════════════
import threading
db_lock = threading.Lock()

def load_data():
    with db_lock:
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

def save_data(data):
    with db_lock:
        temp_file = DB_FILE + ".tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_file, DB_FILE)
        except Exception as e:
            print(f"Veritabani kaydetme hatasi: {e}")

def get_user(user_id):
    data = load_data()
    uid = str(user_id)
    if uid not in data:
        return None
    user = data[uid]
    today = date.today().isoformat()
    if user.get("last_date") != today:
        _rotate_daily(user, today)
        save_user(user_id, user)
    return user

def save_user(user_id, user_data):
    data = load_data()
    data[str(user_id)] = user_data
    save_data(data)

def log_action(user, action_type, details):
    """Kullanıcının her nefesini (hareketini) saat/dakika/saniye olarak loglar."""
    if "action_logs" not in user:
        user["action_logs"] = []
    
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": action_type,
        "details": details
    }
    user["action_logs"].append(log_entry)
    
    # Kullanıcı isteği üzerine log limiti (10000) tamamen kaldırıldı. Sınırsız loglanacak.

def _rotate_daily(user, today):
    """Gün değiştiğinde dünkü logu history'ye kaydet, günlüğü sıfırla ve yeni görevler ver."""
    import random
    old_date = user.get("last_date")
    if old_date and user.get("daily"):
        # Haftalık Reset (Pazartesi ise)
        today_obj = datetime.strptime(today, "%Y-%m-%d").date()
        if today_obj.weekday() == 0:  # Pazartesi
            user["weekly_damage"] = 0
            user["deload_warned"] = False
        # Streak ve Ceza hesapla
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        if old_date == yesterday:
            d = user.get("daily", {})
            t = user.get("targets", {})
            
            # Beslenme Streak'i (Kcal'in en az %40'ı alındıysa)
            if t.get("kcal", 1) > 0:
                pct = d.get("kcal", 0) / t["kcal"] * 100
                user["streak"] = user.get("streak", 0) + (1 if pct >= 40 else 0)
            else:
                user["streak"] = 0
                
            # Antrenman Streak'i ve Cezası (XP Azalması)
            if d.get("sets", 0) > 0 or d.get("cardio_burn", 0) > 0:
                user["workout_streak"] = user.get("workout_streak", 0) + 1
            elif user.get("streak_freeze"):
                user["streak_freeze"] = False
                log_action(user, "freeze_used", "g? Dün antrenman yapmadın ama Seri Dondurucu sayesinde serin korundu!")
            else:
                # Antrenman yapmadıysa serisi bozulur ve XP kaybeder
                if user.get("workout_streak", 0) > 0:
                    user["workout_streak"] = 0
                    penalty = max(10, int(user["level"] * 5)) # Seviyeye göre ceza
                    user["xp"] = max(0, user["xp"] - penalty)
                    log_action(user, "penalty", f"Antrenman yapılmadığı için {penalty} XP kaybedildi.")
        else:
            user["streak"] = 0
            user["workout_streak"] = 0
            user["xp"] = max(0, user["xp"] - 20) # Çoklu gün boşluğu cezası

        # History'ye kaydet
        if "history" not in user:
            user["history"] = {}
        user["history"][old_date] = {
            "water": user["daily"].get("water", 0),
            "kcal": user["daily"].get("kcal", 0),
            "protein": user["daily"].get("protein", 0),
            "carbs": user["daily"].get("carbs", 0),
            "fats": user["daily"].get("fats", 0),
            "sets": user["daily"].get("sets", 0),
            "damage": user["daily"].get("damage", 0),
            "meals": user["daily"].get("meals", []),
            "workouts": user["daily"].get("workouts", []),
            "supplements": user["daily"].get("supplements", []),
            "quests_done": user["daily"].get("quests_done", 0)
        }
        # History'de tüm geçmişi sınırsız tutuyoruz (Kullanıcı İsteği)
        pass

    # Günlük bonus altın
    user["gold"] = user.get("gold", 0) + 50
    log_action(user, "daily_reward", "Günlük giriş ödülü olarak 50 Altın kazanıldı.")

    t = user.get("targets", {})
    # Yeni Günlük Görevler Oluştur
    quests = [
        {"id": "water_goal", "desc": f"{t.get('water', 3000)/1000}L Su İç", "done": False, "xp": 50},
        {"id": "protein_goal", "desc": f"{t.get('protein', 150)}g Protein Al", "done": False, "xp": 75},
        {"id": "workout_10", "desc": "10 set antrenman yap", "xp": 120, "done": False},
        {"id": "cardio_burn", "desc": "Kardiyoda 200 kcal yak", "xp": 100, "done": False},
        {"id": "boss_dmg", "desc": "Boss'a 5.000 hasar vur", "xp": 150, "done": False}
    ]
    random.shuffle(quests)
    selected_quests = quests[:3] # Her gün rastgele 3 görev

    user["daily"] = {
        "water": 0, "kcal": 0, "protein": 0, "carbs": 0, "fats": 0,
        "sets": 0, "damage": 0, "cardio_burn": 0, "meals": [], "workouts": [], "supplements": [],
        "quests": selected_quests, "quests_done": 0
    }
    user["last_date"] = today

def check_quests(user):
    """Görevleri kontrol et, tamamlananlara XP ver."""
    leveled = False
    quests = user.get("daily", {}).get("quests", [])
    d = user.get("daily", {})
    t = user.get("targets", {})
    
    for q in quests:
        if q["done"]: continue
        
        completed = False
        if q["id"] == "water_goal" and d["water"] >= t.get("water", 3000): completed = True
        elif q["id"] == "protein_goal" and d["protein"] >= t.get("protein", 150): completed = True
        elif q["id"] == "workout_10" and d["sets"] >= 10: completed = True
        elif q["id"] == "cardio_burn" and d.get("cardio_burn", 0) >= 200: completed = True
        elif q["id"] == "boss_dmg" and d["damage"] >= 5000: completed = True
        
        if completed:
            q["done"] = True
            d["quests_done"] += 1
            if add_xp(user, q["xp"]): leveled = True
            
    return leveled

BADGES_DB = [
    {"id": "first_blood", "name": "🔸 İlk Kan", "desc": "İlk antrenmanını tamamla"},
    {"id": "dmg_10k", "name": "🔸 Bronz Savaşçı", "desc": "Toplam 10.000 kg kaldır"},
    {"id": "dmg_50k", "name": "🔸 Gümüş ?övalye", "desc": "Toplam 50.000 kg kaldır"},
    {"id": "dmg_100k", "name": "🔸️ Altın Titan", "desc": "Toplam 100.000 kg kaldır"},
    {"id": "streak_7", "name": "🔸 Demir İrade", "desc": "7 gün üst üste idman yap"},
    {"id": "water_master", "name": "🔸 Su Bükücü", "desc": "Tek günde 4000ml su iç"},
    {"id": "lvl_10", "name": "🔸 Usta Savaşçı", "desc": "Seviye 10'a ulaş"}
]

def check_achievements(user):
    """Rozet/Başarımları kontrol eder ve yeni açılanları string olarak döner."""
    if "badges" not in user:
        user["badges"] = []
    
    unlocked = []
    has = user["badges"]
    dmg = user.get("total_damage", 0)
    
    if "first_blood" not in has and dmg > 0: unlocked.append("first_blood")
    if "dmg_10k" not in has and dmg >= 10000: unlocked.append("dmg_10k")
    if "dmg_50k" not in has and dmg >= 50000: unlocked.append("dmg_50k")
    if "dmg_100k" not in has and dmg >= 100000: unlocked.append("dmg_100k")
    if "streak_7" not in has and user.get("streak", 0) >= 7: unlocked.append("streak_7")
    if "water_master" not in has and user.get("daily", {}).get("water", 0) >= 4000: unlocked.append("water_master")
    if "lvl_10" not in has and user.get("level", 1) >= 10: unlocked.append("lvl_10")
    
    # Rozetleri ekle
    for b in unlocked:
        user["badges"].append(b)
        
    # İsimleri dön
    new_badge_names = [next((bd["name"] for bd in BADGES_DB if bd["id"] == b), b) for b in unlocked]
    return new_badge_names


# ══════════════════════════════════════════════════════════════
#                   BMR / TDEE / HEDEF HESAPLAMA
# ══════════════════════════════════════════════════════════════
def calc_bmr(weight, height, age, gender):
    if gender == "erkek":
        return 10 * weight + 6.25 * height - 5 * age + 5
    return 10 * weight + 6.25 * height - 5 * age - 161

def calc_tdee(bmr, activity="orta"):
    m = {"sedanter": 1.2, "hafif": 1.375, "orta": 1.55, "aktif": 1.725, "cok_aktif": 1.9}
    return int(bmr * m.get(activity, 1.55))

def calc_targets(tdee, goal):
    if goal == "kilo_ver":
        kcal = tdee - 500
        pr, cr, fr = 0.35, 0.35, 0.30
    elif goal == "kas_kazan":
        kcal = tdee + 300
        pr, cr, fr = 0.30, 0.45, 0.25
    elif goal == "recomp":
        kcal = tdee - 200 # Hafif açık
        pr, cr, fr = 0.40, 0.30, 0.30 # Yüksek protein
    elif goal == "powerbuild":
        kcal = tdee + 400
        pr, cr, fr = 0.30, 0.45, 0.25
    else:
        kcal = tdee
        pr, cr, fr = 0.30, 0.40, 0.30
    return {
        "kcal": kcal, "protein": int((kcal*pr)/4),
        "carbs": int((kcal*cr)/4), "fats": int((kcal*fr)/9), "water": 3000
    }


# ══════════════════════════════════════════════════════════════
#                     SEVİYE SİSTEMİ (SINIRSIZ)
# ══════════════════════════════════════════════════════════════
def xp_for_level(level):
    return int(500 * (level ** 1.2))

def add_xp(user, amount):
    if user.get("pet") == "eagle":
        amount = int(amount * 1.2) # Kartal Yoldaş = %20 ekstra XP
    user["xp"] += amount
    leveled = False
    while user["xp"] >= xp_for_level(user["level"]):
        user["xp"] -= xp_for_level(user["level"])
        user["level"] += 1
        user["max_hp"] += 5
        user["hp"] = user["max_hp"]
        user["gold"] += user["level"] * 10
        leveled = True
    return leveled

def make_bar(current, maximum, length=10):
    ratio = min(current / maximum, 1.0) if maximum > 0 else 0
    filled = round(ratio * length)
    return "█" * filled + "░" * (length - filled)


# ══════════════════════════════════════════════════════════════
#           BÜYÜK YİYECEK VERİTABANI  (100+ TÜRK YEMEĞ?İ)
#       Değerler 1 porsiyon (birim) başına — "per" alanında açıklama
# ══════════════════════════════════════════════════════════════



# ══════════════════════════════════════════════════════════════
#          DOĞ?AL DİL YEMEK PARSER (Anahtar Kelime Eşleşme)
# ══════════════════════════════════════════════════════════════
QUANTITY_PATTERNS = [
    # "200g tavuk", "200 gram tavuk"
    (r'(\d+(?:[.,]\d+)?)\s*(?:gr(?:am)?|g)\s+', 'gram'),
    # "1 porsiyon", "2 tabak", "yarım ekmek", "çeyrek lahmacun", "1.5 porsiyon"
    (r'(yarım|çeyrek|\d+(?:[.,]\d+)?(?:çuk|buçuk)?)\s*(?:porsiyon|tabak|kase|adet|dilim|bardak|fincan|şiş|top|kaşık|ölçek|dürüm|avuç|ekmek)?\s+', 'portion'),
]

def _parse_number_word(word):
    word = word.lower()
    if word == "yarım": return 0.5
    if word == "çeyrek": return 0.25
    if "buçuk" in word or "çuk" in word:
        # e.g. "1 buçuk" or "1.5"
        num = re.sub(r'[^0-9]', '', word)
        return float(num) + 0.5 if num else 1.5
    try:
        return float(word.replace(",", "."))
    except:
        return 1.0

def _similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_best_food_match(query, custom_foods=None):
    """Yiyecek veritabanında en iyi eşleşmeyi bul (normal + custom)."""
    query = query.lower().strip()
    best_match = None
    best_score = 0.0
    best_fd = None

    # Normal yiyecekler ve özel yiyecekleri birleştir
    all_foods = dict(FOODS)
    if custom_foods:
        all_foods.update(custom_foods)

    for name, fd in all_foods.items():
        # Tam eşleşme
        if name == query:
            return name, 1.0, fd
        # Kısmi eşleşme
        if query in name or name in query:
            score = 0.85 + len(name) / 100
            if score > best_score:
                best_score = score
                best_match = name
                best_fd = fd
        # Fuzzy
        score = _similarity(query, name)
        if score > best_score:
            best_score = score
            best_match = name
            best_fd = fd

    return (best_match, best_score, best_fd) if best_score >= 0.45 else (None, 0, None)

def parse_meal_text(text, custom_foods=None):
    """
    Doğal dil yemek girişini ayrıştır.
    Örnek: "200g tavuk göğsü, 1 tabak pilav, yarım ekmek, çeyrek lahmacun"
    Return: [(food_name, multiplier, food_data), ...]
    """
    results = []
    # Virgül veya "ve" ile ayır
    parts = re.split(r'[,\n]+|\bve\b', text)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        quantity = 1.0
        food_query = part
        is_gram = False
        gram_amount = 0

        # Miktar pattern'lerini dene
        for pattern, qtype in QUANTITY_PATTERNS:
            m = re.match(pattern, part, re.IGNORECASE)
            if m:
                val = _parse_number_word(m.group(1))
                # yiyecek isminden miktar kısmını çıkar
                food_query = part[m.end():].strip()
                if not food_query: 
                    food_query = part # eğer geriye bir şey kalmadıysa tamamını kullan
                
                if qtype == 'gram':
                    is_gram = True
                    gram_amount = val
                else:
                    quantity = val
                break

        # Yarım/Çeyrek gibi kelimeler pattern'e takılmazsa manuel kontrol
        if not is_gram and quantity == 1.0:
            if food_query.startswith("yarım "):
                quantity = 0.5
                food_query = food_query.replace("yarım ", "", 1).strip()
            elif food_query.startswith("çeyrek "):
                quantity = 0.25
                food_query = food_query.replace("çeyrek ", "", 1).strip()

        # Yiyecek bul
        match_name, score, fd = find_best_food_match(food_query, custom_foods)
        if match_name and score >= 0.45:
            if is_gram:
                # Gram bazlı hesapla
                per = fd.get("per", "")
                if "100g" in per or "100ml" in per:
                    quantity = gram_amount / 100.0
                else:
                    # Porsiyon bazlı yiyecek, gramajı tahmin et
                    quantity = gram_amount / 150.0  # ortalama 1 porsiyon ~150g
            results.append((match_name, quantity, fd))

    return results


# ══════════════════════════════════════════════════════════════
#                     EGZERSİZ VERİTABANI
# ══════════════════════════════════════════════════════════════

CARDIO_BURN = {"run_20":200,"run_30":300,"walk_30":120,"walk_60":240,"bike_30":250,"jump_rope":200,"hiit_20":280}


# ══════════════════════════════════════════════════════════════
#                  PROGRESSIVE OVERLOAD MOTORU
# ══════════════════════════════════════════════════════════════
def get_exercise_history(user, move_key, days=14):
    """Son N gündeki belirli bir hareket için set loglarını getir."""
    history = user.get("history", {})
    entries = []
    for d in sorted(history.keys(), reverse=True)[:days]:
        day_data = history[d]
        for w in day_data.get("workouts", []):
            if w.get("type") == "set" and w.get("move") == move_key:
                entries.append({"date": d, "weight": w["weight"], "reps": w["reps"]})
    # Bugünkü
    for w in user.get("daily", {}).get("workouts", []):
        if w.get("type") == "set" and w.get("move") == move_key:
            entries.append({"date": user.get("last_date",""), "weight": w["weight"], "reps": w["reps"]})
    return entries

def suggest_weight(user, move_key):
    """Progressive overload önerisi: Geçmiş performansa göre ağırlık öner."""
    hist = get_exercise_history(user, move_key, days=21)
    if not hist:
        return None, None  # İlk defa yapıyor

    # Son seanstaki en yüksek ağırlık ve tekrar
    last_weight = hist[0]["weight"]
    last_reps = hist[0]["reps"]

    # En yüksek ağırlık (tüm zamanlar son 21 gün)
    max_weight = max(e["weight"] for e in hist)

    note = ""
    suggested = last_weight
    if last_reps >= 10:
        suggested = last_weight + 2.5
        note = f"Geçen sefer {last_weight}kg ile {last_reps} tekrar çıkardın — rahat! Bugün {suggested}kg dene 🔸"
    elif last_reps >= 8:
        suggested = last_weight
        note = f"Geçen sefer {last_weight}kg ile {last_reps} tekrar. Aynı ağırlıkla devam et, tekrarları artır."
    elif last_reps < 6:
        suggested = max(last_weight - 5, 10)
        note = f"Geçen sefer {last_weight}kg ile sadece {last_reps} tekrar çıktı. Biraz düşür ({suggested}kg) ve tekrarı artır."
    else:
        suggested = last_weight
        note = f"Geçen sefer {last_weight}kg ile {last_reps} tekrar — iyi! Aynı ağırlıkla devam."

    return suggested, note


# ══════════════════════════════════════════════════════════════
#             ANTRENMAN PROGRAM ÖNERİ MOTORU
# ══════════════════════════════════════════════════════════════
DAYS_TR = {0:"Pazartesi",1:"Salı",2:"Çarşamba",3:"Perşembe",4:"Cuma",5:"Cumartesi",6:"Pazar"}
GOAL_NAMES = {"kilo_ver":"Kilo Verme","kas_kazan":"Kas Kazanma (Bulk)","koruma":"Koruma", "recomp":"Yağ Yak & Kas Yap", "powerbuild":"Kilo Al & Güçlen"}




# ══════════════════════════════════════════════════════════════
#        KARAKTER OLUŞ?TURMA SİHİRBAZI (İlk Kayıt)
# ══════════════════════════════════════════════════════════════
user_setup = {}  # uid -> state dict

@bot.message_handler(commands=['start'])
def cmd_start(message):
    uid = message.from_user.id
    user = get_user(uid)
    if not user:
        user_setup[uid] = {"step": "dob", "name": message.from_user.first_name}
        bot.send_message(message.chat.id,
            f"⚔️ *Hoş geldin Savaşçı {message.from_user.first_name}!*\n\n"
            f"Sana özel bir program hazırlamam için birkaç bilgiye ihtiyacım var.\n\n"
            f"🔸 *Doğum Tarihin nedir?* (Örn: 15.08.1995)\n"
            f"(Gün.Ay.Yıl olarak yazabilirsin)",
            parse_mode="Markdown")
    else:
        send_main_menu(message.chat.id, uid)

@bot.message_handler(commands=['yardim', 'help'])
def cmd_help(message):
    help_text = """
🔸️ *RPG Fitness Asistanı Komutları*
/start - Ana menüyü açar veya karakterini baştan yaratır.
/grafik - Gelişimini (Kalori ve Zindan Hasarı) görsel grafik olarak çizer.
/yardim - Bu yardım menüsünü açar.

🔸 *Yapay Zeka Fotoğraf Analizi*
Bana herhangi bir yemeğin, takviyenin (protein tozu vs.) veya spor aletinin fotoğrafını atarsan, onu senin için anında analiz ederim!
    """
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['grafik', 'chart'])
def cmd_grafik(message):
    class FakeCall:
        def __init__(self, m):
            self.id = None
            self.from_user = m.from_user
            self.message = m
    show_chart(FakeCall(message))

@bot.message_handler(commands=['kilo', 'weight'])
def cmd_kilo(message):
    uid = message.from_user.id
    user = get_user(uid)
    if not user: return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "⚖️ Kilonu güncellemek için komutla birlikte kilonu yaz:\nÖrn: `/kilo 82.5`", parse_mode="Markdown")
        return
        
    try:
        new_w = float(parts[1].replace(",","."))
        assert 30 <= new_w <= 300
        
        if "weight_history" not in user:
            user["weight_history"] = [{"date": user["last_date"], "weight": user.get("start_weight", user["weight"])}]
            
        old_w = user["weight"]
        diff = new_w - old_w
        
        user["weight"] = new_w
        user["weight_history"].append({"date": date.today().isoformat(), "weight": new_w})
        
        bmr = calc_bmr(new_w, user["height"], user["age"], user["gender"])
        tdee = calc_tdee(bmr, user["activity"])
        user["bmr"] = bmr
        user["tdee"] = tdee
        user["targets"] = calc_targets(tdee, user["goal"])
        
        save_user(uid, user)
        
        diff_str = f"+{diff:.1f}" if diff > 0 else f"{diff:.1f}"
        bot.send_message(message.chat.id, f"⚖️ Kilon güncellendi: *{old_w}kg ? {new_w}kg* ({diff_str}kg)\n\nMakroların (Kalori hedefin) yeni kilona göre yeniden hesaplandı!", parse_mode="Markdown")
    except:
        bot.send_message(message.chat.id, "❌ Lütfen geçerli bir kilo gir. Örn: /kilo 82.5")

@bot.message_handler(func=lambda m: m.from_user.id in user_setup and user_setup[m.from_user.id]["step"] in ("dob","height","weight","injury"))
def setup_text_steps(message):
    uid = message.from_user.id
    state = user_setup[uid]
    txt = message.text.strip()

    if state["step"] == "dob":
        import re
        match = re.search(r'(\d{1,2})[./-](\d{1,2})[./-](\d{4})', txt)
        if match:
            day, month, year = map(int, match.groups())
            try:
                birth_date = date(year, month, day)
                today = date.today()
                age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                assert 10 <= age <= 100
                state["dob"] = birth_date.isoformat()
                state["age"] = age
                state["step"] = "height"
                bot.send_message(message.chat.id, f"g? Harika, {age} yaşındasın!\n\n🔸 *Boyun kaç cm?* (Örn: 175)", parse_mode="Markdown")
            except:
                bot.send_message(message.chat.id, "❌ Tarihte bir sorun var (çok genç/yaşlı olabilirsin).")
        else:
            # Fallback if they just type their age directly (e.g. 25)
            try:
                age = int(txt)
                assert 10 <= age <= 100
                state["dob"] = (date.today() - timedelta(days=age*365)).isoformat()
                state["age"] = age
                state["step"] = "height"
                bot.send_message(message.chat.id, f"g? Tamam, direkt {age} yaş olarak kaydettim.\n\n🔸 *Boyun kaç cm?* (Örn: 175)", parse_mode="Markdown")
            except:
                bot.send_message(message.chat.id, "❌ Lütfen geçerli bir tarih gir (Örn: 15.08.1995) veya sadece yaşını yaz.")

    elif state["step"] == "height":
        try:
            h = int(txt)
            assert 100 <= h <= 250
            state["height"] = h; state["step"] = "weight"
            bot.send_message(message.chat.id, "⚖️ *Kilonu gir (kg):* (Örn: 80)", parse_mode="Markdown")
        except:
            bot.send_message(message.chat.id, "❌ Geçerli bir boy gir (100-250 cm).")

    elif state["step"] == "weight":
        try:
            w = float(txt.replace(",","."))
            assert 30 <= w <= 300
            state["weight"] = w; state["step"] = "gender"
            mk = InlineKeyboardMarkup(row_width=2)
            mk.add(InlineKeyboardButton("♂️ Erkek", callback_data="s_g_erkek"),
                    InlineKeyboardButton("♀️ Kadın", callback_data="s_g_kadin"))
            bot.send_message(message.chat.id, "🔸 *Cinsiyetini seç:*", parse_mode="Markdown", reply_markup=mk)
        except:
            bot.send_message(message.chat.id, "❌ Geçerli bir kilo gir (30-300 kg).")

    elif state["step"] == "injury":
        state["injuries"] = txt
        state["step"] = "notes"
        bot.send_message(message.chat.id,
            "🔸 *Eklemek istediğin özel notlar var mı?*\n"
            "(Örn: Sabahları antrenman yapıyorum, glüten alerjim var)\n\n"
            "Yoksa 'yok' yaz.",
            parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.from_user.id in user_setup and user_setup[m.from_user.id]["step"] == "notes")
def setup_notes(message):
    uid = message.from_user.id
    state = user_setup[uid]
    notes = message.text.strip()
    if notes.lower() in ("yok","hayır","hayir","-",""):
        notes = ""
    state["notes"] = notes
    state["step"] = "measurements"
    
    bot.send_message(message.chat.id, 
        "🔸 *Vücut Ölçülerini Gir (Opsiyonel)*\n"
        "Sana daha özel antrenman (kol/bacak çapı vb.) verebilmem için vücut ölçülerini yazabilirsin.\n"
        "(Örn: Kol 35cm, Bacak 60cm, Bel 80cm)\n\n"
        "Girmek istemiyorsan 'geç' veya 'yok' yazabilirsin.",
        parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.from_user.id in user_setup and user_setup[m.from_user.id]["step"] == "measurements")
def setup_measurements(message):
    uid = message.from_user.id
    state = user_setup[uid]
    meas = message.text.strip()
    if meas.lower() in ("geç", "yok", "hayır", "istemiyorum", "-", ""):
        meas = ""
    state["measurements"] = meas
    state["step"] = "goal"

    mk = InlineKeyboardMarkup(row_width=1)
    mk.add(
        InlineKeyboardButton("🔸 Kilo Vermek", callback_data="s_goal_kilo_ver"),
        InlineKeyboardButton("🔸 Kas Kazanmak (Bulk)", callback_data="s_goal_kas_kazan"),
        InlineKeyboardButton("🔸🔸 Yağ Yak & Kas Yap (Recomp)", callback_data="s_goal_recomp"),
        InlineKeyboardButton("🔸️ Kilo Al & Güçlen", callback_data="s_goal_powerbuild"),
        InlineKeyboardButton("⚖️ Kilo Korumak", callback_data="s_goal_koruma"),
    )
    bot.send_message(message.chat.id, "g? *Hedefin ne?*", parse_mode="Markdown", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("s_g_"))
def setup_gender(call):
    uid = call.from_user.id
    if uid not in user_setup: return
    user_setup[uid]["gender"] = call.data.replace("s_g_","")
    user_setup[uid]["step"] = "activity"
    mk = InlineKeyboardMarkup(row_width=1)
    mk.add(
        InlineKeyboardButton("🔸️ Sedanter (Masa başı)", callback_data="s_act_sedanter"),
        InlineKeyboardButton("🔸 Hafif Aktif (1-2 gün/hafta)", callback_data="s_act_hafif"),
        InlineKeyboardButton("🔸 Orta Aktif (3-5 gün/hafta)", callback_data="s_act_orta"),
        InlineKeyboardButton("🔸️ Çok Aktif (6-7 gün/hafta)", callback_data="s_act_aktif"),
    )
    bot.edit_message_text("🔸 *Aktivite seviyen nedir?*", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("s_act_"))
def setup_activity(call):
    uid = call.from_user.id
    if uid not in user_setup: return
    user_setup[uid]["activity"] = call.data.replace("s_act_","")
    user_setup[uid]["step"] = "injury"
    bot.edit_message_text(
        "🔸 *Sakatlık veya hassasiyetin var mı?*\n"
        "(Örn: Sağ omuzda hassasiyet, bel fıtığı, diz ağrısı)\n\n"
        "Yoksa 'yok' yaz.",
        call.message.chat.id, call.message.message_id, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("s_goal_"))
def setup_goal(call):
    uid = call.from_user.id
    if uid not in user_setup: return
    state = user_setup[uid]
    goal = call.data.replace("s_goal_","")

    bmr = calc_bmr(state["weight"], state["height"], state["age"], state["gender"])
    tdee = calc_tdee(bmr, state["activity"])
    targets = calc_targets(tdee, goal)
    today = date.today().isoformat()

    user = {
        "name": state["name"], "age": state["age"], "dob": state.get("dob", ""), "height": state["height"],
        "weight": state["weight"], "start_weight": state["weight"],
        "gender": state["gender"], "activity": state["activity"], "goal": goal,
        "bmr": int(bmr), "tdee": tdee,
        "injuries": state.get("injuries",""),
        "measurements": state.get("measurements", ""),
        "ai_notes": state.get("notes",""),
        "food_allergies": "",
        "level": 1, "xp": 0, "hp": 100, "max_hp": 100,
        "str": 10, "sta": 10, "gold": 0, "streak": 0,
        "last_date": today,
        "daily": {"water":0,"kcal":0,"protein":0,"carbs":0,"fats":0,
                  "sets":0,"damage":0,"meals":[],"workouts":[]},
        "targets": targets,
        "boss_hp": 50000, "boss_max_hp": 50000,
        "boss_level": 1, "boss_name": "Goblin",
        "total_damage_all": 0, "total_sets_all": 0,
        "exercise_stats": {},
        "action_logs": [],
        "history": {},
    }
    save_user(uid, user)
    del user_setup[uid]

    bot.edit_message_text(
        f"✅ *Karakter Oluşturuldu!*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔸 {state['name']} | {state['age']} yaş {('(' + state.get('dob') + ')') if state.get('dob') else ''} | {state['height']}cm | {state['weight']}kg\n"
        f"g? Hedef: *{GOAL_NAMES.get(goal,goal)}*\n"
        f"🔸 Sakatlık: {state.get('injuries','Yok')}\n"
        f"🔸 Ölçüler: {state.get('measurements','') or 'Belirtilmedi'}\n"
        f"🔸 Not: {state.get('notes','') or 'Yok'}\n\n"
        f"🔸 *Sana Özel Hesaplamalar:*\n"
        f"🔸 BMR: {int(bmr)} kcal | ⚡ TDEE: {tdee} kcal\n\n"
        f"g? *Günlük Hedeflerin:*\n"
        f"🔸 {targets['kcal']} kcal | 🔸 {targets['protein']}g pro | 🔸 {targets['carbs']}g carb | 🔸 {targets['fats']}g yağ | 🔸 {targets['water']}ml su\n\n"
        f"/start yazarak ana menüye dön!",
        call.message.chat.id, call.message.message_id, parse_mode="Markdown")


# ══════════════════════════════════════════════════════════════
#                         ANA MENÜ
# ══════════════════════════════════════════════════════════════
def _get_menu_text(user):
    xn = xp_for_level(user["level"])
    d = user["daily"]; t = user["targets"]
    kl = t["kcal"] - d["kcal"]
    pl = t["protein"] - d["protein"]

    text = (
        f"⚔️ *RPG FITNESS ASISTAN* ⚔️\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔸 *{user['name']}* — Lvl {user['level']}\n"
        f"XP: {make_bar(user['xp'],xn,10)} {user['xp']}/{xn}\n"
        f"❤️ {user['hp']}/{user['max_hp']} | 🔸 STR:{user['str']} | 🔸 STA:{user['sta']} | 🔸 {user['gold']}\n"
        f"🔸 Seri: {user['streak']} gün\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"g? *Günlük Görevler ({d.get('quests_done', 0)}/3)*\n"
    )
    
    quests = d.get("quests", [])
    if not quests:
        text += "_Görev bulunamadı._\n"
    for q in quests:
        icon = "✅" if q["done"] else "⬜"
        text += f"{icon} {q['desc']} (+{q['xp']} XP)\n"
        
    text += f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += (
        f"🔸 *Günlük İlerleme*\n"
        f"🔸 Su:   {make_bar(d['water'],t['water'],10)} {d['water']}/{t['water']}ml\n"
        f"🔸 Kcal: {make_bar(d['kcal'],t['kcal'],10)} {int(d['kcal'])}/{t['kcal']}\n"
        f"🔸 Pro: {int(d['protein'])}/{t['protein']}g | 🔸 {int(d['carbs'])}/{t['carbs']}g | 🔸 {int(d['fats'])}/{t['fats']}g\n"
    )
    if kl > 0:
        text += f"🔸 _{int(kl)} kcal, {int(max(pl,0))}g pro kaldı_\n"
    else:
        text += f"⚠️ _{int(abs(kl))} kcal fazla!_\n"
    text += f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n🔸 Boss: *{user.get('boss_name', 'Goblin')}* (Lvl {user.get('boss_level', 1)})\n{make_bar(user['boss_hp'],user['boss_max_hp'],10)} {user['boss_hp']}/{user['boss_max_hp']}\n"
    return text

def send_main_menu(chat_id, user_id):
    user = get_user(user_id)
    text = _get_menu_text(user)

    mk = InlineKeyboardMarkup(row_width=2)
    mk.row(
        InlineKeyboardButton("🔸 Su İç", callback_data="m_water"),
        InlineKeyboardButton("🔸 Yemek Ekle", callback_data="m_food")
    )
    mk.row(
        InlineKeyboardButton("⚔️ Zindan (Antrenman)", callback_data="m_gym"),
        InlineKeyboardButton("🔸 Bugün Program", callback_data="m_prog")
    )
    mk.row(
        InlineKeyboardButton("🔸 Ne Yedim?", callback_data="m_meallog"),
        InlineKeyboardButton("🔸 Asistan", callback_data="m_advice")
    )
    mk.row(
        InlineKeyboardButton("🔸 Dükkan (Market)", callback_data="m_shop"),
        InlineKeyboardButton("⚔️ Arena (Düello)", callback_data="m_arena")
    )
    mk.row(
        InlineKeyboardButton("🔸 Günlük Menü", callback_data="m_menu_oneri"),
        InlineKeyboardButton("🔸 Grafik & Analiz", callback_data="m_chart")
    )
    mk.row(
        InlineKeyboardButton("🔸 Vitamin & Takviye", callback_data="m_vitamins")
    )
    mk.row(
        InlineKeyboardButton("🔸 İstatistik", callback_data="m_stats"),
        InlineKeyboardButton("🔸 Sıralama", callback_data="m_lb")
    )
    mk.row(
        InlineKeyboardButton("🔸 Notlar", callback_data="m_notes"),
        InlineKeyboardButton("⚙️ Profili Düzenle", callback_data="m_profile")
    )
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=mk)


# ══════════════════════════════════════════════════════════════
#   DOĞ?AL DİL YEMEK GİRİ?İ (Sohbetten direkt mesaj olarak)
# ══════════════════════════════════════════════════════════════
@bot.message_handler(func=lambda m: m.from_user.id not in user_setup and m.from_user.id not in custom_food_state and m.from_user.id not in custom_gram_state and m.from_user.id not in note_state and get_user(m.from_user.id) is not None and not m.text.startswith("/"))
def natural_language_handler(message):
    """Kullanıcı direkt mesaj yazdığında yemek/su/not olarak ayrıştır."""
    uid = message.from_user.id
    txt = message.text.strip().lower()

    # Su girişi kontrol
    water_match = re.search(r'(\d+)\s*(?:ml|litre|lt|l)\s*(?:su|water)?', txt)
    if water_match or "su içtim" in txt or "su iç" in txt:
        amount = 250  # varsayılan
        if water_match:
            val = int(water_match.group(1))
            unit = water_match.group(0)
            if "litre" in unit or "lt" in unit or (unit.endswith("l") and val < 20):
                amount = val * 1000
            else:
                amount = val
        user = get_user(uid)
        user["daily"]["water"] += amount
        log_action(user, "water", f"{amount}ml su içti")
        leveled = add_xp(user, 15)
        leveled_quest = check_quests(user)
        leveled = leveled or leveled_quest
        save_user(uid, user)
        w = user["daily"]["water"]; t = user["targets"]["water"]
        lvl = f"\ng? Seviye Atladın! Lvl {user['level']}" if leveled else ""
        bot.reply_to(message,
            f"🔸 *+{amount}ml su kaydedildi!* (+15 XP)\n"
            f"{make_bar(w,t,15)} {w}/{t}ml{lvl}",
            parse_mode="Markdown")
        return

    # Yemek girişi - GEMINI AI İLE
    wait_msg = bot.reply_to(message, "🔸 _Yapay zeka (Gemini) yemeğini analiz ediyor, lütfen bekle..._", parse_mode="Markdown")
    user = get_user(uid)
    custom_foods = user.get("custom_foods", {})
    
    # Gemini Prompt'u
    custom_food_list = ", ".join([f"{k} ({v['kcal']}kcal, {v['per']} başına)" for k,v in custom_foods.items()])
    prompt = f"""
    Sen profesyonel bir diyetisyen yapay zekasın. 
    Kullanıcının yazdığı metni analiz et ve yenilen yemeklerin adını, miktarını ve toplam makrolarını çıkar.
    Kullanıcı Metni: "{message.text}"
    
    Kullanıcının kayıtlı özel yemekleri: {custom_food_list if custom_food_list else "Yok"}
    
    KURALLAR:
    1. Yemeği porsiyon veya gramajına göre kalori/protein/karb/yağ olarak hesapla.
    2. Sonucu sadece geçerli bir JSON objesi olarak dön. Başka hiçbir açıklama yazma. Markdown (```json) KULLANMA. Sadece süslü parantezlerle başlayan JSON.
    3. JSON Formatı şu olmalı:
    3. JSON Formati su olmali:
    {{
        "foods": [
            {{"name": "Yemek Adi", "multiplier": 1.5, "kcal": 300, "pro": 15, "carb": 30, "fat": 10}}
        ],
        "measurements": {{
            "chest": 105.5,
            "waist": 82,
            "arm": 38,
            "shoulder": 120,
            "fat_percentage": 14.5,
            "weight": 80.5
        }}
    }}
    Eger metinde yemek yoksa foods bos birak. Eger vücut l🔹s (bel, kol, omuz, ggs, yag orani, kilo vb) belirtilmisse 'measurements' objesini sadece verilen degerlerle doldur (verilmeyenleri ekleme).
    """
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        result_text = response.text.strip()
        
        # Markdown bloklarını temizle (```json ... ```)
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
            
        ai_data = json.loads(result_text.strip())
        parsed = ai_data.get("foods", [])
        measurements = ai_data.get("measurements", {})
    except Exception as e:
        bot.edit_message_text(f"? AI Analiz Hatasi: API anahtarin yanlis olabilir veya sistem yanit vermedi. Hata: {str(e)}", wait_msg.chat.id, wait_msg.message_id)
        return

    # l🔹mleri Kaydet
    if measurements:
        if "measurements_history" not in user:
            user["measurements_history"] = []
            
        today_iso = date.today().isoformat()
        measurements["date"] = today_iso
        user["measurements_history"].append(measurements)
        
        # Eger kilo (weight) güncellenmişse karakterin kilosu da güncellensin
        if "weight" in measurements:
            user["weight"] = measurements["weight"]
            if "weight_history" not in user: user["weight_history"] = []
            user["weight_history"].append({"date": today_iso, "weight": user["weight"]})
            
        save_user(uid, user)
        meas_str = ", ".join([f"{k}: {v}" for k,v in measurements.items() if k != "date"])
        bot.edit_message_text(f"?? *Vücut l🔹lerin Kaydedildi!*\n\n{meas_str}", wait_msg.chat.id, wait_msg.message_id, parse_mode="Markdown")
        if not parsed:
            return

    if parsed:
        total_k = total_p = total_c = total_f = 0
        food_lines = []

        for item in parsed:
            name = item.get("name", "Bilinmeyen")
            mult = item.get("multiplier", 1)
            k = item.get("kcal", 0)
            p = item.get("pro", 0)
            c = item.get("carb", 0)
            f = item.get("fat", 0)
            
            # Yiyecek DB'de yoksa otomatik kalıcı olarak kaydet
            safe_name = name.lower().strip()
            if safe_name and safe_name not in FOODS and k > 0:
                FOODS[safe_name] = {
                    "kcal": round(k / mult) if mult > 0 else k,
                    "pro": round(p / mult, 1) if mult > 0 else p,
                    "carb": round(c / mult, 1) if mult > 0 else c,
                    "fat": round(f / mult, 1) if mult > 0 else f,
                    "per": "1 porsiyon (200g - Auto)"
                }
                save_foods()
            
            total_k += k; total_p += p; total_c += c; total_f += f
            user["daily"]["kcal"] += k; user["daily"]["protein"] += p
            user["daily"]["carbs"] += c; user["daily"]["fats"] += f
            user["daily"]["meals"].append({"food":name,"mult":round(mult,2),"kcal":round(k),"pro":round(p)})
            food_lines.append(f"  • {name.title()} x{round(mult,1)} → {int(k)} kcal, {int(p)}g pro")
            log_action(user, "food_nlp", f"{name.title()} yedi ({int(k)} kcal) - Gemini AI")
        # XP hesaplama (Sağlıklıysa daha çok, hedeften şaşıyorsa daha az)
        xp_gain = 30 * len(parsed)
        if user["daily"]["kcal"] <= user["targets"]["kcal"]:
            xp_gain += 15 # Hedef içi bonusu

        leveled = add_xp(user, xp_gain)
        if user["daily"]["protein"] >= user["targets"]["protein"]:
            user["str"] += 1
        
        leveled_quest = check_quests(user)
        leveled = leveled or leveled_quest
        save_user(uid, user)

        d = user["daily"]; t = user["targets"]
        kl = t["kcal"] - d["kcal"]; pl = t["protein"] - d["protein"]

        response = f"🔸 *Gemini AI Analizi Başarılı!* (+{xp_gain} XP)\n\n"
        response += "\n".join(food_lines)
        response += f"\n\n🔸 Toplam: 🔸{int(total_k)} kcal | 🔸{int(total_p)}g | 🔸{int(total_c)}g | 🔸{int(total_f)}g\n"
        response += f"\n{make_bar(d['kcal'],t['kcal'],15)} {int(d['kcal'])}/{t['kcal']} kcal\n"

        if kl > 0 and pl > 0:
            response += f"\n🔸 _Hedefe ulaşmak için {int(kl)} kcal ve {int(pl)}g protein daha lazım._\n"
        elif kl <= 0:
            response += f"\n⚠️ _Kalori hedefini {int(abs(kl))} kcal aştın._"

        lvl = f"\n\ng? *Seviye Atladın! Lvl {user['level']}*" if leveled else ""
        bot.edit_message_text(response + lvl, wait_msg.chat.id, wait_msg.message_id, parse_mode="Markdown")
    else:
        bot.edit_message_text("🔸 Gemini yapay zekası yazdıklarında bir yemek bulamadı.\n(Örn: '1 porsiyon iskender yedim' gibi yazabilirsin)", wait_msg.chat.id, wait_msg.message_id)

# ══════════════════════════════════════════════════════════════
#   FOTOĞ?RAF İLE YEMEK/ANTRENMAN ANALİZİ (GEMINI VISION)
# ══════════════════════════════════════════════════════════════
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = message.from_user.id
    if uid in user_setup or get_user(uid) is None:
        return
        
    wait_msg = bot.reply_to(message, "🔸 _Fotoğraf inceleniyor (Gemini Vision)..._", parse_mode="Markdown")
    
    try:
        # Fotoğrafı Telegram'dan indir
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Geçici olarak diske kaydet
        temp_path = f"temp_{uid}.jpg"
        with open(temp_path, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        # Gemini'ye gönder
        model = genai.GenerativeModel('gemini-1.5-flash')
        myfile = genai.upload_file(temp_path)
        
        prompt = """
        Bu fotoğrafta ne görüyorsun? Bu bir yemek mi, bir spor/antrenman aleti mi, yoksa bir spor takviyesi/vitamini mi (Örn: Kreatin, Protein Tozu, Balık Yağı, Vitamin)?
        Eğer bir yemekse, içindeki besinleri analiz et ve tahmini kalori, protein, karbonhidrat ve yağ oranlarını hesapla.
        Eğer bir spor aletiyse veya spor salonuysa, bu aletle yapılabilecek en iyi hareketi ve hangi kasları çalıştırdığını söyle.
        Eğer bir spor takviyesi veya vitamin ise, markasını/türünü tanı ve ne işe yaradığını kısaca söyle.
        
        Sadece geçerli bir JSON objesi dön. Başka metin yazma.
        Format (Yemek için):
        {"type": "food", "description": "Tabakta ... var", "foods": [{"name": "Yemek Adı", "multiplier": 1, "kcal": 400, "pro": 20, "carb": 40, "fat": 15}]}
        
        Format (Spor için):
        {"type": "gym", "description": "Bu bir ... aleti", "muscle": "Göğüs/Sırt vs", "suggestion": "Bununla 3 set 10 tekrar ... yapabilirsin"}
        
        Format (Takviye/Vitamin için):
        {"type": "supplement", "name": "Kreatin Monohidrat / Balık Yağı vb.", "benefit": "Kaslarda su tutarak gücü artırır."}
        """
        
        response = model.generate_content([prompt, myfile])
        genai.delete_file(myfile.name) # Dosyayı buluttan sil
        os.remove(temp_path) # Yerelden sil
        
        result_text = response.text.strip()
        if result_text.startswith("```json"): result_text = result_text[7:]
        if result_text.startswith("```"): result_text = result_text[3:]
        if result_text.endswith("```"): result_text = result_text[:-3]
            
        ai_data = json.loads(result_text.strip())
        
    except Exception as e:
        bot.edit_message_text(f"❌ Fotoğraf analiz edilemedi: {str(e)}", wait_msg.chat.id, wait_msg.message_id)
        if os.path.exists(f"temp_{uid}.jpg"): os.remove(f"temp_{uid}.jpg")
        return

    user = get_user(uid)
    
    if ai_data.get("type") == "food":
        parsed = ai_data.get("foods", [])
        if not parsed:
            bot.edit_message_text("🔸 Fotoğrafta net bir yemek bulamadım.", wait_msg.chat.id, wait_msg.message_id)
            return
            
        total_k = total_p = total_c = total_f = 0
        food_lines = []

        for item in parsed:
            name = item.get("name", "Bilinmeyen")
            mult = item.get("multiplier", 1)
            k = item.get("kcal", 0)
            p = item.get("pro", 0)
            c = item.get("carb", 0)
            f = item.get("fat", 0)
            
            total_k += k; total_p += p; total_c += c; total_f += f
            user["daily"]["kcal"] += k; user["daily"]["protein"] += p
            user["daily"]["carbs"] += c; user["daily"]["fats"] += f
            user["daily"]["meals"].append({"food":name,"mult":round(mult,2),"kcal":round(k),"pro":round(p)})
            food_lines.append(f"  • {name.title()} → {int(k)} kcal, {int(p)}g pro")
            log_action(user, "food_photo", f"{name.title()} yedi ({int(k)} kcal) - Gemini Vision")

        # XP hesaplama (Sağlıklıysa daha çok, hedeften şaşıyorsa daha az)
        xp_gain = 50 # Fotoğraflı giriş bonusu
        if user["daily"]["kcal"] <= user["targets"]["kcal"]:
            xp_gain += 30 # Hedef içi bonusu
        
        leveled = add_xp(user, xp_gain)
        if user["daily"]["protein"] >= user["targets"]["protein"]:
            user["str"] += 1
        save_user(uid, user)

        d = user["daily"]; t = user["targets"]
        response = f"🔸 *Görsel Analizi (Gemini Vision)*\n🔸 _{ai_data.get('description', '')}_\n\n"
        response += f"✅ *Öğün Kaydedildi!* (+{xp_gain} XP)\n"
        response += "\n".join(food_lines)
        response += f"\n\n🔸 Toplam: 🔸{int(total_k)} kcal | 🔸{int(total_p)}g | 🔸{int(total_c)}g | 🔸{int(total_f)}g\n"
        
        lvl = f"\ng? *Seviye Atladın! Lvl {user['level']}*" if leveled else ""
        bot.edit_message_text(response + lvl, wait_msg.chat.id, wait_msg.message_id, parse_mode="Markdown")
        
    elif ai_data.get("type") == "gym":
        xp_gain = 20
        leveled = add_xp(user, xp_gain)
        save_user(uid, user)
        
        response = f"🔸 *Görsel Analizi (Gemini Vision)* (+{xp_gain} XP)\n"
        response += f"🔸️ *Alet:* _{ai_data.get('description', '')}_\n"
        response += f"🔸 *Çalışan Kas:* {ai_data.get('muscle', '')}\n\n"
        response += f"🔸 *Yapay Zeka Önerisi:*\n{ai_data.get('suggestion', '')}\n\n"
        response += "Hareketi Zindan menüsünden kaydedebilirsin!"
        
        bot.edit_message_text(response, wait_msg.chat.id, wait_msg.message_id, parse_mode="Markdown")
    elif ai_data.get("type") == "supplement":
        xp_gain = 20
        sup_name = ai_data.get('name', 'Bilinmeyen Takviye')
        sup_benefit = ai_data.get('benefit', '')
        
        user["daily"]["supplements"].append({"name": sup_name})
        log_action(user, "supplement", f"Takviye kullandı: {sup_name}")
        
        leveled = add_xp(user, xp_gain)
        save_user(uid, user)
        
        response = f"🔸 *Görsel Analizi (Gemini Vision)* (+{xp_gain} XP)\n"
        response += f"🔸 *Takviye / Vitamin:* _{sup_name}_\n"
        response += f"🔸 *Faydası:* {sup_benefit}\n\n"
        response += "Günlüğüne başarıyla kaydedildi!"
        
        bot.edit_message_text(response, wait_msg.chat.id, wait_msg.message_id, parse_mode="Markdown")
    else:
        bot.edit_message_text("🔸 Fotoğrafta yemek, spor aleti veya vitamin/takviye tanımlayamadım.", wait_msg.chat.id, wait_msg.message_id)


# ══════════════════════════════════════════════════════════════
#                       SU İÇME
# ══════════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "m_water")
def menu_water(call):
    user = get_user(call.from_user.id)
    w = user["daily"]["water"]; t = user["targets"]["water"]
    mk = InlineKeyboardMarkup(row_width=3)
    mk.add(InlineKeyboardButton("🔸250ml",callback_data="w_250"),
           InlineKeyboardButton("🔸500ml",callback_data="w_500"),
           InlineKeyboardButton("🔸1L",callback_data="w_1000"))
    mk.add(InlineKeyboardButton("🔸 Menü",callback_data="back"))
    bot.edit_message_text(f"🔸 *Su Takibi*\n{make_bar(w,t,15)} {w}/{t}ml\n\nBir iksir seç:",
        call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("w_"))
def add_water_btn(call):
    amt = int(call.data.split("_")[1])
    uid = call.from_user.id; user = get_user(uid)
    user["daily"]["water"] += amt
    log_action(user, "water", f"{amt}ml su içti")
    leveled = add_xp(user, 15)
    leveled_quest = check_quests(user)
    leveled = leveled or leveled_quest
    save_user(uid, user)
    w = user["daily"]["water"]; t = user["targets"]["water"]
    lvl = f"\ng? *Lvl {user['level']}!*" if leveled else ""
    mk = InlineKeyboardMarkup(row_width=3)
    mk.add(InlineKeyboardButton("🔸250ml",callback_data="w_250"),
           InlineKeyboardButton("🔸500ml",callback_data="w_500"),
           InlineKeyboardButton("🔸1L",callback_data="w_1000"))
    mk.add(InlineKeyboardButton("🔸 Menü",callback_data="back"))
    bot.edit_message_text(f"🔸 *+{amt}ml!* (+15 XP)\n{make_bar(w,t,15)} {w}/{t}ml ({min(int(w/t*100),100)}%){lvl}",
        call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)


# ══════════════════════════════════════════════════════════════
#                   BUTONLU YEMEK SİSTEMİ
# ══════════════════════════════════════════════════════════════


@bot.callback_query_handler(func=lambda c: c.data == "m_food")
def menu_food(call):
    user = get_user(call.from_user.id)
    d = user["daily"]; t = user["targets"]
    mk = InlineKeyboardMarkup(row_width=2)
    # Önce özel kategoriler
    custom_foods = user.get("custom_foods", {})
    if custom_foods:
        mk.add(InlineKeyboardButton("🔸 Kayıtlı Yemeklerim", callback_data="fc_custom"))
    mk.add(InlineKeyboardButton("? Yeni Yiyecek Oluştur", callback_data="create_food"))
    # Normal kategoriler
    for k,(name,_) in FCAT.items():
        mk.add(InlineKeyboardButton(name, callback_data=k))
    mk.add(InlineKeyboardButton("🔸 Menü", callback_data="back"))
    bot.edit_message_text(
        f"🔸 *Yemek Ekle*\n🔸{int(d['kcal'])}/{t['kcal']}kcal | 🔸{int(d['protein'])}/{t['protein']}g\n\n"
        f"Kategori seç, sohbete direkt yaz, veya *kendi yiyeceğini oluştur!*\n_Örn: 200g tavuk, 1 tabak pilav_",
        call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)


# ── ÖZEL YİYECEK OLUŞ?TURMA SİHİRBAZI ──
@bot.callback_query_handler(func=lambda c: c.data == "create_food")
def create_food_start(call):
    uid = call.from_user.id
    custom_food_state[uid] = {"step": "name"}
    bot.edit_message_text(
        "🔸 *Yeni Yiyecek Oluştur*\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔸 *Yiyeceğin adını yaz:*\n_(Örn: Annemin köftesi, Protein bar X)_",
        call.message.chat.id, call.message.message_id, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.from_user.id in custom_food_state)
def create_food_wizard(message):
    uid = message.from_user.id
    state = custom_food_state[uid]
    txt = message.text.strip()

    if state["step"] == "name":
        state["name"] = txt.lower()
        state["step"] = "kcal"
        bot.reply_to(message, "🔸 *Kaç kalori (kcal)?* Bir porsiyon başına.\n_(Sadece sayı yaz, örn: 350)_", parse_mode="Markdown")

    elif state["step"] == "kcal":
        try:
            state["kcal"] = float(txt.replace(",",".")); state["step"] = "pro"
            bot.reply_to(message, "🔸 *Kaç gram protein?*\n_(Sadece sayı, örn: 25)_", parse_mode="Markdown")
        except:
            bot.reply_to(message, "❌ Geçerli bir sayı gir.")

    elif state["step"] == "pro":
        try:
            state["pro"] = float(txt.replace(",",".")); state["step"] = "carb"
            bot.reply_to(message, "🔸 *Kaç gram karbonhidrat?*\n_(Bilmiyorsan 0 yaz)_", parse_mode="Markdown")
        except:
            bot.reply_to(message, "❌ Geçerli bir sayı gir.")

    elif state["step"] == "carb":
        try:
            state["carb"] = float(txt.replace(",",".")); state["step"] = "fat"
            bot.reply_to(message, "🔸 *Kaç gram yağ?*\n_(Bilmiyorsan 0 yaz)_", parse_mode="Markdown")
        except:
            bot.reply_to(message, "❌ Geçerli bir sayı gir.")

    elif state["step"] == "fat":
        try:
            state["fat"] = float(txt.replace(",",".")); state["step"] = "per"
            bot.reply_to(message,
                "🔸 *Birim nedir?* (Neyi 1 porsiyon sayıyorsun?)\n"
                "_(Örn: 100g, 1 adet, 1 tabak, 1 dilim, 1 bardak)_", parse_mode="Markdown")
        except:
            bot.reply_to(message, "❌ Geçerli bir sayı gir.")

    elif state["step"] == "per":
        state["per"] = txt
        # Kaydet
        user = get_user(uid)
        if "custom_foods" not in user:
            user["custom_foods"] = {}
        user["custom_foods"][state["name"]] = {
            "kcal": state["kcal"], "pro": state["pro"],
            "carb": state["carb"], "fat": state["fat"],
            "per": state["per"]
        }
        save_user(uid, user)
        del custom_food_state[uid]

        bot.reply_to(message,
            f"✅ *Yiyecek kaydedildi!*\n\n"
            f"🔸 *{state['name'].title()}*\n"
            f"🔸 Birim: {state['per']}\n"
            f"🔸 {state['kcal']} kcal | 🔸 {state['pro']}g | 🔸 {state['carb']}g | 🔸 {state['fat']}g\n\n"
            f"Artık bu yiyeceği 'Kayıtlı Yemeklerim' altında veya sohbete adını yazarak kullanabilirsin!\n"
            f"/start ile menüye dön.", parse_mode="Markdown")


# ── KAYITLI YEMEKLERİM KATEGORİSİ ──
@bot.callback_query_handler(func=lambda c: c.data == "fc_custom")
def custom_food_list(call):
    user = get_user(call.from_user.id)
    custom = user.get("custom_foods", {})
    if not custom:
        bot.answer_callback_query(call.id, "Henüz özel yiyecek eklemedin!")
        return
    mk = InlineKeyboardMarkup(row_width=1)
    for fn, fd in custom.items():
        safe = fn.replace(" ","_")[:20]
        mk.add(InlineKeyboardButton(
            f"🔸 {fn.title()} ({fd['kcal']}kcal/{fd['per']})",
            callback_data=f"cf_{safe}"
        ))
    mk.add(InlineKeyboardButton("🔸 Yiyecek Sil", callback_data="del_custom_menu"))
    mk.add(InlineKeyboardButton("🔸 Kategoriler", callback_data="m_food"))
    bot.edit_message_text("🔸 *Kayıtlı Yemeklerin*\nSeç:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)


# ── ÖZEL YİYECEK SEÇ → PORSIYON VEYA GRAM ──
@bot.callback_query_handler(func=lambda c: c.data.startswith("cf_") and not c.data.startswith("cfa_"))
def custom_food_sel(call):
    safe = call.data[3:].replace("_"," ")
    user = get_user(call.from_user.id)
    custom = user.get("custom_foods", {})
    # Fuzzy match custom
    match_name = None
    for fn in custom:
        if safe in fn or fn in safe or _similarity(safe, fn) > 0.6:
            match_name = fn; break
    if not match_name:
        bot.answer_callback_query(call.id, "Bulunamadı!"); return
    fd = custom[match_name]
    safe_n = match_name.replace(" ","_")[:20]
    mk = InlineKeyboardMarkup(row_width=3)
    for m in ["0.5","1","1.5","2","3"]:
        mk.add(InlineKeyboardButton(f"x{m}", callback_data=f"cfa_{safe_n}_{m}"))
    mk.add(InlineKeyboardButton("🔸 Gram Gir", callback_data=f"cg_{safe_n}"))
    mk.add(InlineKeyboardButton("🔸 Geri", callback_data="fc_custom"))
    bot.edit_message_text(
        f"🔸 *{match_name.title()}*\n🔸 Birim: {fd['per']}\n"
        f"🔸{fd['kcal']}kcal | 🔸{fd['pro']}g | 🔸{fd['carb']}g | 🔸{fd['fat']}g\n\n"
        f"Porsiyon seç veya gram olarak gir:",
        call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)


# ── ÖZEL YİYECEK PORSIYON İLE EKLE ──
@bot.callback_query_handler(func=lambda c: c.data.startswith("cfa_"))
def custom_food_add(call):
    parts = call.data[4:].rsplit("_",1)
    safe = parts[0].replace("_"," "); mult = float(parts[1])
    uid = call.from_user.id; user = get_user(uid)
    custom = user.get("custom_foods", {})
    match_name = None
    for fn in custom:
        if safe in fn or fn in safe or _similarity(safe, fn) > 0.6:
            match_name = fn; break
    if not match_name: return
    fd = custom[match_name]
    _add_food_to_daily(uid, user, match_name, fd, mult, call)


# ── ÖZEL YİYECEK SİLME ──
@bot.callback_query_handler(func=lambda c: c.data == "del_custom_menu")
def del_custom_menu(call):
    user = get_user(call.from_user.id)
    custom = user.get("custom_foods", {})
    if not custom:
        bot.answer_callback_query(call.id, "Silinecek yiyecek yok!"); return
    mk = InlineKeyboardMarkup(row_width=1)
    for fn in custom:
        safe = fn.replace(" ","_")[:20]
        mk.add(InlineKeyboardButton(f"🔸 {fn.title()}", callback_data=f"del_cf_{safe}"))
    mk.add(InlineKeyboardButton("🔸 Geri", callback_data="fc_custom"))
    bot.edit_message_text("🔸 *Silmek istediğin yiyeceği seç:*", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_cf_"))
def del_custom_food(call):
    safe = call.data[7:].replace("_"," ")
    uid = call.from_user.id; user = get_user(uid)
    custom = user.get("custom_foods", {})
    to_del = None
    for fn in custom:
        if safe in fn or fn in safe or _similarity(safe, fn) > 0.6:
            to_del = fn; break
    if to_del:
        del user["custom_foods"][to_del]
        save_user(uid, user)
        bot.answer_callback_query(call.id, f"{to_del.title()} silindi!")
    # Geri dön
    custom_food_list(call)


# ══════════════════════════════════════════════════════════════
#         GRAM BAZLI MİKTAR GİRİ?İ (Normal + Özel Yiyecekler)
# ══════════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data.startswith("cg_"))
def custom_gram_input(call):
    """Özel yiyecek için gram girişi başlat."""
    safe = call.data[3:].replace("_"," ")
    uid = call.from_user.id; user = get_user(uid)
    custom = user.get("custom_foods", {})
    match_name = None
    for fn in custom:
        if safe in fn or fn in safe or _similarity(safe, fn) > 0.6:
            match_name = fn; break
    if not match_name: return
    custom_gram_state[uid] = {"food_name": match_name, "food_data": custom[match_name], "is_custom": True}
    bot.edit_message_text(
        f"🔸 *{match_name.title()}* için gram miktarı yaz:\n"
        f"_(Birim: {custom[match_name]['per']} başına değerler. 100g bazlıysa gramı yaz.)_",
        call.message.chat.id, call.message.message_id, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("fg_"))
def normal_gram_input(call):
    """Normal yiyecek için gram girişi başlat."""
    safe = call.data[3:].replace("_"," ")
    match_name, score = find_best_food_match(safe)
    if not match_name: return
    uid = call.from_user.id
    custom_gram_state[uid] = {"food_name": match_name, "food_data": FOODS[match_name], "is_custom": False}
    bot.edit_message_text(
        f"🔸 *{match_name.title()}* için gram miktarı yaz:\n"
        f"_(Birim: {FOODS[match_name]['per']}. 100g bazlıysa gramı yaz, porsiyon bazlıysa porsiyon sayısını ondalık yaz.)_",
        call.message.chat.id, call.message.message_id, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.from_user.id in custom_gram_state)
def gram_input_handler(message):
    uid = message.from_user.id
    state = custom_gram_state[uid]
    try:
        val = float(message.text.strip().replace(",","."))
    except:
        bot.reply_to(message, "❌ Geçerli bir sayı gir (gram veya porsiyon).")
        return

    fd = state["food_data"]
    fname = state["food_name"]
    per = fd.get("per", "")

    # 100g veya 100ml bazlıysa gram olarak hesapla
    if "100g" in per or "100ml" in per:
        mult = val / 100.0
    else:
        mult = val  # Porsiyon sayısı olarak

    user = get_user(uid)
    del custom_gram_state[uid]
    _add_food_to_daily_msg(uid, user, fname, fd, mult, message, gram_val=val)


# ══════════════════════════════════════════════════════════════
#        ORTAK FONKSİYON: Yiyeceği günlüğe ekle (callback)
# ══════════════════════════════════════════════════════════════
def _add_food_to_daily(uid, user, fname, fd, mult, call):
    k=fd["kcal"]*mult; p=fd["pro"]*mult; c_=fd["carb"]*mult; f_=fd["fat"]*mult
    user["daily"]["kcal"]+=k; user["daily"]["protein"]+=p; user["daily"]["carbs"]+=c_; user["daily"]["fats"]+=f_
    user["daily"]["meals"].append({"food":fname,"mult":round(mult,2),"kcal":round(k),"pro":round(p)})
    log_action(user, "food", f"{round(mult,2)} porsiyon {fname.title()} yedi ({int(k)} kcal)")
    if user["daily"]["protein"] >= user["targets"]["protein"]:
        user["str"] += 1
        
    xp_gain = 25
    if user["daily"]["kcal"] <= user["targets"]["kcal"]:
        xp_gain += 15 # Hedef içi sağlıklı beslenme
        
    leveled = add_xp(user, xp_gain) 
    leveled_quest = check_quests(user)
    leveled = leveled or leveled_quest
    save_user(uid, user)

    d = user["daily"]; t = user["targets"]
    kl = t["kcal"]-d["kcal"]
    lvl = f"\ng? *Lvl {user['level']}!*" if leveled else ""
    note = f"\n🔸 _{int(kl)} kcal kaldı_" if kl>0 else f"\n⚠️ _{int(abs(kl))} kcal fazla!_"

    mk = InlineKeyboardMarkup(row_width=2)
    mk.add(InlineKeyboardButton("🔸 Başka Ekle",callback_data="m_food"),
           InlineKeyboardButton("🔸 Menü",callback_data="back"))
    bot.edit_message_text(
        f"✅ *{round(mult,1)}x {fname.title()}* (+{xp_gain} XP)\n"
        f"+🔸{int(k)} | +🔸{int(p)}g | +🔸{int(c_)}g | +🔸{int(f_)}g\n"
        f"\n{make_bar(d['kcal'],t['kcal'],15)} {int(d['kcal'])}/{t['kcal']}kcal{note}{lvl}",
        call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)


def _add_food_to_daily_msg(uid, user, fname, fd, mult, message, gram_val=None):
    """Mesaj ile yiyecek ekle (gram girişi sonrası)."""
    k=fd["kcal"]*mult; p=fd["pro"]*mult; c_=fd["carb"]*mult; f_=fd["fat"]*mult
    user["daily"]["kcal"]+=k; user["daily"]["protein"]+=p; user["daily"]["carbs"]+=c_; user["daily"]["fats"]+=f_
    user["daily"]["meals"].append({"food":fname,"mult":round(mult,2),"kcal":round(k),"pro":round(p)})
    gram_txt = f" ({int(gram_val)}g)" if gram_val else ""
    log_action(user, "food", f"{fname.title()}{gram_txt} yedi ({int(k)} kcal)")
    if user["daily"]["protein"] >= user["targets"]["protein"]:
        user["str"] += 1
        
    xp_gain = 25
    if user["daily"]["kcal"] <= user["targets"]["kcal"]:
        xp_gain += 15 # Hedef içi sağlıklı beslenme
        
    leveled = add_xp(user, xp_gain)
    leveled_quest = check_quests(user)
    leveled = leveled or leveled_quest
    save_user(uid, user)

    d = user["daily"]; t = user["targets"]
    kl = t["kcal"]-d["kcal"]
    lvl = f"\ng? *Lvl {user['level']}!*" if leveled else ""
    note = f"\n🔸 _{int(kl)} kcal kaldı_" if kl>0 else f"\n⚠️ _{int(abs(kl))} kcal fazla!_"
    gram_txt = f" ({int(gram_val)}g)" if gram_val else ""

    bot.reply_to(message,
        f"✅ *{fname.title()}{gram_txt}* kaydedildi! (+{xp_gain} XP)\n"
        f"+🔸{int(k)} | +🔸{int(p)}g | +🔸{int(c_)}g | +🔸{int(f_)}g\n"
        f"\n{make_bar(d['kcal'],t['kcal'],15)} {int(d['kcal'])}/{t['kcal']}kcal{note}{lvl}\n"
        f"/start ile menüye dön.", parse_mode="Markdown")


# ══════════════════════════════════════════════════════════════
#                 NORMAL KATEGORİ YİYECEKLERİ
# ══════════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data.startswith("fc_") and c.data != "fc_custom")
def food_cat(call):
    cat_key = call.data
    name, items = FCAT.get(cat_key, ("?", []))
    mk = InlineKeyboardMarkup(row_width=1)
    for fn in items:
        fd = FOODS.get(fn)
        if fd:
            safe = fn.replace(" ","_")[:20]
            mk.add(InlineKeyboardButton(f"{fn.title()} ({fd['kcal']}kcal/{fd['per']})", callback_data=f"f_{safe}"))
    mk.add(InlineKeyboardButton("🔸 Kategoriler", callback_data="m_food"))
    bot.edit_message_text(f"*{name}*\nSeç:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("f_") and not c.data.startswith("fa_") and not c.data.startswith("fg_") and not c.data.startswith("fc_"))
def food_sel(call):
    safe = call.data[2:].replace("_"," ")
    match_name, score = find_best_food_match(safe)
    if not match_name:
        bot.answer_callback_query(call.id, "Bulunamadı!"); return
    fd = FOODS[match_name]
    safe_n = match_name.replace(" ","_")[:20]
    mk = InlineKeyboardMarkup(row_width=3)
    for m in ["0.5","1","1.5","2","3"]:
        mk.add(InlineKeyboardButton(f"x{m}", callback_data=f"fa_{safe_n}_{m}"))
    mk.add(InlineKeyboardButton("🔸 Gram Gir", callback_data=f"fg_{safe_n}"))
    mk.add(InlineKeyboardButton("🔸 Geri", callback_data="m_food"))
    bot.edit_message_text(
        f"*{match_name.title()}*\n{fd['per']}\n🔸{fd['kcal']}kcal | 🔸{fd['pro']}g | 🔸{fd['carb']}g | 🔸{fd['fat']}g\n\n"
        f"Porsiyon seç veya gram olarak gir:",
        call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("fa_"))
def food_add_btn(call):
    parts = call.data[3:].rsplit("_",1)
    safe = parts[0].replace("_"," ")
    mult = float(parts[1])
    match_name, _ = find_best_food_match(safe)
    if not match_name: return
    fd = FOODS[match_name]
    uid = call.from_user.id; user = get_user(uid)
    _add_food_to_daily(uid, user, match_name, fd, mult, call)


# ══════════════════════════════════════════════════════════════
#                    NE YEDİM LOG
# ══════════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "m_meallog")
def meal_log(call):
    user = get_user(call.from_user.id)
    meals = user["daily"].get("meals",[])
    d = user["daily"]; t = user["targets"]
    text = f"🔸 *Bugün Yediklerin*\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    if meals:
        for i,m in enumerate(meals,1):
            text += f"{i}. {m['food'].title()} x{m['mult']} — {int(m['kcal'])}kcal, {int(m['pro'])}g pro\n"
    else:
        text += "_Henüz bir şey yemedin._\n"
        
    sups = user["daily"].get("supplements", [])
    if sups:
        text += f"\n🔸 *Alınan Takviyeler:*\n"
        for i,s in enumerate(sups,1):
            text += f"• {s['name']}\n"
            
    text += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"🔸 {int(d['kcal'])}/{t['kcal']}kcal | 🔸 {int(d['protein'])}/{t['protein']}g | 🔸 {int(d['carbs'])}/{t['carbs']}g | 🔸 {int(d['fats'])}/{t['fats']}g"
    mk = InlineKeyboardMarkup()
    mk.add(InlineKeyboardButton("🔸 Menü",callback_data="back"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)


# ══════════════════════════════════════════════════════════════
#               ZİNDAN + PROGRESSİVE OVERLOAD
# ══════════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "m_gym")
def menu_gym(call):
    user = get_user(call.from_user.id)
    mk = InlineKeyboardMarkup(row_width=1)
    for k,z in EXERCISES.items():
        mk.add(InlineKeyboardButton(z["name"], callback_data=f"z_{k}"))
    mk.add(InlineKeyboardButton("🔸 Menü",callback_data="back"))
    boss_bar = make_bar(user["boss_hp"],user["boss_max_hp"],15)
    bot.edit_message_text(
        f"⚔️ *Zindan*\n🔸 Boss: *{user.get('boss_name', 'Goblin')}* (Lvl {user.get('boss_level', 1)})\n{boss_bar} {user['boss_hp']}/{user['boss_max_hp']}\n"
        f"Bugün: {user['daily']['sets']} set | {user['daily']['damage']} hasar\n\nBölge seç:",
        call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("z_"))
def zone_sel(call):
    zk = call.data[2:]
    zone = EXERCISES.get(zk)
    if not zone: return
    if zk == "cardio":
        mk = InlineKeyboardMarkup(row_width=1)
        for mk_key,name in zone["moves"].items():
            burn = CARDIO_BURN.get(mk_key,0)
            mk.add(InlineKeyboardButton(f"{name} (~{burn}kcal)", callback_data=f"cd_{mk_key}"))
        mk.add(InlineKeyboardButton("🔸",callback_data="m_gym"))
        bot.edit_message_text("🔸 *Kardiyo*\nAktivite seç:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)
        return
    mk = InlineKeyboardMarkup(row_width=1)
    user = get_user(call.from_user.id)
    for mk_key,name in zone["moves"].items():
        # Progressive overload notu ekle
        sug, _ = suggest_weight(user, mk_key)
        extra = f" ({int(sug)}kg önerilir)" if sug else ""
        mk.add(InlineKeyboardButton(f"{name}{extra}", callback_data=f"mv_{zk}_{mk_key}"))
    mk.add(InlineKeyboardButton("🔸",callback_data="m_gym"))

    # Sakatlık uyarısı
    injuries = user.get("injuries","").lower()
    warn = ""
    if injuries and injuries != "yok":
        warn = f"\n⚠️ _Sakatlık notu: {user['injuries']}_\n"

    bot.edit_message_text(f"*{zone['name']}*{warn}\nHareket seç:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cd_"))
def cardio_log(call):
    mk_key = call.data[3:]
    name = EXERCISES["cardio"]["moves"].get(mk_key, mk_key)
    burn = CARDIO_BURN.get(mk_key, 150)
    uid = call.from_user.id; user = get_user(uid)
    user["sta"] += 2
    user["daily"]["cardio_burn"] = user["daily"].get("cardio_burn", 0) + burn
    leveled = add_xp(user, 50)
    leveled_quest = check_quests(user)
    leveled = leveled or leveled_quest
    user["daily"]["workouts"].append({"type":"cardio","name":name,"burn":burn})
    
    if "exercise_stats" not in user: user["exercise_stats"] = {}
    if mk_key not in user["exercise_stats"]: user["exercise_stats"][mk_key] = {"sets": 0, "reps": 0, "volume": 0}
    user["exercise_stats"][mk_key]["sets"] += 1
    
    log_action(user, "cardio", f"{name} yaptı (Yakılan Kcal: {burn})")
    save_user(uid, user)
    lvl = f"\ng? *Lvl {user['level']}!*" if leveled else ""
    mk = InlineKeyboardMarkup()
    mk.add(InlineKeyboardButton("🔸 Menü",callback_data="back"))
    bot.edit_message_text(f"🔸 *{name}* tamamlandı! (+50 XP)\n🔸 ~{burn}kcal yakıldı! 🔸 STA+2{lvl}",
        call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("mv_"))
def move_sel(call):
    parts = call.data[3:].split("_",1)
    zk = parts[0]; mk_key = parts[1]
    zone = EXERCISES.get(zk,{}); move_name = zone.get("moves",{}).get(mk_key,"?")
    user = get_user(call.from_user.id)
    sug, note = suggest_weight(user, mk_key)

    mk = InlineKeyboardMarkup(row_width=4)
    weights = [20,40,60,80,100,120]
    if sug and sug not in weights and sug > 0:
        weights.append(int(sug))
        weights = sorted(set(weights))
    for w in weights:
        for r in [6,8,10,12]:
            mk.add(InlineKeyboardButton(f"{w}x{r}", callback_data=f"st_{mk_key}_{w}_{r}"))

    mk.add(InlineKeyboardButton("🔸",callback_data=f"z_{zk}"))
    hint = f"\n\n🔸 _{note}_" if note else ""
    bot.edit_message_text(f"🔸️ *{move_name}*{hint}\n\nAğırlık x Tekrar seç:",
        call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("st_"))
def log_set(call):
    parts = call.data.split("_")
    mk_key=parts[1]; w=int(parts[2]); r=int(parts[3])
    uid = call.from_user.id; user = get_user(uid)
    dmg = w*r
    
    if user.get("pet") == "wolf":
        dmg += 50 # Kurt Yoldaş = set başına +50 ekstra hasar!

    user["daily"]["sets"]+=1; user["daily"]["damage"]+=dmg
    user["boss_hp"]-=dmg; user["total_damage_all"]+=dmg; user["total_sets_all"]+=1; user["str"]+=1
    user["daily"]["workouts"].append({"type":"set","move":mk_key,"weight":w,"reps":r,"dmg":dmg})
    
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
            pr_msg = f"\n\n🏆 *YENİ REKOR (PR)!*\n{orm}kg Tahmini 1RM gücüne ulaştın! (+{xp_reward} XP)"
    
    # Derin Loglama
    move_name = EXERCISES.get("cardio", {}).get("moves", {}).get(mk_key, mk_key) # Fallback for name, will be improved
    for zk, zv in EXERCISES.items():
        if mk_key in zv.get("moves", {}):
            move_name = zv["moves"][mk_key]
            break
    log_action(user, "workout_set", f"{move_name} -> {w}kg x {r} tekrar ({dmg} hasar)")

    BOSS_NAMES = ["Goblin", "Ork", "İskelet Kral", "Troll", "Minotor", "Ejderha", "İblis Lordu", "Ölüm ?övalyesi", "Kadim Dev", "Karanlık Tanrı"]
    boss_killed = False
    
    # Boss Kesilme Kontrolü
    if user["boss_hp"] <= 0:
        # Eğer özel boss kesildiyse daha çok altın ver
        is_special = "(ÖZEL BOSS)" in user.get("boss_name", "")
        gold_reward = 2500 if is_special else 500
        
        user["gold"] += gold_reward
        user["boss_max_hp"] = 50000 + (user.get("boss_level", 1) * 10000) # Normal scale'e dön
        user["boss_hp"] = user["boss_max_hp"]
        user["boss_level"] = user.get("boss_level", 1) + 1
        b_idx = (user["boss_level"] - 1) % len(BOSS_NAMES)
        user["boss_name"] = BOSS_NAMES[b_idx]
        boss_killed = True
        
    # ÖZEL GÖREV (MILESTONE) / GİZLİ BOSS KONTROLÜ
    special_t = ""
    if "unlocked_bosses" not in user: user["unlocked_bosses"] = []
    
    if "weekly_damage" not in user: user["weekly_damage"] = 0
    user["weekly_damage"] += dmg
    if user["weekly_damage"] > 50000 and not user.get("deload_warned"):
        user["deload_warned"] = True
        special_t += "\n\n⚠️ *SİSTEM UYARISI:* Bu hafta toplam kaldırdığın ağırlık 50 Tonu aştı! Merkezi sinir sistemini korumak için önümüzdeki hafta 'Deload' (Dinlenme/Hafif Ağırlık) yapman önerilir."

    if mk_key == "bench_press" and w >= 100 and "titan" not in user["unlocked_bosses"]:
        user["unlocked_bosses"].append("titan")
        user["boss_name"] = "Krom Göğüslü Titan (ÖZEL BOSS)"
        user["boss_max_hp"] = 150000
        user["boss_hp"] = 150000
        special_t = "\n🔸 *ÖZEL BAŞ?ARIM: 100kg Bench Press!* Kükreyerek yeni bir Epik Boss uyandı!"
        log_action(user, "achievement", "100kg Bench Press başarıldı! Titan uyandı.")
    elif mk_key == "deadlift" and w >= 150 and "golem" not in user["unlocked_bosses"]:
        user["unlocked_bosses"].append("golem")
        user["boss_name"] = "Kemik Kıran Golem (ÖZEL BOSS)"
        user["boss_max_hp"] = 250000
        user["boss_hp"] = 250000
        special_t = "\n🔸 *ÖZEL BAŞ?ARIM: 150kg Deadlift!* Yer sarsıldı, yeni bir Epik Boss uyandı!"
        log_action(user, "achievement", "150kg Deadlift başarıldı! Golem uyandı.")
    elif mk_key == "squat" and w >= 100 and "dev" not in user["unlocked_bosses"]:
        user["unlocked_bosses"].append("dev")
        user["boss_name"] = "Demir Bacaklı Dev (ÖZEL BOSS)"
        user["boss_max_hp"] = 150000
        user["boss_hp"] = 150000
        special_t = "\n🔸 *ÖZEL BAŞ?ARIM: 100kg Squat!* Dağlardan yeni bir Epik Boss indi!"
        log_action(user, "achievement", "100kg Squat başarıldı! Dev uyandı.")

    xp_gained = max(30, int(dmg*0.1))
    leveled = add_xp(user, xp_gained)
    leveled_quest = check_quests(user)
    leveled = leveled or leveled_quest
    save_user(uid, user)
    
    boss_bar = make_bar(user["boss_hp"],user["boss_max_hp"],15)
    lvl = f"\ng? *Lvl {user['level']}!*" if leveled else ""
    boss_t = f"\n🔸 *BOSS YENİLDİ! Ödül Alındı!*" if boss_killed else ""
    
    final_message = f"⚔️ *{w}kg x {r}* kaydedildi!\n🔸 Boss'a *{dmg}* hasar! (+{xp_gained} XP)\n"
    final_message += f"🔸 Boss: *{user.get('boss_name', 'Goblin')}* (Lvl {user.get('boss_level', 1)})\n"
    final_message += f"{boss_bar} {user['boss_hp']}/{user['boss_max_hp']}\n"
    final_message += f"🔸 Bugün: {user['daily']['sets']} set | {user['daily']['damage']} hasar"
    final_message += f"{boss_t}{special_t}{lvl}"

    mk = InlineKeyboardMarkup(row_width=2)
    mk.add(InlineKeyboardButton("🔸 Tekrarla",callback_data=call.data),
           InlineKeyboardButton("🔸 Zindan",callback_data="m_gym"))
    mk.add(InlineKeyboardButton("🔸 Menü",callback_data="back"))
    bot.edit_message_text(
        final_message,
        call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)


# ══════════════════════════════════════════════════════════════
#               BUGÜNKÜ ANTRENMAN PROGRAMI
# ══════════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "m_prog")
def today_prog(call):
    user = get_user(call.from_user.id)
    goal = user.get("goal","koruma")
    prog = WORKOUT_PROGRAMS.get(goal, WORKOUT_PROGRAMS["koruma"])
    today_name = DAYS_TR[date.today().weekday()]
    dp = prog["days"].get(today_name,{})

    text = f"🔸 *Bugünkü Programın ({today_name})*\n🔸 {prog['title']}\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

    if dp.get("zone") is None:
        text += f"\n🔸 *{dp.get('note','Dinlenme günü')}*\nBugün dinlen, kasların iyileşsin!"
    elif dp.get("zone") == "cardio":
        text += "🔸 *Kardiyo Günü*\n"
        for mk_key in dp.get("moves",[]):
            name = EXERCISES["cardio"]["moves"].get(mk_key,mk_key)
            burn = CARDIO_BURN.get(mk_key,0)
            text += f"• {name} (~{burn} kcal)\n"
    else:
        zone = EXERCISES.get(dp["zone"],{})
        text += f"*{zone.get('name','')}*\n\n"
        for mk_key in dp.get("moves",[]):
            name = zone["moves"].get(mk_key,mk_key)
            sug, note = suggest_weight(user, mk_key)
            weight_hint = f" — *{int(sug)}kg* önerilir" if sug else ""
            po_note = f"\n  _↳ {note}_" if note else ""
            text += f"• {name}: {dp.get('sets',3)} set x {dp.get('reps','8-12')}{weight_hint}{po_note}\n"
        text += f"\n⏱ Dinlenme: {dp.get('rest','60-90 sn')}"

    # Sakatlık uyarısı
    injuries = user.get("injuries","").lower()
    if injuries and injuries != "yok":
        text += f"\n\n⚠️ _Dikkat: {user['injuries']} — hassas hareketlerde dikkatli ol!_"

    # Haftalık genel bakış
    text += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n🔸 *Hafta:*\n"
    for dn in ["Pazartesi","Salı","Çarşamba","Perşembe","Cuma","Cumartesi","Pazar"]:
        dp2 = prog["days"].get(dn,{})
        m = "🔸" if dn==today_name else "  "
        if dp2.get("zone") is None: text += f"{m} {dn}: 🔸\n"
        elif dp2["zone"]=="cardio": text += f"{m} {dn}: 🔸 Kardiyo\n"
        else: text += f"{m} {dn}: {EXERCISES.get(dp2['zone'],{}).get('name','')}\n"

    mk = InlineKeyboardMarkup()
    if dp.get("zone") and dp["zone"]!="cardio":
        mk.add(InlineKeyboardButton("⚔️ Zindana Gir",callback_data="m_gym"))
    mk.add(InlineKeyboardButton("🔸 Menü",callback_data="back"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)


# ══════════════════════════════════════════════════════════════
#                 Kİ?İSEL ASİSTAN ÖNERİ MOTORU
# ══════════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "m_advice")
def advice(call):
    user = get_user(call.from_user.id)
    d = user["daily"]; t = user["targets"]; goal = user.get("goal","koruma")
    tips = []

    # ── Su Analizi ──
    wp = (d["water"]/t["water"]*100) if t["water"]>0 else 0
    if wp < 30: tips.append("🔸 *Su çok az!* Hedefinin %30'unun altındasın. ?imdi bir bardak iç!")
    elif wp < 70: tips.append(f"🔸 Su %{int(wp)}. Hedef için {int(t['water']-d['water'])}ml daha iç.")
    else: tips.append("🔸 ✅ Su tüketimin iyi!")

    # ── Kalori Analizi ──
    kl = t["kcal"]-d["kcal"]
    if kl > t["kcal"]*0.7: tips.append(f"🔸 Neredeyse hiç kalori almamışsın! {int(kl)}kcal almalısın.")
    elif kl > 0 and kl < 500:
        # Akıllı öneri
        suggestions = []
        for fname, fd in FOODS.items():
            if abs(fd["kcal"]-kl) < kl*0.5 and fd["pro"] > 5:
                suggestions.append(f"{fname.title()} ({fd['kcal']}kcal)")
            if len(suggestions) >= 2: break
        sug_text = " veya ".join(suggestions) if suggestions else "hafif bir atıştırmalık"
        tips.append(f"🔸 Son {int(kl)}kcal için {sug_text} öneriyorum.")
    elif kl <= 0 and goal=="kilo_ver":
        tips.append(f"⚠️ *{int(abs(kl))}kcal fazla!* Kilo verme hedefinde dikkat et.")

    # ── Protein Analizi ──
    pl = t["protein"]-d["protein"]
    if pl > t["protein"]*0.6:
        tavuk_g = int(pl/0.31)
        tips.append(f"🔸 *Protein çok düşük!* {int(pl)}g daha lazım. ~{tavuk_g}g tavuk göğsü veya {int(pl/24)} ölçek protein tozu yeterli.")
    elif pl > 0:
        tips.append(f"🔸 Hedefe {int(pl)}g protein kaldı.")
    else:
        tips.append("🔸 ✅ Protein hedefine ulaştın!")

    # ── Antrenman Analizi ──
    today_name = DAYS_TR[date.today().weekday()]
    prog = WORKOUT_PROGRAMS.get(goal, WORKOUT_PROGRAMS["koruma"])
    dp = prog["days"].get(today_name,{})
    if d["sets"]==0 and dp.get("zone") and dp["zone"]!="cardio":
        tips.append(f"🔸️ *Bugün antrenman günün ama zindana gitmedin!* Hadi başla!")
    elif d["sets"]>0 and d["sets"]<12:
        tips.append(f"🔸️ {d['sets']} set yaptın, en az 12 set hedefle!")
    elif d["sets"]>=12:
        tips.append(f"🔸️ ✅ {d['sets']} set — harika!")

    # ── Geçmiş Verileri Analizi ──
    history = user.get("history",{})
    if len(history) >= 3:
        last = sorted(history.keys())[-7:]
        avg_k = sum(history[dd].get("kcal",0) for dd in last)/len(last)
        avg_p = sum(history[dd].get("protein",0) for dd in last)/len(last)
        avg_w = sum(history[dd].get("water",0) for dd in last)/len(last)
        tips.append(f"🔸 *Son {len(last)} gün ortalamaların:*\n  🔸{int(avg_k)}kcal | 🔸{int(avg_p)}g pro | 🔸{int(avg_w)}ml su")

        # Kilo tahmini
        if goal == "kilo_ver" and avg_k < t["kcal"]:
            deficit = t["kcal"] - avg_k + 500  # TDEE - ortalama
            weekly_loss = (deficit * 7) / 7700  # 7700 kcal = 1 kg
            tips.append(f"🔸 _Bu tempoda haftada ~{weekly_loss:.1f}kg kaybedebilirsin._")
        elif goal == "kas_kazan" and avg_k > user.get("tdee", 2500):
            surplus = avg_k - user.get("tdee", 2500)
            tips.append(f"🔸 _Günlük ~{int(surplus)}kcal fazlan var. Kas kazanmak için güzel!_")

    # ── Seri ──
    if user["streak"]>=7: tips.append(f"🔸 *{user['streak']} günlük seri!* Efsane!")
    elif user["streak"]>=3: tips.append(f"🔸 {user['streak']} gün seri, devam!")
    else: tips.append("🔸 Seriyi başlatmak için bugün hedeflerin %40'ını tamamla!")

    # ── Vücut Ölçüleri ve Takviyeler ──
    meas = user.get("measurements", "")
    sups = user["daily"].get("supplements", [])
    sup_text = ", ".join([s["name"] for s in sups]) if sups else "Yok"
    
    tips_str = "\n".join(tips)
    
    wait_msg = bot.edit_message_text("🔸 _Asistan durumunu inceliyor ve özel tavsiyeler hazırlıyor..._", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Sen fantastik bir RPG dünyasında deneyimli bir vücut geliştirme ustası ve yaşam koçusun (Adın: Demir Yumruk Usta). 
        Kullanıcı senin öğrencin. Aşağıda öğrencinin bugünkü istatistikleri ve geçmiş verileri var.
        Öğrenciye kısa, motive edici, RPG ağzıyla (kılıç, zindan, kalkan, iksir metaforları kullanarak) kişisel bir koçluk tavsiyesi ver.
        
        Öğrenci Bilgileri:
        - İsim: {user.get("name","Savaşçı")}
        - Yaş/Doğum: {user.get("age","Bilinmiyor")} ({user.get("dob","Tarih Yok")})
        - Hedef: {user.get("goal","Koruma")}
        - Vücut Ölçüleri (Kol, bacak çapı vs.): {meas if meas else "Bilinmiyor"}
        - Sakatlıklar: {user.get("injuries","Yok")}
        - Notlar: {user.get("ai_notes","Yok")}
        - Alınan Takviyeler (İksirler): {sup_text}
        
        Öğrencinin bugünkü durumu:
        {tips_str}
        
        KULLANICIYA YANITIN (SADECE CEVABI YAZ, Kısa ve öz olsun, maksimum 2-3 paragraf. Markdown kullanabilirsin):
        """
        response = model.generate_content(prompt)
        ai_text = response.text.strip()
    except Exception as e:
        ai_text = f"Yapay zeka asistanı yorgun düştü ({str(e)}). ?imdilik temel tavsiyelerime kulak ver:\n\n{tips_str}"

    text = f"🔸 *Demir Yumruk Usta'nın Tavsiyesi*\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n{ai_text}"
    mk = InlineKeyboardMarkup()
    mk.add(InlineKeyboardButton("🔸 Menü",callback_data="back"))
    bot.edit_message_text(text, wait_msg.chat.id, wait_msg.message_id, parse_mode="Markdown", reply_markup=mk)


# ══════════════════════════════════════════════════════════════
#             NOT EKLEME & PROFİL DÜZENLEME
# ══════════════════════════════════════════════════════════════
note_state = {}
custom_food_state = {}   # uid -> {step, name, kcal, pro, carb, fat, per}
custom_gram_state = {}   # uid -> {food_name, food_data, is_custom}

@bot.callback_query_handler(func=lambda c: c.data == "m_notes")
def menu_notes(call):
    user = get_user(call.from_user.id)
    text = (
        f"🔸 *AI Not Defteri*\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Mevcut notlar: _{user.get('ai_notes','') or 'Boş'}_\n"
        f"Sakatlıklar: _{user.get('injuries','') or 'Yok'}_\n\n"
        f"Yeni not eklemek veya güncellemek için aşağıya yaz:\n"
        f"_(Örn: Sabahları antrenman yapmayı seviyorum, glüten alerjim var)_"
    )
    note_state[call.from_user.id] = True
    mk = InlineKeyboardMarkup()
    mk.add(InlineKeyboardButton("🔸 Notları Temizle", callback_data="clear_notes"))
    mk.add(InlineKeyboardButton("🔸 Menü",callback_data="back"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data == "clear_notes")
def clear_notes(call):
    uid = call.from_user.id; user = get_user(uid)
    user["ai_notes"] = ""; save_user(uid, user)
    note_state.pop(uid, None)
    bot.answer_callback_query(call.id, "Notlar temizlendi!")
    bot.edit_message_text("✅ Notlar temizlendi.\n/start ile menüye dön.", call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda m: m.from_user.id in note_state)
def save_note(message):
    uid = message.from_user.id; user = get_user(uid)
    if not user: return
    existing = user.get("ai_notes","")
    new_note = message.text.strip()
    user["ai_notes"] = (existing + " | " + new_note).strip(" |") if existing else new_note
    save_user(uid, user)
    del note_state[uid]
    bot.reply_to(message, f"✅ *Not kaydedildi!*\n🔸 _{user['ai_notes']}_\n\n/start ile menüye dön.", parse_mode="Markdown")


@bot.callback_query_handler(func=lambda c: c.data == "m_profile")
def menu_profile(call):
    user = get_user(call.from_user.id)
    new_badges = check_achievements(user)
    if new_badges:
        save_user(call.from_user.id, user)
        
    badge_list = user.get("badges", [])
    badge_names = [next((bd["name"] for bd in BADGES_DB if bd["id"] == b), b) for b in badge_list]
    badges_str = " ".join(badge_names) if badge_names else "Henüz Yok"

    text = (
        f"⚙️ *Profil Bilgilerin*\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔸 {user['name']} | {user.get('age','?')} yaş\n"
        f"🔸 Boy: {user.get('height','?')}cm | ⚖️ Kilo: {user.get('weight','?')}kg\n"
        f"g? Hedef: {GOAL_NAMES.get(user.get('goal',''),'?')}\n"
        f"🔸 BMR: {user.get('bmr','?')} | TDEE: {user.get('tdee','?')}kcal\n"
        f"🔸 Sakatlık: {user.get('injuries','Yok')}\n"
        f"🔸 AI Notları: {user.get('ai_notes','') or 'Yok'}\n\n"
        f"g?️ *Rozetler:*\n{badges_str}\n\n"
        f"g? *Günlük Hedefler:*\n"
        f"🔸 {user['targets']['kcal']}kcal | 🔸 {user['targets']['protein']}g | 🔸 {user['targets']['carbs']}g | 🔸 {user['targets']['fats']}g | 🔸 {user['targets']['water']}ml\n\n"
        f"_Profili sıfırlamak için /reset yazabilirsin._"
    )
    mk = InlineKeyboardMarkup()
    mk.add(InlineKeyboardButton("🔸 Menü",callback_data="back"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)


# ══════════════════════════════════════════════════════════════
#                    İSTATİSTİK & SIRALAMA
# ══════════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "m_stats")
def stats(call):
    user = get_user(call.from_user.id)
    xn = xp_for_level(user["level"]); d = user["daily"]; t = user["targets"]
    wp = min(int(d["water"]/t["water"]*100),100) if t["water"]>0 else 0
    kp = min(int(d["kcal"]/t["kcal"]*100),100) if t["kcal"]>0 else 0
    pp = min(int(d["protein"]/t["protein"]*100),100) if t["protein"]>0 else 0
    overall = (wp+kp+pp)//3
    text = (
        f"🔸 *İstatistikler*\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔸 {user['name']} | {user.get('age','?')} | {user.get('height','?')}cm | {user.get('weight','?')}kg\n"
        f"g? {GOAL_NAMES.get(user.get('goal',''),'?')} | BMR:{user.get('bmr','?')} | TDEE:{user.get('tdee','?')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔸 Lvl {user['level']} | XP: {user['xp']}/{xn}\n"
        f"🔸 STR:{user['str']} | 🔸 STA:{user['sta']} | 🔸 {user['gold']} | 🔸 Seri:{user['streak']}\n"
        f"🔸 Yoldaş: {'🔸 Kurt (Boss Hasarı +50)' if user.get('pet')=='wolf' else '🔸 Kartal (%20 XP)' if user.get('pet')=='eagle' else 'Yok'}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔸 *Bugün:*\n"
        f"🔸 {d['water']}/{t['water']}ml ({wp}%) | 🔸 {int(d['kcal'])}/{t['kcal']} ({kp}%)\n"
        f"🔸 {int(d['protein'])}/{t['protein']}g ({pp}%) | 🔸 {int(d['carbs'])}/{t['carbs']}g | 🔸 {int(d['fats'])}/{t['fats']}g\n"
        f"🔸️ {d['sets']} set | {d['damage']} hasar\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔸 *Tüm Zamanlar:*\n"
        f"⚔️ Toplam Hasar: {user.get('total_damage_all',0)}\n"
        f"🔸️ Toplam Set: {user.get('total_sets_all',0)}\n"
        f"🔸 Detaylı Sistem Logu: {len(user.get('action_logs', []))} kayıt\n"
        f"g? *Günlük Başarı: %{overall}*"
    )
    
    # En çok yapılan hareketler
    ex_stats = user.get("exercise_stats", {})
    if ex_stats:
        top_ex = sorted(ex_stats.items(), key=lambda x: x[1].get("sets", 0), reverse=True)[:3]
        text += f"\n\n🔸 *En Sevdiğin Hareketler:*\n"
        for i, (k, v) in enumerate(top_ex):
            m_name = k
            for zk, zv in EXERCISES.items():
                if k in zv.get("moves", {}):
                    m_name = zv["moves"][k]
                    break
            text += f"{i+1}. {m_name} ({v.get('sets',0)} set, {v.get('volume',0)} tonaj)\n"

    mk = InlineKeyboardMarkup()
    mk.add(InlineKeyboardButton("🔸 Menü",callback_data="back"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)

import matplotlib
matplotlib.use('Agg') # GUI olmadan arkada çalışması için
import matplotlib.pyplot as plt
import io

@bot.callback_query_handler(func=lambda c: c.data == "m_menu_oneri")
def get_daily_menu(call):
    uid = call.from_user.id
    user = get_user(uid)
    if not user: return
    
    if call.id:
        bot.answer_callback_query(call.id, "Öneri hazırlanıyor...", show_alert=False)
        
    t = user["targets"]
    prompt = f"""
    Sen profesyonel bir fitness diyetisyenisin. Kullanıcının hedefi: {GOAL_NAMES.get(user.get('goal',''), '?')}
    Kullanıcının günlük makro hedefleri: {t['kcal']} kcal, {t['protein']}g Protein, {t['carbs']}g Karbonhidrat, {t['fats']}g Yağ.
    
    Bana bu hedeflere (+- %10 sapma payı ile) uygun olan, sabah, öğle, akşam ve ara öğün içeren pratik ve sağlıklı bir 1 GÜNLÜK yemek menüsü hazırla. Yemekler Türk mutfağına veya ulaşılabilir gıdalara (yumurta, yulaf, tavuk, pilav vb.) uygun olsun.
    Kullanıcının uymak zorunda olmadığı sadece tavsiye niteliğinde bir menü hazırla. Sadece markdown formatında şık bir liste ver. Uzun cümleler kurma. En altına tahmini toplam makroları yaz.
    """
    
    wait_msg = bot.send_message(call.message.chat.id, "🔸 _Yapay Zeka (Gemini) bugüne özel yemek menüsü hazırlıyor..._", parse_mode="Markdown")
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        res = model.generate_content(prompt)
        bot.edit_message_text(f"🔸️ *Günün Menü Önerisi*\n\n{res.text.strip()}", wait_msg.chat.id, wait_msg.message_id, parse_mode="Markdown")
    except Exception as e:
        bot.edit_message_text("❌ Menü hazırlanırken bir hata oluştu.", wait_msg.chat.id, wait_msg.message_id)

@bot.callback_query_handler(func=lambda c: c.data == "m_arena")
def open_arena(call):
    uid = call.from_user.id
    user = get_user(uid)
    if not user: return
    
    my_power = user.get("str", 10) * 10 + user.get("max_hp", 100)
    
    text = (
        f"⚔️ *ARENA'YA HOŞ? GELDİN!*\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Burada diğer Savaşçılara veya Yapay Zeka Rakiplerine karşı düello yaparsın.\n\n"
        f"🔸 Senin Savaş Gücün: *{my_power}*\n"
        f"🔸 Giriş Ücreti: *100 Altın*\n"
        f"🔸 Ödül: *250 Altın + 500 XP*\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Düelloya hazır mısın?"
    )
    mk = InlineKeyboardMarkup()
    mk.row(InlineKeyboardButton("⚔️ SAVAŞ? (100 Altın)", callback_data="arena_fight"))
    mk.row(InlineKeyboardButton("🔸 Menü", callback_data="back"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data == "arena_fight")
def arena_fight(call):
    uid = call.from_user.id
    user = get_user(uid)
    if not user: return
    
    if user.get("gold", 0) < 100:
        bot.answer_callback_query(call.id, "❌ Yeterli altının yok! (100 Altın Gerekli)", show_alert=True)
        return
        
    user["gold"] -= 100
    my_power = user.get("str", 10) * 10 + user.get("max_hp", 100)
    
    import random
    rival_power = int(my_power * random.uniform(0.7, 1.2)) # %70 ile %120 arası güçte rakip
    
    text = f"⚔️ *ARENA SAVAŞ?I*\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"Senin Gücün: *{my_power}* 🔸 Rakibin Gücü: *{rival_power}*\n\n"
    
    my_score = my_power * random.uniform(0.8, 1.2)
    rival_score = rival_power * random.uniform(0.8, 1.2)
    
    if my_score >= rival_score:
        user["gold"] += 250
        leveled = add_xp(user, 500)
        text += f"🔸 *KAZANDIN!*\nRakibini ezip geçtin!\n🔸 +250 Altın\n🔸 +500 XP"
        if leveled:
            text += "\n\n🔸 *SEVİYE ATLADIN!*"
    else:
        text += f"🔸 *KAYBETTİN!*\nRakibin çok güçlü çıktı. 100 Altın kaybettin."
        
    save_user(uid, user)
    
    mk = InlineKeyboardMarkup()
    mk.row(InlineKeyboardButton("⚔️ Tekrar Savaş", callback_data="arena_fight"))
    mk.row(InlineKeyboardButton("🔸 Menü", callback_data="back"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data == "m_vitamins")
def open_vitamins(call):
    text = (
        "🔸 *VİTAMİN & TAKVİYE MENÜSÜ*\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Bugün hangi takviyeyi veya vitamini aldın? Tek tıkla günlüğüne kaydet!"
    )
    mk = InlineKeyboardMarkup()
    mk.row(InlineKeyboardButton("🔸 Kreatin (5g)", callback_data="log_vitamin_kreatin"),
           InlineKeyboardButton("🔸 Omega-3", callback_data="log_vitamin_omega3"))
    mk.row(InlineKeyboardButton("🔸 C Vitamini", callback_data="log_vitamin_cvitamini"),
           InlineKeyboardButton("☀️ D Vitamini", callback_data="log_vitamin_dvitamini"))
    mk.row(InlineKeyboardButton("🔸 B Kompleks", callback_data="log_vitamin_bkompleks"),
           InlineKeyboardButton("🔸 ZMA / Magnezyum", callback_data="log_vitamin_zma"))
    mk.row(InlineKeyboardButton("🔸 Protein Tozu (1 Ölçek)", callback_data="log_vitamin_proteintozu"))
    mk.row(InlineKeyboardButton("🔸 Menü", callback_data="back"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("log_vitamin_"))
def log_vitamin(call):
    uid = call.from_user.id
    user = get_user(uid)
    if not user: return
    
    item = call.data.split("log_vitamin_")[1]
    
    names = {
        "kreatin": "Kreatin (5g)",
        "omega3": "Omega-3 (Balık Yağı)",
        "cvitamini": "C Vitamini",
        "dvitamini": "D Vitamini",
        "bkompleks": "B Kompleks Vitamini",
        "zma": "ZMA / Magnezyum",
        "proteintozu": "Protein Tozu (1 Ölçek)"
    }
    
    sup_name = names.get(item, item)
    
    if "supplements" not in user["daily"]:
        user["daily"]["supplements"] = []
        
    user["daily"]["supplements"].append({"name": sup_name})
    log_action(user, "supplement", f"Takviye kullanıldı: {sup_name}")
    
    # Protein tozu özel durumu: Makro da eklesin
    if item == "proteintozu":
        user["daily"]["kcal"] = user["daily"].get("kcal", 0) + 120
        user["daily"]["protein"] = user["daily"].get("protein", 0) + 24
        if "meals" not in user["daily"]: user["daily"]["meals"] = []
        user["daily"]["meals"].append({"food": "Protein Tozu (Takviye)", "mult": 1, "kcal": 120, "pro": 24})
        bot.answer_callback_query(call.id, f"✅ {sup_name} kaydedildi! (+120 kcal, +24g Protein)", show_alert=True)
    else:
        bot.answer_callback_query(call.id, f"✅ {sup_name} günlüğe eklendi!", show_alert=True)
        
    save_user(uid, user)

@bot.callback_query_handler(func=lambda c: c.data == "m_shop")
def open_shop(call):
    uid = call.from_user.id
    user = get_user(uid)
    if not user: return
    
    gold = user.get("gold", 0)
    text = (
        f"🔸 *RPG Dükkanına Hoşgeldin!*\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔸 Bakiye: *{gold} Altın*\n"
        f"_(Antrenman yaptıkça ve görevleri bitirdikçe altın kazanırsın)_\n\n"
        f"Ne satın almak istersin?"
    )
    mk = InlineKeyboardMarkup(row_width=1)
    mk.add(
        InlineKeyboardButton("g? Gizemli Kutu (100 Altın) [Rastgele Ödül]", callback_data="buy_chest"),
        InlineKeyboardButton("g? Seri Dondurucu (200 Altın) [Seri Koruması]", callback_data="buy_freeze"),
        InlineKeyboardButton("🔸 Can İksiri (50 Altın) [HP Fulle]", callback_data="buy_hp"),
        InlineKeyboardButton("🔸 XP İksiri (300 Altın) [+250 XP]", callback_data="buy_xp"),
        InlineKeyboardButton("🔸️ Savaşçı Tılsımı (500 Altın) [+5 STR]", callback_data="buy_str"),
        InlineKeyboardButton("🔸️ Demir Zırh (500 Altın) [+50 Max HP]", callback_data="buy_maxhp"),
        InlineKeyboardButton("🔸 Kurt Yoldaş (1500 Altın) [Boss Hasarı]", callback_data="buy_pet_wolf"),
        InlineKeyboardButton("🔸 Kartal Yoldaş (1000 Altın) [%20 XP]", callback_data="buy_pet_eagle"),
        InlineKeyboardButton("🔸 Menü", callback_data="back")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_"))
def buy_item(call):
    uid = call.from_user.id
    user = get_user(uid)
    if not user: return
    
    item = call.data[4:]
    gold = user.get("gold", 0)
    
    costs = {"hp": 50, "xp": 300, "str": 500, "maxhp": 500, "chest": 100, "freeze": 200, "pet_wolf": 1500, "pet_eagle": 1000}
    cost = costs.get(item, 99999)
    
    if gold < cost:
        bot.answer_callback_query(call.id, "❌ Yeterli altının yok!", show_alert=True)
        return
        
    user["gold"] -= cost
    msg = ""
    
    if item == "hp":
        user["hp"] = user["max_hp"]
        msg = "🔸 Can İksiri içtin! HP'n tamamen doldu."
    elif item == "freeze":
        user["streak_freeze"] = True
        msg = "g? Seri Dondurucu aldın! Eğer bugün idman yapmazsan serin bozulmayacak."
    elif item == "xp":
        add_xp(user, 250)
        msg = "🔸 XP İksiri içtin! 250 XP kazandın."
    elif item == "str":
        user["str"] = user.get("str", 10) + 5
        msg = "🔸️ Savaşçı Tılsımı kuşandın! Kalıcı olarak +5 STR eklendi."
    elif item == "maxhp":
        user["max_hp"] = user.get("max_hp", 100) + 50
        user["hp"] += 50
        msg = "🔸️ Demir Zırh giydin! Kalıcı olarak +50 Max HP eklendi."
    elif item == "pet_wolf":
        user["pet"] = "wolf"
        msg = "🔸 Kurt Yoldaş edindin! Artık her setinde Bosslara +50 Ekstra hasar vuracak!"
    elif item == "pet_eagle":
        user["pet"] = "eagle"
        msg = "🔸 Kartal Yoldaş edindin! Artık %20 daha fazla XP kazanacaksın!"
    elif item == "chest":
        import random
        pool = [
            ("xp", 100, "🔸 Kutu içinden 100 XP Çıktı!"),
            ("xp", 500, "🔸 ?ANSLISIN! Kutudan 500 XP Çıktı!"),
            ("str", 1, "🔸️ Küçük bir taş buldun. Kalıcı olarak +1 STR eklendi."),
            ("str", 10, "🔸 İNANILMAZ! Efsanevi Tılsım buldun! +10 STR eklendi!"),
            ("hp", 10, "🔸️ Kırık Zırh Parçası buldun. +10 Max HP."),
            ("gold", 300, "🔸 Hazine Buldun! 300 Altın Çıktı!"),
            ("empty", 0, "🔸️ Kutunun içi maalesef BOŞ? çıktı...")
        ]
        reward = random.choices(pool, weights=[30, 5, 20, 2, 20, 10, 13], k=1)[0]
        
        rtype, rval, msg = reward
        if rtype == "xp":
            add_xp(user, rval)
        elif rtype == "str":
            user["str"] = user.get("str", 10) + rval
        elif rtype == "hp":
            user["max_hp"] = user.get("max_hp", 100) + rval
        elif rtype == "gold":
            user["gold"] += rval
        
    save_user(uid, user)
    bot.answer_callback_query(call.id, f"✅ Satın alındı!\n{msg}", show_alert=True)
    open_shop(call)

@bot.callback_query_handler(func=lambda c: c.data == "m_chart")
def show_chart(call):
    if call.id:
        bot.answer_callback_query(call.id, "Grafik oluşturuluyor...", show_alert=False)
    user = get_user(call.from_user.id)
    history = user.get("history", {})
    
    if len(history) < 1:
        bot.send_message(call.message.chat.id, "❌ Çizecek yeterli geçmiş verisi yok. En az 1 tam gün geçmesi (gece 00:00) gerek!")
        return
        
    dates = sorted(history.keys())[-7:] # Son 7 gün
    
    kcal_data = []
    dmg_data = []
    labels = []
    
    for d in dates:
        labels.append(d[-5:]) # MM-DD
        kcal_data.append(history[d].get("kcal", 0))
        dmg_data.append(history[d].get("damage", 0))
        
    # Grafiği Çiz (Matplotlib)
    fig, ax1 = plt.subplots(figsize=(8, 4))
    
    color = 'tab:red'
    ax1.set_xlabel('Tarih')
    ax1.set_ylabel('Kalori (kcal)', color=color, fontweight='bold')
    ax1.plot(labels, kcal_data, color=color, marker='o', linewidth=2, label="Kalori")
    ax1.tick_params(axis='y', labelcolor=color)
    
    ax2 = ax1.twinx()  
    color = 'tab:blue'
    ax2.set_ylabel('Zindan Hasarı (Tonaj)', color=color, fontweight='bold')  
    ax2.bar(labels, dmg_data, color=color, alpha=0.3, label="Hasar")
    ax2.tick_params(axis='y', labelcolor=color)
    
    plt.title(f"{user.get('name', 'Savaşçı')} - 7 Günlük Gelişim Tablosu", fontweight='bold')
    fig.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    plt.close(fig)
    
    bot.send_photo(call.message.chat.id, buf, caption="🔸 *İşte son 7 günlük gelişimin!*\nKırmızı çizgi kaloriyi, mavi barlar ise zindanda vurduğun toplam hasarı (kaldırdığın tonajı) gösterir.", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "m_lb")
def leaderboard(call):
    data = load_data()
    sl = sorted(data.items(), key=lambda x:(x[1].get("level",0),x[1].get("xp",0)), reverse=True)
    medals = ["🔸","🔸","🔸"]
    text = "🔸 *Sıralama (Seviye)*\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for i,(uid,u) in enumerate(sl[:10]):
        m = medals[i] if i<3 else f"{i+1}."
        me = " ⬅️" if str(uid)==str(call.from_user.id) else ""
        text += f"{m} *{u['name']}* — Lvl {u['level']}{me}\n"
    if not sl: text += "_Henüz kimse yok._\n"
    sd = sorted(data.items(), key=lambda x:x[1].get("total_damage_all",0), reverse=True)
    text += "\n⚔️ *En Çok Hasar*\n"
    for i,(uid,u) in enumerate(sd[:5]):
        m = medals[i] if i<3 else f"{i+1}."
        text += f"{m} *{u['name']}* — {u.get('total_damage_all',0)}\n"
    mk = InlineKeyboardMarkup()
    mk.add(InlineKeyboardButton("🔸 Menü",callback_data="back"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)


# ══════════════════════════════════════════════════════════════
#                     RESET & BACK
# ══════════════════════════════════════════════════════════════
@bot.message_handler(commands=['reset'])
def reset(message):
    data = load_data()
    uid = str(message.from_user.id)
    if uid in data:
        del data[uid]
        save_data(data)
    bot.send_message(message.chat.id, "🔸 Profil silindi. /start ile yeniden oluştur.")

@bot.callback_query_handler(func=lambda c: c.data == "back")
def back_main(call):
    uid = call.from_user.id
    user = get_user(uid)
    if not user:
        bot.edit_message_text("Profil bulunamadı. /start ile başla.", call.message.chat.id, call.message.message_id)
        return
        
    text = _get_menu_text(user)

    mk = InlineKeyboardMarkup(row_width=2)
    mk.row(
        InlineKeyboardButton("🔸 Su İç", callback_data="m_water"),
        InlineKeyboardButton("🔸 Yemek Ekle", callback_data="m_food")
    )
    mk.row(
        InlineKeyboardButton("⚔️ Zindan (Antrenman)", callback_data="m_gym"),
        InlineKeyboardButton("🔸 Bugün Program", callback_data="m_prog")
    )
    mk.row(
        InlineKeyboardButton("🔸 Ne Yedim?", callback_data="m_meallog"),
        InlineKeyboardButton("🔸 Asistan", callback_data="m_advice")
    )
    mk.row(
        InlineKeyboardButton("🔸 Dükkan (Market)", callback_data="m_shop"),
        InlineKeyboardButton("⚔️ Arena (Düello)", callback_data="m_arena")
    )
    mk.row(
        InlineKeyboardButton("🔸 Günlük Menü", callback_data="m_menu_oneri"),
        InlineKeyboardButton("🔸 Grafik & Analiz", callback_data="m_chart")
    )
    mk.row(
        InlineKeyboardButton("🔸 Vitamin & Takviye", callback_data="m_vitamins")
    )
    mk.row(
        InlineKeyboardButton("🔸 İstatistik", callback_data="m_stats"),
        InlineKeyboardButton("🔸 Sıralama", callback_data="m_lb")
    )
    mk.row(
        InlineKeyboardButton("🔸 Notlar", callback_data="m_notes"),
        InlineKeyboardButton("⚙️ Profili Düzenle", callback_data="m_profile")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)


# ══════════════════════════════════════════════════════════════
#                          BAŞ?LAT
# ══════════════════════════════════════════════════════════════
import threading
import time

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
                        msg = "🔸 *Savaşçı, bugün kılıcını (ağırlıkları) kaldırmadın!*\n"
                        if u.get("measurements"):
                            msg += f"Vücut Ölçülerin ({u['measurements']}) gerilemesin! Evde yapabileceğin 10 dakikalık şınav/mekik setleriyle bile günü kurtarabilirsin.\n"
                        else:
                            msg += "Evde yapabileceğin 10 dakikalık şınav/mekik setleriyle bile günü kurtarabilirsin.\n"
                        msg += "\nUnutma, hiç yapmamaktansa yarım yapmak daha iyidir!"
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
                        msg = f"🍗 *Dikkat Savaşçı!* Hedefinden {int(protein_left)}g protein geridesin.\nKaslarını beslemek için bir porsiyon tavuk, lor peyniri veya yumurta yemelisin! Yoksa bugünkü XP kazanımın düşecek."
                        try:
                            bot.send_message(int(uid), msg, parse_mode="Markdown")
                            u[f"macro_reminded_{now.hour}"] = True
                            save_user(uid, u)
                        except: pass
                    elif kcal_left > 500:
                        msg = f"🔥 *Kalori Açığı Çok Yüksek!* Bugün daha {int(kcal_left)} kcal kalori alman lazım.\nBu şekilde uyursan kas kaybedebilirsin!"
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

def recalculate_database_macros():
    data = load_data()
    changed = False
    
    sup_macros = {
        'Protein Tozu (Takviye)': {'kcal': 120, 'pro': 24, 'carb': 3, 'fat': 1}
    }
    
    for uid, user in data.items():
        if "daily" in user and "meals" in user["daily"]:
            new_kcal = 0; new_pro = 0; new_carbs = 0; new_fats = 0
            for meal in user["daily"]["meals"]:
                fname = meal.get("food", "").lower()
                mult = meal.get("mult", 1)
                
                food_data = FOODS.get(fname)
                if not food_data and meal.get("food") in sup_macros:
                    food_data = sup_macros[meal.get("food")]
                
                if food_data:
                    meal["kcal"] = round(food_data.get("kcal", 0) * mult)
                    meal["pro"] = round(food_data.get("pro", 0) * mult)
                    new_kcal += meal["kcal"]
                    new_pro += meal["pro"]
                    new_carbs += round(food_data.get("carb", 0) * mult)
                    new_fats += round(food_data.get("fat", 0) * mult)
                else:
                    new_kcal += meal.get("kcal", 0)
                    new_pro += meal.get("pro", 0)
                    new_carbs += meal.get("carb", 0)
                    new_fats += meal.get("fat", 0)
                    
            user["daily"]["kcal"] = new_kcal
            user["daily"]["protein"] = new_pro
            user["daily"]["carbs"] = new_carbs
            user["daily"]["fats"] = new_fats
            changed = True
            
        if "history" in user:
            for d, dayData in user["history"].items():
                if "meals" in dayData and isinstance(dayData["meals"], list):
                    new_h_kcal = 0; new_h_pro = 0
                    for meal in dayData["meals"]:
                        fname = meal.get("food", "").lower()
                        mult = meal.get("mult", 1)
                        food_data = FOODS.get(fname)
                        if not food_data and meal.get("food") in sup_macros:
                            food_data = sup_macros[meal.get("food")]
                            
                        if food_data:
                            meal["kcal"] = round(food_data.get("kcal", 0) * mult)
                            meal["pro"] = round(food_data.get("pro", 0) * mult)
                            new_h_kcal += meal["kcal"]
                            new_h_pro += meal["pro"]
                        else:
                            new_h_kcal += meal.get("kcal", 0)
                            new_h_pro += meal.get("pro", 0)
                    dayData["kcal"] = new_h_kcal
                    dayData["protein"] = new_h_pro
                    changed = True
                    
    if changed:
        save_data(data)
        print("Veritabani makrolari foods.json ile guncellendi!")

if __name__ == "__main__":
    recalculate_database_macros()
    print("="*50)
    print("    RPG FITNESS ASISTAN BA?LATILDI  ")
    print("="*50)
    threading.Thread(target=reminder_thread, daemon=True).start()
    print("Bot mesajlar dinliyor...")
    bot.infinity_polling()
