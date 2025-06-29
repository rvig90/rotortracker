import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

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
        creds_dict = dict(st.secrets["gcp_service_account"])
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

# Verify connection on first run
if 'verified' not in st.session_state:
    with st.spinner("Connecting to Google Sheets..."):
        test_sheet = get_gsheet()
        if test_sheet:
            st.session_state.verified = True
            st.session_state.data = read_sheet_as_df()
        else:
            st.error("Failed to connect to Google Sheets. Please check your credentials.")
            st.stop()

# --- Rest of your app code remains the same ---
