def generate_chart_data(extracted: dict[str,str]) -> dict:
    # Aqui você deve parsear o texto de temperatura para extrair pares (timestamp, valor)
    # e retornar algo como:
    return {
        "datasets": [
            {
                "label": "Temperatura (°C)",
                "type": "scatter",
                "data": [
                    {"x": "16:00", "y": 4.5},
                    {"x": "16:10", "y": 4.7},
                    # … e assim por diante …
                ]
            }
        ]
    }
