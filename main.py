import os    
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

from modules.extractor import extract_from_pdf, extract_from_image, extract_from_excel, ALLOWED_EXT
from modules.validator import validate_content
from modules.reporter  import generate_report_md
from modules.chart     import generate_chart_data

app = Flask(__name__)

@app.route('/analisar', methods=['POST'])
def analisar():
    # coleta arquivos
    temp = request.files.get('relatorio_temp')
    sm   = request.files.get('solicitacao_sm')
    cte  = request.files.get('cte')  # opcional
    if not temp or not sm:
        return jsonify(error="Relatório de Temperatura e SM são obrigatórios"), 400

    to_proc = [('relatorio_temp', temp), ('solicitacao_sm', sm)]
    if cte and cte.filename:
        to_proc.append(('cte', cte))

    extracted = {}
    for tipo, f in to_proc:
        fn  = secure_filename(f.filename)
        ext = fn.rsplit('.', 1)[-1].lower()
        if ext not in ALLOWED_EXT:
            return jsonify(error=f"Extensão não suportada: {fn}"), 400

        # extrai e valida
        if ext == 'pdf':
            text = extract_from_pdf(f)
        elif ext in ('png','jpg','jpeg'):
            text = extract_from_image(f)
        else:
            text = extract_from_excel(f, ext)

        try:
            validate_content(text, fn, tipo)
        except ValueError as e:
            return jsonify(error=str(e)), 400

        extracted[tipo] = text.replace("\r\n", "\n")

    # Etapa 1: relatório
    report_md = generate_report_md(extracted)

    # Etapa 2: gráfico opcional
    gerar_graf = bool(request.form.get('gerar_grafico'))
    grafico    = generate_chart_data(extracted) if gerar_graf else None

    resp = {"report_md": report_md}
    if grafico is not None:
        resp["grafico"] = grafico

    return jsonify(resp)


if __name__ == '__main__':
    # Faz o bind na porta que o Render fornece, ou 5000 localmente
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
