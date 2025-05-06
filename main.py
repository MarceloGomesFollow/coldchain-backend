from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
import pdfplumber
import os
from openai import OpenAI

app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Variáveis globais temporárias (memória do último embarque)
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

    # Simular extração de temperaturas para o gráfico
# Em produção, extraia isso do PDF
temperaturas = [6, 7, 8.5, 9, 7, 5, 3, 1.5, 2, 6]  # Exemplo
labels = [f"{2*i} min" for i in range(len(temperaturas))]

# Separar cores por valor
datasets = [
    {
        "label": "Temperatura",
        "data": temperaturas,
        "borderColor": ["red" if t > 8 or t < 2 else "green" for t in temperaturas],
        "backgroundColor": "transparent",
        "pointBackgroundColor": ["red" if t > 8 or t < 2 else "green" for t in temperaturas],
        "tension": 0.4,
    },
    {
        "label": "Limite Máx (8°C)",
        "data": [8]*len(temperaturas),
        "borderColor": "rgba(255,0,0,0.3)",
        "borderDash": [5, 5],
        "pointRadius": 0,
        "fill": False
    },
    {
        "label": "Limite Mín (2°C)",
        "data": [2]*len(temperaturas),
        "borderColor": "rgba(0,0,255,0.3)",
        "borderDash": [5, 5],
        "pointRadius": 0,
        "fill": False
    }
]

grafico = {
    "tipo": "line",
    "labels": labels,
    "datasets": datasets
}

# Incluir no retorno
return jsonify({'report_md': resultado.strip(), 'grafico': grafico})

    if not embarque or not temp_pdf or not sm_pdf:
        return jsonify({'error': 'Faltam dados no formulário'}), 400

    try:
        # Leitura do relatório de temperatura
        temp_text = ''
        with fitz.open(stream=temp_pdf.read(), filetype="pdf") as doc:
            for page in doc:
                temp_text += page.get_text()

        # Leitura do SM
        sm_text = ''
        sm_pdf.stream.seek(0)
        with pdfplumber.open(sm_pdf.stream) as pdf:
            for page in pdf.pages:
                sm_text += page.extract_text() or ''

        # Armazena na memória para uso posterior no chat
        ultimo_embarque = embarque
        ultimo_temp_text = temp_text[:3000]  # limitar tamanho para o prompt
        ultimo_sm_text = sm_text[:3000]

        # Prompt para cabeçalho e análise executiva
        prompt = f"""
Você é um analista técnico de cadeia fria. Gere um relatório executivo para o embarque abaixo, com os seguintes tópicos:
1. Cabeçalho com Nome do Cliente, Origem e Destino (data/hora), se presentes no conteúdo.
2. Breve resumo técnico da excursão de temperatura, se houver desvios.
3. Pontos críticos encontrados.
4. Se possível, sugerir melhorias preventivas.

RELATÓRIO DE TEMPERATURA:
{ultimo_temp_text}

RELATÓRIO SM:
{ultimo_sm_text}
"""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Você é um analista técnico em transporte refrigerado."},
                {"role": "user", "content": prompt}
            ]
        )

        gpt_response = response.choices[0].message.content.strip()

        # Simulação de gráfico de temperatura
        grafico_data = {
            "tipo": "line",
            "labels": ["00h", "06h", "12h", "18h"],
            "datasets": [{
                "label": "Temperatura (°C)",
                "data": [2.5, 3.0, 4.1, 3.3],
                "borderColor": "#007bff",
                "fill": False
            }]
        }

        return jsonify({
            'report_md': gpt_response,
            'grafico': grafico_data
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
