with open('Web/analiz.html', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('VeritabanÄ±', 'Veritabanı')
text = text.replace('okunamadÄ±!', 'okunamadı!')
text = text.replace('TarayÄ±cÄ±', 'Tarayıcı')
text = text.replace('gÃ¼venlik', 'güvenlik')
text = text.replace('kurallarÄ±', 'kuralları')
text = text.replace('gereÄŸi', 'gereği')
text = text.replace('dosyayÄ±', 'dosyayı')
text = text.replace('Ã§ift', 'çift')
text = text.replace('tÄ±klayarak', 'tıklayarak')
text = text.replace('deÄŸil,', 'değil,')
text = text.replace('aÃ§malÄ±sÄ±n.', 'açmalısın.')
text = text.replace('paneli_ac.bat', 'panel_ac.bat')

# And some general ones if there are any
text = text.replace('Ä±', 'ı').replace('ÄŸ', 'ğ').replace('Ã¼', 'ü').replace('Ã§', 'ç').replace('Ã¶', 'ö').replace('ÅŸ', 'ş').replace('Ä°', 'İ')

with open('Web/analiz.html', 'w', encoding='utf-8') as f:
    f.write(text)