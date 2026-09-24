import json

def fix_double_utf8(text):
    try:
        # We take the double-encoded string, encode it to 1254 to get the original utf-8 bytes back,
        # then decode as utf-8.
        return text.encode('cp1254').decode('utf-8')
    except:
        return text

with open('Bot/bot.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Let's see if we can fix a sample piece
idx = text.find('Foto')
if idx != -1:
    print('Original:', text[idx:idx+20].encode('utf-8'))
    try:
        fixed = fix_double_utf8(text[idx:idx+20])
        print('Fixed:', fixed.encode('utf-8'))
    except Exception as e:
        print('Error:', e)