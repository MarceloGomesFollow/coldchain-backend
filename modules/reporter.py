def generate_report_md(extracted: dict, template: str) -> str:
    # extrai metadados do extracted (cte, client_name, origin, etc)
    # monta temp_table e deviations via reporter utils
    # preenche template:
    return template.format(
        embarque=extracted["relatorio_temp_meta"]["embarque"],
        cte_number=extracted.get("cte_meta", {}).get("cte_number","—"),
        client_name=extracted["solicitacao_sm_meta"]["client_name"],
        origin=extracted["solicitacao_sm_meta"]["origin"],
        destination=extracted["solicitacao_sm_meta"]["destination"],
        departure=extracted["solicitacao_sm_meta"]["departure"],
        arrival=extracted["solicitacao_sm_meta"]["arrival"],
        weight=extracted["relatorio_temp_meta"]["weight"],
        volume=extracted["relatorio_temp_meta"]["volume"],
        temp_min=extracted["relatorio_temp_meta"]["temp_min"],
        temp_max=extracted["relatorio_temp_meta"]["temp_max"],
        temp_table=build_temperature_table(extracted),
        deviations_table=build_deviations_table(extracted),
        analysis_summary=generate_summary(extracted),
        recommendations=generate_recommendations(extracted),
    )
