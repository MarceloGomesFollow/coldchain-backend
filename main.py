from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
import pdfplumber
import os

app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    return "Coldchain backend está no ar! 🚀"

@app.route("/analisar", methods=["POST"])
def analisar_pdfs():
    embarque = request.form.get("embarque")
    relatorio_file = request.files.get("relatorio")
    sm_file = request.files.get("sm")

    if not relatorio_file or not sm_file:
        return jsonify({"erro": "Arquivos obrigatórios não enviados."}), 400

    resultados = {}

    try:
        # Processa com PyMuPDF
        relatorio_file_stream = relatorio_file.read()
        with fitz.open(stream=relatorio_file_stream, filetype="pdf") as doc:
            texto_pymupdf = ""
            for page in doc:
                texto_pymupdf += page.get_text()
            resultados["pymupdf"] = texto_pymupdf[:1000]  # limitar para exibição

        # Resetar ponteiro do segundo PDF
        sm_file.seek(0)

        # Processa com pdfplumber
        with pdfplumber.open(sm_file) as pdf:
            texto_pdfplumber = ""
            for page in pdf.pages:
                texto_pdfplumber += page.extract_text() or ""
            resultados["pdfplumber"] = texto_pdfplumber[:1000]

        return jsonify({
            "embarque": embarque,
            "resultado": resultados
        })
    except Exception as e:
        return jsonify({"erro": f"Falha ao processar os PDFs: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True, port=10000)

