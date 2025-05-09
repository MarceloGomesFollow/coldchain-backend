# modules/chart.py
import re

def generate_chart_data(extracted: dict[str, str]) -> dict:
    """
    Gera datasets para Chart.js a partir do relatório de temperatura.
    Extrai pares (hora, temperatura) e retorna labels, datasets,
    além dos limites mínimos e máximos detectados.
    """
    # Texto para análise: temperatura e SM juntos
    text = (extracted.get('relatorio_temp', '') + '\n' + extracted.get('solicitacao_sm', '')).strip()

    # Regex para capturar horas (HH:MM) e valores de temperatura (com ponto ou vírgula)
    pattern = r"(\d{1,2}:\d{2})\s+([\d.,]+)"
    matches = re.findall(pattern, text)
    if not matches:
        return {}

    # Monta as listas de dados
    labels = []
    data_points = []
    temps = []
    for hour, temp_str in matches:
        try:
            temp = float(temp_str.replace(',', '.'))
        except ValueError:
            continue
        labels.append(hour)
        data_points.append({'x': hour, 'y': temp})
        temps.append(temp)
    
    # Detecta limites (busca padrão 'X a Y')
    faixa_pattern = r"(\d+(?:[\.,]\d+)?)\s*a\s*(\d+(?:[\.,]\d+)?)"
    faixa_match = re.search(faixa_pattern, text, re.IGNORECASE)
    if faixa_match:
        y_min = float(faixa_match.group(1).replace(',', '.'))
        y_max = float(faixa_match.group(2).replace(',', '.'))
    else:
        # Caso não encontrado, definir com base nos dados
        y_min = min(temps) if temps else 0.0
        y_max = max(temps) if temps else 0.0

    # Configurações do dataset principal
    main_dataset = {
        'label': 'Temperatura (°C)',
        'type': 'line',
        'data': data_points,
        'borderColor': [ 'green' if y_min <= pt['y'] <= y_max else 'red' for pt in data_points ],
        'backgroundColor': 'transparent',
        'pointRadius': [ 4 for _ in data_points ],
        'tension': 0.3,
        'fill': False,
        'borderWidth': 2
    }

    # Datasets de limite mínimo e máximo
    limit_datasets = [
        {
            'label': f'Limite Máx ({y_max}°C)',
            'type': 'line',
            'data': [ {'x': lbl, 'y': y_max} for lbl in labels ],
            'borderColor': 'rgba(255,0,0,0.5)',
            'borderDash': [6, 4],
            'pointRadius': 0,
            'fill': False,
        },
        {
            'label': f'Limite Mín ({y_min}°C)',
            'type': 'line',
            'data': [ {'x': lbl, 'y': y_min} for lbl in labels ],
            'borderColor': 'rgba(0,0,255,0.5)',
            'borderDash': [6, 4],
            'pointRadius': 0,
            'fill': False,
        }
    ]
    
    return {
        'labels': labels,
        'datasets': [main_dataset] + limit_datasets,
        'yMin': y_min,
        'yMax': y_max
    }
