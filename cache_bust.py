with open('Web/analiz.html', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace("fetch('../Data/database.json')", "fetch('../Data/database.json?v=' + new Date().getTime(), {cache: 'no-store'})")

with open('Web/analiz.html', 'w', encoding='utf-8') as f:
    f.write(text)