from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
import pdfplumber
import os
from openai import OpenAI

app = Flask(__name__)
CORS(app)

# Cliente da API OpenAI com nova sintaxe
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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
        # Extrair texto dos PDFs
        temp_text = ''
        with fitz.open(stream=temp_pdf.read(), filetype="pdf") as doc:
            for page in doc:
                temp_text += page.get_text()

        sm_text = ''
        sm_pdf.stream.seek(0)
        with pdfplumber.open(sm_pdf.stream) as pdf:
            for page in pdf.pages:
                sm_text += page.extract_text() or ''

        # Preparar prompt para GPT
        prompt = f"""
A seguir estão trechos de dois relatórios em PDF para o embarque '{embarque}'. Gere um resumo técnico com foco em desvios de temperatura e pontos críticos:

RELATÓRIO DE TEMPERATURA:
{temp_text[:2000]}

RELATÓRIO SM:
{sm_text[:2000]}
"""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Você é um analista técnico de cadeia fria."},
                {"role": "user", "content": prompt}
            ]
        )

        gpt_response = response.choices[0].message.content

        resultado = f"""
### Relatório ColdChain

**Embarque:** {embarque}

#### Resumo do Relatório de Temperatura:
{temp_text.strip()[:1000] or 'Nenhum dado encontrado.'}

#### Resumo do SM:
{sm_text.strip()[:1000] or 'Nenhum dado encontrado.'}

#### Análise da IA:
{gpt_response}
"""
        return jsonify({'report_md': resultado.strip()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    pergunta = data.get("pergunta")

    if not pergunta:
        return jsonify({"erro": "Pergunta não enviada."}), 400

    try:
        resposta = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Você é um especialista em cadeia fria e logística de temperatura."},
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
