import streamlit as st
import asyncio
from processor import process_all
from utils import to_excel, build_zip

# ---------------------------
# UI
# ---------------------------
st.set_page_config(page_title="CV Parser ATS", layout="wide")

st.title("🚀 CV Parser – ATS Smart Version")

files = st.file_uploader(
    "Upload CVs (PDF)",
    type=["pdf"],
    accept_multiple_files=True
)

if "df" not in st.session_state:
    st.session_state.df = None

if files:
    st.info(f"{len(files)} files uploaded")

    if st.button("🚀 Process CVs"):
        with st.spinner("Processing..."):
            df = asyncio.run(process_all(files))

        st.session_state.df = df
        st.success("Done!")

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
        zip_file = build_zip(files, edited_df, start_number, prefix_text, postfix)

        st.download_button(
            label="📥 Download ZIP",
            data=zip_file,
            file_name="renamed_cvs.zip",
            mime="application/zip"
        )