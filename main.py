from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz   # PyMuPDF
import pdfplumber
import os
import re
from openai import OpenAI

app = Flask(__name__)
CORS(app)

# Configura cliente OpenAI
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Memória temporária para chat
ultimo_embarque   = None
ultimo_temp_text  = ""
ultimo_sm_text    = ""

@app.route('/health', methods=['GET'])
def health():
    return jsonify(status="ok"), 200

@app.route('/')
def home():
    return 'Coldchain backend está no ar! 🚀'

@app.route('/analisar', methods=['POST'])
def analisar():
    global ultimo_embarque, ultimo_temp_text, ultimo_sm_text

    embarque    = request.form.get('embarque')
    temp_pdf    = request.files.get('relatorio_temp')      # <-- corrigido
    sm_pdf      = request.files.get('solicitacao_sm')      # <-- corrigido

    if not embarque or not temp_pdf or not sm_pdf:
        return jsonify({'error': 'Faltam dados no formulário'}), 400

    try:
        # 1) Extrai textos brutos dos PDFs
        temp_text = ""
        with fitz.open(stream=temp_pdf.read(), filetype="pdf") as doc:
            for page in doc:
                temp_text += page.get_text()

        sm_pdf.stream.seek(0)
        sm_text = ""
        with pdfplumber.open(sm_pdf.stream) as pdf:
            for page in pdf.pages:
                sm_text += page.extract_text() or ""

        # 2) Armazena para contexto de chat
        ultimo_embarque  = embarque
        ultimo_temp_text = temp_text[:3000]
        ultimo_sm_text   = sm_text[:3000]

        # 3) Prompt para detectar faixas e sensores
        faixa_prompt = f"""
Você é um analista técnico de cadeia fria. A partir dos textos abaixo, identifique:
- Nome do Cliente, Origem, Destino (data/hora), se houver;
- Sensores usados e faixas controladas (ex: 2 a 8°C).

RELATÓRIO DE TEMPERATURA:
{ultimo_temp_text}

RELATÓRIO SM:
{ultimo_sm_text}
"""
        faixa_resp = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role":"system","content":"Você é um analista técnico de cadeia fria."},
                {"role":"user",  "content":faixa_prompt}
            ]
        )
        faixa_text = faixa_resp.choices[0].message.content.strip()

        # 4) Extrai dados tabulares para o gráfico
        temp_pdf.stream.seek(0)
        sm_pdf.stream.seek(0)
        sensor_data = {}
        timestamps  = []
        with pdfplumber.open(temp_pdf.stream) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    headers = table[0]
                    if not headers or "sensor" not in str(headers).lower():
                        continue
                    for row in table[1:]:
                        time_str = row[0]
                        if not time_str:
                            continue
                        timestamps.append(time_str.strip())
                        for idx, val in enumerate(row[1:], start=1):
                            try:
                                t = float(val.strip().replace(",", "."))
                            except:
                                continue
                            key = headers[idx].strip()
                            sensor_data.setdefault(key, []).append(t)

        # 5) Detecta limites via regex no texto de faixa
        match = re.search(r'(\d+(?:\.\d+)?)\s*a\s*(\d+(?:\.\d+)?)', faixa_text)
        limite_min = float(match.group(1)) if match else 2.0
        limite_max = float(match.group(2)) if match else 8.0

        # 6) Monta os datasets do Chart.js
        cores = ["#006400","#00aa00","#00cc44"]
        datasets = []
        for i, (sensor, vals) in enumerate(sensor_data.items()):
            datasets.append({
                "label": sensor,
                "data": vals,
                "borderColor": cores[i % len(cores)],
                "backgroundColor": "transparent",
                "pointBackgroundColor": [
                    "red" if v < limite_min or v > limite_max else cores[i % len(cores)]
                    for v in vals
                ],
                "pointRadius": [
                    6 if v < limite_min or v > limite_max else 3
                    for v in vals
                ],
                "borderWidth": 2,
                "fill": False,
                "tension": 0.4
            })

        # linhas de limite mínimo e máximo
        datasets.append({
            "label": f"Limite Máx ({limite_max}°C)",
            "data": [limite_max] * len(timestamps),
            "borderColor": "rgba(255,0,0,0.3)",
            "borderDash": [5,5],
            "pointRadius": 0,
            "fill": False
        })
        datasets.append({
            "label": f"Limite Mín ({limite_min}°C)",
            "data": [limite_min] * len(timestamps),
            "borderColor": "rgba(0,0,255,0.3)",
            "borderDash": [5,5],
            "pointRadius": 0,
            "fill": False
        })

        grafico = {
+           "tipo": "line",
+           "labels": timestamps,
+           "datasets": datasets,
+           # envia para o front qual o limite mínimo e máximo de temperatura
+           "yMin": limite_min,
+           "yMax": limite_max
        }

        # 7) Prompt final para gerar o markdown executivo
        final_prompt = f"""
Com base nos relatórios abaixo, gere um relatório executivo abordando:
- Cabeçalho (Cliente, Origem, Destino, Datas)
- Resumo de excursão de temperatura
- Pontos críticos
- Sugestões de melhoria

RELATÓRIO DE TEMPERATURA:
{ultimo_temp_text}

RELATÓRIO SM:
{ultimo_sm_text}
"""
        exec_resp = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role":"system","content":"Você é um analista experiente em cadeia fria."},
                {"role":"user",  "content":final_prompt}
            ]
        )
        report_md = exec_resp.choices[0].message.content.strip()

        return jsonify(report_md=report_md, grafico=grafico)

    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route('/chat', methods=['POST'])
def chat():
    global ultimo_embarque, ultimo_temp_text, ultimo_sm_text

    data     = request.get_json()
    pergunta = data.get("pergunta")
    if not pergunta:
        return jsonify(erro="Pergunta não enviada."), 400
    if not ultimo_embarque:
        return jsonify(erro="Nenhum embarque analisado."), 400

    contexto = f"""
Você está ajudando com o embarque: {ultimo_embarque}.
Use estes dados:

RELATÓRIO DE TEMPERATURA:
{ultimo_temp_text}

RELATÓRIO SM:
{ultimo_sm_text}
"""
    try:
        resp = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role":"system","content":"Você é um especialista em cadeia fria."},
                {"role":"user",  "content":contexto},
                {"role":"user",  "content":pergunta}
            ]
        )
        return jsonify(resposta=resp.choices[0].message.content.strip())
    except Exception as e:
        return jsonify(erro=str(e)), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
