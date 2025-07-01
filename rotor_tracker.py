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

# Google Sheets integration
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

# Mobile-friendly CSS
st.markdown("""
<style>
    @media (max-width: 768px) {
        .mobile-table {
            font-size: 14px;
        }
        .mobile-table th, .mobile-table td {
            padding: 6px 8px;
        }
    }
    .mobile-table {
        width: 100%;
        overflow-x: auto;
    }
</style>
""", unsafe_allow_html=True)

# UI Setup
st.set_page_config(page_title="Rotor Inventory", page_icon="🔄", layout="wide")
st.title("🔄 Rotor Inventory Management System")

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

# Movement Log - Tabular format with edit/delete
st.subheader("📋 Movement Log")
with st.expander("View/Edit Entries", expanded=st.session_state.log_expanded):
    if not st.session_state.data.empty:
        try:
            # Search functionality
            search_col1, search_col2 = st.columns(2)
            with search_col1:
                date_query = st.date_input("📅 Filter by date", value=None)
            with search_col2:
                text_query = st.text_input("🔍 Search text", placeholder="Search any field...")
            
            # Filter data
            search_df = st.session_state.data.copy()
            search_df['Date'] = pd.to_datetime(search_df['Date'])
            
            if date_query:
                date_query = pd.to_datetime(date_query)
                search_df = search_df[search_df['Date'].dt.date == date_query.date()]
            
            if text_query:
                search_df = search_df[
                    search_df['Size (mm)'].astype(str).str.contains(text_query, case=False) |
                    search_df['Type'].str.contains(text_query, case=False) |
                    search_df['Quantity'].astype(str).str.contains(text_query, case=False) |
                    search_df['Remarks'].str.contains(text_query, case=False) |
                    search_df['Status'].str.contains(text_query, case=False)
                ]
            
            search_df = search_df.sort_values('Date', ascending=False)
            
            if not search_df.empty:
                # Display table with action buttons
                st.markdown('<div class="mobile-table">', unsafe_allow_html=True)
                
                # Create a custom table using columns
                cols = st.columns([3, 1.5, 1.5, 1.5, 3, 1.5, 0.8, 0.8])
                headers = ["Date", "Size (mm)", "Type", "Qty", "Remarks", "Status", "Edit", "Delete"]
                for i, header in enumerate(headers):
                    cols[i].write(f"{header}")
                
                for idx, row in search_df.iterrows():
                    cols = st.columns([3, 1.5, 1.5, 1.5, 3, 1.5, 0.8, 0.8])
                    
                    # Data columns
                    cols[0].write(row['Date'].strftime('%Y-%m-%d') if pd.notna(row['Date']) else "")
                    cols[1].write(row['Size (mm)'])
                    cols[2].write(row['Type'])
                    cols[3].write(row['Quantity'])
                    cols[4].write(row['Remarks'])
                    cols[5].write(row['Status'])
                    
                    # Action buttons
                    with cols[6]:
                        if st.button("✏", key=f"edit_{idx}"):
                            st.session_state.editing_index = idx
                    with cols[7]:
                        if st.button("❌", key=f"del_{idx}"):
                            st.session_state.delete_trigger = idx
                            st.session_state.unsaved_changes = True
                
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Edit form
                if st.session_state.editing_index is not None:
                    with st.form(key="edit_form"):
                        row = st.session_state.data.loc[st.session_state.editing_index]
                        st.subheader("Edit Entry")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            new_date = st.date_input(
                                "Date",
                                value=datetime.strptime(row['Date'], '%Y-%m-%d').date() if pd.notna(row['Date']) else datetime.today()
                            )
                            new_size = st.number_input(
                                "Size (mm)",
                                value=row['Size (mm)'],
                                min_value=1
                            )
                        with col2:
                            new_type = st.selectbox(
                                "Type",
                                ["Inward", "Outgoing"],
                                index=0 if row['Type'] == 'Inward' else 1
                            )
                            new_qty = st.number_input(
                                "Quantity",
                                value=row['Quantity'],
                                min_value=1
                            )
                        
                        new_remarks = st.text_input("Remarks", value=row['Remarks'])
                        new_status = st.selectbox(
                            "Status",
                            ["Current", "Pending", "Future"],
                            index=["Current", "Pending", "Future"].index(row['Status'])
                        )
                        
                        save_col, cancel_col = st.columns(2)
                        with save_col:
                            if st.form_submit_button("💾 Save Changes"):
                                st.session_state.data.at[st.session_state.editing_index, 'Date'] = new_date.strftime('%Y-%m-%d')
                                st.session_state.data.at[st.session_state.editing_index, 'Size (mm)'] = new_size
                                st.session_state.data.at[st.session_state.editing_index, 'Type'] = new_type
                                st.session_state.data.at[st.session_state.editing_index, 'Quantity'] = new_qty
                                st.session_state.data.at[st.session_state.editing_index, 'Remarks'] = new_remarks
                                st.session_state.data.at[st.session_state.editing_index, 'Status'] = new_status
                                if auto_save_to_gsheet():
                                    st.success("Changes saved!")
                                st.session_state.editing_index = None
                                st.rerun()
                        with cancel_col:
                            if st.form_submit_button("❌ Cancel"):
                                st.session_state.editing_index = None
                                st.rerun()
                
                # Handle deletion
                if st.session_state.get('delete_trigger') is not None:
                    st.session_state.data = st.session_state.data.drop(st.session_state.delete_trigger)
                    st.session_state.data = st.session_state.data.reset_index(drop=True)
                    if auto_save_to_gsheet():
                        st.success("Entry deleted!")
                    st.session_state.delete_trigger = None
                    st.rerun()
            else:
                st.info("No entries match your search")
        except Exception as e:
            st.error(f"Error displaying log: {str(e)}")
    else:
        st.info("No entries to display")

# [Rest of your existing code for forms, stock summary, etc.]
# [Keep all the remaining code from previous implementation...]
# Status footer
if st.session_state.last_sync != "Never":
    st.caption(f"Last synced: {st.session_state.last_sync}")

# Sidebar with save reminder
with st.sidebar:
    st.subheader("System Controls")
    if st.button("🔄 Reset Session Data", help="Clear all local data"):
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
    
    st.caption(f"Entries in system: *{len(st.session_state.data)}*")
    
    if st.secrets.get("DEBUG_MODE", False):
        st.divider()
        st.subheader("Debug Information")
        st.caption(f"Google Sheets connection: {'Working' if get_gsheet_connection() else 'Failed'}")
        st.caption(f"Sync status: {st.session_state.sync_status}")
        st.caption(f"Data shape: {st.session_state.data.shape}")
        st.caption(f"Delete trigger: {st.session_state.get('delete_trigger')}")
