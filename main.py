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

# --- OpenAI client ------------------------------------------------------
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# --- Memória simples de última análise ---------------------------------
ultimo_embarque   = None
ultimo_temp_text  = ""
ultimo_sm_text    = ""
ultimo_cte_text   = ""

# -----------------------------------------------------------------------
@app.route('/health')
def health():
    return jsonify(status="ok"), 200

@app.route('/')
def home():
    return 'Coldchain backend está no ar! 🚀'

# -----------------------------------------------------------------------
@app.route('/analisar', methods=['POST'])
def analisar():
    global ultimo_embarque, ultimo_temp_text, ultimo_sm_text, ultimo_cte_text

    embarque = request.form.get('embarque')
    temp_pdf = request.files.get('relatorio_temp')
    sm_pdf   = request.files.get('solicitacao_sm')
    cte_pdf  = request.files.get('cte')  # opcional

    if not embarque or not temp_pdf or not sm_pdf:
        return jsonify(error='Faltam dados no formulário'), 400

    # ----------------- 1. Extração de texto --------------------------------
    def extract_pdf_text(f):
        text = ""
        try:
            with fitz.open(stream=f.read(), filetype='pdf') as doc:
                for pg in doc:
                    text += pg.get_text() or ""
        except Exception:
            pass
        return text

    temp_text = extract_pdf_text(temp_pdf)
    sm_text   = ""
    with pdfplumber.open(sm_pdf.stream) as pdf:
        for pg in pdf.pages:
            sm_text += pg.extract_text() or ""

    cte_text = extract_pdf_text(cte_pdf) if cte_pdf else ""

    # ----------------- 2. Dados do gráfico ---------------------------------
    grafico = generate_chart_data({'relatorio_temp': temp_text,
                                   'solicitacao_sm': sm_text})

    # ----------------- 3. Persistência de contexto -------------------------
    ultimo_embarque  = embarque
    ultimo_temp_text = temp_text[:3000]
    ultimo_sm_text   = sm_text[:3000]
    ultimo_cte_text  = cte_text[:3000]

    # ----------------- 4. Extração de campos chave ------------------------
    # Transportadora (primeira linha caixa‑alta que termina em LTDA / EIRELI / S.A.)
    transportadora = "Não encontrado"
    m = re.search(r'^[A-Z].*?(?:LTDA|EIRELI|S\/?A)', cte_text, re.MULTILINE)
    if m:
        transportadora = m.group(0).strip()

    # Início / Término da prestação (Cidade – UF)
    inicio_prestacao  = "Não encontrado"
    termino_prestacao = "Não encontrado"
    mi = re.search(r'IN[IÍ]CIO DA PRESTA[ÇC][ÃA]O[\s\S]*?\n\s*([A-ZÀ-Ú\- ]+)',
                   cte_text, re.IGNORECASE)
    if mi:
        inicio_prestacao = mi.group(1).strip()
    mt = re.search(r'TERMINO DA PRESTA[ÇC][ÃA]O[\s\S]*?\n\s*([A-ZÀ-Ú\- ]+)',
                   cte_text, re.IGNORECASE)
    if mt:
        termino_prestacao = mt.group(1).strip()

    # Cliente origem/destino (SM) – fallback para início/término
    cliente_origem  = re.search(r'Cliente(?: Origem)?:\s*([^\n]+)', sm_text, re.I)
    cliente_destino = re.search(r'Destinat[áa]rio:?\s*([^\n]+)', sm_text, re.I)
    cliente_origem  = cliente_origem.group(1).strip() if cliente_origem else inicio_prestacao
    cliente_destino = cliente_destino.group(1).strip() if cliente_destino else termino_prestacao

    # Cidades (SM) – fallback
    cidade_origem = inicio_prestacao
    cidade_destino = termino_prestacao
    mco = re.search(r'Origem:?\s*([^/\n]+)/', sm_text, re.I)
    if mco:
        cidade_origem = mco.group(1).strip()
    mcd = re.search(r'Destino:?\s*([^/\n]+)/', sm_text, re.I)
    if mcd:
        cidade_destino = mcd.group(1).strip()

    # Endereços (SM)
    endereco_origem  = "Não encontrado"
    endereco_destino = "Não encontrado"
    meo = re.search(r'Origem:?[^/\n]+/([^\n]+)', sm_text, re.I)
    if meo:
        endereco_origem = meo.group(1).strip()
    med = re.search(r'Destino:?[^/\n]+/([^\n]+)', sm_text, re.I)
    if med:
        endereco_destino = med.group(1).strip()

    # Previsões
    prev_coleta  = re.search(r'Previs[ãa]o de In[ií]cio:?\s*([0-9/ :]+)', sm_text)
    prev_entrega = re.search(r'Previs[ãa]o de Fim:?\s*([0-9/ :]+)',   sm_text)
    prev_coleta  = prev_coleta.group(1).strip()  if prev_coleta  else inicio_prestacao
    prev_entrega = prev_entrega.group(1).strip() if prev_entrega else termino_prestacao

    # Material
    material = "Não encontrado"
    mm = re.search(r'Material:?\s*([^\n]+)', temp_text + sm_text + cte_text, re.I)
    if mm:
        material = mm.group(1).strip()

    # ----------------- 5. Prompt de relatório -----------------------------
    agora = datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M:%S')
    prompt = f'''
1. Cabeçalho
   - Título: Análise de Embarque com Temperatura Controlada
   - Data/Hora: {agora} (Horário de Brasília)

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
'''

    res = openai_client.chat.completions.create(
        model='gpt-4',
        messages=[
            {'role': 'system', 'content': 'Você é um analista experiente em cadeia fria.'},
            {'role': 'user',   'content': prompt}
        ]
    )
    report_md = res.choices[0].message.content.strip()

    return jsonify(report_md=report_md, grafico=grafico)

# -----------------------------------------------------------------------
@app.route('/chat', methods=['POST'])
def chat():
    if not ultimo_embarque:
        return jsonify(error='Nenhum embarque analisado.'), 400

    data = request.get_json()
    pergunta = data.get('pergunta')
    if not pergunta:
        return jsonify(error='Pergunta não enviada.'), 400

    contexto = f'''
Embarque: {ultimo_embarque}

RELATÓRIO TEMP:
{ultimo_temp_text}

RELATÓRIO SM:
{ultimo_sm_text}

CTE:
{ultimo_cte_text}'''

    resp = openai_client.chat.completions.create(
        model='gpt-4',
        messages=[
            {'role': 'system', 'content': 'Você é um especialista em cadeia fria.'},
            {'role': 'user',   'content': contexto},
            {'role': 'user',   'content': pergunta}
        ]
    )
    return jsonify(resposta=resp.choices[0].message.content.strip())

# -----------------------------------------------------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
