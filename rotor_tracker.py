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
    st.session_state.unsaved_changes = False  # Track unsaved changes

# Improved Google Sheets integration
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
        st.error("Please verify your service account credentials in secrets.toml")
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
                    st.toast("Data loaded successfully from Google Sheets!", icon="✅")
                else:
                    st.session_state.sync_status = "success"
                    st.toast("Google Sheet exists but contains no data", icon="ℹ")
            except gspread.SpreadsheetNotFound:
                spreadsheet = client.create("Rotor Log")
                sa_email = creds.service_account_email
                spreadsheet.share(sa_email, perm_type='user', role='writer')
                st.session_state.sync_status = "success"
                st.toast("Created new Google Sheet 'Rotor Log'", icon="🆕")
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
            st.toast("Auto-saved to Google Sheets", icon="✅")
            st.session_state.delete_trigger = None
            return True
    return False

# JavaScript to detect browser/tab close
close_warning_js = """
<script>
window.addEventListener('beforeunload', function(e) {
    if(%s) {
        e.preventDefault();
        e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
    }
});
</script>
""" % ("true" if st.session_state.get("unsaved_changes", False) else "false")

# Inject the JavaScript
st.components.v1.html(close_warning_js, height=0)

# UI Setup
st.set_page_config(page_title="Rotor Inventory", page_icon="🔄", layout="wide")
st.title("🔄 Rotor Inventory Management System")

# Sync status and buttons
sync_col, status_col = st.columns([1, 3])
with sync_col:
    sync_btn = st.button("🔄 Sync Now", help="Load latest data from Google Sheets")
    if sync_btn:
        load_from_gsheet()
    
    save_btn = st.button("💾 Save to Google Sheets", help="Save current data to Google Sheets")
    if save_btn:
        if save_to_gsheet(st.session_state.data):
            st.success("Data saved successfully to Google Sheets!")

with status_col:
    if st.session_state.sync_status == "loading":
        st.info("Syncing data from Google Sheets...")
    elif st.session_state.last_sync != "Never":
        st.caption(f"Last synced: {st.session_state.last_sync}")
    else:
        st.caption("Never synced")
    
    if st.session_state.unsaved_changes:
        st.warning("You have unsaved changes!")
    
    if st.session_state.sync_status == "error":
        st.error("Sync failed. Please check connection and try again.")

# Entry forms (all existing form code remains the same)
# [Previous form code here...]

# Stock Summary (existing code remains the same)
# [Previous stock summary code here...]

# Movement Log with deletion handling
with st.expander("📋 View/Edit Entries", expanded=st.session_state.log_expanded):
    if not st.session_state.data.empty:
        try:
            search_query = st.text_input("🔍 Search entries", placeholder="Search by size, remarks, or status...")
            
            if search_query:
                search_df = st.session_state.data[
                    st.session_state.data['Size (mm)'].astype(str).str.contains(search_query) |
                    st.session_state.data['Remarks'].str.contains(search_query, case=False) |
                    st.session_state.data['Status'].str.contains(search_query, case=False)
                ]
            else:
                search_df = st.session_state.data
            
            search_df = search_df.sort_values('Date', ascending=False)
            
            if not search_df.empty:
                for idx, row in search_df.iterrows():
                    st.markdown("---")
                    
                    cols = st.columns([8, 1, 1])
                    with cols[0]:
                        st.dataframe(pd.DataFrame(row).T, use_container_width=True, hide_index=True)
                    
                    with cols[1]:
                        if st.button("✏", key=f"edit_{idx}"):
                            st.session_state.editing_index = idx
                    
                    with cols[2]:
                        if st.button("❌", key=f"del_{idx}"):
                            st.session_state.delete_trigger = idx
                            st.session_state.unsaved_changes = True
                    
                    if st.session_state.get('delete_trigger') == idx:
                        st.session_state.data = st.session_state.data.drop(idx).reset_index(drop=True)
                        if auto_save_to_gsheet():
                            st.success("Entry deleted and saved!")
                        st.session_state.delete_trigger = None
                        st.rerun()
                    
                    # [Existing edit form code...]
                
                st.markdown("---")
            else:
                st.info("No entries match your search")
        except Exception as e:
            st.error(f"Error displaying log: {e}")
    else:
        st.info("No entries to display")

# Status footer
if st.session_state.last_sync != "Never":
    st.caption(f"Last synced: {st.session_state.last_sync}")

# Sidebar with save reminder
with st.sidebar:
    st.subheader("System Controls")
    if st.button("🔄 Reset Session Data"):
        st.session_state.data = pd.DataFrame(columns=[
            'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status'
        ])
        st.session_state.last_sync = "Never"
        st.session_state.editing_index = None
        st.rerun()
    
    st.divider()
    st.caption("*Data Safety Notice:*")
    
    if st.session_state.unsaved_changes:
        st.error("⚠ You have unsaved changes!")
        st.caption("Please save to Google Sheets before closing the app.")
    else:
        st.success("✓ All changes saved")
    
    st.caption("Entries in system: *{}*".format(len(st.session_state.data)))
    
    if st.secrets.get("DEBUG_MODE", False):
        st.divider()
        st.subheader("Debug Information")
        st.caption(f"Unsaved changes: {st.session_state.unsaved_changes}")
        st.caption(f"Last sync: {st.session_state.last_sync}")

# Set unsaved changes flag when modifying data
def track_changes():
    st.session_state.unsaved_changes = True

# Attach track_changes to all form submit buttons
st.session_state.get("current_form_submit", st.empty()).on_submit(track_changes)
st.session_state.get("future_form_submit", st.empty()).on_submit(track_changes)
st.session_state.get("pending_form_submit", st.empty()).on_submit(track_changes)
