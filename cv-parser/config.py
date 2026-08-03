import json
import os
import logging
from pathlib import Path

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


# ---------------------------
# RECRUITMENT CHANNEL TAXONOMY (Rec_Channel → allowed Name_Channel)
# Persisted to CHANNELS_FILE; falls back to CHANNEL_DATA_DEFAULT on first run.
# ---------------------------
CHANNELS_FILE = Path(__file__).parent / "channels.json"

CHANNEL_DATA_DEFAULT = {
    "EB Channel": ["Careerspage", "EB Events", "Social Network", "Email", "Linkedin (Post)", "Vieclam24h", "Ybox"],
    "Active Search": ["Vietnamworks", "Itviec", "TopCV", "Linkedin (Search)", "Sales (Search)", "Vieclam24h", "TA Network", "Thread"],
    "Referral": ["Referral"],
    "Headhunt": ["Michael Page", "HR1", "Robert Walters", "Pegasi", "We Network", "Manpower"],
    "Others": ["Others"],
    "Paid Ads": ["Google Ads", "Facebook Ads", "Linkedin Ads"],
    "Job Board": ["Vietnamworks", "Itviec", "TopCV", "TopDev"],
}


def load_channels() -> dict:
    """Load channel taxonomy from disk; fall back to defaults if missing/corrupt."""
    if CHANNELS_FILE.exists():
        try:
            data = json.loads(CHANNELS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and all(isinstance(v, list) for v in data.values()):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {k: list(v) for k, v in CHANNEL_DATA_DEFAULT.items()}


def save_channels(data: dict) -> None:
    CHANNELS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# Convenience snapshot at import time (used only for legacy imports).
CHANNEL_DATA = load_channels()
REC_CHANNEL_OPTIONS = list(CHANNEL_DATA.keys())
ALL_NAME_CHANNEL_OPTIONS = sorted({n for names in CHANNEL_DATA.values() for n in names})
