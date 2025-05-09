# modules/chart.py
import re
from typing import Dict, Any, List


def generate_chart_data(extracted: Dict[str, str]) -> Dict[str, Any]:
    """
    Gera dados para Chart.js a partir do relatório de temperatura.
    - Extrai pares (horário, temperatura) (HH:MM e valor).
    - Identifica sensores (colunas) se houver múltiplos.
    - Detecta faixa controlada (ex: 2 a 8°C) via regex.
    - Retorna labels, datasets, yMin, yMax para o gráfico.
    """
    temp_text = extracted.get('relatorio_temp', '')
    sm_text = extracted.get('solicitacao_sm', '')

    # 1) Detecta faixa controlada (min a max °C)
    faixa_match = re.search(r"(\d+(?:[\.,]\d+)?)\s*[–\-a]\s*(\d+(?:[\.,]\d+)?)\s*°?C", temp_text + " " + sm_text)
    if faixa_match:
        y_min = float(faixa_match.group(1).replace(',', '.'))
        y_max = float(faixa_match.group(2).replace(',', '.'))
    else:
        y_min, y_max = None, None

    # 2) Extrai linhas de dados: busca HH:MM seguido de valores
    lines = temp_text.splitlines()
    sensor_names: List[str] = []
    data_rows: List[List[str]] = []

    # Tenta identificar cabeçalho de sensores (contém 'Sensor')
    for line in lines:
        if re.search(r'sensor', line, re.IGNORECASE):
            parts = line.strip().split()
            sensor_names = parts[1:]
            break

    # Se encontrou cabeçalho, parseia tabela logo abaixo
    if sensor_names:
        parse = False
        for line in lines:
            if parse:
                parts = line.strip().split()
                if len(parts) >= 1 + len(sensor_names):
                    time = parts[0]
                    if re.match(r'\d{2}:\d{2}', time):
                        temps = parts[1:1+len(sensor_names)]
                        data_rows.append([time] + temps)
                else:
                    break
            if sensor_names and re.search(r'sensor', line, re.IGNORECASE):
                parse = True
    else:
        # fallback: extrai todos HH:MM VALOR
        for m in re.finditer(r"(\d{2}:\d{2})\s+([\d\.,]+)", temp_text):
            time = m.group(1)
            val = m.group(2)
            data_rows.append([time, val])
        sensor_names = ['Sensor']

    # 3) Monta labels e valores por sensor
    labels = [row[0] for row in data_rows]
    # transpoe os valores (sem o timestamp)
    raw_vals = [row[1:] for row in data_rows]
    # cria listas separadas por sensor
    sensor_values: List[List[float]] = list(map(
        lambda idx: [float(vals[idx].replace(',', '.')) for vals in raw_vals],
        range(len(sensor_names))
    ))

    # 4) Configura datasets com cores e pontos fora de faixa
    palette = ['#006400', '#00aa00', '#00cc44', '#88cc00']
    datasets: List[Dict[str, Any]] = []
    for i, name in enumerate(sensor_names):
        temps = sensor_values[i]
        point_colors = []
        point_sizes = []
        for t in temps:
            if y_min is not None and (t < y_min or t > y_max):
                point_colors.append('red')
                point_sizes.append(6)
            else:
                point_colors.append(palette[i % len(palette)])
                point_sizes.append(3)

        datasets.append({
            'label': name,
            'data': temps,
            'borderColor': palette[i % len(palette)],
            'backgroundColor': 'transparent',
            'pointBackgroundColor': point_colors,
            'pointRadius': point_sizes,
            'borderWidth': 2,
            'fill': False,
            'tension': 0.3
        })

    # 5) Adiciona linhas de limite
    if y_min is not None and y_max is not None:
        datasets.append({
            'label': f'Limite Máx ({y_max}°C)',
            'data': [y_max] * len(labels),
            'borderColor': 'rgba(255,0,0,0.3)',
            'borderDash': [5, 5],
            'pointRadius': 0,
            'fill': False
        })
        datasets.append({
            'label': f'Limite Mín ({y_min}°C)',
            'data': [y_min] * len(labels),
            'borderColor': 'rgba(0,0,255,0.3)',
            'borderDash': [5, 5],
            'pointRadius': 0,
            'fill': False
        })

    result: Dict[str, Any] = {'labels': labels, 'datasets': datasets}
    if y_min is not None:
        result['yMin'] = y_min
    if y_max is not None:
        result['yMax'] = y_max
    return result
