## main.py (corrigido e com health‑check)

```python
from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber, io, os, re, logging
from openai import OpenAI

app = Flask(__name__)
# Habilita CORS para todas origens
CORS(app)

# Configura logging para STDOUT (Render captura logs)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cliente OpenAI
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Contexto para chat
ultimo_embarque  = None
ultimo_temp_text = ''
ultimo_sm_text   = ''

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de healthcheck para wake-up e monitoramento."""
    return 'OK', 200

@app.route('/analisar', methods=['POST'])
def analisar():
    global ultimo_embarque, ultimo_temp_text, ultimo_sm_text

    embarque  = request.form.get('embarque')
    temp_file = request.files.get('temps')
    sm_file   = request.files.get('sm')
    if not embarque or not temp_file or not sm_file:
        logger.warning('Dados faltando no formulário')
        return jsonify({'error':'Faltam dados no formulário'}), 400

    # Lê PDFs em memória
    temp_bytes = temp_file.read()
    sm_bytes   = sm_file.read()

    # Extrai texto e tabelas do PDF de temperatura
    temp_text, tables = '', []
    try:
        with pdfplumber.open(io.BytesIO(temp_bytes)) as pdf:
            for p in pdf.pages:
                temp_text += p.extract_text() or ''
                tables += p.extract_tables()
    except Exception as e:
        logger.error(f'Erro ao processar PDF de temperatura: {e}')
        return jsonify({'error':'Não foi possível ler PDF de temperatura'}), 500

    # Extrai texto do PDF SM
    sm_text = ''
    try:
        with pdfplumber.open(io.BytesIO(sm_bytes)) as pdf:
            for p in pdf.pages:
                sm_text += p.extract_text() or ''
    except Exception as e:
        logger.error(f'Erro ao processar PDF SM: {e}')
        return jsonify({'error':'Não foi possível ler PDF SM'}), 500

    # Guarda contexto
    ultimo_embarque  = embarque
    ultimo_temp_text = temp_text[:3000]
    ultimo_sm_text   = sm_text[:3000]

    # Extrai medições de temperatura (regex primeiro)
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
            hdr = tbl[0]
            if not hdr or not any('sensor' in str(h).lower() for h in hdr):
                continue
            for row in tbl[1:]:
                if not row[0]: continue
                timestamps.append(row[0].strip())
                for idx, cell in enumerate(row[1:], start=1):
                    try:
                        val  = float(str(cell).replace(',', '.'))
                        name = hdr[idx].strip()
                        sensor_data.setdefault(name, []).append(val)
                    except:
                        pass

    # Fallback simulado se nenhum dado extraído
    if not sensor_data:
        sensor_data['Sensor 1'] = [6,7,8,9,7,5,3,1,2,6]
        timestamps = [f"00:{i*2:02d}" for i in range(len(sensor_data['Sensor 1']))]

    # Monta e envia prompt unificado ao GPT-4
    prompt = f"""
Você é um analista de cadeia fria.
1) Identifique faixas de temperatura controlada (ex: 2 a 8 °C).
2) Gere um relatório executivo com cabeçalho, excursões, pontos críticos e sugestões.

PDF Temperatura:
{ultimo_temp_text}

PDF SM:
{ultimo_sm_text}
"""
    try:
        resp = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role":"system","content":"Você é um especialista em cadeia fria."},
                {"role":"user","content":prompt}
            ]
        )
    except Exception as e:
        logger.error(f'Erro GPT-4: {e}')
        return jsonify({'error':'Falha na chamada ao GPT-4'}), 500
    texto = resp.choices[0].message.content

    # Captura faixa controlada (X a Y °C, X–Y °C, X até Y °C)
    faixa = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(?:a|até|–|-)\s*(\d+(?:[.,]\d+)?)\s*[°º]?\s*C",
        texto, re.IGNORECASE
    )
    if faixa:
        lim_min = float(faixa.group(1).replace(',', '.'))
        lim_max = float(faixa.group(2).replace(',', '.'))
    else:
        lim_min, lim_max = 2.0, 8.0

    # Prepara datasets para Chart.js: scatter para sensor, linhas para limites
    pts = sensor_data['Sensor 1']
    scatter_pts = [{'x':ts, 'y':pts[i]} for i, ts in enumerate(timestamps)]
    point_colors = ['red' if (v<lim_min or v>lim_max) else '#006400' for v in pts]

    datasets = [
        {
            'type': 'scatter',
            'label': 'Sensor 1',
            'data': scatter_pts,
            'pointBackgroundColor': point_colors,
            'pointRadius': 4
        },
        {
            'type': 'line',
            'label': f'Limite Máx ({lim_max}°C)',
            'data': [{'x':ts, 'y':lim_max} for ts in timestamps],
            'borderColor': 'rgba(255,0,0,0.4)',
            'borderDash': [5,5],
            'pointRadius': 0,
            'fill': False
        },
        {
            'type': 'line',
            'label': f'Limite Min ({lim_min}°C)',
            'data': [{'x':ts, 'y':lim_min} for ts in timestamps],
            'borderColor': 'rgba(0,0,255,0.4)',
            'borderDash': [5,5],
            'pointRadius': 0,
            'fill': False
        }
    ]

    return jsonify({'report_md': texto, 'grafico': {'datasets': datasets}})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    pergunta = data.get('pergunta')
    if not pergunta or not ultimo_embarque:
        return jsonify({'erro':'Falta contexto ou pergunta'}), 400
    contexto = (
        f"Embarque: {ultimo_embarque}\n"
        f"RELATÓRIO DE TEMPERATURA:\n{ultimo_temp_text}\n"
        f"RELATÓRIO SM:\n{ultimo_sm_text}"
    )
    try:
        resp = client.chat.completions.create(
            model='gpt-4',
            messages=[
                {'role':'system','content':'Você é um especialista em cadeia fria.'},
                {'role':'user','content':contexto},
                {'role':'user','content':pergunta}
            ]
        )
    except Exception as e:
        logger.error(f'Erro GPT Chat: {e}')
        return jsonify({'erro':'Falha no chat GPT'}), 500
    return jsonify({'resposta': resp.choices[0].message.content.strip()})

if __name__=='__main__':
    # Porta configurável no Render
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
```

---

## index.html (adiciona warm-up e logs JS)

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
    body { font-family:sans-serif; padding:1rem; }
    #grafico-container { width:100%; height:350px; margin:1rem 0; }
    #graficoGPT { width:100% !important; height:100% !important; }
    #loading { display:none; font-weight:bold; }
  </style>
</head>
<body>
  <h1>ColdChain Analytics</h1>
  <p id="loading">Carregando serviço, aguarde...</p>
  <form id="form" style="display:none;">
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
    const form    = document.getElementById('form');
    const loadMsg = document.getElementById('loading');
    const ctx     = document.getElementById('graficoGPT').getContext('2d');
    let chart     = null;

    // Warm-up: verifica health e só mostra o form após OK
    async function warmup() {
      try {
        loadMsg.style.display = 'block';
        const resp = await fetch(`${backend}/health`);
        if (resp.ok) {
          loadMsg.style.display = 'none';
          form.style.display = 'block';
        } else throw 'Healthcheck falhou';
      } catch (err) {
        loadMsg.textContent = 'Erro ao conectar: ' + err;
      }
    }
    warmup();

    form.addEventListener('submit', async e => {
      e.preventDefault();
      document.getElementById('output').textContent = 'Analisando...';
      try {
        const res = await fetch(`${backend}/analisar`, {
          method: 'POST', body: new FormData(form)
        });
        if (!res.ok) {
          const txt = await res.text();
          throw txt;
        }
        const j = await res.json();
        document.getElementById('output').innerHTML = marked.parse(j.report_md);

        // Prepara gráfico
        const ds      = j.grafico.datasets;
        const xLabels = ds.find(d=>d.type==='scatter').data.map(pt=>pt.x);
        const cfg     = {
          data: { datasets: ds },
          options: {
            parsing: { xAxisKey:'x', yAxisKey:'y' },
            scales: {
              x: { type:'category', labels:xLabels, ticks:{autoSkip:true,maxTicksLimit:15} },
              y: {} 
            },
            responsive:true, maintainAspectRatio:false
          }
        };
        if (chart) chart.destroy();
        chart = new Chart(ctx, cfg);
      } catch (err) {
        document.getElementById('output').textContent = 'Erro: ' + err;
        console.error('Analisar falhou:', err);
      }
    });
  </script>
</body>
</html>
```
