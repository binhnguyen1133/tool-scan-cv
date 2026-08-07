import json
from datetime import datetime

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode

from processor import process_all
from utils import to_excel, build_zip
from config import MAX_FILES, load_channels, save_channels

# ---------------------------
# UI
# ---------------------------
st.set_page_config(page_title="CV Parser ATS", layout="wide")

st.title("🚀 CV Parser – ATS Smart Version")

if "df" not in st.session_state:
    st.session_state.df = None

# Live channel taxonomy (reloaded each rerun so edits in "Update Channel" propagate)
channels = load_channels()
rec_options = list(channels.keys())
all_names = sorted({n for names in channels.values() for n in names})

# ---------------------------
# UPDATE CHANNEL
# ---------------------------
with st.expander("⚙️ Update Channel (Rec_Channel ↔ Name_Channel mapping)"):
    st.caption("Thêm / sửa / xóa các cặp (Rec_Channel, Name_Channel). Sau khi Save, các dropdown ở bảng chính sẽ tự cập nhật.")

    channel_pairs = [
        {"Rec_Channel": rec, "Name_Channel": name}
        for rec, names in channels.items()
        for name in names
    ]
    channel_df = pd.DataFrame(channel_pairs, columns=["Rec_Channel", "Name_Channel"])

    edited_channels = st.data_editor(
        channel_df,
        num_rows="dynamic",
        width='stretch',
        key="channel_editor",
        column_config={
            "Rec_Channel": st.column_config.TextColumn("Rec_Channel", required=True),
            "Name_Channel": st.column_config.TextColumn("Name_Channel", required=True),
        },
    )

    save_col, reset_col = st.columns([1, 1])
    with save_col:
        if st.button("💾 Save Channel Data", type="primary"):
            new_channels: dict[str, list[str]] = {}
            for _, row in edited_channels.iterrows():
                rec = str(row.get("Rec_Channel", "")).strip()
                name = str(row.get("Name_Channel", "")).strip()
                if not rec or not name:
                    continue
                bucket = new_channels.setdefault(rec, [])
                if name not in bucket:
                    bucket.append(name)
            if not new_channels:
                st.error("Ít nhất phải có 1 cặp Rec_Channel / Name_Channel hợp lệ.")
            else:
                save_channels(new_channels)
                st.session_state.grid_version = st.session_state.get("grid_version", 0) + 1
                st.success(f"Đã lưu {sum(len(v) for v in new_channels.values())} cặp thuộc {len(new_channels)} Rec_Channel.")
                st.rerun()
    with reset_col:
        if st.button("↩️ Reset về default"):
            from config import CHANNEL_DATA_DEFAULT
            save_channels({k: list(v) for k, v in CHANNEL_DATA_DEFAULT.items()})
            st.session_state.grid_version = st.session_state.get("grid_version", 0) + 1
            st.success("Đã reset về default.")
            st.rerun()

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

    if "MR_code" not in df.columns:
        df["MR_code"] = st.session_state.get("mr_code_input", "")
    if "Rec_Channel" not in df.columns:
        df["Rec_Channel"] = st.session_state.get("rec_channel_input", "")
    if "Name_Channel" not in df.columns:
        df["Name_Channel"] = st.session_state.get("name_channel_input", "")
    if "Input_date" not in df.columns:
        df["Input_date"] = datetime.now().strftime("%d-%b-%Y")
    desired_order = ["File Name", "Name", "Name (No Accent)", "Phone", "Email", "Input_date", "MR_code", "Rec_Channel", "Name_Channel"]
    df = df[[c for c in desired_order if c in df.columns] + [c for c in df.columns if c not in desired_order]]
    st.session_state.df = df

    channel_map_json = json.dumps(channels)
    all_names_json = json.dumps(all_names)

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(editable=True, resizable=True, sortable=False, filter=False)

    date_cell_editor = JsCode(
        """
        class DateCellEditor {
            init(params) {
                const months = {Jan:'01',Feb:'02',Mar:'03',Apr:'04',May:'05',Jun:'06',
                                Jul:'07',Aug:'08',Sep:'09',Oct:'10',Nov:'11',Dec:'12'};
                this.eInput = document.createElement('input');
                this.eInput.type = 'date';
                this.eInput.style.width = '100%';
                this.eInput.style.height = '100%';
                this.eInput.style.border = 'none';
                this.eInput.style.outline = 'none';
                if (params.value) {
                    const parts = String(params.value).split('-');
                    if (parts.length === 3 && months[parts[1]]) {
                        this.eInput.value = parts[2] + '-' + months[parts[1]] + '-' + parts[0].padStart(2,'0');
                    }
                }
            }
            getGui() { return this.eInput; }
            afterGuiAttached() {
                this.eInput.focus();
                if (this.eInput.showPicker) { try { this.eInput.showPicker(); } catch(e) {} }
            }
            getValue() {
                const v = this.eInput.value;
                if (!v) return '';
                const monthNames = ['Jan','Feb','Mar','Apr','May','Jun',
                                    'Jul','Aug','Sep','Oct','Nov','Dec'];
                const [y, m, d] = v.split('-');
                return d + '-' + monthNames[parseInt(m,10)-1] + '-' + y;
            }
            isPopup() { return false; }
        }
        """
    )
    gb.configure_column(
        "Input_date",
        cellEditor=date_cell_editor,
        editable=True,
        singleClickEdit=True,
    )

    gb.configure_column(
        "Rec_Channel",
        cellEditor="agSelectCellEditor",
        cellEditorParams={"values": [""] + rec_options},
        editable=True,
        singleClickEdit=True,
    )

    name_editor_params = JsCode(
        f"""
        function(params) {{
            const map = {channel_map_json};
            const rec = params.data.Rec_Channel;
            const all = {all_names_json};
            const values = rec && map[rec] ? map[rec] : all;
            return {{ values: [""].concat(values) }};
        }}
        """
    )
    gb.configure_column(
        "Name_Channel",
        cellEditor="agSelectCellEditor",
        cellEditorParams=name_editor_params,
        editable=True,
        singleClickEdit=True,
    )

    # When Rec_Channel changes, auto-clear Name_Channel if invalid for the new Rec_Channel
    on_cell_value_changed = JsCode(
        f"""
        function(event) {{
            if (event.colDef.field === 'Rec_Channel') {{
                const map = {channel_map_json};
                const valid = map[event.newValue] || [];
                if (event.data.Name_Channel && !valid.includes(event.data.Name_Channel)) {{
                    event.node.setDataValue('Name_Channel', '');
                }}
            }}
        }}
        """
    )
    gb.configure_grid_options(onCellValueChanged=on_cell_value_changed, stopEditingWhenCellsLoseFocus=True)

    grid_options = gb.build()

    grid_version = st.session_state.setdefault("grid_version", 0)
    response = AgGrid(
        df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.MODEL_CHANGED,
        data_return_mode=DataReturnMode.AS_INPUT,
        allow_unsafe_jscode=True,
        height=500,
        theme="streamlit",
        key=f"aggrid_{grid_version}",
        reload_data=False,
    )
    edited_df = pd.DataFrame(response["data"])
    st.session_state.df = edited_df.copy()

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

    def _bump_grid():
        st.session_state.grid_version = st.session_state.get("grid_version", 0) + 1

    def _apply_mr_code():
        if st.session_state.df is not None:
            st.session_state.df["MR_code"] = st.session_state.mr_code_input
        _bump_grid()

    def _apply_rec_channel():
        val = st.session_state.rec_channel_input
        if st.session_state.df is not None:
            st.session_state.df["Rec_Channel"] = val
        # If current Name_Channel selection is incompatible, clear it (both bulk widget and column)
        valid_names = [""] + channels.get(val, all_names)
        if st.session_state.get("name_channel_input", "") not in valid_names:
            st.session_state.name_channel_input = ""
            if st.session_state.df is not None:
                st.session_state.df["Name_Channel"] = ""
        _bump_grid()

    def _apply_name_channel():
        if st.session_state.df is not None:
            st.session_state.df["Name_Channel"] = st.session_state.name_channel_input
        _bump_grid()

    # Sanitize stale session values if the channel taxonomy changed
    if st.session_state.get("rec_channel_input") and st.session_state["rec_channel_input"] not in rec_options:
        st.session_state["rec_channel_input"] = ""
    _cur_rec = st.session_state.get("rec_channel_input", "")
    _valid_names = channels.get(_cur_rec, all_names) if _cur_rec else all_names
    if st.session_state.get("name_channel_input") and st.session_state["name_channel_input"] not in _valid_names:
        st.session_state["name_channel_input"] = ""

    mcol1, mcol2, mcol3 = st.columns(3)
    with mcol1:
        st.text_input(
            "MR_code (optional)",
            key="mr_code_input",
            on_change=_apply_mr_code,
            help="Nhập để set MR_code cho tất cả các row. Có thể chỉnh riêng từng row trong bảng.",
        )
    with mcol2:
        st.selectbox(
            "Rec_Channel (optional)",
            options=[""] + rec_options,
            key="rec_channel_input",
            on_change=_apply_rec_channel,
            help="Chọn để apply cho tất cả các row. Sẽ filter danh sách Name_Channel.",
        )
    with mcol3:
        selected_rec = st.session_state.get("rec_channel_input", "")
        name_options = [""] + (channels.get(selected_rec, all_names) if selected_rec else all_names)
        st.selectbox(
            "Name_Channel (optional)",
            options=name_options,
            key="name_channel_input",
            on_change=_apply_name_channel,
            help="Options tương ứng với Rec_Channel đã chọn. Apply cho tất cả các row.",
        )

    if st.button("📦 Download Renamed CVs"):
        zip_path = build_zip(files, edited_df, start_number, prefix_text, postfix)

        with open(zip_path, "rb") as f:
            st.download_button(
                label="📥 Download ZIP",
                data=f,
                file_name="renamed_cvs.zip",
                mime="application/zip"
            )