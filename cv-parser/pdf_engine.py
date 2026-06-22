import time
import base64
import requests
import pdfplumber
import fitz
from io import BytesIO
from config import ocr_key, OCR_DPI, MAX_IMAGE_SIDE


def ocr_space_image(image_bytes: bytes, retries: int = 2) -> str:
    url = "https://api.ocr.space/parse/image"
    payload = {'apikey': ocr_key, 'language': 'eng', 'scale': True, 'OCREngine': 2}
    for attempt in range(retries + 1):
        try:
            res = requests.post(
                url, files={'file': ('image.jpg', image_bytes)}, data=payload, timeout=60
            ).json()
            if res.get("ParsedResults"):
                return res["ParsedResults"][0]["ParsedText"]
            return ""
        except Exception as e:
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            print("OCR API error:", e)
    return ""


def _render_page(fitz_page, resolution: int) -> bytes:
    """Render a page to JPEG bytes, capping the longest side to bound memory."""
    scale = resolution / 72
    # Pre-cap the scale so the rendered pixmap never exceeds MAX_IMAGE_SIDE on its long edge.
    rect = fitz_page.rect
    long_side_pt = max(rect.width, rect.height) or 1
    if long_side_pt * scale > MAX_IMAGE_SIDE:
        scale = MAX_IMAGE_SIDE / long_side_pt
    pix = fitz_page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    try:
        return pix.tobytes("jpeg", jpg_quality=85)
    finally:
        pix = None  # release the pixmap buffer promptly


# ---------------------------
# FAST PATH — text only, no image (accepts bytes, no re-read)
# ---------------------------
def extract_text_only(pdf_bytes: bytes) -> tuple[str, set]:
    """pdfplumber, first 2 pages only. Returns (text, pages_need_ocr)."""
    text = ""
    pages_need_ocr: set[int] = set()

    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages[:2]):  # contact info always on page 1-2
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
# SLOW PATH — image rendering + OCR (accepts bytes, no re-read)
# ---------------------------
def render_first_page(pdf_bytes: bytes, pages_need_ocr: set) -> tuple[str | None, str]:
    """Render first page as JPEG + OCR if needed. Returns (image_b64, extra_ocr_text)."""
    image_b64 = None
    extra_text = ""
    doc = None

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        if len(doc) > 0:
            need_ocr_p0 = (0 in pages_need_ocr) and bool(ocr_key)
            res = OCR_DPI if need_ocr_p0 else 96
            png = _render_page(doc[0], res)
            image_b64 = base64.b64encode(png).decode()
            if need_ocr_p0:
                extra_text += ocr_space_image(png) + "\n"

        for i in range(1, min(len(doc), 2)):
            if (i in pages_need_ocr) and ocr_key:
                png = _render_page(doc[i], OCR_DPI)
                extra_text += ocr_space_image(png) + "\n"

    except Exception as e:
        print("PyMuPDF error:", e)
    finally:
        if doc is not None:
            doc.close()

    return image_b64, extra_text.strip()
