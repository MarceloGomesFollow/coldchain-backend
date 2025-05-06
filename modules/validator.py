# modules/validator.py

REQUIRED_FIELDS = {
    'relatorio_temp': [
        # se no PDF vier abreviado ou com acento diferente, substitua por:
        "temp",      # estamos usando lowercase para comparação case-insensitive
        "data",
        "hora"
    ],
    'solicitacao_sm': [
        "solicitação",
        "monitoramento",
        "sm"
    ],
    if tipo != 'cte':
    validate_content(text, fn, tipo)
    ]
}

def validate_content(text: str, filename: str, tipo: str):
    """
    Garante que todos os campos em REQUIRED_FIELDS[tipo] estejam presentes em text.
    Faz a checagem em lowercase para ignorar caixa alta/baixa.
    """
    text_low = text.lower()
    missing = []
    for campo in REQUIRED_FIELDS[tipo]:
        if campo not in text_low:
            missing.append(campo)
    if missing:
        campos_str = ", ".join(missing)
        raise ValueError(f"{filename} está faltando campos: {campos_str}")
