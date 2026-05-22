import base64
import requests
import pdfplumber
import fitz
from io import BytesIO
from config import ocr_key


def ocr_space_image(image_bytes: bytes) -> str:
    url = "https://api.ocr.space/parse/image"
    payload = {'apikey': ocr_key, 'language': 'eng', 'scale': True, 'OCREngine': 2}
    try:
        res = requests.post(url, files={'file': ('image.jpg', image_bytes)}, data=payload).json()
        if res.get("ParsedResults"):
            return res["ParsedResults"][0]["ParsedText"]
    except Exception as e:
        print("OCR API error:", e)
    return ""


def _render_page(fitz_page, resolution: int) -> bytes:
    scale = resolution / 72
    pix = fitz_page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    return pix.tobytes("jpeg", jpg_quality=85)


# ---------------------------
# FAST PATH — text only, no image rendering
# ---------------------------
def extract_text_only(file) -> tuple[str, set]:
    """pdfplumber text extraction only. Returns (text, pages_need_ocr)."""
    file.seek(0)
    pdf_bytes = file.read()
    text = ""
    pages_need_ocr: set[int] = set()

    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                try:
                    t = (page.extract_text() or "").strip()
                    if len(t) > 30:
                        text += t + "\n"
                    else:
                        pages_need_ocr.add(i)
                except Exception:
                    pages_need_ocr.add(i)
    except Exception as e:
        print("pdfplumber error:", e)

    return text.strip(), pages_need_ocr


# ---------------------------
# SLOW PATH — image rendering + OCR (called lazily)
# ---------------------------
def render_first_page(file, pages_need_ocr: set) -> tuple[str | None, str]:
    """Render first page as JPEG + OCR image-only pages.
    Returns (image_b64, extra_ocr_text).
    """
    file.seek(0)
    pdf_bytes = file.read()
    image_b64 = None
    extra_text = ""

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        if len(doc) > 0:
            need_ocr_p0 = (0 in pages_need_ocr) and bool(ocr_key)
            res = 300 if need_ocr_p0 else 96
            png = _render_page(doc[0], res)
            image_b64 = base64.b64encode(png).decode()
            if need_ocr_p0:
                extra_text += ocr_space_image(png) + "\n"

        for i in range(1, len(doc)):
            if (i in pages_need_ocr) and ocr_key:
                png = _render_page(doc[i], 300)
                extra_text += ocr_space_image(png) + "\n"

        doc.close()
    except Exception as e:
        print("PyMuPDF error:", e)

    return image_b64, extra_text.strip()
