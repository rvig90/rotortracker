import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import streamlit.components.v1 as components

# ====== INITIALIZE DATA ======
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status'
    ])
    st.session_state.last_sync = "Never"

# Initialize editing state
if 'editing_index' not in st.session_state:
    st.session_state.editing_index = None
if 'edit_form_data' not in st.session_state:
    st.session_state.edit_form_data = None

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
                st.session_state.data = df
                st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success("Data loaded successfully!")
            else:
                st.info("No data found in Google Sheet")
    except Exception as e:
        st.error(f"Error loading data: {e}")

def auto_save_to_gsheet():
    try:
        sheet = get_gsheet_connection()
        if sheet and not st.session_state.data.empty:
            sheet.clear()
            sheet.append_row(st.session_state.data.columns.tolist())
            for _, row in st.session_state.data.iterrows():
                sheet.append_row(row.tolist())
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"Auto-save failed: {e}")

# ====== SINGLE SYNC BUTTON ======
if st.button("🔄 Sync Now", help="Load latest data from Google Sheets"):
    load_from_gsheet()

# ====== ENTRY FORMS ======
form_tabs = st.tabs(["Current Movement", "Coming Rotors"])

with form_tabs[0]:  # Current Movement
    with st.form("current_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Date", value=datetime.today())
            rotor_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, format="%d")
        with col2:
            entry_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"])
            quantity = st.number_input("🔢 Quantity", min_value=1, step=1, format="%d")
        remarks = st.text_input("📝 Remarks")
        
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
            auto_save_to_gsheet()
            st.rerun()

with form_tabs[1]:  # Coming Rotors
    with st.form("future_form"):
        col1, col2 = st.columns(2)
        with col1:
            future_date = st.date_input("📅 Expected Date", min_value=datetime.today() + timedelta(days=1))
            future_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, format="%d")
        with col2:
            future_qty = st.number_input("🔢 Quantity", min_value=1, step=1, format="%d")
            future_remarks = st.text_input("📝 Remarks")
        
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
            auto_save_to_gsheet()
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
        
        # Combined view
        combined = pd.merge(stock, coming, on='Size (mm)', how='outer').fillna(0)
        combined.columns = ['Size (mm)', 'Current Stock', 'Coming Rotors']
        
        st.dataframe(
            combined,
            use_container_width=True,
            hide_index=True
        )
    except Exception as e:
        st.error(f"Error generating summary: {e}")
else:
    st.info("No data available yet")

# ====== MOVEMENT LOG WITH EDIT FUNCTIONALITY ======
# ====== MOVEMENT LOG WITH FILTERS AND FULL DISPLAY ======
with st.expander("📋 View Movement Log", expanded=False):
    if not st.session_state.data.empty:
        try:
            # Add filter controls at the top
            st.write("### Filter Options")
            filter_col1, filter_col2 = st.columns(2)
            
            # Date filter
            with filter_col1:
                filter_date = st.date_input("Filter by date", value=None)
                date_filter_applied = st.button("Apply Date Filter")
            
            # Remarks search
            with filter_col2:
                remarks_search = st.text_input("Search in remarks")
                remarks_filter_applied = st.button("Search Remarks")
            
            # Handle filter applications
            if date_filter_applied:
                st.session_state.filter_date = filter_date.strftime('%Y-%m-%d') if filter_date else None
            
            if remarks_filter_applied:
                st.session_state.remarks_search = remarks_search.strip().lower() if remarks_search.strip() else None
            
            # Clear filters button if any filter is active
            if (hasattr(st.session_state, 'filter_date') and st.session_state.filter_date) or \
               (hasattr(st.session_state, 'remarks_search') and st.session_state.remarks_search):
                if st.button("Clear All Filters"):
                    st.session_state.filter_date = None
                    st.session_state.remarks_search = None
                    st.rerun()

            # Apply filters to data
            display_data = st.session_state.data.copy()
            
            # Apply date filter if set
            if hasattr(st.session_state, 'filter_date') and st.session_state.filter_date:
                display_data = display_data[display_data['Date'] == st.session_state.filter_date]
                st.info(f"Showing entries for {st.session_state.filter_date}")
            
            # Apply remarks search if set
            if hasattr(st.session_state, 'remarks_search') and st.session_state.remarks_search:
                display_data = display_data[
                    display_data['Remarks'].str.lower().str.contains(
                        st.session_state.remarks_search, na=False
                    )
                ]
                st.info(f"Showing entries containing: '{st.session_state.remarks_search}'")

            # Show message if no results
            if display_data.empty:
                st.warning("No entries match the current filters")
            else:
                # Sort data by date (newest first)
                sorted_data = display_data.sort_values('Date', ascending=False)
                
                for idx, row in sorted_data.iterrows():
                    st.markdown("---")
                    
                    # Check if this row is being edited
                    is_editing = st.session_state.editing_index == idx
                    
                    if not is_editing:
                        # Display mode
                        cols = st.columns([10, 1, 1])
                        
                        with cols[0]:
                            st.dataframe(
                                pd.DataFrame(row[['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status']]).T,
                                use_container_width=True,
                                hide_index=True
                            )
                        
                        with cols[1]:
                            if st.button("✏", key=f"edit_{idx}"):
                                st.session_state.editing_index = idx
                                st.session_state.edit_form_data = row.to_dict()
                                st.rerun()
                        
                        with cols[2]:
                            if st.button("❌", key=f"del_{idx}"):
                                st.session_state.data = st.session_state.data.drop(idx).reset_index(drop=True)
                                auto_save_to_gsheet()
                                st.rerun()
                    else:
                        # Edit mode
                        with st.form(f"edit_form_{idx}"):
                            col1, col2 = st.columns(2)
                            with col1:
                                edit_date = st.date_input(
                                    "📅 Date", 
                                    value=datetime.strptime(row['Date'], '%Y-%m-%d'), 
                                    key=f"date_{idx}"
                                )
                                edit_size = st.number_input(
                                    "📐 Rotor Size (mm)", 
                                    value=row['Size (mm)'], 
                                    min_value=1, 
                                    key=f"size_{idx}"
                                )
                            with col2:
                                edit_type = st.selectbox(
                                    "🔄 Type", 
                                    ["Inward", "Outgoing"], 
                                    index=0 if row['Type'] == 'Inward' else 1,
                                    key=f"type_{idx}"
                                )
                                edit_qty = st.number_input(
                                    "🔢 Quantity", 
                                    value=row['Quantity'], 
                                    min_value=1, 
                                    key=f"qty_{idx}"
                                )
                            edit_remarks = st.text_input(
                                "📝 Remarks", 
                                value=row['Remarks'], 
                                key=f"remarks_{idx}"
                            )
                            edit_status = st.selectbox(
                                "Status", 
                                ["Current", "Future"], 
                                index=0 if row['Status'] == 'Current' else 1,
                                key=f"status_{idx}"
                            )
                            
                            # Form submission buttons
                            save_col, cancel_col = st.columns(2)
                            with save_col:
                                if st.form_submit_button("💾 Save Changes"):
                                    st.session_state.data.at[idx, 'Date'] = edit_date.strftime('%Y-%m-%d')
                                    st.session_state.data.at[idx, 'Size (mm)'] = edit_size
                                    st.session_state.data.at[idx, 'Type'] = edit_type
                                    st.session_state.data.at[idx, 'Quantity'] = edit_qty
                                    st.session_state.data.at[idx, 'Remarks'] = edit_remarks
                                    st.session_state.data.at[idx, 'Status'] = edit_status
                                    auto_save_to_gsheet()
                                    st.session_state.editing_index = None
                                    st.session_state.edit_form_data = None
                                    st.rerun()
                            with cancel_col:
                                if st.form_submit_button("❌ Cancel"):
                                    st.session_state.editing_index = None
                                    st.session_state.edit_form_data = None
                                    st.rerun()
                
                st.markdown("---")
            
        except Exception as e:
            st.error(f"Error displaying log: {e}")
    else:
        st.info("No entries to display")
# Status footer
if st.session_state.last_sync != "Never":
    st.caption(f"Last synced: {st.session_state.last_sync}")
