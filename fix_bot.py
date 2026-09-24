import google.generativeai as genai
import os
import re

# Use the same API key from bot.py
import sys
sys.path.append('Bot')
# We can't import bot.py because it might have syntax errors due to corruption or we just read the key
with open('Bot/bot.py', 'r', encoding='utf-8') as f:
    text = f.read()

match = re.search(r'genai\.configure\(api_key=["\'](.*?)["\']\)', text)
if match:
    api_key = match.group(1)
else:
    print("API key not found")
    sys.exit(1)

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

prompt = '''
Aşağıdaki Python kodunda Türkçe karakterler ve emojiler \ufffd veya benzeri bozuk karakterlere (örneğin "g\ufffd") dönüşmüş durumda.
Lütfen sadece bu bozuk karakterleri orijinal Türkçe harflere (ş, ğ, ı, ö, ç, ü vb.) ve mantıklı emojilere dönüştürerek TÜM KODU geri ver.
Kodun yapısını, mantığını veya İngilizce değişken isimlerini KESİNLİKLE değiştirme.
Sadece string içindeki ve yorum satırlarındaki bozuklukları düzelt.

KOD:
''' + text

print("Fixing with Gemini...")
response = model.generate_content(prompt)
fixed_text = response.text

if fixed_text.startswith("`python"):
    fixed_text = fixed_text[9:]
if fixed_text.startswith("`"):
    fixed_text = fixed_text[3:]
if fixed_text.endswith("`"):
    fixed_text = fixed_text[:-3]

with open('Bot/bot.py', 'w', encoding='utf-8') as f:
    f.write(fixed_text.strip() + '\n')
print("Fixed successfully!")