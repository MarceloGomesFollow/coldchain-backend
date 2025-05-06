rom flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import io
import os
import re
from openai import OpenAI

app = Flask(__name__)
CORS(app)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

ultimo_embarque  = None
ultimo_temp_text = ''
ultimo_sm_text   = ''

@app.route('/analisar', methods=['POST'])
def analisar():
    global ultimo_embarque, ultimo_temp_text, ultimo_sm_text

    embarque  = request.form.get('embarque')
    temp_file = request.files.get('temps')
    sm_file   = request.files.get('sm')
    if not embarque or not temp_file or not sm_file:
        return jsonify({'error':'Faltam dados no formulário'}), 400

    temp_bytes = temp_file.read()
    sm_bytes   = sm_file.read()

    # Extrai texto e tabelas de temperatura
    temp_text, tables = '', []
    with pdfplumber.open(io.BytesIO(temp_bytes)) as pdf:
        for p in pdf.pages:
            temp_text += p.extract_text() or ''
            tables += p.extract_tables()

    # Extrai texto SM
    sm_text = ''
    with pdfplumber.open(io.BytesIO(sm_bytes)) as pdf:
        for p in pdf.pages:
            sm_text += p.extract_text() or ''

    ultimo_embarque  = embarque
    ultimo_temp_text = temp_text
    ultimo_sm_text   = sm_text

    # Regex para medições
    pts = re.findall(r"(\d{2}:\d{2})\s+(\d+(?:[.,]\d+)?)", temp_text)
    labels = [t for t,_ in pts]
    data   = [float(v.replace(',','.')) for _,v in pts]

    # Regex para limites na SM
    faixa = re.search(
        r"[Ff]aixa.*?(\d+(?:[.,]\d+)?)°?C.*?(\d+(?:[.,]\d+)?)°?C",
        sm_text, re.DOTALL
    )
    if faixa:
        lim_min = float(faixa.group(1).replace(',','.'))
        lim_max = float(faixa.group(2).replace(',','.'))
    else:
        lim_min, lim_max = 2.0, 8.0

    # Monta gráfico: scatter + linhas de limite
    datasets = []
    # Sensor
    scatter_data = [ {'x':lbl,'y':dat} for lbl,dat in zip(labels,data) ]
    scatter_color = ['red' if (dat<lim_min or dat>lim_max) else '#006400' for dat in data]
    datasets.append({
        'type':'scatter',
        'label':'Sensor 1',
        'data':scatter_data,
        'pointBackgroundColor':scatter_color,
        'pointRadius':4
    })
    # Limites
    datasets.append({
        'type':'line',
        'label':f'Limite Máx ({lim_max}°C)',
        'data':[{'x':lbl,'y':lim_max} for lbl in labels],
        'borderColor':'rgba(255,0,0,0.4)',
        'borderDash':[5,5],
        'pointRadius':0,
        'fill':False
    })
    datasets.append({
        'type':'line',
        'label':f'Limite Min ({lim_min}°C)',
        'data':[{'x':lbl,'y':lim_min} for lbl in labels],
        'borderColor':'rgba(0,0,255,0.4)',
        'borderDash':[5,5],
        'pointRadius':0,
        'fill':False
    })

    # Gera relatório via GPT-4
    resp = client.chat.completions.create(
        model='gpt-4',
        messages=[
            {'role':'system','content':'Você é um analista técnico de cadeia fria.'},
            {'role':'user','content':f"Analise e crie relatório executivo com estes textos:\nTEMP:{temp_text}\nSM:{sm_text}"}
        ]
    )
    report_md = resp.choices[0].message.content

    return jsonify({
        'report_md': report_md,
        'grafico': { 'labels': labels, 'datasets': datasets }
    })

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    pergunta = data.get('pergunta')
    if not pergunta or not ultimo_embarque:
        return jsonify({'erro':'Sem contexto'}), 400
    resp = client.chat.completions.create(
        model='gpt-4',
        messages=[
            {'role':'system','content':'Você é especialista em cadeia fria.'},
            {'role':'user','content':f'{ultimo_temp_text}\n{ultimo_sm_text}'},
            {'role':'user','content':pergunta}
        ]
    )
    return jsonify({'resposta': resp.choices[0].message.content})

if __name__=='__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
