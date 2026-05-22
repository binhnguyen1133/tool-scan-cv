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
    first_page_text_len = 0

    # --- Pass 1: collect text from pdfplumber (better layout) ---
    plumber_text: dict[int, str] = {}
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                try:
                    t = page.extract_text() or ""
                    plumber_text[i] = t.strip()
                except Exception:
                    plumber_text[i] = ""
    except Exception as e:
        print("pdfplumber error:", e)

    # --- Pass 2: PyMuPDF for text (more complete) + image rendering ---
    pages_need_ocr: set[int] = set()
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for i in range(len(doc)):
            fitz_page = doc[i]

            # Prefer whichever extractor gives more text (usually fitz is more complete)
            t_fitz = (fitz_page.get_text() or "").strip()
            t_plumber = plumber_text.get(i, "")
            t = t_fitz if len(t_fitz) >= len(t_plumber) else t_plumber

            if len(t) > 30:
                text += t + "\n"
                if i == 0:
                    first_page_text_len = len(t)
            else:
                pages_need_ocr.add(i)

        # Image rendering pass — always render page 0 for vision
        # (design-tool PDFs like Figma/Canva have truncated text layers; image is ground truth)
        for i in range(len(doc)):
            fitz_page = doc[i]
            need_ocr = (i in pages_need_ocr) and ocr_key

            if i == 0:
                res = 300 if need_ocr else 150
                png = _render_page(fitz_page, res)
                first_page_b64 = base64.b64encode(png).decode()
                if need_ocr:
                    text += ocr_space_image(png) + "\n"
            elif need_ocr:
                png = _render_page(fitz_page, 300)
                text += ocr_space_image(png) + "\n"

        doc.close()
    except Exception as e:
        print("PyMuPDF error:", e)

    return text.strip(), first_page_b64
