from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz   # PyMuPDF
import pdfplumber
import os
from openai import OpenAI
from modules.chart import generate_chart_data

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

        # 3) Armazena para contexto de chat (limita tamanho)
        ultimo_embarque = embarque
        ultimo_temp_text = temp_text[:3000]
        ultimo_sm_text = sm_text[:3000]

        # 4) Prompt final para relatório executivo
        final_prompt = f"""
Você é um analista experiente em cadeia fria. Com base nos relatórios abaixo, gere um relatório executivo abordando:
- Cabeçalho (Cliente, Origem, Destino, Datas)
- Resumo de excursão de temperatura
- Pontos críticos
- Sugestões de melhoria

RELATÓRIO DE TEMPERATURA:
{ultimo_temp_text}

RELATÓRIO SM:
{ultimo_sm_text}
"""
          # 4) Prompt final para relatório executivo com estrutura tabular
from datetime import datetime
from zoneinfo import ZoneInfo

# Data/hora atuais em Brasília
agora = datetime.now(ZoneInfo("America/Sao_Paulo"))\
          .strftime("%d/%m/%Y %H:%M:%S")

final_prompt = f"""
1. Cabeçalho
   - **Título**: Análise de Embarque com Temperatura Controlada
   - **Data/Hora**: {agora} (Horário de Brasília)

2. Origem e Destino
   | Campo                | Valor                                                  |
   |----------------------|--------------------------------------------------------|
   | Cliente              | {{nome do cliente extraído ou “Não encontrado”}}       |
   | Cidade Origem        | {{cidade de coleta ou “Não encontrado”}}              |
   | Endereço Origem      | {{endereço de coleta ou “Não encontrado”}}            |
   | Cidade Destino       | {{cidade de entrega ou “Não encontrado”}}             |
   | Endereço Destino     | {{endereço de entrega ou “Não encontrado”}}           |
   | Prev. Coleta         | {{data/hora prevista de coleta ou “Não encontrado”}}  |
   | Prev. Entrega        | {{data/hora prevista de entrega ou “Não encontrado”}} |

3. Dados da Carga
   - **Material**: {{tipo de material ou “Não encontrado”}}
   - **Faixa de Temperatura**: {grafico['yMin']} a {grafico['yMax']} °C

4. Avaliação dos Eventos
   Forneça uma avaliação detalhada de como se comportou a temperatura durante o transporte,
   destacando excursões, pontos críticos e variações relevantes.

### RELATÓRIO DE TEMPERATURA
{ultimo_temp_text}

### RELATÓRIO SM
{ultimo_sm_text}
"""
