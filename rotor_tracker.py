import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ====== SESSION STATE INITIALIZATION ======
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending'
    ])
    st.session_state.last_sync = "Never"
    st.session_state.editing = None

if 'first_load_done' not in st.session_state:
    st.session_state.first_load_done = False

# ====== GOOGLE SHEETS INTEGRATION ======
def get_gsheet_connection():
    try:
        scope = ["https://spreadsheets.google.com/feeds", 
                 "https://www.googleapis.com/auth/drive"]
        
        if isinstance(st.secrets["gcp_service_account"], str):
            creds_dict = json.loads(st.secrets["gcp_service_account"])
        else:
            creds_dict = dict(st.secrets["gcp_service_account"])
        
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Rotor Log").sheet1
    except Exception as e:
        st.error(f"Google Sheets connection failed: {str(e)}")
        return None

def load_from_gsheet():
    try:
        sheet = get_gsheet_connection()
        if sheet:
            records = sheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
                if 'Status' not in df.columns:
                    df['Status'] = 'Current'
                if 'Pending' not in df.columns:
                    df['Pending'] = False
                df['Pending'] = df['Pending'].apply(lambda x: True if str(x).strip().lower() == 'true' else False)
                st.session_state.data = df
                st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success("✅ Data loaded from Google Sheets")
            else:
                st.info("No data found in Google Sheet")
    except Exception as e:
        st.error(f"Error loading data: {e}")

def save_to_backup_sheet(df):
    try:
        spreadsheet = get_gsheet_connection().spreadsheet
        try:
            backup_sheet = spreadsheet.worksheet("Backup")
        except gspread.exceptions.WorksheetNotFound:
            backup_sheet = spreadsheet.add_worksheet(title="Backup", rows="1000", cols="20")

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        df.insert(0, 'Backup Time', timestamp)
        records = [df.columns.tolist()] + df.values.tolist()
        backup_sheet.append_rows(records)
    except Exception as e:
        st.warning(f"Backup failed: {e}")

def auto_save_to_gsheet():
    try:
        sheet = get_gsheet_connection()
        if sheet:
            sheet.clear()

            if not st.session_state.data.empty:
                df = st.session_state.data.copy()
                df['Pending'] = df['Pending'].apply(lambda x: "TRUE" if x else "FALSE")
                records = [df.columns.tolist()] + df.values.tolist()
                sheet.update(records)

                # ✅ Backup to backup sheet
                save_to_backup_sheet(df.copy())

            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"Auto-save failed: {e}")

# ====== AUTO-LOAD DATA ON FIRST RUN ======
if not st.session_state.first_load_done:
    load_from_gsheet()
    st.session_state.first_load_done = True

# ====== SYNC BUTTONS ======
col_sync, col_saved = st.columns(2)

with col_sync:
    if st.button("🔄 Sync Now", help="Save current data to Google Sheets"):
        auto_save_to_gsheet()

with col_saved:
    if st.button("📂 Load Previously Saved", help="Load the last saved version from Google Sheets"):
        load_from_gsheet()
        st.rerun()
