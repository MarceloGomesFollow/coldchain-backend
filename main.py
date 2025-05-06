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
        # Leitura do PDF de temperatura
        temp_text = ''
        with fitz.open(stream=temp_pdf.read(), filetype="pdf") as doc:
            for page in doc:
                temp_text += page.get_text()

        # Leitura do PDF do SM
        sm_text = ''
        sm_pdf.stream.seek(0)
        with pdfplumber.open(sm_pdf.stream) as pdf:
            for page in pdf.pages:
                sm_text += page.extract_text() or ''

        # Salvar para o chat
        ultimo_embarque = embarque
        ultimo_temp_text = temp_text[:3000]
        ultimo_sm_text = sm_text[:3000]

        # Enviar prompt para GPT
        prompt = f"""
Você é um analista técnico de cadeia fria. Gere um relatório executivo para o embarque abaixo com:
- Cabeçalho com Nome do Cliente, Origem e Destino (data/hora), se presentes no conteúdo.
- Breve resumo técnico da excursão de temperatura, se houver desvios.
- Pontos críticos encontrados.
- Sugestões de melhoria.

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

        # Exemplo de gráfico com temperatura
        temperaturas = [6, 7, 8.5, 9, 7, 5, 3, 1.5, 2, 6]
        labels = [f"{2*i} min" for i in range(len(temperaturas))]

        datasets = [
            {
                "label": "Temperatura",
                "data": temperaturas,
                "borderColor": ["red" if t > 8 or t < 2 else "green" for t in temperaturas],
                "backgroundColor": "transparent",
                "pointBackgroundColor": ["red" if t > 8 or t < 2 else "green" for t in temperaturas],
                "tension": 0.4
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
