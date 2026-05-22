import base64
import requests
import pdfplumber
import fitz  # pymupdf — used for all image rendering (stable, no PDFium crashes)
from io import BytesIO
from config import ocr_key


# ---------------------------
# OCR API
# ---------------------------
def ocr_space_image(image_bytes: bytes) -> str:
    url = "https://api.ocr.space/parse/image"
    payload = {
        'apikey': ocr_key,
        'language': 'eng',
        'scale': True,
        'OCREngine': 2
    }
    try:
        res = requests.post(url, files={'file': ('image.png', image_bytes)}, data=payload).json()
        if res.get("ParsedResults"):
            return res["ParsedResults"][0]["ParsedText"]
    except Exception as e:
        print("OCR API error:", e)
    return ""


def _render_page(fitz_page, resolution: int) -> bytes:
    scale = resolution / 72
    pix = fitz_page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    return pix.tobytes("png")


# ---------------------------
# PDF TEXT + FIRST PAGE IMAGE
# ---------------------------
def extract_text_and_image(file) -> tuple:
    """Returns (full_text, first_page_png_base64_or_None).

    pdfplumber  → text extraction (fast, accurate for text-layer PDFs)
    PyMuPDF     → all image rendering (stable, no PDFium double-free crashes)
    """
    file.seek(0)
    pdf_bytes = file.read()

    text = ""
    first_page_b64 = None
    pages_need_ocr: set[int] = set()

    # --- Pass 1: text via pdfplumber ---
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                try:
                    t = page.extract_text()
                    if t and len(t.strip()) > 30:
                        text += t + "\n"
                    else:
                        pages_need_ocr.add(i)
                except Exception:
                    pages_need_ocr.add(i)
    except Exception as e:
        print("pdfplumber error:", e)

    # --- Pass 2: image rendering via PyMuPDF ---
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for i in range(len(doc)):
            page = doc[i]
            need_ocr = (i in pages_need_ocr) and ocr_key

            if i == 0:
                # Render at higher res when OCR is also needed, reuse for vision
                res = 300 if need_ocr else 150
                png = _render_page(page, res)
                first_page_b64 = base64.b64encode(png).decode()
                if need_ocr:
                    text += ocr_space_image(png) + "\n"
            elif need_ocr:
                png = _render_page(page, 300)
                text += ocr_space_image(png) + "\n"

        doc.close()
    except Exception as e:
        print("PyMuPDF error:", e)

    return text.strip(), first_page_b64
