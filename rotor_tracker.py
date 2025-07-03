import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ====== INITIALIZE SESSION STATE ======
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending'
    ])
    st.session_state.last_sync = "Never"
    st.session_state.editing = None
    st.session_state.loaded = False

# ====== NORMALIZE PENDING COLUMN ======
def normalize_pending_column(df):
    df['Pending'] = df['Pending'].apply(
        lambda x: str(x).lower() == 'true' if isinstance(x, str) else bool(x)
    )
    return df

# ====== GOOGLE SHEETS SETUP ======
def get_gsheet_connection():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(st.secrets["gcp_service_account"]) if isinstance(st.secrets["gcp_service_account"], str) else dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Rotor Log").sheet1
    except Exception as e:
        st.error(f"Google Sheets connection failed: {str(e)}")
        return None

# ====== LOAD DATA FROM GOOGLE SHEETS ======
def load_from_gsheet():
    try:
        sheet = get_gsheet_connection()
        if sheet:
            records = sheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
                if 'Status' not in df.columns: df['Status'] = 'Current'
                if 'Pending' not in df.columns: df['Pending'] = False
                df = normalize_pending_column(df)
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                st.session_state.data = df
                st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success("✅ Data loaded from Google Sheet")
            else:
                st.info("ℹ No records found in Google Sheet.")
    except Exception as e:
        st.error(f"❌ Error loading from Google Sheet: {e}")

# ====== AUTOLOAD ON FIRST RUN ======
if not st.session_state.loaded:
    load_from_gsheet()
    st.session_state.loaded = True

# ====== AUTO SAVE TO GOOGLE SHEETS ======
def auto_save_to_gsheet():
    try:
        sheet = get_gsheet_connection()
        if sheet:
            sheet.clear()
            df = st.session_state.data.copy()
            if not df.empty:
                df['Pending'] = df['Pending'].apply(lambda x: "TRUE" if x else "FALSE")
                df['Date'] = df['Date'].astype(str)
                expected_cols = ['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending']
                for col in expected_cols:
                    if col not in df.columns:
                        df[col] = ""
                df = df[expected_cols]
                records = [df.columns.tolist()] + df.values.tolist()
                sheet.update('A1', records)
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"❌ Auto-save failed: {e}")

# ====== MANUAL SYNC BUTTON ======
if st.button("🔄 Sync Now"):
    load_from_gsheet()

# ====== DEBUG PREVIEW ======
with st.expander("🐞 Raw Data Preview"):
    st.dataframe(st.session_state.data)

# ====== MOVEMENT LOG ======
# ====== MOVEMENT LOG ======
with st.expander("📋 View Movement Log", expanded=True):
    if not st.session_state.data.empty:
        df = st.session_state.data.copy()

        st.markdown("### 🔍 Filter Movement Log")
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.selectbox("📂 Status", ["All", "Current", "Future"])
        with col2:
            size_filter = st.multiselect("📐 Size (mm)", sorted(df['Size (mm)'].dropna().unique()))
        with col3:
            pending_filter = st.selectbox("❗ Pending", ["All", "Yes", "No"])

        remark_search = st.text_input("📝 Search Remarks")
        selected_date = st.date_input("📅 Filter by Specific Date (optional)")

        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

        # Optional date filter
        if selected_date != datetime.today().date():
            df = df[df['Date'] == pd.to_datetime(selected_date)]

        if status_filter != "All":
            df = df[df["Status"] == status_filter]
        if size_filter:
            df = df[df["Size (mm)"].isin(size_filter)]
        if pending_filter == "Yes":
            df = df[df["Pending"] == True]
        elif pending_filter == "No":
            df = df[df["Pending"] == False]
        if remark_search:
            df = df[df["Remarks"].str.contains(remark_search, case=False)]

        # Show filtered table for debug
        st.markdown("### 🛠 Filtered Log Preview")
        st.dataframe(df, use_container_width=True)

        for i, row in df.iterrows():
            actual_idx = st.session_state.data[
                (st.session_state.data['Date'] == row['Date']) &
                (st.session_state.data['Size (mm)'] == row['Size (mm)']) &
                (st.session_state.data['Type'] == row['Type']) &
                (st.session_state.data['Quantity'] == row['Quantity']) &
                (st.session_state.data['Remarks'] == row['Remarks']) &
                (st.session_state.data['Status'] == row['Status']) &
                (st.session_state.data['Pending'] == row['Pending'])
            ].index
            if len(actual_idx) == 0:
                continue
            actual_idx = actual_idx[0]

            if st.session_state.editing == actual_idx:
                with st.form(f"edit_{actual_idx}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        edit_date = st.date_input("📅 Date", value=pd.to_datetime(row["Date"]), key=f"date_{actual_idx}")
                        edit_size = st.number_input("📐 Size (mm)", value=int(row["Size (mm)"]), key=f"size_{actual_idx}")
                    with col2:
                        edit_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"], index=0 if row["Type"] == "Inward" else 1, key=f"type_{actual_idx}")
                        edit_qty = st.number_input("🔢 Quantity", value=int(row["Quantity"]), key=f"qty_{actual_idx}")
                    edit_remarks = st.text_input("📝 Remarks", value=row["Remarks"], key=f"rem_{actual_idx}")
                    edit_status = st.selectbox("📂 Status", ["Current", "Future"], index=0 if row["Status"] == "Current" else 1, key=f"status_{actual_idx}")
                    edit_pending = st.checkbox("❗ Pending", value=row["Pending"], key=f"pend_{actual_idx}")
                    colA, colB = st.columns(2)
                    with colA:
                        if st.form_submit_button("💾 Save"):
                            st.session_state.data.at[actual_idx, "Date"] = edit_date.strftime('%Y-%m-%d')
                            st.session_state.data.at[actual_idx, "Size (mm)"] = edit_size
                            st.session_state.data.at[actual_idx, "Type"] = edit_type
                            st.session_state.data.at[actual_idx, "Quantity"] = edit_qty
                            st.session_state.data.at[actual_idx, "Remarks"] = edit_remarks
                            st.session_state.data.at[actual_idx, "Status"] = edit_status
                            st.session_state.data.at[actual_idx, "Pending"] = edit_pending
                            st.session_state.editing = None
                            auto_save_to_gsheet()
                            st.rerun()
                    with colB:
                        if st.form_submit_button("❌ Cancel"):
                            st.session_state.editing = None
                            st.rerun()
            else:
                col1, col2 = st.columns([10, 1])
                with col1:
                    st.dataframe(pd.DataFrame([{
                        "Date": row["Date"],
                        "Size (mm)": row["Size (mm)"],
                        "Type": row["Type"],
                        "Quantity": row["Quantity"],
                        "Remarks": row["Remarks"],
                        "Status": row["Status"],
                        "Pending": "Yes" if row["Pending"] else "No"
                    }]), hide_index=True, use_container_width=True)
                with col2:
                    if st.button("✏", key=f"edit_{actual_idx}"):
                        st.session_state.editing = actual_idx
                    if st.button("❌", key=f"del_{actual_idx}"):
                        st.session_state.data = st.session_state.data.drop(actual_idx).reset_index(drop=True)
                        auto_save_to_gsheet()
                        st.rerun()
# ====== SYNC TIMESTAMP ======
if st.session_state.last_sync != "Never":
    st.caption(f"🕒 Last synced: {st.session_state.last_sync}")
