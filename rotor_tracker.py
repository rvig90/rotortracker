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

# Improved Google Sheets integration
def get_gsheet_connection():
    try:
        scope = ["https://spreadsheets.google.com/feeds", 
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/spreadsheets"]
        
        # Handle both string and dict credentials
        if isinstance(st.secrets["gcp_service_account"], str):
            creds_dict = json.loads(st.secrets["gcp_service_account"])
        else:
            creds_dict = dict(st.secrets["gcp_service_account"])
        
        # Properly format private key
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
            sheet = client.open("Rotor Log").sheet1
            records = sheet.get_all_records()
            
            if records:
                df = pd.DataFrame(records)
                # Ensure all required columns exist
                for col in ['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status']:
                    if col not in df.columns:
                        df[col] = None if col == 'Remarks' else '' if col == 'Status' else 0
                
                st.session_state.data = df
                st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state.sync_status = "success"
                st.toast("Data loaded successfully from Google Sheets!", icon="✅")
            else:
                st.session_state.sync_status = "success"
                st.toast("Google Sheet exists but contains no data", icon="ℹ")
    except gspread.exceptions.APIError as e:
        st.session_state.sync_status = "error"
        st.error(f"Google API Error: {str(e)}")
        st.error("Please check your Google Sheets API quota and permissions")
    except gspread.exceptions.SpreadsheetNotFound:
        st.session_state.sync_status = "error"
        st.error("Spreadsheet 'Rotor Log' not found. Please create it first.")
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
                # Create spreadsheet if it doesn't exist
                spreadsheet = client.create("Rotor Log")
                # Share with service account email for access
                client.insert_permission(spreadsheet.id, 
                                        creds_dict["client_email"], 
                                        perm_type="user", 
                                        role="writer")
                
            sheet = spreadsheet.sheet1
            
            # Clear existing data
            sheet.clear()
            
            # Prepare data for writing
            headers = df.columns.tolist()
            data = [headers] + df.fillna('').values.tolist()
            
            # Batch write all data
            sheet.update('A1', data)
            
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
    if not st.session_state.data.empty:
        if save_to_gsheet(st.session_state.data):
            st.toast("Auto-saved to Google Sheets", icon="✅")
            return True
    return False

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
            st.toast("Data saved successfully to Google Sheets!", icon="✅")

with status_col:
    if st.session_state.sync_status == "loading":
        st.info("Syncing data from Google Sheets...")
    elif st.session_state.last_sync != "Never":
        st.caption(f"Last synced: {st.session_state.last_sync}")
    else:
        st.caption("Never synced")
    
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
        
        if st.form_submit_button("➕ Add Entry", use_container_width=True):
            new_entry = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'),
                'Size (mm)': rotor_size, 
                'Type': entry_type, 
                'Quantity': quantity, 
                'Remarks': remarks,
                'Status': 'Current'  # All current movements are 'Current' status
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
        
        if st.form_submit_button("➕ Add Coming Rotors", use_container_width=True):
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
        
        if st.form_submit_button("➕ Add Pending Outgoing", use_container_width=True):
            new_entry = pd.DataFrame([{
                'Date': pending_date.strftime('%Y-%m-%d'),
                'Size (mm)': pending_size, 
                'Type': 'Outgoing', 
                'Quantity': pending_qty, 
                'Remarks': f"[PENDING] {pending_remarks}",
                'Status': 'Pending'  # Special status for pending shipments
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

# Movement Log
st.subheader("📋 Movement Log")
with st.expander("View/Edit Entries", expanded=st.session_state.log_expanded):
    if not st.session_state.data.empty:
        try:
            # Search functionality
            search_query = st.text_input("🔍 Search entries", placeholder="Search by size, remarks, or status...")
            
            # Filter data based on search
            if search_query:
                search_df = st.session_state.data[
                    st.session_state_data['Size (mm)'].astype(str).str.contains(search_query) |
                    st.session_state_data['Remarks'].str.contains(search_query, case=False) |
                    st.session_state_data['Status'].str.contains(search_query, case=False)
                ]
            else:
                search_df = st.session_state.data
            
            # Sort by date descending
            search_df = search_df.sort_values('Date', ascending=False)
            
            if not search_df.empty:
                for idx, row in search_df.iterrows():
                    st.markdown("---")
                    
                    # Display entry
                    cols = st.columns([8, 1, 1])
                    with cols[0]:
                        st.dataframe(
                            pd.DataFrame(row).T,
                            use_container_width=True,
                            hide_index=True
                        )
                    
                    # Edit button
                    with cols[1]:
                        if st.button("✏", key=f"edit_{idx}"):
                            st.session_state.editing_index = idx
                    
                    # Delete button
                    with cols[2]:
                        if st.button("❌", key=f"del_{idx}"):
                            st.session_state.data = st.session_state.data.drop(idx)
                            if auto_save_to_gsheet():
                                st.success("Entry deleted and saved!")
                            st.rerun()
                    
                    # Edit form
                    if st.session_state.editing_index == idx:
                        with st.form(key=f"edit_form_{idx}"):
                            st.subheader("Edit Entry")
                            # Get current values
                            current_date = datetime.strptime(row['Date'], '%Y-%m-%d').date()
                            current_size = row['Size (mm)']
                            current_type = row['Type']
                            current_qty = row['Quantity']
                            current_remarks = row['Remarks']
                            current_status = row['Status']
                            
                            # Create editable fields
                            col1, col2 = st.columns(2)
                            with col1:
                                new_date = st.date_input("Date", value=current_date)
                                new_size = st.number_input("Size (mm)", value=current_size, min_value=1)
                            with col2:
                                new_type = st.selectbox(
                                    "Type",
                                    ["Inward", "Outgoing"],
                                    index=0 if current_type == 'Inward' else 1
                                )
                                new_qty = st.number_input("Quantity", value=current_qty, min_value=1)
                            
                            new_remarks = st.text_input("Remarks", value=current_remarks)
                            new_status = st.selectbox(
                                "Status",
                                ["Current", "Pending", "Future"],
                                index=["Current", "Pending", "Future"].index(current_status)
                            )
                            
                            # Form buttons
                            save_col, cancel_col = st.columns(2)
                            with save_col:
                                if st.form_submit_button("💾 Save Changes", use_container_width=True):
                                    st.session_state.data.at[idx, 'Date'] = new_date.strftime('%Y-%m-%d')
                                    st.session_state.data.at[idx, 'Size (mm)'] = new_size
                                    st.session_state.data.at[idx, 'Type'] = new_type
                                    st.session_state.data.at[idx, 'Quantity'] = new_qty
                                    st.session_state.data.at[idx, 'Remarks'] = new_remarks
                                    st.session_state.data.at[idx, 'Status'] = new_status
                                    if auto_save_to_gsheet():
                                        st.success("Changes saved successfully!")
                                    st.session_state.editing_index = None
                                    st.rerun()
                            with cancel_col:
                                if st.form_submit_button("❌ Cancel", use_container_width=True):
                                    st.session_state.editing_index = None
                                    st.rerun()
                
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

# Auto-save notification
if st.session_state.get('auto_save_success'):
    st.toast("Auto-save completed", icon="✅")
    st.session_state.auto_save_success = False

# Add a reset button in sidebar
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
    st.caption("All changes are automatically saved to Google Sheets. Manual saves are recommended before closing.")
    st.caption(f"Entries in system: *{len(st.session_state.data)}*")
