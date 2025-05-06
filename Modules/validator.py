REQUIRED_FIELDS = {
    'relatorio_temp': ["Temperatura","Data","Hora"],
    'solicitacao_sm': ["Solicitação","Monitoramento","SM"],
    'cte':             ["Conhecimento","Embarque","CTE"]
}

def validate_content(text, filename, tipo):
    faltam = [c for c in REQUIRED_FIELDS[tipo] if c not in text]
    if faltam:
        campos = ", ".join(faltam)
        raise ValueError(f"{filename} está faltando: {campos}")

