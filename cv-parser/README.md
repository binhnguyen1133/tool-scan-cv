---
title: CV Parser ATS
emoji: 🚀
colorFrom: blue
colorTo: green
sdk: streamlit
sdk_version: 1.57.0
app_file: app.py
pinned: false
---

# CV Parser ATS

Upload PDF CVs, extract structured info (name, email, phone, education) via AI, edit results, then export to Excel or download renamed/zipped PDFs.

## Required Secrets

Set these in Space Settings → Repository secrets:

- `OPENAI_API_KEY` — for GPT-4.1-mini extraction
- `OCR_API_KEY` — (optional) OCR.space fallback for image-only PDFs
