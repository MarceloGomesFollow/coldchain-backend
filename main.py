from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
import pdfplumber
import io
import os
from openai import OpenAI
import re

app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Memória temporária para chat
ultimo_embarque = None
ultimo_temp_text = ""
ultimo_sm_text = ""

@app.route('/')
def home():
    return 'Coldchain backend está no ar! 🚀'

@app.route('/analisar', methods=['POST'])
def analisar():
    global ultimo_embarque, ultimo_temp_text, ultimo_sm_text

    embarque = request.form.get('embarque')
    temp_file = request.files.get('temps')
    sm_file   = request.files.get('sm')

    if not embarque or not temp_file or not sm_file:
        return jsonify({'error': 'Faltam dados no formulário'}), 400

    # Ler bytes para reutilização
    temp_bytes = temp_file.read()
    sm_bytes   = sm_file.read()

    try:
        # Extrair texto do PDF de temperatura
        temp_text = ''
        with fitz.open(stream=temp_bytes, filetype="pdf") as doc:
            for page in doc:
                temp_text += page.get_text()

        # Extrair texto do PDF de SM
        sm_text = ''
        with pdfplumber.open(io.BytesIO(sm_bytes)) as pdf:
            for page in pdf.pages:
                sm_text += page.extract_text() or ""

        # Salvar contexto para chat posterior
        ultimo_embarque   = embarque
        ultimo_temp_text  = temp_text[:3000]
        ultimo_sm_text    = sm_text[:3000]

        # Prompt para identificar faixas de temperatura e sensores
        faixa_prompt = f"""
Você é um analista técnico de cadeia fria. Identifique faixas de temperatura controlada (ex: 2 a 8 °C) e liste sensores:

RELATÓRIO DE TEMPERATURA:
{ultimo_temp_text}

RELATÓRIO SM:
{ultimo_sm_text}
"""
        faixa_resp = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Você é um analista de cadeia fria."},
                {"role": "user",   "content": faixa_prompt}
            ]
        )
        faixa_text = faixa_resp.choices[0].message.content

        # Extrair limites via regex
        match = re.search(r"(\d+(?:\.\d+)?)\s*a\s*(\d+(?:\.\d+)?)", faixa_text)
        limite_min = float(match.group(1)) if match else 2.0
        limite_max = float(match.group(2)) if match else 8.0

        # Extrair dados dos sensores a partir de tabelas no PDF
        sensor_data = {}
        timestamps  = []
        with pdfplumber.open(io.BytesIO(temp_bytes)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    headers = table[0]
                    # Procura colunas que contenham "sensor"
                    if not headers or not any('sensor' in str(h).lower() for h in headers):
                        continue
                    # Processa cada linha da tabela
                    for row in table[1:]:
                        time_str = row[0]
                        if not time_str:
                            continue
                        timestamps.append(time_str.strip())
                        for idx, cell in enumerate(row[1:], start=1):
                            try:
                                val = float(str(cell).replace(",", "."))
                                name = headers[idx].strip()
                                sensor_data.setdefault(name, []).append(val)
                            except:
                                continue

        # Fallback simulado caso não encontre tabelas
        if not sensor_data:
            sensor_data = {
                'Sensor 1': [6,7,8,9,7,5,3,1,2,6]
            }
            timestamps = [f"00:{i*2:02d}" for i in range(len(sensor_data['Sensor 1']))]

        # Montar datasets do gráfico
        cores = ['#006400','#00aa00','#00cc44']
        datasets = []
        for idx, (name, temps) in enumerate(sensor_data.items()):
            datasets.append({
                'label': name,
                'data': temps,
                'borderColor': cores[idx % len(cores)],
                'backgroundColor': 'transparent',
                'pointBackgroundColor': [
                    'red' if t < limite_min or t > limite_max else cores[idx % len(cores)]
                    for t in temps
                ],
                'pointRadius': [
                    6 if t < limite_min or t > limite_max else 3
                    for t in temps
                ],
                'borderWidth': 2,
                'fill': False,
                'tension': 0.4
            })

        # Linhas de limite
        datasets += [
            {
                'label': f"Limite Máx ({limite_max}°C)",
                'data': [limite_max] * len(timestamps),
                'borderColor': 'rgba(255,0,0,0.3)',
                'borderDash': [5,5],
                'pointRadius': 0,
                'fill': False
            },
            {
                'label': f"Limite Mín ({limite_min}°C)",
                'data': [limite_min] * len(timestamps),
                'borderColor': 'rgba(0,0,255,0.3)',
                'borderDash': [5,5],
                'pointRadius': 0,
                'fill': False
            }
        ]

        grafico = {
            'tipo':   'line',
            'labels': timestamps,
            'datasets': datasets
        }

        # Prompt final para gerar relatório
        final_prompt = f"""
Gere relatório executivo com:
- Cabeçalho (Cliente, Origem, Destino, Datas)
- Resumo de excursões
- Pontos críticos
- Sugestões

RELATÓRIO DE TEMPERATURA:
{ultimo_temp_text}

RELATÓRIO SM:
{ultimo_sm_text}
"""
        final_resp = client.chat.completions.create(
            model='gpt-4',
            messages=[
                {'role': 'system', 'content':'Você é um analista experiente em cadeia fria.'},
                {'role': 'user',   'content': final_prompt}
            ]
        )
        report_md = final_resp.choices[0].message.content

        return jsonify({'report_md': report_md, 'grafico': grafico})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    global ultimo_embarque, ultimo_temp_text, ultimo_sm_text
    data = request.get_json()
    pergunta = data.get('pergunta')
    if not pergunta:
        return jsonify({'erro': 'Pergunta não enviada.'}), 400
    if not ultimo_embarque:
        return jsonify({'erro': 'Nenhum embarque analisado.'}), 400
    try:
        contexto = f"""Você está ajudando com o embarque: {ultimo_embarque}.
Use os dados abaixo:
RELATÓRIO DE TEMPERATURA:
{ultimo_temp_text}

RELATÓRIO SM:
{ultimo_sm_text}"""
        resp = client.chat.completions.create(
            model='gpt-4',
            messages=[
                {'role':'system','content':'Você é um especialista em cadeia fria.'},
                {'role':'user',  'content': contexto},
                {'role':'user',  'content': pergunta}
            ]
        )
        return jsonify({'resposta': resp.choices[0].message.content.strip()})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
