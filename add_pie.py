import re

with open('Web/analiz.html', 'r', encoding='utf-8') as f:
    text = f.read()

# I will add a Muscle Group Pie Chart
html_add = '''
            <div class="chart-box">
                <h3>💪 Çalışan Kas Grupları (Hacim Dağılımı)</h3>
                <canvas id="muscleChart"></canvas>
            </div>
'''

text = text.replace('<canvas id="prChart"></canvas>\\n            </div>\\n        </div>', '<canvas id="prChart"></canvas>\\n            </div>\\n' + html_add + '        </div>')


js_add = '''
        // Kas Grubu (Pie Chart)
        const EXERCISE_MAP = {
            "bench_press": "Göğüs",
            "squat": "Bacak",
            "deadlift": "Sırt/Bel",
            "overhead_press": "Omuz",
            "barbell_row": "Sırt",
            "pullup": "Sırt",
            "bicep_curl": "Kol (Biceps)",
            "tricep_extension": "Kol (Triceps)",
            "leg_press": "Bacak",
            "lat_pulldown": "Sırt"
        };
        
        let muscleData = {};
        if (user.exercise_stats) {
            for (const [move, data] of Object.entries(user.exercise_stats)) {
                let muscle = EXERCISE_MAP[move] || "Diğer";
                if (!muscleData[muscle]) muscleData[muscle] = 0;
                muscleData[muscle] += data.volume;
            }
        }
        
        let mLabels = Object.keys(muscleData);
        let mValues = Object.values(muscleData);
        
        if(typeof muscleChartInst !== 'undefined' && muscleChartInst) muscleChartInst.destroy();
        window.muscleChartInst = new Chart(document.getElementById('muscleChart'), {
            type: 'pie',
            data: {
                labels: mLabels,
                datasets: [{
                    data: mValues,
                    backgroundColor: ['#ff6384', '#36a2eb', '#ffce56', '#4bc0c0', '#9966ff', '#ff9f40', '#8e44ad']
                }]
            },
            options: { responsive: true }
        });
'''

text = text.replace('// 3. KALORİ', js_add.strip() + '\\n\\n        // 3. KALORİ')

with open('Web/analiz.html', 'w', encoding='utf-8') as f:
    f.write(text)