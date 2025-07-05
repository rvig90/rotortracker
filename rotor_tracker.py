import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from PIL import Image
import io
import requests

# ====== INITIALIZE DATA ======
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending'
    ])
    st.session_state.last_sync = "Never"
    st.session_state.editing = None
    st.session_state.filter_reset = False

# ====== APP LOGO ======
def display_logo():
    try:
        logo_url = "https://via.placeholder.com/200x100?text=Rotor+Tracker"
        logo = Image.open(io.BytesIO(requests.get(logo_url).content))
        st.image(logo, width=200)
    except:
        st.title("Rotor Tracker")

display_logo()

# ====== HELPER FUNCTIONS ======
def normalize_pending_column(df):
    df['Pending'] = df['Pending'].apply(
        lambda x: str(x).lower() == 'true' if isinstance(x, str) else bool(x)
    )
    return df

def safe_delete_entry(orig_idx):
    try:
        if not st.session_state.data.empty and orig_idx in st.session_state.data.index:
            st.session_state.data = st.session_state.data.drop(orig_idx).reset_index(drop=True)
            auto_save_to_gsheet()
            st.success("Entry deleted successfully")
            st.rerun()
        else:
            st.warning("Entry not found or already deleted")
    except Exception as e:
        st.error(f"Error deleting entry: {e}")

# ====== GOOGLE SHEETS INTEGRATION ======
def get_gsheet_connection():
    try:
        scope = [
            "https://spreadsheets.google.com/feeds", 
            "https://www.googleapis.com/auth/drive"
        ]
        if isinstance(st.secrets["gcp_service_account"], str):
            creds_dict = json.loads(st.secrets["gcp_service_account"])
        else:
            creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Rotor Log").sheet1
    except Exception as e:
        st.error(f"Google Sheets connection failed: {e}")
        return None

# [Rest of your Google Sheets functions remain the same...]

# ====== MAIN APP ======
if st.session_state.last_sync == "Never":
    load_from_gsheet()

if st.button("🔄 Sync Now", help="Manually reload data from Google Sheets"):
    load_from_gsheet()

# ====== ENTRY FORMS ======
form_tabs = st.tabs(["Current Movement", "Coming Rotors", "Pending Rotors"])

with form_tabs[0]:
    with st.form("current_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Date", value=datetime.today())
            rotor_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
        with col2:
            entry_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"])
            quantity = st.number_input("🔢 Quantity", min_value=1, step=1)
        remarks = st.text_input("📝 Remarks")
        if st.form_submit_button("➕ Add Entry"):
            new = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'),
                'Size (mm)': rotor_size,
                'Type': entry_type,
                'Quantity': quantity,
                'Remarks': remarks,
                'Status': 'Current',
                'Pending': False
            }])
            st.session_state.data = pd.concat([st.session_state.data, new], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

with form_tabs[1]:
    with st.form("future_form"):
        col1, col2 = st.columns(2)
        with col1:
            future_date = st.date_input(  # Fixed this line - was missing closing parenthesis
                "📅 Expected Date", 
                min_value=datetime.today() + timedelta(days=1)
            )
            future_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
        with col2:
            future_qty = st.number_input("🔢 Quantity", min_value=1, step=1)
            future_remarks = st.text_input("📝 Remarks")
        if st.form_submit_button("➕ Add Coming Rotors"):
            new = pd.DataFrame([{
                'Date': future_date.strftime('%Y-%m-%d'),
                'Size (mm)': future_size,
                'Type': 'Inward',
                'Quantity': future_qty,
                'Remarks': future_remarks,
                'Status': 'Future',
                'Pending': False
            }])
            st.session_state.data = pd.concat([st.session_state.data, new], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

# [Rest of your code remains the same...]

# ====== MOVEMENT LOG WITH FIXED FILTERS ======
with st.expander("📋 View Movement Log", expanded=True):
    if st.session_state.data.empty:
        st.info("No entries to show yet.")
    else:
        df = st.session_state.data.copy()
        st.markdown("### 🔍 Filter Movement Log")

        # Reset filters button
        if st.button("🔄 Reset All Filters"):
            st.session_state.filter_reset = True
            st.rerun()

        # Initialize filter values
        if 'filter_reset' not in st.session_state:
            st.session_state.filter_reset = False

        # Reset filter values when reset is triggered
        if st.session_state.filter_reset:
            st.session_state.sf = "All"
            st.session_state.zf = []
            st.session_state.pf = "All"
            st.session_state.rs = ""
            min_date = pd.to_datetime(df['Date']).min().date()
            max_date = pd.to_datetime(df['Date']).max().date()
            st.session_state.dr = [min_date, max_date]
            st.session_state.filter_reset = False
            st.rerun()

        # Filter controls
        c1, c2, c3 = st.columns(3)
        with c1:
            status_f = st.selectbox(
                "📂 Status", 
                ["All", "Current", "Future"], 
                key="sf",
                index=0 if "sf" not in st.session_state else ["All", "Current", "Future"].index(st.session_state.sf)
            )
        with c2:
            size_f = st.multiselect(
                "📐 Size (mm)", 
                options=sorted(df['Size (mm)'].unique()), 
                key="zf",
                default=st.session_state.zf if "zf" in st.session_state else []
            )
        with c3:
            pending_f = st.selectbox(
                "❗ Pending", 
                ["All", "Yes", "No"], 
                key="pf",
                index=0 if "pf" not in st.session_state else ["All", "Yes", "No"].index(st.session_state.pf)
            )

        # [Rest of your movement log code remains the same...]

# ====== LAST SYNC STATUS ======
if st.session_state.last_sync != "Never":
    st.caption(f"Last synced: {st.session_state.last_sync}")
