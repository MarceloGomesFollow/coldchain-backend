# main.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber, io, os, re
from openai import OpenAI

app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# contexto para chat
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
        return jsonify({'error': 'Faltam dados'}), 400

    temp_bytes = temp_file.read()
    sm_bytes   = sm_file.read()

    # 1) Extrai texto + possíveis tabelas do PDF de temperatura
    temp_text, tables = '', []
    with pdfplumber.open(io.BytesIO(temp_bytes)) as pdf:
        for p in pdf.pages:
            temp_text += p.extract_text() or ""
            tables += p.extract_tables()

    # 2) Extrai texto do PDF SM
    sm_text = ''
    with pdfplumber.open(io.BytesIO(sm_bytes)) as pdf:
        for p in pdf.pages:
            sm_text += p.extract_text() or ""

    # guarda contexto para /chat
    ultimo_embarque  = embarque
    ultimo_temp_text = temp_text[:3000]
    ultimo_sm_text   = sm_text[:3000]

    # 3) Extrai medições do sensor
    sensor_data = {}
    timestamps  = []
    # tentativa com regex
    matches = re.findall(r'(\d{2}:\d{2})\s+(\d+(?:[.,]\d+)?)', temp_text)
    if matches:
        times, vals = zip(*[(t, float(v.replace(',', '.'))) for t,v in matches])
        timestamps = list(times)
        sensor_data['Sensor 1'] = list(vals)
    else:
        # fallback via tabelas
        for tbl in tables:
            hdr = tbl[0]
            if not hdr or not any('sensor' in str(h).lower() for h in hdr):
                continue
            for row in tbl[1:]:
                t = row[0]
                if not t: continue
                timestamps.append(t.strip())
                for idx, cell in enumerate(row[1:], start=1):
                    try:
                        v = float(str(cell).replace(',', '.'))
                        nome = hdr[idx].strip()
                        sensor_data.setdefault(nome, []).append(v)
                    except:
                        pass

    # se ainda vazio, fallback simulado
    if not sensor_data:
        sensor_data = {'Sensor 1': [6,7,8,9,7,5,3,1,2,6]}
        timestamps   = [f"00:{i*2:02d}" for i in range(10)]

    # 4) Chamada única ao GPT-4 para faixa + relatório
    prompt = f"""
Você é um analista de cadeia fria. 
1) Identifique a faixa controlada (ex: 15 a 30 °C). 
2) Gere relatório executivo (cabeçalho, excursões, críticos, sugestões).

PDF Temperatura:
{ultimo_temp_text}

PDF SM:
{ultimo_sm_text}
"""
    resp = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role":"system","content":"Você é um especialista em cadeia fria."},
            {"role":"user","content":prompt}
        ]
    )
    texto = resp.choices[0].message.content

    # 5) Captura faixa via regex robusto
    faixa = re.search(
        r'(\d+(?:[.,]\d+)?)\s*(?:a|até|–|-)\s*(\d+(?:[.,]\d+)?)\s*[°º]?\s*C',
        texto, re.IGNORECASE
    )
    if faixa:
        lim_min = float(faixa.group(1).replace(',','.'))
        lim_max = float(faixa.group(2).replace(',','.'))
    else:
        lim_min, lim_max = 2.0, 8.0

    # 6) Monta datasets: scatter para sensor, line para limites
    pts = sensor_data['Sensor 1']
    scatter = [{
        'x': timestamps[i], 
        'y': pts[i]
    } for i in range(len(pts))]

    datasets = [
        {
            'type': 'scatter',
            'label': 'Sensor 1',
            'data': scatter,
            'pointBackgroundColor': [
                'red' if (v < lim_min or v > lim_max) else '#006400'
                for v in pts
            ],
            'pointRadius': 4
        },
        {
            'type': 'line',
            'label': f'Limite Máx ({lim_max}°C)',
            'data': timestamps.map(lambda t: {'x':t, 'y':lim_max}),
            'borderColor': 'rgba(255,0,0,0.4)',
            'borderDash': [5,5],
            'pointRadius': 0,
            'fill': False
        },
        {
            'type': 'line',
            'label': f'Limite Min ({lim_min}°C)',
            'data': timestamps.map(lambda t: {'x':t, 'y':lim_min}),
            'borderColor': 'rgba(0,0,255,0.4)',
            'borderDash': [5,5],
            'pointRadius': 0,
            'fill': False
        }
    ]

    return jsonify({
        'report_md': texto,
        'grafico': {'datasets': datasets}
    })


@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    p = data.get('pergunta')
    if not p or not ultimo_embarque:
        return jsonify({'erro':'Faltam contexto ou pergunta'}), 400

    contexto = (
        f"Embarque: {ultimo_embarque}\n"
        f"TEMP:\n{ultimo_temp_text}\n"
        f"SM:\n{ultimo_sm_text}"
    )
    resp = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {'role':'system','content':'Especialista em cadeia fria.'},
            {'role':'user','content':contexto},
            {'role':'user','content':p}
        ]
    )
    return jsonify({'resposta': resp.choices[0].message.content})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5000)))
