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
st.subheader("📋 Movement Log")
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

    # Filter logic
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

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

    if selected_date:
        df = df[df['Date'] == pd.to_datetime(selected_date)]

    if df.empty:
        st.warning("⚠ No matching entries found. Try adjusting filters.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("ℹ No entries available yet.")

# ====== SYNC TIMESTAMP ======
if st.session_state.last_sync != "Never":
    st.caption(f"🕒 Last synced: {st.session_state.last_sync}")
