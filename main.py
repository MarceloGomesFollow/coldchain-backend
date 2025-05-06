from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import io
import os
import re
import logging
from openai import OpenAI
from werkzeug.exceptions import HTTPException

# --- App setup ---
app = Flask(__name__)
CORS(app)  # Permitir chamadas de qualquer origem

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- OpenAI client ---
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# --- Global context for chat ---
ultimo_embarque  = None
ultimo_temp_text = ''
ultimo_sm_text   = ''

# --- Routes ---

@app.route('/', methods=['GET', 'HEAD'])
def root():
    # Rota raiz para satisfazer health checks (GET e HEAD)
    return jsonify({'status': 'running'}), 200

@app.route('/health', methods=['GET'])
def health():
    """Healthcheck para wake-up e monitoramento."""
    return jsonify({'status': 'ok'}), 200

@app.route('/analisar', methods=['POST'])
def analisar():
    global ultimo_embarque, ultimo_temp_text, ultimo_sm_text

    # 1) Validação dos arquivos
    embarque  = request.form.get('embarque')
    temp_file = request.files.get('temps')
    sm_file   = request.files.get('sm')
    if not embarque or not temp_file or not sm_file:
        return jsonify({'error': 'Faltam dados no formulário'}), 400

    # 2) Leitura dos PDFs
    temp_bytes = temp_file.read()
    sm_bytes   = sm_file.read()

    # 3) Extração de texto e tabelas do PDF de temperatura
    temp_text, tables = '', []
    with pdfplumber.open(io.BytesIO(temp_bytes), strict=False) as pdf:
        for page in pdf.pages:
            temp_text += page.extract_text() or ''
            tables += page.extract_tables()

    # 4) Extração de texto do PDF SM
    sm_text = ''
    with pdfplumber.open(io.BytesIO(sm_bytes), strict=False) as pdf:
        for page in pdf.pages:
            sm_text += page.extract_text() or ''

    # 5) Armazena contexto para o endpoint /chat
    ultimo_embarque  = embarque
    ultimo_temp_text = temp_text
    ultimo_sm_text   = sm_text

    # 6) Extrai medições de temperatura via regex
    pts = re.findall(r'(\d{2}:\d{2})\s+(\d+(?:[.,]\d+)?)', temp_text)
    labels = [t for t, _ in pts]
    values = [float(v.replace(',', '.')) for _, v in pts]

    # 7) Captura faixa de temperatura controlada no texto SM
    m = re.search(
        r'[Ff]aixa.*?(\d+(?:[.,]\d+)?)°?C.*?(\d+(?:[.,]\d+)?)°?C',
        sm_text,
        flags=re.DOTALL
    )
    if m:
        lim_min = float(m.group(1).replace(',', '.'))
        lim_max = float(m.group(2).replace(',', '.'))
    else:
        lim_min, lim_max = 2.0, 8.0  # fallback

    # 8) Prepara datasets para Chart.js
    scatter_data = [{'x': lbl, 'y': val} for lbl, val in zip(labels, values)]
    scatter_colors = [
        'red' if (val < lim_min or val > lim_max) else '#006400'
        for val in values
    ]

    datasets = [
        {
            'type': 'scatter',
            'label': 'Sensor 1',
            'data': scatter_data,
            'pointBackgroundColor': scatter_colors,
            'pointRadius': 4
        },
        {
            'type': 'line',
            'label': f'Limite Máx ({lim_max}°C)',
            'data': [{'x': lbl, 'y': lim_max} for lbl in labels],
            'borderColor': 'rgba(255,0,0,0.4)',
            'borderDash': [5, 5],
            'pointRadius': 0,
            'fill': False
        },
        {
            'type': 'line',
            'label': f'Limite Min ({lim_min}°C)',
            'data': [{'x': lbl, 'y': lim_min} for lbl in labels],
            'borderColor': 'rgba(0,0,255,0.4)',
            'borderDash': [5, 5],
            'pointRadius': 0,
            'fill': False
        }
    ]

    # 9) Gera relatório executivo com GPT-4
    resp = client.chat.completions.create(
        model='gpt-4',
        messages=[
            {'role': 'system', 'content': 'Você é um analista técnico de cadeia fria.'},
            {'role': 'user',   'content': f'Analise estes textos e gere relatório executivo:\nTEMP:{temp_text}\nSM:{sm_text}'}
        ]
    )
    report_md = resp.choices[0].message.content

    # 10) Retorna JSON
    return jsonify({
        'report_md': report_md,
        'grafico': {
            'labels': labels,
            'datasets': datasets
        }
    })


@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json() or {}
    pergunta = data.get('pergunta')
    if not pergunta or not ultimo_embarque:
        return jsonify({'erro': 'Sem contexto'}), 400

    resp = client.chat.completions.create(
        model='gpt-4',
        messages=[
            {'role': 'system', 'content': 'Você é especialista em cadeia fria.'},
            {'role': 'user',   'content': f'{ultimo_temp_text}\n{ultimo_sm_text}'},
            {'role': 'user',   'content': pergunta}
        ]
    )
    return jsonify({'resposta': resp.choices[0].message.content})


# --- Tratamento de exceções não HTTP (não atrapalha 404/405) ---
@app.errorhandler(Exception)
def handle_unexpected_error(error):
    if isinstance(error, HTTPException):
        return error
    logger.exception("Erro inesperado:")
    return jsonify({'error': str(error)}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
