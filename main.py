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
CORS(app)

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- OpenAI client ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Global context for chat ---
ultimo_embarque  = None
ultimo_temp_text = ''
ultimo_sm_text   = ''

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200

@app.route('/analisar', methods=['POST'])
def analisar():
    global ultimo_embarque, ultimo_temp_text, ultimo_sm_text
    try:
        # 1) Valida form
        embarque  = request.form.get('embarque')
        temp_file = request.files.get('temps')
        sm_file   = request.files.get('sm')
        if not embarque or not temp_file or not sm_file:
            return jsonify({'error': 'Faltam dados no formulário'}), 400

        # 2) Lê PDFs
        temp_bytes = temp_file.read()
        sm_bytes   = sm_file.read()

        # 3) Extrai texto bruto do SM só para limites
        sm_text = ''
        with pdfplumber.open(io.BytesIO(sm_bytes)) as pdf:
            for p in pdf.pages:
                sm_text += p.extract_text() or ''

        # 4) Regex para limites X a Y °C
        m = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:a|até|–|-)\s*(\d+(?:[.,]\d+)?)\s*°?C', sm_text, re.IGNORECASE)
        if m:
            lim_min = float(m.group(1).replace(',', '.'))
            lim_max = float(m.group(2).replace(',', '.'))
        else:
            lim_min, lim_max = 2.0, 8.0

        # 5) Extrai medições de temperatura via regex do PDF de temperatura
        temp_text = ''
        with pdfplumber.open(io.BytesIO(temp_bytes)) as pdf:
            for p in pdf.pages:
                temp_text += p.extract_text() or ''
        pts = re.findall(r'(\d{2}:\d{2})\s+(\d+(?:[.,]\d+)?)', temp_text)
        labels = [t for t, _ in pts]
        values = [float(v.replace(',', '.')) for _, v in pts]

        # 6) Constrói CSV em texto
        csv_lines = ['timestamp,temperature']
        for t, v in zip(labels, values):
            csv_lines.append(f'{t},{v}')
        csv_data = '\n'.join(csv_lines)

        # 7) Prepara prompt reduzido para GPT-4
        prompt = f"""
Você é um analista de cadeia fria. A seguir, os dados de temperatura em CSV:

{csv_data}

A faixa controlada de temperatura é de {lim_min}°C a {lim_max}°C.

Com base nisso, gere um relatório executivo contendo:
- Cabeçalho (Cliente, Origem, Destino, Data)
- Resumo de excursões
- Pontos críticos
- Sugestões
"""
        resp = client.chat.completions.create(
            model='gpt-4',
            messages=[
                {'role':'system','content':'Você é um analista técnico de cadeia fria.'},
                {'role':'user','content':prompt}
            ]
        )
        report_md = resp.choices[0].message.content

        # 8) Monta datasets para Chart.js
        scatter_data = [{'x':lbl,'y':val} for lbl,val in zip(labels,values)]
        scatter_colors = ['red' if (val<lim_min or val>lim_max) else '#006400' for val in values]
        datasets = [
            {'type':'scatter','label':'Sensor 1','data':scatter_data,
             'pointBackgroundColor':scatter_colors,'pointRadius':4},
            {'type':'line','label':f'Limite Máx ({lim_max}°C)',
             'data':[{'x':lbl,'y':lim_max} for lbl in labels],
             'borderColor':'rgba(255,0,0,0.4)','borderDash':[5,5],
             'pointRadius':0,'fill':False},
            {'type':'line','label':f'Limite Min ({lim_min}°C)',
             'data':[{'x':lbl,'y':lim_min} for lbl in labels],
             'borderColor':'rgba(0,0,255,0.4)','borderDash':[5,5],
             'pointRadius':0,'fill':False}
        ]

        return jsonify({
            'report_md': report_md,
            'grafico': {'labels': labels, 'datasets': datasets}
        })

    except Exception as e:
        logger.exception("Erro em /analisar:")
        return jsonify({'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json() or {}
    pergunta = data.get('pergunta')
    if not pergunta:
        return jsonify({'erro':'Sem pergunta'}), 400

    resp = client.chat.completions.create(
        model='gpt-4',
        messages=[
            {'role':'system','content':'Você é especialista em cadeia fria.'},
            {'role':'user','content':pergunta}
        ]
    )
    return jsonify({'resposta': resp.choices[0].message.content})

# converte erros não-HTTP em JSON
@app.errorhandler(Exception)
def handle_all(e):
    if isinstance(e, HTTPException):
        return e
    logger.exception("Erro interno:")
    return jsonify({'error': str(e)}), 500

if __name__=='__main__':
    port = int(os.getenv('PORT',5000))
    app.run(host='0.0.0.0', port=port)
