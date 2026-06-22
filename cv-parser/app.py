import streamlit as st
from processor import process_all
from utils import to_excel, build_zip
from config import MAX_FILES

# ---------------------------
# UI
# ---------------------------
st.set_page_config(page_title="CV Parser ATS", layout="wide")

st.title("🚀 CV Parser – ATS Smart Version")

if "df" not in st.session_state:
    st.session_state.df = None

files = st.file_uploader(
    "Upload CVs (PDF)",
    type=["pdf"],
    accept_multiple_files=True
)

if files:
    n = len(files)
    if n > MAX_FILES:
        st.warning(f"⚠️ {n} files uploaded — limit is {MAX_FILES}. Only the first {MAX_FILES} will be processed.")
        files = files[:MAX_FILES]
        n = MAX_FILES
    else:
        st.info(f"{n} files uploaded")

    if st.button("🚀 Process CVs"):
        progress_bar = st.progress(0, text=f"0/{n} CVs processed…")

        def _on_progress(done, total):
            progress_bar.progress(done / total, text=f"{done}/{total} CVs processed…")

        st.session_state.df = process_all(files, on_progress=_on_progress)
        progress_bar.progress(1.0, text=f"{n}/{n} CVs processed")
        st.success(f"Done! Processed {n} CVs.")

# ---------------------------
# RESULTS
# ---------------------------
if st.session_state.df is not None:
    df = st.session_state.df

    edited_df = st.data_editor(df, height=500)

    st.download_button(
        "📥 Download Excel",
        data=to_excel(edited_df),
        file_name="cv_results.xlsx"
    )

    # ---------------------------
    # RENAME
    # ---------------------------
    st.subheader("📁 Rename CV Files")

    col1, col2 = st.columns(2)

    with col1:
        start_number = st.number_input("Start Number", value=1)

    with col2:
        prefix_text = st.text_input("Prefix Text", "")

    postfix = st.text_input("Postfix (optional)", "")

    if st.button("📦 Download Renamed CVs"):
        zip_path = build_zip(files, edited_df, start_number, prefix_text, postfix)

        with open(zip_path, "rb") as f:
            st.download_button(
                label="📥 Download ZIP",
                data=f,
                file_name="renamed_cvs.zip",
                mime="application/zip"
            )