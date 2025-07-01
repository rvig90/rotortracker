import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ====== INITIALIZATION ======
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status'
    ])
    st.session_state.last_sync = "Never"
    st.session_state.editing_index = None
    st.session_state.edit_form_data = None
    st.session_state.log_expanded = True

# ====== IMPROVED GOOGLE SHEETS INTEGRATION ======
def get_gsheet_connection():
    try:
        # Verify credentials exist
        if 'gcp_service_account' not in st.secrets:
            st.error("❌ Google Sheets credentials not found in secrets")
            return None
            
        scope = ["https://spreadsheets.google.com/feeds", 
                "https://www.googleapis.com/auth/drive"]
        
        # Handle credential format
        try:
            if isinstance(st.secrets["gcp_service_account"], str):
                creds_dict = json.loads(st.secrets["gcp_service_account"])
            else:
                creds_dict = dict(st.secrets["gcp_service_account"])
        except Exception as e:
            st.error(f"❌ Invalid credential format: {str(e)}")
            return None
        
        # Verify required fields
        required_fields = ['private_key', 'client_email', 'token_uri']
        for field in required_fields:
            if field not in creds_dict:
                st.error(f"❌ Missing required field in credentials: {field}")
                return None
                
        # Fix newlines in private key
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        # Create credentials
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Test connection
        try:
            sheet = client.open("Rotor Log").sheet1
            sheet.get_all_records()  # Test read
            return sheet
        except gspread.exceptions.SpreadsheetNotFound:
            st.error("❌ 'Rotor Log' spreadsheet not found")
            return None
        except Exception as e:
            st.error(f"❌ Sheets API error: {str(e)}")
            return None
            
    except Exception as e:
        st.error(f"❌ Connection failed: {str(e)}")
        return None

def load_from_gsheet():
    try:
        sheet = get_gsheet_connection()
        if not sheet:
            return False
            
        records = sheet.get_all_records()
        if records:
            df = pd.DataFrame(records)
            # Ensure required columns exist
            required_cols = ['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks']
            for col in required_cols:
                if col not in df.columns:
                    st.error(f"❌ Missing column in sheet: {col}")
                    return False
            
            # Add Status if missing
            if 'Status' not in df.columns:
                df['Status'] = 'Current'
                
            st.session_state.data = df
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.success("✅ Data loaded successfully!")
            return True
        else:
            st.info("ℹ Google Sheet is empty")
            return True
            
    except Exception as e:
        st.error(f"❌ Load error: {str(e)}")
        return False

def auto_save_to_gsheet():
    try:
        if st.session_state.data.empty:
            return True
            
        sheet = get_gsheet_connection()
        if not sheet:
            return False
            
        # Prepare data for saving
        data_to_save = st.session_state.data.copy()
        if 'Status' not in data_to_save.columns:
            data_to_save['Status'] = 'Current'
            
        # Save to sheet
        sheet.clear()
        sheet.append_row(data_to_save.columns.tolist())
        for _, row in data_to_save.iterrows():
            sheet.append_row(row.tolist())
            
        st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return True
        
    except Exception as e:
        st.error(f"❌ Save failed: {str(e)}")
        return False

# ====== SYNC BUTTON ======
if st.button("🔄 Sync Now", help="Load latest data from Google Sheets"):
    with st.spinner("Syncing with Google Sheets..."):
        if load_from_gsheet():
            st.rerun()

# ====== ENTRY FORMS ======
form_tabs = st.tabs(["Current Movement", "Coming Rotors", "Pending Outgoing"])

with form_tabs[0]:  # Current Movement
    with st.form("current_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Date", value=datetime.today(), key="current_date")
            rotor_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, format="%d", key="current_size")
        with col2:
            entry_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"], key="current_type")
            quantity = st.number_input("🔢 Quantity", min_value=1, step=1, format="%d", key="current_qty")
        remarks = st.text_input("📝 Remarks", key="current_remarks")
        
        if st.form_submit_button("➕ Add Entry"):
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

with form_tabs[1]:  # Coming Rotors
    with st.form("future_form"):
        col1, col2 = st.columns(2)
        with col1:
            future_date = st.date_input("📅 Expected Date", min_value=datetime.today() + timedelta(days=1), key="future_date")
            future_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, format="%d", key="future_size")
        with col2:
            future_qty = st.number_input("🔢 Quantity", min_value=1, step=1, format="%d", key="future_qty")
            future_remarks = st.text_input("📝 Remarks", key="future_remarks")
        
        if st.form_submit_button("➕ Add Coming Rotors"):
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
                st.rerun()

with form_tabs[2]:  # Pending Outgoing
    with st.form("pending_form"):
        col1, col2 = st.columns(2)
        with col1:
            pending_date = st.date_input("📅 Ship Date", value=datetime.today(), key="pending_date")
            pending_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, format="%d", key="pending_size")
        with col2:
            pending_qty = st.number_input("🔢 Quantity", min_value=1, step=1, format="%d", key="pending_qty")
            pending_remarks = st.text_input("📝 Remarks", key="pending_remarks")
        
        if st.form_submit_button("➕ Add Pending Outgoing"):
            new_entry = pd.DataFrame([{
                'Date': pending_date.strftime('%Y-%m-%d'),
                'Size (mm)': pending_size, 
                'Type': 'Outgoing', 
                'Quantity': pending_qty, 
                'Remarks': f"[PENDING] {pending_remarks}",
                'Status': 'Current'
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            if auto_save_to_gsheet():
                st.rerun()

# ====== STOCK SUMMARY ======
st.subheader("📊 Current Stock Summary")
if not st.session_state.data.empty:
    try:
        # Current stock
        current = st.session_state.data[st.session_state.data['Status'] == 'Current'].copy()
        current['Net'] = current.apply(lambda x: x['Quantity'] if x['Type'] == 'Inward' else -x['Quantity'], axis=1)
        stock = current.groupby('Size (mm)')['Net'].sum().reset_index()
        stock = stock[stock['Net'] != 0]
        
        # Coming rotors
        future = st.session_state.data[st.session_state.data['Status'] == 'Future']
        coming = future.groupby('Size (mm)')['Quantity'].sum().reset_index()
        
        # Pending outgoing
        pending = current[current['Type'] == 'Outgoing']
        pending = pending.groupby('Size (mm)')['Quantity'].sum().reset_index()
        
        # Combine all data
        combined = pd.merge(stock, coming, on='Size (mm)', how='outer').fillna(0)
        combined = pd.merge(combined, pending, on='Size (mm)', how='outer').fillna(0)
        combined.columns = ['Size (mm)', 'Current Stock', 'Coming Rotors', 'Pending Outgoing']
        combined['Available Stock'] = combined['Current Stock'] - combined['Pending Outgoing']
        
        # Display
        st.dataframe(
            combined[['Size (mm)', 'Current Stock', 'Pending Outgoing', 'Available Stock', 'Coming Rotors']],
            use_container_width=True,
            hide_index=True
        )
        
    except Exception as e:
        st.error(f"❌ Summary error: {str(e)}")
else:
    st.info("ℹ No data available yet")

# ====== MOVEMENT LOG ======
with st.expander("📋 View Movement Log", expanded=True):
    if not st.session_state.data.empty:
        try:
            # Filter controls
            st.write("### Filter Options")
            filter_col1, filter_col2, filter_col3 = st.columns(3)
            
            with filter_col1:
                filter_date = st.date_input("Filter by date", value=None, key="filter_date")
                date_filter_applied = st.button("Apply Date Filter", key="date_filter_btn")
            
            with filter_col2:
                remarks_search = st.text_input("Search remarks", key="remarks_search")
                remarks_filter_applied = st.button("Search Remarks", key="remarks_filter_btn")
            
            with filter_col3:
                size_options = sorted(st.session_state.data['Size (mm)'].unique())
                selected_size = st.selectbox("Filter by size", [""] + size_options, key="size_filter")
                size_filter_applied = st.button("Apply Size Filter", key="size_filter_btn")
            
            # Handle filters
            if date_filter_applied:
                st.session_state.filter_date = filter_date.strftime('%Y-%m-%d') if filter_date else None
            if remarks_filter_applied:
                st.session_state.remarks_search = remarks_search.lower().strip() if remarks_search else None
            if size_filter_applied:
                st.session_state.filter_size = int(selected_size) if selected_size else None
            
            # Clear filters
            if (st.session_state.get('filter_date') or 
                st.session_state.get('remarks_search') or 
                st.session_state.get('filter_size')):
                if st.button("❌ Clear All Filters", key="clear_filters"):
                    st.session_state.filter_date = None
                    st.session_state.remarks_search = None
                    st.session_state.filter_size = None
                    st.rerun()
            
            # Apply filters
            display_data = st.session_state.data.copy()
            if st.session_state.get('filter_date'):
                display_data = display_data[display_data['Date'] == st.session_state.filter_date]
            if st.session_state.get('remarks_search'):
                display_data = display_data[display_data['Remarks'].str.lower().str.contains(
                    st.session_state.remarks_search, na=False)]
            if st.session_state.get('filter_size'):
                display_data = display_data[display_data['Size (mm)'] == st.session_state.filter_size]
            
            # Display filtered data
            if display_data.empty:
                st.warning("⚠ No entries match filters")
            else:
                for idx, row in display_data.sort_values('Date', ascending=False).iterrows():
                    cols = st.columns([8, 1, 1])
                    with cols[0]:
                        st.dataframe(pd.DataFrame(row).T, hide_index=True)
                    with cols[1]:
                        if st.button("✏", key=f"edit_{idx}"):
                            st.session_state.editing_index = idx
                            st.session_state.edit_form_data = row.to_dict()
                            st.rerun()
                    with cols[2]:
                        if st.button("❌", key=f"del_{idx}"):
                            st.session_state.data = st.session_state.data.drop(idx)
                            if auto_save_to_gsheet():
                                st.rerun()
                    st.markdown("---")
                    
        except Exception as e:
            st.error(f"❌ Log error: {str(e)}")
    else:
        st.info("ℹ No entries to display")

# Status footer
if st.session_state.last_sync != "Never":
    st.caption(f"Last synced: {st.session_state.last_sync}")
