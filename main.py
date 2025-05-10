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

# -----------------------------------------------------------------------
# 0. Configuração do OpenAI
# -----------------------------------------------------------------------
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# -----------------------------------------------------------------------
# 1. Variáveis globais de contexto (para o endpoint /chat)
# -----------------------------------------------------------------------
ultimo_embarque   = None
ultimo_temp_text  = ""
ultimo_sm_text    = ""
ultimo_cte_text   = ""

# -----------------------------------------------------------------------
# 2. Endpoints básicos (health e home)
# -----------------------------------------------------------------------
@app.route('/health')
def health():
    return jsonify(status="ok"), 200

@app.route('/')
def home():
    return 'Coldchain backend está no ar! 🚀'

# -----------------------------------------------------------------------
# 3. Endpoint /analisar — processa PDFs, gera relatório e gráfico
# -----------------------------------------------------------------------
@app.route('/analisar', methods=['POST'])
def analisar():
    global ultimo_embarque, ultimo_temp_text, ultimo_sm_text, ultimo_cte_text

    # ----------------- 3.1 Validação de entrada -------------------------
    embarque = request.form.get('embarque')
    temp_pdf = request.files.get('relatorio_temp')
    sm_pdf   = request.files.get('solicitacao_sm')
    cte_pdf  = request.files.get('cte')  # opcional
    if not embarque or not temp_pdf or not sm_pdf:
        return jsonify(error='Faltam dados no formulário'), 400

    # ----------------- 3.2 Função util PDF → texto ----------------------
    def pdf_to_text(file_storage):
        if not file_storage:
            return ""
        txt = ""
        try:
            file_storage.stream.seek(0)
            with fitz.open(stream=file_storage.read(), filetype='pdf') as doc:
                for pg in doc:
                    txt += pg.get_text() or ""
        except Exception:
            pass
        file_storage.stream.seek(0)
        return txt

    # ----------------- 3.3 Extração de texto ----------------------------
    temp_text = pdf_to_text(temp_pdf)
    sm_text   = ""
    with pdfplumber.open(sm_pdf.stream) as pdf:
        for pg in pdf.pages:
            sm_text += pg.extract_text() or ""
    cte_text  = pdf_to_text(cte_pdf)

    # ----------------- 3.4 Geração do gráfico ---------------------------
    grafico = generate_chart_data({'relatorio_temp': temp_text,
                                   'solicitacao_sm': sm_text})

    # ----------------- 3.5 Persistência p/ endpoint /chat ---------------
    ultimo_embarque  = embarque
    ultimo_temp_text = temp_text[:3000]
    ultimo_sm_text   = sm_text[:3000]
    ultimo_cte_text  = cte_text[:3000]

    # ----------------- 3.6 Extração de metadados via regex --------------
    def rex(pattern, text, flags=0):
        m = re.search(pattern, text, flags)
        return m.group(1).strip() if m else "Não encontrado"

    transportadora = rex(r'^[A-Z].*?(?:LTDA|EIRELI|S\/?A)', cte_text, re.M)
    inicio_prest   = rex(r'IN[IÍ]CIO DA PRESTA[ÇC][ÃA]O[\s\S]*?\n\s*([A-ZÀ-Ú\- ]+)', cte_text, re.I)
    termino_prest  = rex(r'TERMINO DA PRESTA[ÇC][ÃA]O[\s\S]*?\n\s*([A-ZÀ-Ú\- ]+)', cte_text, re.I)

    cliente_origem  = rex(r'Cliente(?: Origem)?:\s*([^\n]+)', sm_text, re.I)
    cliente_destino = rex(r'Destinat[áa]rio:?[ \t]*([^\n]+)', sm_text, re.I)
    if cliente_origem == "Não encontrado":
        cliente_origem = inicio_prest
    if cliente_destino == "Não encontrado":
        cliente_destino = termino_prest

    cidade_origem  = rex(r'Origem:?[ \t]*([^/\n]+)/', sm_text, re.I)
    cidade_destino = rex(r'Destino:?[ \t]*([^/\n]+)/', sm_text, re.I)
    if cidade_origem == "Não encontrado":
        cidade_origem = inicio_prest
    if cidade_destino == "Não encontrado":
        cidade_destino = termino_prest

    endereco_origem  = rex(r'Origem:?[^/\n]+/([^\n]+)', sm_text, re.I)
    endereco_destino = rex(r'Destino:?[^/\n]+/([^\n]+)', sm_text, re.I)

    prev_coleta  = rex(r'Previs[ãa]o de In[ií]cio:?[ \t]*([0-9/ :]+)', sm_text)
    prev_entrega = rex(r'Previs[ãa]o de Fim:?[ \t]*([0-9/ :]+)',   sm_text)
    if prev_coleta == "Não encontrado":
        prev_coleta = inicio_prest
    if prev_entrega == "Não encontrado":
        prev_entrega = termino_prest

    material = rex(r'Material:?[ \t]*([^\n]+)', temp_text + sm_text + cte_text, re.I)

    # ----------------- 3.7 Construção do Markdown fixo ------------------
    agora = datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M:%S')

    md_cabecalho = (
        "### 1. Cabeçalho\n\n"
        f"**Título:** Análise de Embarque com Temperatura Controlada  \n"
        f"**Data/Hora:** {agora} (Horário de Brasília)"
    )

    md_origem_destino = (
        "### 2. Origem e Destino\n\n"
        "| Campo | Valor |\n|-------|-------|\n" +
        f"| Cliente Origem | {cliente_origem} |\n" +
        f"| Cliente Destino | {cliente_destino} |\n" +
        f"| Transportadora | {transportadora} |\n" +
        f"| Cidade Origem | {cidade_origem} |\n" +
        f"| Endereço Origem | {endereco_origem} |\n" +
        f"| Cidade Destino | {cidade_destino} |\n" +
        f"| Endereço Destino | {endereco_destino} |\n" +
        f"| Prev. Coleta | {prev_coleta} |\n" +
        f"| Prev. Entrega | {prev_entrega} |"
    )

    md_dados_carga = (
        "### 3. Dados da Carga\n\n"
        f"* **Material:** {material}  \n"
        f"* **Faixa de Temperatura:** {grafico['yMin']} – {grafico['yMax']} °C"
    )

    # ----------------- 3.8 GPT – Avaliação e Conclusão ------------------
    gpt_prompt = (
        "Gere **apenas** as seções abaixo em Markdown.\n\n"
        "### 4. Avaliação dos Eventos\n"
        "Descreva em até 6 linhas o comportamento da temperatura, destacando excursões (quando ocorreram, duração).\n\n"
        "### 5. Conclusão\n"
        "Resuma impacto potencial e dê 1–2 recomendações curtas."
    )

    md_avaliacao_conclusao = openai_client.chat.completions.create(
        model='gpt-4',
        messages=[
            {'role': 'system', 'content': 'Você é um analista de cadeia fria.'},
            {'role': 'user',   'content': gpt_prompt + "\n\n" + temp_text[:1500] }
        ]
    ).choices[0].message.content.strip()

    # ----------------- 3.9 Montagem final e retorno ---------------------
    page_break = '<div style="page-break-after:always;height:0;"></div>'
    report_md = "\n\n".join([
        md_cabecalho,
        md_origem_destino,
        md_dados_carga,
        md_avaliacao_conclusao,
        page_break
    ])

    return jsonify(report_md


# -----------------------------------------------------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
