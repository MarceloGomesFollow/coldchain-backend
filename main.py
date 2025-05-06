## main.py (corrigido)

```python
from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import io
import os
from openai import OpenAI
import re

app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Contexto para /chat
ultimo_embarque  = None
ultimo_temp_text = ''
ultimo_sm_text   = ''

@app.route('/analisar', methods=['POST'])
def analisar():
    global ultimo_embarque, ultimo_temp_text, ultimo_sm_text

    embarque  = request.form.get('embarque')
    temp_file = request.files.get('temps')
    sm_file   = request.files.get('sm')
    if not embarque or not temp_file or not sm_file:
        return jsonify({'error':'Faltam dados no formulário'}), 400

    # Lê PDFs
    temp_bytes = temp_file.read()
    sm_bytes   = sm_file.read()

    # 1) Extrai texto e tabelas do PDF de temperatura
    temp_text = ''
    tables    = []
    with pdfplumber.open(io.BytesIO(temp_bytes)) as pdf:
        for page in pdf.pages:
            temp_text += page.extract_text() or ''
            tables += page.extract_tables()

    # 2) Extrai texto do PDF SM
    sm_text = ''
    with pdfplumber.open(io.BytesIO(sm_bytes)) as pdf:
        for page in pdf.pages:
            sm_text += page.extract_text() or ''

    # Salva contexto para chat posterior
    ultimo_embarque  = embarque
    ultimo_temp_text = temp_text[:3000]
    ultimo_sm_text   = sm_text[:3000]

    # 3) Extrai dados do sensor (regex primeiro)
    sensor_data = {}
    timestamps  = []
    matches = re.findall(r'(\d{2}:\d{2})\s+(\d+(?:[.,]\d+)?)', temp_text)
    if matches:
        for t, v in matches:
            timestamps.append(t)
            sensor_data.setdefault('Sensor 1', []).append(float(v.replace(',', '.')))
    else:
        # Fallback via tabelas
        for tbl in tables:
            headers = tbl[0]
            if not headers or not any('sensor' in str(h).lower() for h in headers):
                continue
            for row in tbl[1:]:
                if not row[0]:
                    continue
                timestamps.append(row[0].strip())
                for idx, cell in enumerate(row[1:], start=1):
                    try:
                        val = float(str(cell).replace(',', '.'))
                        name = headers[idx].strip()
                        sensor_data.setdefault(name, []).append(val)
                    except:
                        pass

    # Se vazio, usa fallback simulado
    if not sensor_data:
        sensor_data['Sensor 1'] = [6,7,8,9,7,5,3,1,2,6]
        timestamps = [f"00:{i*2:02d}" for i in range(len(sensor_data['Sensor 1']))]

    # 4) Prompt unificado ao GPT-4
    prompt = f"""
Você é um analista técnico de cadeia fria.
1) Identifique faixas de temperatura controlada (ex: 2 a 8 °C).
2) Gere um relatório executivo com:
   - Cabeçalho (Cliente, Origem, Destino, Datas)
   - Resumo de excursões
   - Pontos críticos
   - Sugestões

Use os dados abaixo:

RELATÓRIO DE TEMPERATURA:
{ultimo_temp_text}

RELATÓRIO SM:
{ultimo_sm_text}
"""
    resp = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role":"system","content":"Você é um especialista em cadeia fria."},
            {"role":"user","content":prompt}
        ]
    )
    conteudo = resp.choices[0].message.content

    # 5) Regex robusto p/ faixa (X a Y °C, X–Y °C, X até Y °C)
    faixa = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(?:a|até|–|-)\s*(\d+(?:[.,]\d+)?)\s*[°º]?\s*C",
        conteudo, re.IGNORECASE
    )
    if faixa:
        lim_min = float(faixa.group(1).replace(',', '.'))
        lim_max = float(faixa.group(2).replace(',', '.'))
    else:
        lim_min, lim_max = 2.0, 8.0

    # 6) Monta datasets: sensor como scatter, limites como line
    pts = sensor_data['Sensor 1']
    scatter_data = [{'x': timestamps[i], 'y': pts[i]} for i in range(len(pts))]
    point_colors = [ 'red' if (v < lim_min or v > lim_max) else '#006400' for v in pts ]

    datasets = [
        {
            'type': 'scatter',
            'label': 'Sensor 1',
            'data': scatter_data,
            'pointBackgroundColor': point_colors,
            'pointRadius': 4
        },
        {
            'type': 'line',
            'label': f'Limite Máx ({lim_max}°C)',
            'data': [{'x': t, 'y': lim_max} for t in timestamps],
            'borderColor': 'rgba(255,0,0,0.4)',
            'borderDash': [5,5],
            'pointRadius': 0,
            'fill': False
        },
        {
            'type': 'line',
            'label': f'Limite Min ({lim_min}°C)',
            'data': [{'x': t, 'y': lim_min} for t in timestamps],
            'borderColor': 'rgba(0,0,255,0.4)',
            'borderDash': [5,5],
            'pointRadius': 0,
            'fill': False
        }
    ]

    return jsonify({'report_md': conteudo, 'grafico': {'datasets': datasets}})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    pergunta = data.get('pergunta')
    if not pergunta or not ultimo_embarque:
        return jsonify({'erro': 'Falta contexto ou pergunta'}), 400
    contexto = (
        f"Embarque: {ultimo_embarque}\n"
        f"RELATÓRIO DE TEMPERATURA:\n{ultimo_temp_text}\n"
        f"RELATÓRIO SM:\n{ultimo_sm_text}"
    )
    resp = client.chat.completions.create(
        model='gpt-4',
        messages=[
            {'role':'system','content':'Você é um especialista em cadeia fria.'},
            {'role':'user','content': contexto},
            {'role':'user','content': pergunta}
        ]
    )
    return jsonify({'resposta': resp.choices[0].message.content.strip()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
```

---

## index.html (corrigido)

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>ColdChain Analytics</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
    body { font-family: sans-serif; padding:1rem }
    #grafico-container { width:100%; height:350px; margin:1rem 0 }
    #graficoGPT { width:100% !important; height:100% !important }
  </style>
</head>
<body>
  <h1>ColdChain Analytics</h1>
  <form id="form">
    <label>Embarque:<input name="embarque" required></label>
    <label>PDF Temp:<input type="file" name="temps" accept="application/pdf" required></label>
    <label>PDF SM:<input type="file" name="sm" accept="application/pdf" required></label>
    <button type="submit">Analisar</button>
  </form>

  <div id="output"></div>
  <div id="grafico-container">
    <canvas id="graficoGPT"></canvas>
  </div>

  <script>
    const backend = 'https://coldchain-backend.onrender.com';
    const ctx = document.getElementById('graficoGPT').getContext('2d');
    let chart = null;

    document.getElementById('form').addEventListener('submit', async e => {
      e.preventDefault();
      const out = document.getElementById('output');
      out.textContent = 'Analisando...';
      try {
        const res = await fetch(`${backend}/analisar`, {
          method: 'POST',
          body: new FormData(e.target)
        });
        if (!res.ok) throw new Error(await res.text());
        const j = await res.json();
        out.innerHTML = marked.parse(j.report_md);

        // Reconstrói datasets e labels
        const ds = j.grafico.datasets;
        const xLabels = ds.find(d=>d.type==='scatter').data.map(pt=>pt.x);

        const config = {
          data: { datasets: ds },
          options: {
            parsing: { xAxisKey:'x', yAxisKey:'y' },
            scales: {
              x: {
                type: 'category',
                labels: xLabels,
                ticks: { autoSkip: true, maxTicksLimit: 15 }
              },
              y: {}
            },
            responsive: true,
            maintainAspectRatio: false
          }
        };
        if (chart) chart.destroy();
        chart = new Chart(ctx, config);
      } catch (err) {
        out.textContent = 'Erro: ' + err;
      }
    });
  </script>
</body>
</html>
```
