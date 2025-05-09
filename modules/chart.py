# modules/chart.py
import re

def generate_chart_data(extracted: dict[str, str]) -> dict:
    """
    Gera configurações para Chart.js a partir do relatório de temperatura.
    Extrai pares (hora, temperatura) e detecta faixas de temperatura (mín e máx) via regex.
    Retorna um dict com 'labels' e 'datasets'.
    """
    # Texto bruto do relatório
    text = extracted.get('relatorio_temp', '')

    # Regex para capturar horários (HH:MM) e valores de temperatura
    pattern = r"(\d{1,2}:\d{2})\s+([+-]?\d+(?:[.,]\d+)?)"
    matches = re.findall(pattern, text)
    if not matches:
        return {}

    # Separar labels e valores
    labels = [hour for hour, _ in matches]
    temps = [float(val.replace(',', '.')) for _, val in matches]

    # Detectar limites de temperatura (e.g. "2 a 8°C") do SM ou do texto
    sm_text = extracted.get('solicitacao_sm', '')
    faixa_match = re.search(r"(\d+(?:[.,]\d+)?)\s*[°]?C?\s*a\s*(\d+(?:[.,]\d+)?)", sm_text)
    if faixa_match:
        limite_min = float(faixa_match.group(1).replace(',', '.'))
        limite_max = float(faixa_match.group(2).replace(',', '.'))
    else:
        limite_min, limite_max = min(temps), max(temps)

    # Dataset principal de temperatura (linha com pontos)
    main_ds = {
        'label': 'Temperatura (°C)',
        'type': 'line',
        'data': temps,
        'borderColor': ['red' if (v < limite_min or v > limite_max) else 'green' for v in temps],
        'backgroundColor': 'transparent',
        'pointBackgroundColor': ['red' if (v < limite_min or v > limite_max) else 'green' for v in temps],
        'pointRadius': [6 if (v < limite_min or v > limite_max) else 4 for v in temps],
        'borderWidth': 2,
        'tension': 0.3,
        'fill': False
    }

    # Linhas de limite mínimo e máximo
    max_ds = {
        'label': f'Limite Máx ({limite_max}°C)',
        'type': 'line',
        'data': [limite_max] * len(labels),
        'borderColor': 'rgba(255,0,0,0.3)',
        'borderDash': [5, 5],
        'pointRadius': 0,
        'fill': False
    }
    min_ds = {
        'label': f'Limite Mín ({limite_min}°C)',
        'type': 'line',
        'data': [limite_min] * len(labels),
        'borderColor': 'rgba(0,0,255,0.3)',
        'borderDash': [5, 5],
        'pointRadius': 0,
        'fill': False
    }

    return {
        'labels': labels,
        'datasets': [main_ds, max_ds, min_ds]
    }
