# modules/validator.py

REQUIRED_FIELDS = {
    'relatorio_temp': [
        # termos em lowercase para comparação case-insensitive
        "temp",
        "data",
        "hora"
    ],
    'solicitacao_sm': [
        "solicitação",
        "monitoramento",
        "sm"
    ],
    'cte': [
        "conhecimento",
        
    ]
}

def validate_content(text: str, filename: str, tipo: str):
    """
    Garante que todos os campos em REQUIRED_FIELDS[tipo] estejam presentes em text.
    A comparação é feita em lowercase para ignorar caixa alta/baixa.
    """
    text_low = text.lower()
    missing = []
    for campo in REQUIRED_FIELDS[tipo]:
        if campo not in text_low:
            missing.append(campo)
    if missing:
        campos_str = ", ".join(missing)
        raise ValueError(f"{filename} está faltando campos: {campos_str}")
