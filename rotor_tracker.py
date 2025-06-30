
import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ====== PROPER GOOGLE SHEETS AUTHENTICATION ======
def get_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", 
             "https://www.googleapis.com/auth/drive"]
    
    try:
        # Parse the service account info properly
        if isinstance(st.secrets["gcp_service_account"], str):
            creds_dict = json.loads(st.secrets["gcp_service_account"])
        else:
            creds_dict = dict(st.secrets["gcp_service_account"])
        
        # Fix newline characters in private key
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Rotor Log").sheet1
    except Exception as e:
        st.error(f"Google Sheets connection failed: {str(e)}")
        return None

# ====== DATA SYNC FUNCTIONS ======
def sync_with_gsheet():
    try:
        sheet = get_gsheet()
        if sheet:
            records = sheet.get_all_records()
            st.session_state.data = pd.DataFrame(records) if records else pd.DataFrame(
                columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks']
            )
    except Exception as e:
        st.error(f"Sync error: {e}")

def update_gsheet():
    try:
        sheet = get_gsheet()
        if sheet:
            sheet.clear()
            sheet.append_row(['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks'])
            for _, row in st.session_state.data.iterrows():
                sheet.append_row(row.tolist())
    except Exception as e:
        st.error(f"Update error: {e}")

# ====== INITIALIZE APP ======
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks'])
    sync_with_gsheet()

# ====== REST OF YOUR APP CODE ======
# (Include all your existing UI components, forms, and functions here)
# Make sure to call update_gsheet() after any data modifications

# Example delete function:
def delete_entry(index):
    try:
        st.session_state.data = st.session_state.data.drop(index).reset_index(drop=True)
        update_gsheet()
        st.success("Entry deleted successfully!")
        st.rerun()
    except Exception as e:
        st.error(f"Failed to delete entry: {e}")




# ====== MAIN APP ======
st.title("🔧 Submersible Pump Rotor Tracker")

# Entry Form
with st.form("entry_form"):
    col1, col2 = st.columns(2)
    with col1:
        date = st.date_input("📅 Date", value=datetime.today())
        rotor_size = st.number_input("📐 Rotor Size (in mm)", min_value=1, step=1, format="%d")
    with col2:
        entry_type = st.selectbox("🔄 Entry Type", ["Inward", "Outgoing"])
        quantity = st.number_input("🔢 Quantity (number of rotors)", min_value=1, step=1, format="%d")
    remarks = st.text_input("📝 Remarks")
    
    if st.form_submit_button("➕ Add Entry"):
        new_entry = pd.DataFrame([{
            'Date': date.strftime('%Y-%m-%d'),
            'Size (mm)': rotor_size, 
            'Type': entry_type, 
            'Quantity': quantity, 
            'Remarks': remarks
        }])
        st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
        update_gsheet()
        st.rerun()

# Stock Summary
st.subheader("📊 Current Stock by Size (mm)")
if not st.session_state.data.empty:
    summary = st.session_state.data.copy()
    summary['Net Quantity'] = summary.apply(
        lambda row: row['Quantity'] if row['Type'] == 'Inward' else -row['Quantity'], 
        axis=1
    )
    stock_summary = summary.groupby('Size (mm)')['Net Quantity'].sum().reset_index()
    stock_summary = stock_summary[stock_summary['Net Quantity'] != 0]
    st.dataframe(stock_summary, use_container_width=True)
else:
    st.info("No data available yet.")

# ====== MOVEMENT LOG (HIDDEN BY DEFAULT) ======
with st.expander("📋 View Full Movement Log", expanded=False):
    if not st.session_state.data.empty:
        for i in st.session_state.data.index:
            cols = st.columns([10, 1])
            with cols[0]:
                st.dataframe(st.session_state.data.iloc[[i]], use_container_width=True, hide_index=True)
            with cols[1]:
                if st.button("❌", key=f"delete_{i}"):
                    delete_entry(i)
    else:
        st.info("No entries to display.")

# Manual sync button
if st.button("🔄 Sync with Google Sheets"):
    sync_with_gsheet()
    st.rerun()
