# modules/reporter.py
def generate_report_md(extracted: dict[str, str]) -> str:
    md = "# Relatório Executivo de ColdChain\n\n"
    # Se existir campo embarque
    if extracted.get('embarque'):
        md += f"**Embarque:** {extracted['embarque']}\n\n"

    md += "## 1. Relatório de Temperatura\n"
    md += "```\n" + extracted['relatorio_temp'] + "\n```\n\n"

    md += "## 2. Solicitação SM\n"
    md += "```\n" + extracted['solicitacao_sm'] + "\n```\n\n"

    if extracted.get('cte'):
        md += "## 3. CTE (Conhecimento de Embarque)\n"
        md += "```\n" + extracted['cte'] + "\n```\n\n"

    md += "---\n"
    md += "*Gerado automaticamente pelo sistema ColdChain Analytics.*\n"
    return md
