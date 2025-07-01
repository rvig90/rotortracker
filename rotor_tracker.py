import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import time

# Initialize session state
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status'
    ])
    st.session_state.last_sync = "Never"
    st.session_state.editing_index = None
    st.session_state.log_expanded = True
    st.session_state.sync_status = "idle"
    st.session_state.delete_trigger = None
    st.session_state.unsaved_changes = False

# Google Sheets integration functions
def get_gsheet_connection():
    try:
        scope = ["https://spreadsheets.google.com/feeds", 
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/spreadsheets"]
        
        if isinstance(st.secrets["gcp_service_account"], str):
            creds_dict = json.loads(st.secrets["gcp_service_account"])
        else:
            creds_dict = dict(st.secrets["gcp_service_account"])
        
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Google Sheets connection failed: {str(e)}")
        return None

def load_from_gsheet():
    try:
        st.session_state.sync_status = "loading"
        client = get_gsheet_connection()
        if client:
            try:
                spreadsheet = client.open("Rotor Log")
                sheet = spreadsheet.sheet1
                records = sheet.get_all_records()
                
                if records:
                    df = pd.DataFrame(records)
                    for col in ['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status']:
                        if col not in df.columns:
                            df[col] = None if col == 'Remarks' else '' if col == 'Status' else 0
                    
                    st.session_state.data = df
                    st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    st.session_state.sync_status = "success"
                    st.session_state.unsaved_changes = False
                    st.toast("Data loaded successfully!", icon="✅")
                else:
                    st.session_state.sync_status = "success"
                    st.toast("Google Sheet is empty", icon="ℹ")
            except gspread.SpreadsheetNotFound:
                spreadsheet = client.create("Rotor Log")
                sa_email = creds.service_account_email
                spreadsheet.share(sa_email, perm_type='user', role='writer')
                st.session_state.sync_status = "success"
                st.toast("Created new Google Sheet", icon="🆕")
                st.session_state.data = pd.DataFrame(columns=[
                    'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status'
                ])
                save_to_gsheet(st.session_state.data)
                st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.session_state.sync_status = "error"
        st.error(f"Error loading data: {str(e)}")

def save_to_gsheet(df):
    try:
        client = get_gsheet_connection()
        if client:
            try:
                spreadsheet = client.open("Rotor Log")
            except gspread.SpreadsheetNotFound:
                spreadsheet = client.create("Rotor Log")
                sa_email = creds.service_account_email
                spreadsheet.share(sa_email, perm_type='user', role='writer')
                time.sleep(3)
                
            sheet = spreadsheet.sheet1
            sheet.clear()
            
            if not df.empty:
                headers = df.columns.tolist()
                data = [headers] + df.fillna('').values.tolist()
                sheet.update('A1', data)
            
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state.unsaved_changes = False
            return True
    except Exception as e:
        st.error(f"Error saving to Google Sheets: {str(e)}")
        return False
    return False

def auto_save_to_gsheet():
    if not st.session_state.data.empty or st.session_state.delete_trigger:
        if save_to_gsheet(st.session_state.data):
            st.toast("Auto-saved successfully!", icon="✅")
            st.session_state.delete_trigger = None
            return True
    return False

# UI Setup
st.set_page_config(page_title="Rotor Inventory", page_icon="🔄", layout="wide")
st.title("🔄 Rotor Inventory Management System")

# Track changes function
def track_changes():
    st.session_state.unsaved_changes = True

# Sync controls
sync_col, status_col = st.columns([1, 3])
with sync_col:
    if st.button("🔄 Sync Now"):
        load_from_gsheet()
    
    if st.button("💾 Save Now"):
        if save_to_gsheet(st.session_state.data):
            st.success("Saved successfully!")

with status_col:
    if st.session_state.sync_status == "loading":
        st.info("Syncing...")
    elif st.session_state.last_sync != "Never":
        st.caption(f"Last sync: {st.session_state.last_sync}")
    else:
        st.caption("Never synced")
    
    if st.session_state.unsaved_changes:
        st.warning("Unsaved changes!")
    
    if st.session_state.sync_status == "error":
        st.error("Sync failed")

# Entry forms
form_tabs = st.tabs(["Current", "Coming", "Pending"])

with form_tabs[0]:  # Current
    with st.form("current_form"):
        st.subheader("Add Current Movement")
        date = st.date_input("Date", value=datetime.today())
        rotor_size = st.number_input("Size (mm)", min_value=1)
        entry_type = st.selectbox("Type", ["Inward", "Outgoing"])
        quantity = st.number_input("Quantity", min_value=1)
        remarks = st.text_input("Remarks")
        
        if st.form_submit_button("Add Entry"):
            track_changes()
            new_entry = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'),
                'Size (mm)': rotor_size, 
                'Type': entry_type, 
                'Quantity': quantity, 
                'Remarks': remarks,
                'Status': 'Current'
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            if auto_save_to_gsheet():
                st.rerun()

# [Include similar forms for Coming and Pending tabs...]

# Stock Summary
st.subheader("Stock Summary")
if not st.session_state.data.empty:
    try:
        # [Include your stock summary calculations...]
        st.dataframe(st.session_state.data, use_container_width=True)
    except Exception as e:
        st.error(f"Error generating summary: {e}")
else:
    st.info("No data available")

# Movement Log
st.subheader("Movement Log")
with st.expander("View/Edit Entries"):
    if not st.session_state.data.empty:
        # [Include your movement log display code...]
        pass
    else:
        st.info("No entries to display")

# Sidebar
with st.sidebar:
    st.subheader("Controls")
    if st.button("Reset Data"):
        st.session_state.data = pd.DataFrame(columns=[
            'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status'
        ])
        st.rerun()
    
    st.divider()
    if st.session_state.unsaved_changes:
        st.error("⚠ Save your changes!")
    else:
        st.success("✓ All saved")
    
    st.caption(f"Entries: {len(st.session_state.data)}")
