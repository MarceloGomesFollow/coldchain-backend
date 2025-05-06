Changelog

Este arquivo documenta as mudanças notáveis neste projeto, permitindo acompanhar versões e reverter alterações quando necessário.

[Unreleased]

Gráfico: Extração de pares (hora, temperatura) via regex, pontos configuráveis, linhas conectadas. (modules/chart.py)

Markdown: Template executivo unificado com cabeçalhos, seções e blocos de texto formatados. (modules/reporter.py)

Changelog: Criação deste arquivo de log de mudanças.

## [1.1.0] – 2025-05-07
### Added
- Gráfico: geração de scatter com `showLine` e `pointRadius`.  
- Markdown: template executivo com seções numeradas.

## [Unreleased]


[1.0.0] - 2025-05-06

Added

Modularização das funções de extração, validação, geração de relatório e gráfico.

Rota /analisar no backend Flask com CORS e health-check.

PWA frontend com integração com Chart.js e Markdown.

