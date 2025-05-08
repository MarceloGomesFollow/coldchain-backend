# Prompt: Avaliação Executiva de Embarque

**Objetivo:** gerar avaliação executiva com base nos arquivos PDF de CTE, Relatório de Temperatura e SM, seguindo o padrão:

1. **Cabeçalho**  
   - Número do Embarque (CTE)  
   - Cliente  
   - Origem → Destino (Data/Hora de saída e chegada)  
   - Peso bruto e volumes  
   - Faixa de temperatura controlada  

2. **Desempenho de Pontualidade**  
   - Tabela comparando horários previstos × reais (saída e chegada), com cálculo de desvio  

3. **Excursão de Temperatura**  
   - Tabela listando cada timestamp de medição, valor (°C) e status (dentro/fora da faixa)  
   - Estatísticas de maior desvio  

4. **Pontos Críticos**  
   - Bullets descrevendo riscos identificados (e.g. congelamento, pico de temperatura)  

5. **Recomendações**  
   - Ações preventivas e de melhoria

---

**Uso sugerido no backend**  
```python
with open("docs/avaliacao_embarque_prompt.md") as f:
    prompt_template = f.read()
# Substituir na runtime pelas variáveis embarque, temp_text e sm_text
prompt = prompt_template.format(
    cte_number=cte_number,
    client_name=client,
    origin=origem,
    destination=destino,
    departure=saida_horario,
    arrival=chegada_horario,
    weight=peso_bruto,
    volume=volume,
    temp_min=temp_min,
    temp_max=temp_max,
    temp_table=temp_table_markdown,
    deviations_table=desvios_table_markdown
)
