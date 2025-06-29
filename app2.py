import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Initialize session data
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks'])

st.set_page_config(page_title="Submersible Rotor Tracker", layout="centered")
st.title("🔧 Submersible Pump Rotor Tracker")

# Google Sheets setup
def get_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Rotor Log").sheet1

def append_to_sheet(row):
    sheet = get_gsheet()
    sheet.append_row(row)

def read_sheet_as_df():
    sheet = get_gsheet()
    return pd.DataFrame(sheet.get_all_records())

# Load initial data from Google Sheet
if st.session_state.data.empty:
    st.session_state.data = read_sheet_as_df()

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
        new_entry = pd.DataFrame([{'Date': date, 'Size (mm)': rotor_size, 'Type': entry_type, 'Quantity': quantity, 'Remarks': remarks}])
        st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
        append_to_sheet([str(date), rotor_size, entry_type, quantity, remarks])  # Sync with Google Sheet
        st.success("✅ Entry logged and saved to Google Sheet!")

# --- Rotor Log Table ---
st.subheader("📋 Rotor Movement Log")
if not st.session_state.data.empty:
    df = st.session_state.data.reset_index(drop=True)
    for i in df.index:
        delete_col = st.columns([10, 1])
        with delete_col[0]:
            st.dataframe(df.iloc[[i]], use_container_width=True, hide_index=True)
        with delete_col[1]:
            if st.button("❌", key=f"delete_{i}"):
                st.session_state.data.drop(index=i, inplace=True)
                st.session_state.data.reset_index(drop=True, inplace=True)
                append_to_sheet([])  # Optional: Clear row in Google Sheet if supported
                st.rerun()
else:
    st.info("No entries to display.")

# --- Summary by Size ---
st.subheader("📊 Current Stock by Size (mm)")
if not st.session_state.data.empty:
    summary = st.session_state.data.copy()
    summary['Net Quantity'] = summary.apply(lambda row: row['Quantity'] if row['Type'] == 'Inward' else -row['Quantity'], axis=1)
    stock_summary = summary.groupby('Size (mm)')['Net Quantity'].sum().reset_index()
    stock_summary = stock_summary[stock_summary['Net Quantity'] != 0]
    st.dataframe(stock_summary, use_container_width=True)
else:
    st.info("No data available yet.")

# --- Export Section ---
st.subheader("📤 Export Data")
csv = st.session_state.data.to_csv(index=False).encode('utf-8')
st.download_button("📥 Download CSV", csv, "submersible_rotor_log.csv", "text/csv")
excel_bytes = to_excel(st.session_state.data)
st.download_button("📊 Download Excel", excel_bytes, "submersible_rotor_log.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def to_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Rotor Data')
    writer.close()
    return output.getvalue()
