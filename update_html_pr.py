import re

with open('Web/analiz.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Add a canvas for 1RM
html_add = '''
        <div class="charts-container double">
            <div class="chart-box">
                <h3>🏆 En İyi Kaldırışlar (Tahmini 1RM PR)</h3>
                <canvas id="prChart"></canvas>
            </div>
        </div>
        <br>
'''

# Find a good place to insert it
text = text.replace('<!-- charts container ends -->', html_add + '\\n<!-- charts container ends -->')
# wait, there's no such comment. Let's insert after measureChart div

insert_after = '''
            <div class="chart-box">
                <h3>📏 Vücut Ölçüleri ve Yağ Oranı</h3>
                <canvas id="measureChart"></canvas>
            </div>
        </div>
        
        <br>
'''

text = text.replace(insert_after.strip(), insert_after.strip() + '\\n' + html_add.strip())

# Add JS logic
js_add = '''
        // PR (1RM) Grafiği
        let prLabels = [];
        let prValues = [];
        if (user.pr_records) {
            for (const [move, max_w] of Object.entries(user.pr_records)) {
                prLabels.push(move.replace(/_/g, " ").toUpperCase());
                prValues.push(max_w);
            }
        }
        
        if(typeof prChartInst !== 'undefined' && prChartInst) prChartInst.destroy();
        window.prChartInst = new Chart(document.getElementById('prChart'), {
            type: 'bar',
            data: {
                labels: prLabels,
                datasets: [{
                    label: 'Maksimum 1RM Gücü (kg)',
                    data: prValues,
                    backgroundColor: '#ffd700',
                    borderWidth: 1
                }]
            },
            options: { responsive: true, indexAxis: 'y' }
        });
'''

text = text.replace('// 3. KALORİ', js_add.strip() + '\\n\\n        // 3. KALORİ')

with open('Web/analiz.html', 'w', encoding='utf-8') as f:
    f.write(text)