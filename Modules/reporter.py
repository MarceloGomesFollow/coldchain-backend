def generate_report_md(extracted: dict[str,str]) -> str:
    md = f"**Relatório de Temperatura**  \n```\n{extracted['relatorio_temp'][:200]}...\n```  \n\n"
    md += f"**Solicitação SM**  \n```\n{extracted['solicitacao_sm'][:200]}...\n```  \n"
    if 'cte' in extracted:
        md += f"\n**CTE**  \n```\n{extracted['cte'][:200]}...\n```  \n"
    return md

