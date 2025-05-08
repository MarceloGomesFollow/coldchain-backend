--- a/main.py
+++ b/main.py
@@ top
 from modules.extractor import (
     extract_from_pdf,
     extract_from_image,
     extract_from_excel,
     ALLOWED_EXT
 )
 from modules.validator import validate_content
-from modules.reporter  import generate_report_md
+from modules.reporter  import generate_report_md
 from modules.chart     import generate_chart_data

+# Carrega template de avaliação
+TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "docs", "avaliacao.md")
+with open(TEMPLATE_PATH, encoding="utf-8") as f:
+    PROMPT_TEMPLATE = f.read()

@@ def analisar():
-    # 7) Gera o relatório em Markdown
-    report_md = generate_report_md(extracted)
+    # 7) Gera o relatório em Markdown usando o template
+    report_md = generate_report_md(
+        extracted=extracted,
+        template=PROMPT_TEMPLATE
+    )

@@ def analisar():
-    # 9) Monta a resposta JSON
-    resp = {"report_md": report_md}
+    # 9) Monta a resposta JSON (inclui gráfico se houver)
+    resp = {"report_md": report_md}
     if grafico is not None:
         resp["grafico"] = grafico

     return jsonify(resp)
