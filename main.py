import os
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # libera CORS para todas as origens

@app.route("/analyse", methods=["POST"])
def analyse():
    # sua lógica de análise dos PDFs…
    return jsonify(report_md="…seu relatório aqui…")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

@app.route("/")
def home():
    return "Coldchain backend está no ar! 🚀"

