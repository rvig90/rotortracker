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
    except gspread.exceptions.APIError as e:
        st.session_state.sync_status = "error"
        st.error(f"Google API Error: {str(e)}")
        st.error("Please check your Google Sheets API quota and permissions")
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
    except gspread.exceptions.APIError as e:
        error_msg = str(e)
        st.error(f"Google API Error: {error_msg}")
        if "quota" in error_msg.lower():
            st.error("Google Sheets API quota exceeded - try again later")
        return False
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

# Track changes function
def track_changes():
    st.session_state.unsaved_changes = True

# Sync status and buttons
sync_col, status_col = st.columns([1, 3])
with sync_col:
    sync_btn = st.button("🔄 Sync Now", help="Load latest data from Google Sheets")
    if sync_btn:
        load_from_gsheet()
    
    save_btn = st.button("💾 Save to Google Sheets", help="Save current data to Google Sheets")
    if save_btn:
        if save_to_gsheet(st.session_state.data):
            st.toast("Data saved successfully to Google Sheets!", icon="✅")

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

# Entry forms
form_tabs = st.tabs(["Current Movement", "Coming Rotors", "Pending Outgoing"])

with form_tabs[0]:  # Current Movement
    with st.form("current_form"):
        st.subheader("➕ Add Current Movement")
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Date", value=datetime.today())
            rotor_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, format="%d")
        with col2:
            entry_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"])
            quantity = st.number_input("🔢 Quantity", min_value=1, step=1, format="%d")
        remarks = st.text_input("📝 Remarks")
        
        submitted = st.form_submit_button("➕ Add Entry", use_container_width=True)
        if submitted:
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
                st.success("Entry added and saved!")
            st.rerun()

with form_tabs[1]:  # Coming Rotors
    with st.form("future_form"):
        st.subheader("➕ Add Coming Rotors")
        col1, col2 = st.columns(2)
        with col1:
            future_date = st.date_input("📅 Expected Date", min_value=datetime.today() + timedelta(days=1))
            future_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, format="%d")
        with col2:
            future_qty = st.number_input("🔢 Quantity", min_value=1, step=1, format="%d")
            future_remarks = st.text_input("📝 Remarks")
        
        submitted = st.form_submit_button("➕ Add Coming Rotors", use_container_width=True)
        if submitted:
            track_changes()
            new_entry = pd.DataFrame([{
                'Date': future_date.strftime('%Y-%m-%d'),
                'Size (mm)': future_size, 
                'Type': 'Inward', 
                'Quantity': future_qty, 
                'Remarks': future_remarks,
                'Status': 'Future'
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            if auto_save_to_gsheet():
                st.success("Entry added and saved!")
            st.rerun()

with form_tabs[2]:  # Pending Outgoing
    with st.form("pending_form"):
        st.subheader("➕ Add Pending Outgoing")
        col1, col2 = st.columns(2)
        with col1:
            pending_date = st.date_input("📅 Expected Ship Date", value=datetime.today())
            pending_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, format="%d", key="pending_size")
        with col2:
            pending_qty = st.number_input("🔢 Quantity", min_value=1, step=1, format="%d", key="pending_qty")
            pending_remarks = st.text_input("📝 Remarks", key="pending_remarks")
        
        submitted = st.form_submit_button("➕ Add Pending Outgoing", use_container_width=True)
        if submitted:
            track_changes()
            new_entry = pd.DataFrame([{
                'Date': pending_date.strftime('%Y-%m-%d'),
                'Size (mm)': pending_size, 
                'Type': 'Outgoing', 
                'Quantity': pending_qty, 
                'Remarks': f"[PENDING] {pending_remarks}",
                'Status': 'Pending'
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            if auto_save_to_gsheet():
                st.success("Entry added and saved!")
            st.rerun()

# Stock Summary
st.subheader("📊 Current Stock Summary")
if not st.session_state.data.empty:
    try:
        # Current inward stock (positive additions)
        current_inward = st.session_state.data[
            (st.session_state.data['Status'] == 'Current') & 
            (st.session_state.data['Type'] == 'Inward')
        ]
        inward_stock = current_inward.groupby('Size (mm)')['Quantity'].sum().reset_index()
        
        # Current outgoing (immediate deductions - negative values)
        current_outgoing = st.session_state.data[
            (st.session_state.data['Status'] == 'Current') & 
            (st.session_state.data['Type'] == 'Outgoing')
        ]
        outgoing = current_outgoing.groupby('Size (mm)')['Quantity'].sum().reset_index()
        outgoing['Quantity'] = -outgoing['Quantity']  # Convert to negative for subtraction
        
        # Pending outgoing (future deductions - shown separately)
        pending_outgoing = st.session_state.data[
            (st.session_state.data['Status'] == 'Pending') & 
            (st.session_state.data['Type'] == 'Outgoing')
        ]
        pending = pending_outgoing.groupby('Size (mm)')['Quantity'].sum().reset_index()
        
        # Coming rotors (future additions)
        future = st.session_state.data[st.session_state.data['Status'] == 'Future']
        coming = future.groupby('Size (mm)')['Quantity'].sum().reset_index()
        
        # Combine all data with explicit column naming
        stock = pd.concat([
            inward_stock.assign(Type='Inward'),
            outgoing.assign(Type='Outgoing')
        ])
        
        # Calculate net current stock (inward minus outgoing)
        current_stock = stock.groupby('Size (mm)')['Quantity'].sum().reset_index()
        current_stock = current_stock.rename(columns={'Quantity': 'Current Stock'})
        
        # Get pending and coming quantities
        pending = pending.rename(columns={'Quantity': 'Pending Outgoing'})
        coming = coming.rename(columns={'Quantity': 'Coming Rotors'})
        
        # Merge all data
        combined = current_stock.merge(
            pending, on='Size (mm)', how='left'
        ).merge(
            coming, on='Size (mm)', how='left'
        ).fillna(0)
        
        # Add outgoing quantities for reference (absolute values)
        outgoing_ref = current_outgoing.groupby('Size (mm)')['Quantity'].sum().reset_index()
        outgoing_ref = outgoing_ref.rename(columns={'Quantity': 'Current Outgoing'})
        combined = combined.merge(outgoing_ref, on='Size (mm)', how='left').fillna(0)
        
        # Filter out sizes with zero stock and no activity
        combined = combined[
            (combined['Current Stock'] != 0) | 
            (combined['Pending Outgoing'] != 0) | 
            (combined['Coming Rotors'] != 0)
        ]
        
        # Display
        if not combined.empty:
            st.dataframe(
                combined[['Size (mm)', 'Current Stock', 'Current Outgoing', 'Pending Outgoing', 'Coming Rotors']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No active stock items to display")
        
    except Exception as e:
        st.error(f"Error generating summary: {str(e)}")
else:
    st.info("No data available yet")

# Movement Log - Restored to original table format
# [Previous imports and session state initialization remain the same...]

# Movement Log - Mobile Responsive Table
st.subheader("📋 Movement Log")
with st.expander("View/Edit Entries", expanded=st.session_state.log_expanded):
    if not st.session_state.data.empty:
        try:
            # Search functionality
            search_query = st.text_input("🔍 Search entries", 
                                       placeholder="Search by size, remarks, or status...",
                                       key="log_search")
            
            # Filter and sort data
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
                # Mobile-responsive table using columns
                for idx, row in search_df.iterrows():
                    cols = st.columns([2, 1, 1, 1, 0.5, 0.5])
                    with cols[0]:
                        st.markdown(f"{row['Date']}**  \n{row['Remarks']}")
                    with cols[1]:
                        st.markdown(f"{row['Size (mm)']}mm**")
                    with cols[2]:
                        st.markdown(f"{row['Type']}")
                    with cols[3]:
                        st.markdown(f"{row['Quantity']}")
                    with cols[4]:
                        if st.button("✏", key=f"edit_{idx}"):
                            st.session_state.editing_index = idx
                    with cols[5]:
                        if st.button("❌", key=f"del_{idx}"):
                            st.session_state.delete_trigger = idx
                            st.session_state.unsaved_changes = True
                    
                    st.markdown("---")  # Divider between entries
                
                # Edit form (appears when edit button is clicked)
                if st.session_state.editing_index is not None:
                    with st.form(key="edit_form"):
                        row = st.session_state.data.loc[st.session_state.editing_index]
                        st.subheader("Edit Entry")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            new_date = st.date_input(
                                "Date",
                                value=datetime.strptime(row['Date'], '%Y-%m-%d').date()
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
                                    st.success("Changes saved successfully!")
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
                        st.success("Entry deleted successfully!")
                    st.session_state.delete_trigger = None
                    st.rerun()
            else:
                st.info("No entries match your search")
        except Exception as e:
            st.error(f"Error displaying log: {str(e)}")
    else:
        st.info("No entries to display")

# [Rest of the code remains unchanged...]
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
