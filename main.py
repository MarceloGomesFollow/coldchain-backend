import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

from modules.extractor import (
    extract_from_pdf,
    extract_from_image,
    extract_from_excel,
    ALLOWED_EXT
)
from modules.validator import validate_content
from modules.reporter  import generate_report_md
from modules.chart     import generate_chart_data

app = Flask(__name__)
CORS(app)  # libera CORS para todas as origens

# Carrega template de avaliação
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "doc", "avaliacao_embarque_prompt.md")
with open(TEMPLATE_PATH, encoding="utf-8") as f:
    PROMPT_TEMPLATE = f.read()


# Health-check simples
@app.route('/health', methods=['GET'])
def health():
    return jsonify(status="ok"), 200


# Rota principal de análise
@app.route('/analisar', methods=['POST'])
def analisar():
    # 1) Coleta arquivos do form
    temp = request.files.get('relatorio_temp')
    sm   = request.files.get('solicitacao_sm')
    cte  = request.files.get('cte')  # opcional

    # 2) Verifica obrigatoriedade
    if not temp or not sm:
        return jsonify(error="Relatório de Temperatura e SM são obrigatórios"), 400

    # 3) Prepara lista de arquivos a processar
    to_proc = [
        ('relatorio_temp', temp),
        ('solicitacao_sm', sm)
    ]
    if cte and cte.filename:
        to_proc.append(('cte', cte))

    extracted = {}
    for tipo, f in to_proc:
        fn  = secure_filename(f.filename)
        ext = fn.rsplit('.', 1)[-1].lower()

        # 4) Valida extensão
        if ext not in ALLOWED_EXT:
            return jsonify(error=f"Extensão não suportada: {fn}"), 400

        # 5) Extrai o conteúdo
        if ext == 'pdf':
            text = extract_from_pdf(f)
        elif ext in ('png','jpg','jpeg'):
            text = extract_from_image(f)
        else:
            text = extract_from_excel(f, ext)

        # 6) Valida campos obrigatórios no texto
        try:
            validate_content(text, fn, tipo)
        except ValueError as e:
            return jsonify(error=str(e)), 400

        extracted[tipo] = text.replace("\r\n", "\n")

    # 7) Gera o relatório em Markdown usando o template
    report_md = generate_report_md(extracted, PROMPT_TEMPLATE)

    # 8) Gera o gráfico se solicitado
    gerar_graf = bool(request.form.get('gerar_grafico'))
    grafico    = generate_chart_data(extracted) if gerar_graf else None

    # 9) Monta a resposta JSON
    resp = {"report_md": report_md}
    if grafico is not None:
        resp["grafico"] = grafico

    return jsonify(resp)


if __name__ == '__main__':
    # Usa a porta definida pelo Render ou 5000 localmente
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
