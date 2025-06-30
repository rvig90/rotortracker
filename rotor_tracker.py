import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ====== INITIALIZE DATA ======
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status'
    ])
    st.session_state.last_sync = "Never"
    st.session_state.editing_index = None  # Track which row is being edited

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
with st.expander("📋 View Movement Log", expanded=False):
    if not st.session_state.data.empty:
        try:
            # Sort data by date (newest first)
            sorted_data = st.session_state.data.sort_values('Date', ascending=False)
            
            for idx, row in sorted_data.iterrows():
                st.markdown("---")
                cols = st.columns([10, 1, 1])
                
                # Display the entry
                with cols[0]:
                    st.dataframe(
                        pd.DataFrame(row[['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status']]).T,
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
                        st.session_state.data = st.session_state.data.drop(idx).reset_index(drop=True)
                        auto_save_to_gsheet()
                        st.rerun()
                
                # Edit form (appears when edit button is clicked)
                if st.session_state.editing_index == idx:
                    with st.form(f"edit_form_{idx}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            edit_date = st.date_input("📅 Date", 
                                                      value=datetime.strptime(row['Date'], '%Y-%m-%d'), 
                                                      key=f"date_{idx}")
                            edit_size = st.number_input("📐 Rotor Size (mm)", 
                                                      value=row['Size (mm)'], 
                                                      min_value=1, 
                                                      key=f"size_{idx}")
                        with col2:
                            edit_type = st.selectbox("🔄 Type", 
                                                    ["Inward", "Outgoing"], 
                                                    index=0 if row['Type'] == 'Inward' else 1,
                                                    key=f"type_{idx}")
                            edit_qty = st.number_input("🔢 Quantity", 
                                                      value=row['Quantity'], 
                                                      min_value=1, 
                                                      key=f"qty_{idx}")
                        edit_remarks = st.text_input("📝 Remarks", 
                                                    value=row['Remarks'], 
                                                    key=f"remarks_{idx}")
                        edit_status = st.selectbox("Status", 
                                                 ["Current", "Future"], 
                                                 index=0 if row['Status'] == 'Current' else 1,
                                                 key=f"status_{idx}")
                        
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
                                st.rerun()
                        with cancel_col:
                            if st.form_submit_button("❌ Cancel"):
                                st.session_state.editing_index = None
                                st.rerun()
            
            st.markdown("---")
        except Exception as e:
            st.error(f"Error displaying log: {e}")
    else:
        st.info("No entries to display")

# Status footer
if st.session_state.last_sync != "Never":
    st.caption(f"Last synced: {st.session_state.last_sync}")
