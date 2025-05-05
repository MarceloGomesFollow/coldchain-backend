from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
import pdfplumber
import openai
import os

# Inicializa Flask e CORS
app = Flask(__name__)
CORS(app)

# Define a chave da OpenAI (vinda do Render)
openai.api_key = os.environ.get("OPENAI_API_KEY")

@app.route('/')
def home():
    return 'Coldchain backend está no ar! 🚀'

@app.route('/analisar', methods=['POST'])
def analisar():
    embarque = request.form.get('embarque')
    temp_pdf = request.files.get('temps')
    sm_pdf = request.files.get('sm')

    if not embarque or not temp_pdf or not sm_pdf:
        return jsonify({'error': 'Faltam dados no formulário'}), 400

    try:
        # Processar PDF de temperatura com PyMuPDF
        temp_text = ''
        with fitz.open(stream=temp_pdf.read(), filetype="pdf") as doc:
            for page in doc:
                temp_text += page.get_text()

        # Processar PDF de SM com pdfplumber
        sm_text = ''
        sm_pdf.stream.seek(0)
        with pdfplumber.open(sm_pdf.stream) as pdf:
            for page in pdf.pages:
                sm_text += page.extract_text() or ''

        # Prompt para GPT
        prompt = f"""
Você é um especialista em cadeia fria e compliance regulatório.

Analise os seguintes documentos de um embarque:

**1. Relatório de Temperatura:**
{temp_text.strip()[:3000] or 'Sem dados'}

**2. SM - Solicitação de Monitoramento (rastreamento e horários):**
{sm_text.strip()[:3000] or 'Sem dados'}

Com base nessas informações, responda de forma técnica e objetiva:
- Houve alguma excursão de temperatura?
- Os horários e paradas indicam risco para o produto?
- Existe algum indício de não conformidade?
- Qual recomendação para a área da qualidade?

Responda como um parecer técnico com até 1000 palavras.
"""

        # Chamada ao GPT
        resposta = openai.ChatCompletion.create(
            model="gpt-4",  # ou "gpt-3.5-turbo" se preferir
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        gpt_output = resposta['choices'][0]['message']['content']

        return jsonify({
            'embarque': embarque,
            'report_md': gpt_output
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
