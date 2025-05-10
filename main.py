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

    # 0) Coleta parâmetros e arquivos
    embarque = request.form.get('embarque')
    temp_pdf = request.files.get('relatorio_temp')
    sm_pdf   = request.files.get('solicitacao_sm')
    cte_pdf  = request.files.get('cte')

    if not embarque or not temp_pdf or not sm_pdf:
        return jsonify({'error': 'Faltam dados no formulário'}), 400

    try:
        # 1) Extrai textos brutos dos PDFs de temperatura e SM
        temp_text = ""
        with fitz.open(stream=temp_pdf.read(), filetype="pdf") as doc:
            for page in doc:
                temp_text += page.get_text()

        sm_pdf.stream.seek(0)
        sm_text = ""
        with pdfplumber.open(sm_pdf.stream) as pdf:
            for page in pdf.pages:
                sm_text += page.extract_text() or ""

        # 2) Extrai texto do CTE, se fornecido
        cte_text = ""
        if cte_pdf:
            try:
                cte_bytes = cte_pdf.read()
                with fitz.open(stream=cte_bytes, filetype='pdf') as doc_cte:
                    for p in doc_cte:
                        cte_text += p.get_text()
            except Exception:
                cte_text = ""

        # 3) Gera payload do gráfico via módulo
        extracted = {'relatorio_temp': temp_text, 'solicitacao_sm': sm_text}
        grafico = generate_chart_data(extracted)

        # 4) Armazena para contexto de chat (limitando tamanho)
        ultimo_embarque  = embarque
        ultimo_temp_text = temp_text[:3000]
        ultimo_sm_text   = sm_text[:3000]

        # 5) Monta prompt com nova estrutura obrigatória
        agora = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")
        final_prompt = f"""
1. Cabeçalho
   - Título: Análise de Embarque com Temperatura Controlada
   - Data/Hora: {agora} (Horário de Brasília)
   - Observação: se algum campo estiver ausente no Relatório de Temperatura, SM ou CTE, escreva “Não encontrado”.

2. Origem e Destino
   A partir dos conteúdos abaixo, preencha a tabela ou indique “Não encontrado”:

RELATÓRIO DE TEMPERATURA:
{ultimo_temp_text}

RELATÓRIO SM:
{ultimo_sm_text}

CTE – Conhecimento de Embarque:
{cte_text}

   | Campo              | Valor                              |
   |--------------------|------------------------------------|
   | Transportadora     |                                    |
   | Cliente Origem     |                                    |
   | Cidade Origem      |                                    |
   | Endereço Origem    |                                    |
   | Cliente Destino    |                                    |
   | Cidade Destino     |                                    |
   | Endereço Destino   |                                    |
   | Prev. Coleta(data e horário)    |                                    |
   | Prev. Entrega (data e horário)     |                                    |

3. Dados da Carga
   - Material: extraia do Relatório ou escreva “Não encontrado”
   - Faixa de Temperatura: {grafico['yMin']} a {grafico['yMax']} °C

4. Avaliação dos Eventos
   Descreva o comportamento da temperatura durante o transporte, destacando excursões e pontos críticos.

---

### RELATÓRIO DE TEMPERATURA
{ultimo_temp_text}

### RELATÓRIO SM
{ultimo_sm_text}

### CTE – Conhecimento de Embarque
{cte_text}
"""

        exec_resp = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Você é um analista experiente em cadeia fria."},
                {"role": "user",   "content": final_prompt}
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

CTE – Conhecimento de Embarque:
{cte_text}
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
