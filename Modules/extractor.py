import pdfplumber
from PIL import Image
import pandas as pd

ALLOWED_EXT = {'pdf','xls','xlsx','csv','png','jpg','jpeg'}

def extract_from_pdf(stream):
    text = ""
    with pdfplumber.open(stream) as pdf:
        for p in pdf.pages:
            text += (p.extract_text() or "") + "\n"
    return text

def extract_from_image(stream):
    img = Image.open(stream)
    return pytesseract.image_to_string(img)

def extract_from_excel(stream, ext):
    if ext in ('xls','xlsx'):
        df = pd.read_excel(stream)
    else:
        df = pd.read_csv(stream)
    return df.to_csv(index=False)

