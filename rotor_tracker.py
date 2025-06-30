import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ====== LOGO IMPLEMENTATION ======
def add_logo():
    st.markdown(
        """
        <style>
            .logo-container {
                display: flex;
                flex-direction: column;
                align-items: center;
                margin-bottom: 1rem;
            }
            .established {
                font-family: 'Arial', sans-serif;
                font-size: 0.9rem;
                color: #555555;
                letter-spacing: 0.1em;
                margin-bottom: -8px;
            }
            .logo-text {
                font-family: 'Arial Black', sans-serif;
                font-size: 1.8rem;
                font-weight: 900;
                color: #333333;
                line-height: 1;
                text-align: center;
            }
            .logo-hr {
                width: 70%;
                border: 0;
                height: 1px;
                background: linear-gradient(90deg, transparent, #333333, transparent);
                margin: 0.5rem 0;
            }
            .compact-log {
                font-size: 0.9rem;
                margin-bottom: 0.5rem;
            }
            .log-entry {
                padding: 0.5rem;
                border-bottom: 1px solid #eee;
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

# ====== GOOGLE SHEETS INTEGRATION ======
def get_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", 
             "https://www.googleapis.com/auth/drive"]
    try:
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

def sync_with_gsheet():
    try:
        sheet = get_gsheet()
        if sheet:
            records = sheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
                if 'Modified' not in df.columns:
                    df['Modified'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                st.session_state.data = df
            else:
                st.session_state.data = pd.DataFrame(columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Modified'])
    except Exception as e:
        st.error(f"Sync error: {e}")

def update_gsheet():
    try:
        sheet = get_gsheet()
        if sheet:
            st.session_state.data['Modified'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            sheet.clear()
            sheet.append_row(st.session_state.data.columns.tolist())
            for _, row in st.session_state.data.iterrows():
                sheet.append_row(row.tolist())
    except Exception as e:
        st.error(f"Update error: {e}")

# Initialize data
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Modified'])
    sync_with_gsheet()

# ====== DELETION FUNCTION ======
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
            'Modified': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }])
        st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
        update_gsheet()
        st.rerun()

# Stock Summary
st.subheader("📊 Current Stock by Size")
if not st.session_state.data.empty:
    summary = st.session_state.data.copy()
    summary['Net Quantity'] = summary.apply(
        lambda row: row['Quantity'] if row['Type'] == 'Inward' else -row['Quantity'], 
        axis=1
    )
    stock_summary = summary.groupby('Size (mm)')['Net Quantity'].sum().reset_index()
    stock_summary = stock_summary[stock_summary['Net Quantity'] != 0]
    st.dataframe(stock_summary, use_container_width=True, hide_index=True)
else:
    st.info("No data available yet.")

# ====== CONDENSED MOVEMENT LOG ======
with st.expander("📋 Movement Log (Newest First)", expanded=False):
    if not st.session_state.data.empty:
        # Sort by Modified date (newest first)
        sorted_data = st.session_state.data.sort_values('Modified', ascending=False)
        
        # Display compact log entries
        for i, row in sorted_data.iterrows():
            cols = st.columns([1, 1, 1, 1, 2, 1])
            with cols[0]:
                st.markdown(f"<div class='compact-log'>{row['Date']}</div>", unsafe_allow_html=True)
            with cols[1]:
                st.markdown(f"<div class='compact-log'>{row['Size (mm)']}mm</div>", unsafe_allow_html=True)
            with cols[2]:
                st.markdown(f"<div class='compact-log'>{row['Type']}</div>", unsafe_allow_html=True)
            with cols[3]:
                st.markdown(f"<div class='compact-log'>{row['Quantity']}</div>", unsafe_allow_html=True)
            with cols[4]:
                st.markdown(f"<div class='compact-log'>{row['Remarks']}</div>", unsafe_allow_html=True)
            with cols[5]:
                if st.button("❌", key=f"delete_{i}"):
                    delete_entry(i)
            st.markdown("<div class='log-entry'></div>", unsafe_allow_html=True)
    else:
        st.info("No entries to display.")

# Manual sync button
if st.button("🔄 Sync with Google Sheets"):
    sync_with_gsheet()
    st.rerun()
