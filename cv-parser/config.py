import os
import logging
from openai import OpenAI

# ---------------------------
# CONFIG
# ---------------------------
logging.getLogger("pdfminer").setLevel(logging.ERROR)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
ocr_key = os.getenv("OCR_API_KEY")

EMAIL_REGEX = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
COMMON_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com"]


# ---------------------------
# SCALING / MEMORY TUNABLES (env-overridable, no redeploy needed)
# ---------------------------
def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, default)))
    except (TypeError, ValueError):
        return default


MAX_FILES = _env_int("MAX_FILES", 150)       # upload cap
CONCURRENCY = _env_int("CONCURRENCY", 4)     # worker threads — caps concurrent renders
OCR_DPI = _env_int("OCR_DPI", 200)           # slow-path OCR render DPI (was 300)
MAX_IMAGE_SIDE = _env_int("MAX_IMAGE_SIDE", 2000)  # cap longest side of rendered image (px)
