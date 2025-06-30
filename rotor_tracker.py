import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

import streamlit as st
import pandas as pd
from datetime import datetime
import base64

# ====== LOGO IMPLEMENTATION ======
def add_logo():
    st.markdown(
        """
        <style>
            .logo-container {
                display: flex;
                flex-direction: column;
                align-items: center;
                margin-bottom: 2rem;
            }
            .established {
                font-family: 'Arial', sans-serif;
                font-size: 1rem;
                color: #555555;
                letter-spacing: 0.1em;
                margin-bottom: -10px;
            }
            .logo-text {
                font-family: 'Arial Black', sans-serif;
                font-size: 2rem;
                font-weight: 900;
                color: #333333;
                line-height: 1;
                text-align: center;
            }
            .logo-hr {
                width: 80%;
                border: 0;
                height: 2px;
                background: linear-gradient(90deg, transparent, #333333, transparent);
                margin: 0.5rem 0;
            }
        </style>
        <div class="logo-container">
            <div class="established">EST. 1993</div>
            <div class="logo-text">MR<br>M.R ENTERPRISES</div>
            <div class="logo-hr"></div>
        </div>
        """,
        unsafe_allow_html=True
    )

# Initialize app
add_logo()
st.set_page_config(page_title="MR Enterprises - Rotor Tracker", layout="centered")

# Initialize session data
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks'])

# ====== DELETION FUNCTION ======
def delete_entry(index):
    try:
        # Create copy before modification
        df = st.session_state.data.copy()
        # Remove the entry
        df = df.drop(index=index).reset_index(drop=True)
        # Update session state
        st.session_state.data = df
        st.success("Entry deleted successfully!")
        st.rerun()  # Refresh to show changes
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
        st.rerun()

# Movement Log Display
st.subheader("📋 Rotor Movement Log")
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

# Your existing app content
st.title("🔧 Submersible Pump Rotor Tracker")

# Rest of your existing form and components...
with st.form("entry_form"):
    # Your form fields here
    pass
st.markdown("""
<style>
/* Remove spin buttons from number inputs */
input[type="number"]::-webkit-inner-spin-button,
input[type="number"]::-webkit-outer-spin-button {
    -webkit-appearance: none;
    margin: 0;
}
/* Firefox */
input[type="number"] {
    -moz-appearance: textfield;
}
</style>
""", unsafe_allow_html=True)
# Initialize session data
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks'])

st.set_page_config(page_title="Submersible Rotor Tracker", layout="centered")
st.title("🔧 Submersible Pump Rotor Tracker")

# Google Sheets setup
def get_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", 
             "https://www.googleapis.com/auth/drive"]
    
    try:
        # Parse the JSON service account string from secrets
        creds_dict = json.loads(st.secrets["gcp_service_account"])
        
        # Fix newline characters in private key
        if "\\n" in creds_dict["private_key"]:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Rotor Log").sheet1
    except Exception as e:
        st.error(f"Google Sheets connection failed: {str(e)}")
        return None

def append_to_sheet(row):
    try:
        sheet = get_gsheet()
        if sheet:
            sheet.append_row(row)
            return True
        return False
    except Exception as e:
        st.error(f"Failed to append row: {e}")
        return False

def read_sheet_as_df():
    try:
        sheet = get_gsheet()
        if not sheet:
            return pd.DataFrame()
            
        records = sheet.get_all_records()
        if records:
            return pd.DataFrame(records)
        return pd.DataFrame(columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks'])
    except Exception as e:
        st.error(f"Error reading sheet: {e}")
        return pd.DataFrame()

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Rotor Data')
    return output.getvalue()

# Verify connection and load initial data
if 'verified' not in st.session_state:
    with st.spinner("Connecting to Google Sheets..."):
        test_sheet = get_gsheet()
        if test_sheet:
            st.session_state.verified = True
            st.session_state.data = read_sheet_as_df()
            if not st.session_state.data.empty:
                st.success("Successfully loaded data from Google Sheets!")
        else:
            st.error("Failed to connect to Google Sheets. Please check your credentials.")
            st.stop()

# --- Entry Form ---
with st.form("entry_form"):
    col1, col2 = st.columns(2)
    with col1:
        date = st.date_input("📅 Date", value=datetime.today())
        # Use number_input with proper parameters for numeric keyboard
        rotor_size = st.number_input(
            "📐 Rotor Size (in mm)", 
            min_value=1,
            step=1,
            format="%d",  # Ensures integer input
            key="rotor_size"
        )
    with col2:
        entry_type = st.selectbox("🔄 Entry Type", ["Inward", "Outgoing"])
        quantity = st.number_input(
            "🔢 Quantity (number of rotors)", 
            min_value=1, 
            step=1,
            format="%d",  # Ensures integer input
            key="quantity"
        )
    remarks = st.text_input("📝 Remarks")
    
    # The crucial submit button - must be inside the form
    submitted = st.form_submit_button("➕ Add Entry")
    
    if submitted:
        # Your submission handling logic here
        new_entry = pd.DataFrame([{
            'Date': date.strftime('%Y-%m-%d'),
            'Size (mm)': rotor_size, 
            'Type': entry_type, 
            'Quantity': quantity, 
            'Remarks': remarks
        }])
        # Rest of your submission logic...        
        try:
            # Add to session state
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            
            # Add to Google Sheets
            if append_to_sheet([date.strftime('%Y-%m-%d'), rotor_size, entry_type, quantity, remarks]):
                st.success("✅ Entry logged and saved to Google Sheet!")
                st.rerun()
        except Exception as e:
            st.error(f"Failed to save entry: {e}")

# --- Rotor Log Table ---
# Replace your movement log section with:
with st.expander("📋 Rotor Movement Log", expanded=False):
    if not st.session_state.data.empty:
        df = st.session_state.data.copy()
        for i in df.index:
            delete_col = st.columns([10, 1])
            with delete_col[0]:
                st.dataframe(df.iloc[[i]], use_container_width=True, hide_index=True)
            with delete_col[1]:
                if st.button("❌", key=f"delete_{i}"):
                    try:
                        st.session_state.data = st.session_state.data.drop(index=i).reset_index(drop=True)
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

# Connection test button (hidden by default)
with st.expander("Developer Tools", expanded=False):
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
