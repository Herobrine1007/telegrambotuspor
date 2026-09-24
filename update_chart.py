import re

with open('Web/analiz.html', 'r', encoding='utf-8') as f:
    text = f.read()

# I will replace the history iteration logic in loadUser to also include 'Bugün'
old_history_logic = '''
        if (user.history) {
            const dates = Object.keys(user.history).sort();
            dates.forEach(d => {
                historyLabels.push(d);
                kcalValues.push(user.history[d].kcal || 0);
                dmgValues.push(user.history[d].damage || 0);
                waterValues.push(user.history[d].water || 0);
                proteinValues.push(user.history[d].protein || 0);
                carbsValues.push(user.history[d].carbs || 0);
                fatsValues.push(user.history[d].fats || 0);
            });
        }
'''

new_history_logic = '''
        if (user.history) {
            const dates = Object.keys(user.history).sort();
            dates.forEach(d => {
                historyLabels.push(d);
                kcalValues.push(user.history[d].kcal || 0);
                dmgValues.push(user.history[d].damage || 0);
                waterValues.push(user.history[d].water || 0);
                proteinValues.push(user.history[d].protein || 0);
                carbsValues.push(user.history[d].carbs || 0);
                fatsValues.push(user.history[d].fats || 0);
            });
        }
        // Bugünü de grafiğe ekleyelim!
        historyLabels.push("Bugün");
        kcalValues.push(user.daily.kcal || 0);
        dmgValues.push(user.daily.damage || 0);
        waterValues.push(user.daily.water || 0);
        proteinValues.push(user.daily.protein || 0);
        carbsValues.push(user.daily.carbs || 0);
        fatsValues.push(user.daily.fats || 0);
'''

text = text.replace(old_history_logic.strip(), new_history_logic.strip())

with open('Web/analiz.html', 'w', encoding='utf-8') as f:
    f.write(text)