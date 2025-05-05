from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
import pdfplumber
import os
import re
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


@app.route('/analisar', methods=['POST'])
def analisar():
    global ultimo_embarque, ultimo_temp_text, ultimo_sm_text

    embarque = request.form.get('embarque')
    temp_pdf = request.files.get('temps')
    sm_pdf = request.files.get('sm')

    if not embarque or not temp_pdf or not sm_pdf:
        return jsonify({'error': 'Faltam dados no formulário'}), 400

    try:
        # Leitura dos PDFs
        temp_text = ''
        with fitz.open(stream=temp_pdf.read(), filetype="pdf") as doc:
            for page in doc:
                temp_text += page.get_text()

        sm_text = ''
        sm_pdf.stream.seek(0)
        with pdfplumber.open(sm_pdf.stream) as pdf:
            for page in pdf.pages:
                sm_text += page.extract_text() or ''

        # Salva em memória
        ultimo_embarque = embarque
        ultimo_temp_text = temp_text[:3000]
        ultimo_sm_text = sm_text[:3000]

        # 🧠 Análise GPT
        prompt = f"""
Você é um analista de cadeia fria. Gere um resumo técnico com foco em desvios de temperatura.

RELATÓRIO DE TEMPERATURA:
{ultimo_temp_text}

RELATÓRIO SM:
{ultimo_sm_text}
"""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Você é um analista técnico de cadeia fria."},
                {"role": "user", "content": prompt}
            ]
        )

        gpt_response = response.choices[0].message.content.strip()

        # 🔍 Regex para extrair temperaturas com horário (ex: "08:00 - 2.3°C")
        matches = re.findall(r'(\d{2}[:h]\d{2}).*?([-+]?\d{1,2}[.,]?\d{0,2}) ?°?C', temp_text)
        labels = []
        valores = []

        for hora, temp in matches:
            labels.append(hora.replace("h", ":"))
            valores.append(float(temp.replace(",", ".")))

        grafico_json = {
            "grafico": {
                "tipo": "line",
                "labels": labels,
                "datasets": [{
                    "label": "Temperatura (°C)",
                    "data": valores,
                    "borderColor": "rgba(75,192,192,1)",
                    "fill": False
                }]
            }
        } if labels and valores else {}

        resultado = f"""
### Relatório ColdChain

**Embarque:** {embarque}

#### Resumo do Relatório de Temperatura:
{ultimo_temp_text[:1000] or 'Nenhum dado encontrado.'}

#### Resumo do SM:
{ultimo_sm_text[:1000] or 'Nenhum dado encontrado.'}

#### Análise da IA:
{gpt_response}
"""

        return jsonify({'report_md': resultado.strip(), **grafico_json})

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
