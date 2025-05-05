from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# Rota de status para evitar o erro 404
@app.route("/")
def home():
    return "Coldchain backend está no ar! 🚀"

# Rota para análise de arquivos
@app.route("/analisar", methods=["POST"])
def analisar():
    if 'relatorio' not in request.files or 'sm' not in request.files:
        return jsonify({"erro": "Arquivos PDF não enviados corretamente."}), 400

    relatorio = request.files['relatorio']
    sm = request.files['sm']
    embarque = request.form.get('embarque', 'Sem nome')

    # Exemplo: apenas retorna os nomes dos arquivos
    return jsonify({
        "mensagem": f"Arquivos recebidos para o embarque {embarque}",
        "relatorio_filename": relatorio.filename,
        "sm_filename": sm.filename
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
