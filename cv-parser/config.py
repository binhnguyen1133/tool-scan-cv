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
