import requests
import pdfplumber
from io import BytesIO
from config import ocr_key

# ---------------------------
# OCR API
# ---------------------------
def ocr_space_image(image_bytes):
    url = "https://api.ocr.space/parse/image"

    payload = {
        'apikey': ocr_key,
        'language': 'eng',
        'scale': True,
        'OCREngine': 2
    }

    files = {'file': ('image.png', image_bytes)}

    try:
        res = requests.post(url, files=files, data=payload).json()
        if res.get("ParsedResults"):
            return res["ParsedResults"][0]["ParsedText"]
    except Exception as e:
        print("OCR API error:", e)

    return ""

# ---------------------------
# PDF TEXT EXTRACT
# ---------------------------
def extract_text_from_pdf(file):
    text = ""

    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                try:
                    t = page.extract_text()
                    if t and len(t.strip()) > 30:
                        text += t + "\n"
                        continue
                except:
                    pass

                try:
                    img = page.to_image(resolution=450).original
                    buf = BytesIO()
                    img.save(buf, format="PNG")

                    ocr_text = ocr_space_image(buf.getvalue())
                    text += ocr_text + "\n"
                except:
                    pass

    except Exception as e:
        print("PDF open fail:", e)

    return text
