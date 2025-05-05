from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
import pdfplumber
import os

app = Flask(__name__)
CORS(app)

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
        # Processar com PyMuPDF
        temp_text = ''
        with fitz.open(stream=temp_pdf.read(), filetype="pdf") as doc:
            for page in doc:
                temp_text += page.get_text()

        # Processar com pdfplumber
        sm_text = ''
        sm_pdf.stream.seek(0)  # Resetar ponteiro
        with pdfplumber.open(sm_pdf.stream) as pdf:
            for page in pdf.pages:
                sm_text += page.extract_text() or ''

        # Gerar relatório simples
        resultado = f"""
### Relatório ColdChain

**Embarque:** {embarque}

#### Resumo do Relatório de Temperatura:
{temp_text.strip()[:1000] or 'Nenhum dado encontrado.'}

#### Resumo do SM:
{sm_text.strip()[:1000] or 'Nenhum dado encontrado.'}
"""

        return jsonify({'report_md': resultado.strip()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
