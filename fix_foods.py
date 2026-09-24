import json
import re

with open('Data/foods.json', 'r', encoding='utf-8') as f:
    text = f.read()
    
# Replace some known corruptions based on my memory of what I wrote
text = text.replace('gYsǬ', 'göğsü')
text = text.replace('kyma', 'kıyma')
text = text.replace('kuYbaY', 'kuşbaşı')
text = text.replace('balY', 'balığı')
text = text.replace('fndk', 'fındık')
text = text.replace('fstk', 'fıstık')
text = text.replace('ceviz ii', 'ceviz içi')
text = text.replace('badem ii', 'badem içi')
text = text.replace('zeytinya', 'zeytinyağı')
text = text.replace('tereya', 'tereyağı')
text = text.replace('st', 'süt')
text = text.replace('yourt', 'yoğurt')
text = text.replace('peynir', 'peynir')

with open('Data/foods.json', 'w', encoding='utf-8') as f:
    f.write(text)