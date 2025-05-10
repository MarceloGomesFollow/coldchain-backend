from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz   # PyMuPDF
import pdfplumber
import os
from openai import OpenAI
from modules.chart import generate_chart_data
from datetime import datetime
from zoneinfo import ZoneInfo

app = Flask(__name__)
CORS(app)

# Configura cliente OpenAI
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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

    embarque = request.form.get('embarque')
    temp_pdf = request.files.get('relatorio_temp')
    sm_pdf = request.files.get('solicitacao_sm')

    if not embarque or not temp_pdf or not sm_pdf:
        return jsonify({'error': 'Faltam dados no formulário'}), 400

    try:
        # 1) Extrai textos brutos dos PDFs
        temp_text = ""
        with fitz.open(stream=temp_pdf.read(), filetype="pdf") as doc:
            for page in doc:
                temp_text += page.get_text()

        sm_pdf.stream.seek(0)
        sm_text = ""
        with pdfplumber.open(sm_pdf.stream) as pdf:
            for page in pdf.pages:
                sm_text += page.extract_text() or ""

        # 2) Gera payload do gráfico via módulo
        extracted = {
            'relatorio_temp': temp_text,
            'solicitacao_sm': sm_text
        }
        grafico = generate_chart_data(extracted)

        # (Opcional) Extrai texto do CTE se enviado
        cte_text = ""
        cte_pdf = request.files.get('cte')
        if cte_pdf:
            try:
                # tenta extrair texto via PyMuPDF
                cte_bytes = cte_pdf.read()
                with fitz.open(stream=cte_bytes, filetype='pdf') as doc_cte:
                    for p in doc_cte:
                        cte_text += p.get_text()
            except Exception:
                cte_text = ""

        # 3) Armazena para contexto de chat (limita tamanho)
        ultimo_embarque = embarque
        ultimo_temp_text = temp_text[:3000]
        ultimo_sm_text = sm_text[:3000]

        # 4) Prompt final para relatório executivo com estrutura customizada e extração
        agora = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")
        final_prompt = f"""
1. Cabeçalho
   - **Título**: Análise de Embarque com Temperatura Controlada
   - **Data/Hora**: {agora} (Horário de Brasília)
   - **Verificação**: Se algum campo do cabeçalho não for encontrado nos relatórios, escreva “Não encontrado”.

2. Origem e Destino
   A partir dos seguintes textos (incluindo o CTE se disponível), extraia ou escreva “Não encontrado” quando a informação não estiver disponível:

RELATÓRIO DE TEMPERATURA:
{ultimo_temp_text}

RELATÓRIO SM:
{ultimo_sm_text}

CTE – Conhecimento de Embarque:
{cte_text}

   | Campo                  | Valor                                |
   |------------------------|--------------------------------------|
   | Cliente Origem         |                                      |
   | Cliente Destino        |                                      |
   | Transportadora         |                                      |
   | Cidade Origem          |                                      |
   | Endereço Origem        |                                      |
   | Cidade Destino         |                                      |
   | Endereço Destino       |                                      |
   | Prev. Coleta           |                                      |
   | Prev. Entrega          |                                      |

3. Dados da Carga
   - **Material**: extraia do relatório ou escreva “Não encontrado”
   - **Faixa de Temperatura**: {grafico['yMin']} a {grafico['yMax']} °C

4. Avaliação dos Eventos
   Forneça uma avaliação detalhada de como se comportou a temperatura durante o transporte,
   destacando excursões, pontos críticos e variações relevantes.

### RELATÓRIO DE TEMPERATURA
{ultimo_temp_text}

### RELATÓRIO SM
{ultimo_sm_text}

### CTE – Conhecimento de Embarque
{cte_text}
"""
        exec_resp = client.chat.completions.create
        agora = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")
        final_prompt = f"""
1. Cabeçalho
   - **Título**: Análise de Embarque com Temperatura Controlada
   - **Data/Hora**: {agora} (Horário de Brasília)

2. Origem e Destino
   A partir dos textos abaixo, extraia ou escreva “Não encontrado” quando a informação não estiver disponível:

RELATÓRIO DE TEMPERATURA:
{ultimo_temp_text}

RELATÓRIO SM:
{ultimo_sm_text}

   | Campo                | Valor                               |
   |----------------------|-------------------------------------|
   | Cliente              |                                     |
   | Cidade Origem        |                                     |
   | Endereço Origem      |                                     |
   | Cidade Destino       |                                     |
   | Endereço Destino     |                                     |
   | Prev. Coleta         |                                     |
   | Prev. Entrega        |                                     |

3. Dados da Carga
   - **Material**: extraia do relatório ou escreva “Não encontrado”
   - **Faixa de Temperatura**: {grafico['yMin']} a {grafico['yMax']} °C

4. Avaliação dos Eventos
   Forneça uma avaliação detalhada de como se comportou a temperatura durante o transporte,
   destacando excursões, pontos críticos e variações relevantes.

### RELATÓRIO DE TEMPERATURA
{ultimo_temp_text}

### RELATÓRIO SM
{ultimo_sm_text}
"""
        exec_resp = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system",  "content": "Você é um analista experiente em cadeia fria."},
                {"role": "user",    "content": final_prompt}
            ]
        )
        report_md = exec_resp.choices[0].message.content.strip()

        return jsonify(report_md=report_md, grafico=grafico)
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route('/chat', methods=['POST'])
def chat():
    global ultimo_embarque, ultimo_temp_text, ultimo_sm_text

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
"""
    try:
        resp = client.chat.completions.create(
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
