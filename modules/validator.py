# modules/validator.py

REQUIRED_FIELDS = {
    'relatorio_temp': [
        # antes:
        # "Temperatura",
        # se no PDF vier abreviado ou com acento diferente, substitua por:
        "Temp",      # vai cobrir "Temp:" ou "Temp. (°C)"
        "Data",
        "Hora"
    ],
    'solicitacao_sm': ["Solicitação", "Monitoramento", "SM"],
    'cte':            ["Conhecimento", "Embarque", "CTE"]

    def validate_content(text, filename, tipo):
    text_low = text.lower()
    missing = []
    for campo in REQUIRED_FIELDS[tipo]:
        if campo.lower() not in text_low:
            missing.append(campo)
    if missing:
        raise ValueError(f"{filename} está faltando campos: {', '.join(missing)}")

}

