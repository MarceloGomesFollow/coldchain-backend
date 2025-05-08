TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "docs", "avaliacao_embarque_prompt.md")
with open(TEMPLATE_PATH, encoding="utf-8") as f:
    PROMPT_TEMPLATE = f.read()

