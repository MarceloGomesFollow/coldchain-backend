# Avaliação Executiva de Embarque

**Embarque:** {cte_number}  
**Cliente:** {client_name}  
**Origem → Destino:** {origin} → {destination}  
**Saída (prevista/real):** {departure_planned} / {departure_actual}  
**Chegada (prevista/real):** {arrival_planned} / {arrival_actual}  
**Peso Bruto:** {weight}  
**Volumes:** {volume}  
**Faixa de Temperatura Controlada:** {temp_min}°C a {temp_max}°C  

---

## 1. Desempenho de Pontualidade

| Evento   | Previsto    | Real        | Desvio  |
|----------|-------------|-------------|---------|
| Saída    | {departure_planned} | {departure_actual} | {departure_delta} |
| Chegada  | {arrival_planned}   | {arrival_actual}   | {arrival_delta}   |

---

## 2. Excursão de Temperatura

| Horário    | {sensor_headers} | Status      |
|------------|------------------|-------------|
{temp_table}

**Maior Desvio:** {max_deviation}°C em {max_dev_time}

---

## 3. Pontos Críticos

{critical_points}

---

## 4. Recomendações

{recommendations}

---
*Gerado automaticamente pelo sistema ColdChain Analytics da Follow Advisor.*
