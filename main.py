from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
import pdfplumber
import os
from openai import OpenAI

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
    temp_pdf = request.files.get('temps')
    sm_pdf = request.files.get('sm')

    if not embarque or not temp_pdf or not sm_pdf:
        return jsonify({'error': 'Faltam dados no formulário'}), 400

    try:
        temp_text = ''
        with fitz.open(stream=temp_pdf.read(), filetype="pdf") as doc:
            for page in doc:
                temp_text += page.get_text()

        sm_text = ''
        sm_pdf.stream.seek(0)
        with pdfplumber.open(sm_pdf.stream) as pdf:
            for page in pdf.pages:
                sm_text += page.extract_text() or ''

        # Salvar contexto para chat posterior
        ultimo_embarque = embarque
        ultimo_temp_text = temp_text[:3000]
        ultimo_sm_text = sm_text[:3000]

        # Prompt inicial para o GPT entender faixas de temperatura
        faixa_prompt = f"""
A seguir estão dois relatórios de um embarque de cadeia fria.
Você é um analista técnico de cadeia fria. Gere um relatório executivo para o embarque abaixo com:
A seguir estão dois relatórios de um embarque de cadeia fria.
- Cabeçalho com Nome do Cliente, Origem e Destino (data/hora), se presentes no conteúdo.
Sua tarefa é identificar as faixas de temperatura controlada adotadas (ex: 2 a 8 °C) e nome dos sensores presentes:
- Identifique os sensores usados e as faixas de temperatura controlada adotadas.
- Breve resumo técnico da excursão de temperatura, se houver desvios.
- Pontos críticos encontrados.
- Sugestões de melhoria. Sua tarefa é identificar as faixas de temperatura controlada adotadas (ex: 2 a 8 °C) e nome dos sensores presentes:

RELATÓRIO DE TEMPERATURA:
{ultimo_temp_text}

RELATÓRIO SM:
{ultimo_sm_text}
"""
        faixa_resp = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Você é um analista técnico de cadeia fria."},
                {"role": "user", "content": faixa_prompt}
            ]
        )
        faixa_text = faixa_resp.choices[0].message.content.strip()

        # Tentativa de extração de dados tabulares com pdfplumber
        sm_pdf.stream.seek(0)
        sensor_data = {}
        timestamps = []
        with pdfplumber.open(temp_pdf.stream) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    headers = table[0]
                    if not headers or "sensor" not in str(headers).lower():
                        continue

                    for row in table[1:]:
                        if len(row) < 2:
                            continue
                        time_str = row[0]
                        if not time_str:
                            continue
                        timestamps.append(time_str.strip())
                        for idx, val in enumerate(row[1:], 1):
                            try:
                                t = float(val.strip().replace(',', '.'))
                            except:
                                continue
                            key = headers[idx].strip()
                            sensor_data.setdefault(key, []).append(t)

        # Determinar limites de temperatura a partir da faixa_text
        import re
        match = re.search(r'(\d+(?:\.\d+)?)\s*a\s*(\d+(?:\.\d+)?)', faixa_text)
        limite_min = float(match.group(1)) if match else 2.0
        limite_max = float(match.group(2)) if match else 8.0

        cores = ["#006400", "#00aa00", "#00cc44"]
        datasets = []
        for idx, (nome_sensor, temperaturas) in enumerate(sensor_data.items()):
            datasets.append({
                "label": nome_sensor,
                "data": temperaturas,
                "borderColor": cores[idx % len(cores)],
                "backgroundColor": "transparent",
                "pointBackgroundColor": ["red" if t < limite_min or t > limite_max else cores[idx % len(cores)] for t in temperaturas],
                "pointRadius": [6 if t < limite_min or t > limite_max else 3 for t in temperaturas],
                "pointStyle": "circle",
                "borderWidth": 2,
                "fill": False,
                "tension": 0.4
            })

        datasets.append({
            "label": f"Limite Máx ({limite_max}°C)",
            "data": [limite_max]*len(timestamps),
            "borderColor": "rgba(255,0,0,0.3)",
            "borderDash": [5, 5],
            "pointRadius": 0,
            "fill": False
        })

        datasets.append({
            "label": f"Limite Mín ({limite_min}°C)",
            "data": [limite_min]*len(timestamps),
            "borderColor": "rgba(0,0,255,0.3)",
            "borderDash": [5, 5],
            "pointRadius": 0,
            "fill": False
        })

        grafico = {
            "tipo": "line",
            "labels": timestamps,
            "datasets": datasets
        }

        # Gerar relatório final
        final_prompt = f"""
Com base nos relatórios a seguir, gere um relatório executivo para o cliente com:
- Cabeçalho com Nome, Origem, Destino, Datas.
- Resumo de excursões.
- Pontos Críticos.
- Sugestões de melhoria.

RELATÓRIO DE TEMPERATURA:
{ultimo_temp_text}

RELATÓRIO SM:
{ultimo_sm_text}
"""
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Você é um analista experiente em cadeia fria."},
                {"role": "user", "content": final_prompt}
            ]
        )

        gpt_response = response.choices[0].message.content.strip()

        return jsonify({
            'report_md': gpt_response,
            'grafico': grafico
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    global ultimo_embarque, ultimo_temp_text, ultimo_sm_text

    data = request.get_json()
    pergunta = data.get("pergunta")

    if not pergunta:
        return jsonify({"erro": "Pergunta não enviada."}), 400

    if not ultimo_embarque:
        return jsonify({"erro": "Nenhum embarque foi analisado ainda."}), 400

    try:
        contexto = f"""
Você está ajudando com o embarque: {ultimo_embarque}.
Use os dados abaixo para responder com precisão:

RELATÓRIO DE TEMPERATURA:
{ultimo_temp_text}

RELATÓRIO SM:
{ultimo_sm_text}
"""
        resposta = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Você é um especialista técnico em cadeia fria e transporte refrigerado."},
                {"role": "user", "content": contexto},
                {"role": "user", "content": pergunta}
            ]
        )
        mensagem = resposta.choices[0].message.content.strip()
        return jsonify({"resposta": mensagem})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
