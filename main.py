from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
import pdfplumber
import os
import re
from openai import OpenAI
from modules.chart import generate_chart_data
from datetime import datetime
from zoneinfo import ZoneInfo

app = Flask(__name__)
CORS(app)

# Configura cliente OpenAI
deep_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Memória temporária para chat
ultimo_embarque = None
ultimo_temp_text = ""
ultimo_sm_text = ""

@app.route('/health', methods=['GET'])
def health():
    return jsonify(status="ok"), 200

@app.route('/')
def home():
    return 'Coldchain backend está no ar! 🚀'

@app.route('/analisar', methods=['POST'])
def analisar():
    global ultimo_embarque, ultimo_temp_text, ultimo_sm_text

    # 0) Coleta parâmetros e arquivos
    embarque = request.form.get('embarque')
    temp_pdf = request.files.get('relatorio_temp')
    sm_pdf = request.files.get('solicitacao_sm')
    cte_pdf = request.files.get('cte')

    if not embarque or not temp_pdf or not sm_pdf:
        return jsonify({'error': 'Faltam dados no formulário'}), 400

    try:
        # 1) Extrai textos dos PDFs
        temp_text = ""
        with fitz.open(stream=temp_pdf.read(), filetype="pdf") as doc:
            for page in doc:
                temp_text += page.get_text() or ""
        sm_pdf.stream.seek(0)
        sm_text = ""
        with pdfplumber.open(sm_pdf.stream) as pdf:
            for page in pdf.pages:
                sm_text += page.extract_text() or ""
        # extrai texto do CTE se houver
        cte_text = ""
        if cte_pdf:
            try:
                cte_bytes = cte_pdf.read()
                with fitz.open(stream=cte_bytes, filetype='pdf') as doc_cte:
                    for p in doc_cte:
                        cte_text += p.get_text() or ""
            except Exception:
                cte_text = ""

        # 2) Gera payload do gráfico
        grafico = generate_chart_data({'relatorio_temp': temp_text, 'solicitacao_sm': sm_text})

        # 3) Armazena contexto de chat
        ultimo_embarque = embarque
        ultimo_temp_text = temp_text[:3000]
        ultimo_sm_text = sm_text[:3000]

        # 4) Extrai campos para relatório
        # Transportadora (busca no CTE)
        transportadora = "Não encontrado"
        m = re.search(r"([A-ZÀ-Ú0-9\s]+TRANSPORTES E LOG[ÍI]STICA[^
]*)", cte_text, re.IGNORECASE)
        if m:
            transportadora = m.group(1).strip()
        # Cliente Origem/Destino (busca no SM)
        cliente_origem = "Não encontrado"
        cliente_destino = "Não encontrado"
        m1 = re.search(r"Cliente(?: Origem)?:\s*([^
]+)", sm_text, re.IGNORECASE)
        if m1:
            cliente_origem = m1.group(1).strip()
        m2 = re.search(r"Destino:?\s*([^
]+)", sm_text, re.IGNORECASE)
        if m2:
            cliente_destino = m2.group(1).strip()
        # Cidades e Endereços (SM)
        cidade_origem = "Não encontrado"
        endereco_origem = "Não encontrado"
        cidade_destino = "Não encontrado"
        endereco_destino = "Não encontrado"
        m3 = re.search(r"Origem:?\s*([^/\n]+)/([^\n]+)", sm_text, re.IGNORECASE)
        if m3:
            cidade_origem, endereco_origem = m3.group(1).strip(), m3.group(2).strip()
        m4 = re.search(r"Destino:?\s*([^/\n]+)/([^\n]+)", sm_text, re.IGNORECASE)
        if m4:
            cidade_destino, endereco_destino = m4.group(1).strip(), m4.group(2).strip()
        # Previsões
        prev_coleta = "Não encontrado"
        prev_entrega = "Não encontrado"
        m5 = re.search(r"Previs[ãa]o de In[ií]cio:?\s*([0-9/: ]+)" , sm_text)
        if m5:
            prev_coleta = m5.group(1).strip()
        m6 = re.search(r"Previs[ãa]o de Fim:?\s*([0-9/: ]+)" , sm_text)
        if m6:
            prev_entrega = m6.group(1).strip()
        # Material (busca geral)
        material = "Não encontrado"
        combined = temp_text + "\n" + sm_text + "\n" + cte_text
        m7 = re.search(r"Material[:]?\s*([^
]+)", combined, re.IGNORECASE)
        if m7:
            material = m7.group(1).strip()

        # 5) Monta prompt final para o GPT
        agora = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")
        final_prompt = f"""
1. Cabeçalho
   - Título: Análise de Embarque com Temperatura Controlada
   - Data/Hora: {agora} (Horário de Brasília)
   - Observação: use "Não encontrado" se faltar no Relatório, SM ou CTE.

2. Origem e Destino
   | Campo              | Valor                                           |
   |--------------------|-------------------------------------------------|
   | Cliente Origem     | {cliente_origem}                                |
   | Cliente Destino    | {cliente_destino}                               |
   | Transportadora     | {transportadora}                                |
   | Cidade Origem      | {cidade_origem}                                 |
   | Endereço Origem    | {endereco_origem}                               |
   | Cidade Destino     | {cidade_destino}                                |
   | Endereço Destino   | {endereco_destino}                              |
   | Prev. Coleta       | {prev_coleta}                                   |
   | Prev. Entrega      | {prev_entrega}                                  |

3. Dados da Carga
   - Material: {material}
   - Faixa de Temperatura: {grafico['yMin']} a {grafico['yMax']} °C

4. Avaliação dos Eventos
   Descreva o comportamento da temperatura durante o transporte, destacando excursões críticas.
"""

        exec_resp = deep_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Você é um analista experiente em cadeia fria."},
                {"role": "user", "content": final_prompt}
            ]
        )
        report_md = exec_resp.choices[0].message.content.strip()

        return jsonify(report_md=report_md, grafico=grafico)
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    pergunta = data.get("pergunta")
    if not pergunta:
        return jsonify(error="Pergunta não enviada."), 400
    if not ultimo_embarque:
        return jsonify(error="Nenhum embarque analisado."), 400

    contexto = f"""
Você está ajudando com o embarque: {ultimo_embarque}.
Use estes dados:

RELATÓRIO DE TEMPERATURA:
{ultimo_temp_text}

RELATÓRIO SM:
{ultimo_sm_text}

CTE – Conhecimento de Embarque:
{cte_text}
"""
    try:
        resp = deep_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Você é um especialista em cadeia fria."},
                {"role": "user",   "content": contexto},
                {"role": "user",   "content": pergunta}
            ]
        )
        return jsonify(resposta=resp.choices[0].message.content.strip())
    except Exception as e:
        return jsonify(error=str(e)), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
