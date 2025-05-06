# modules/chart.py
import re

def generate_chart_data(extracted: dict[str, str]) -> dict:
    """
    Gera datasets para Chart.js a partir do relatório de temperatura.
    Extrai pares (hora, temperatura) e permite parametrização.
    """
    text = extracted.get('relatorio_temp', '')
    # Regex para capturar horas (HH:MM) e valores (com ponto ou vírgula)
    pattern = r'(\\d{2}:\\d{2})h?\\s+(\\d+[\\.,]\\d+)'
    matches = re.findall(pattern, text)
    data = []
    for hour, temp_str in matches:
        temp = float(temp_str.replace(',', '.'))
        data.append({'x': hour, 'y': temp})

    # Configurações do dataset
    dataset = {
        "label": "Temperatura (°C)",
        "type": "scatter",
        "data": data,
        "pointRadius": 3,
        "showLine": True,
        "borderWidth": 2
    }
    return {"datasets": [dataset]}
