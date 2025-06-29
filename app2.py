import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json  # Added missing import

# Initialize session data
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks'])

st.set_page_config(page_title="Submersible Rotor Tracker", layout="centered")
st.title("🔧 Submersible Pump Rotor Tracker")

# Google Sheets setup
def get_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", 
             "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]  # Removed json.loads() as Streamlit secrets are already dicts
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Rotor Log").sheet1

def append_to_sheet(row):
    sheet = get_gsheet()
    sheet.append_row(row)

def read_sheet_as_df():
    sheet = get_gsheet()
    records = sheet.get_all_records()
    if records:  # Only convert to DataFrame if there are records
        return pd.DataFrame(records)
    return pd.DataFrame(columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks'])

# Load initial data from Google Sheet
if st.session_state.data.empty:
    try:
        st.session_state.data = read_sheet_as_df()
    except Exception as e:
        st.error(f"Failed to load data from Google Sheet: {e}")
        st.session_state.data = pd.DataFrame(columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks'])

# --- Entry Form ---
with st.form("entry_form"):
    col1, col2 = st.columns(2)
    with col1:
        date = st.date_input("📅 Date", value=datetime.today())
        rotor_size = st.number_input("📐 Rotor Size (in mm)", min_value=1)
    with col2:
        entry_type = st.selectbox("🔄 Entry Type", ["Inward", "Outgoing"])
        quantity = st.number_input("🔢 Quantity (number of rotors)", min_value=1, step=1)
    remarks = st.text_input("📝 Remarks")
    submitted = st.form_submit_button("➕ Add Entry")
    
    if submitted:
        new_entry = pd.DataFrame([{
            'Date': date.strftime('%Y-%m-%d'),  # Format date as string for consistency
            'Size (mm)': rotor_size, 
            'Type': entry_type, 
            'Quantity': quantity, 
            'Remarks': remarks
        }])
        
        try:
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            append_to_sheet([date.strftime('%Y-%m-%d'), rotor_size, entry_type, quantity, remarks])
            st.success("✅ Entry logged and saved to Google Sheet!")
            st.rerun()  # Refresh to show new entry
        except Exception as e:
            st.error(f"Failed to save entry: {e}")

# --- Rotor Log Table ---
st.subheader("📋 Rotor Movement Log")
if not st.session_state.data.empty:
    df = st.session_state.data.copy()
    for i in df.index:
        delete_col = st.columns([10, 1])
        with delete_col[0]:
            st.dataframe(df.iloc[[i]], use_container_width=True, hide_index=True)
        with delete_col[1]:
            if st.button("❌", key=f"delete_{i}"):
                try:
                    # Remove from session state
                    st.session_state.data = st.session_state.data.drop(index=i).reset_index(drop=True)
                    
                    # For Google Sheets, we'd need to rewrite the entire sheet
                    sheet = get_gsheet()
                    sheet.clear()
                    # Add headers
                    sheet.append_row(['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks'])
                    # Add remaining data
                    for _, row in st.session_state.data.iterrows():
                        sheet.append_row(row.tolist())
                    
                    st.success("Entry deleted successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to delete entry: {e}")
else:
    st.info("No entries to display.")

# --- Summary by Size ---
st.subheader("📊 Current Stock by Size (mm)")
if not st.session_state.data.empty:
    summary = st.session_state.data.copy()
    summary['Net Quantity'] = summary.apply(
        lambda row: row['Quantity'] if row['Type'] == 'Inward' else -row['Quantity'], 
        axis=1
    )
    stock_summary = summary.groupby('Size (mm)')['Net Quantity'].sum().reset_index()
    stock_summary = stock_summary[stock_summary['Net Quantity'] != 0]
    if not stock_summary.empty:
        st.dataframe(stock_summary, use_container_width=True)
    else:
        st.info("All stock levels are currently zero.")
else:
    st.info("No data available yet.")

# --- Export Section ---
st.subheader("📤 Export Data")

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Rotor Data')
    return output.getvalue()

if not st.session_state.data.empty:
    # CSV Download
    csv = st.session_state.data.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Download CSV", 
        csv, 
        "submersible_rotor_log.csv", 
        "text/csv"
    )
    
    # Excel Download
    excel_bytes = to_excel(st.session_state.data)
    st.download_button(
        "📊 Download Excel", 
        excel_bytes, 
        "submersible_rotor_log.xlsx", 
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.warning("No data available to export.")

if st.button("Test Google Sheets Connection"):
    try:
        sheet = get_gsheet()
        if sheet:
            st.success("Connection successful!")
            st.write(f"Found sheet with {len(sheet.get_all_records())} rows")
        else:
            st.error("Connection failed")
    except Exception as e:
        st.error(f"Connection error: {e}")
