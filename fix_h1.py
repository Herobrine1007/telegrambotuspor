with open('Web/analiz.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re

# Fix title
text = re.sub(r'<title>.*?</title>', '<title>Savaşçı Analiz & Gelişim Paneli</title>', text)

# Fix h1
text = re.sub(r'<h1>.*?</h1>', '<h1>⚔️ Savaşçı Gelişim Analizi</h1>', text)

with open('Web/analiz.html', 'w', encoding='utf-8') as f:
    f.write(text)