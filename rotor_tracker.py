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

# ====== GOOGLE SHEETS INTEGRATION ======
def get_gsheet_connection():
    try:
        scope = ["https://spreadsheets.google.com/feeds", 
                "https://www.googleapis.com/auth/drive"]
        
        # Handle both string and dict formats for secrets
        if isinstance(st.secrets["gcp_service_account"], str):
            creds_dict = json.loads(st.secrets["gcp_service_account"])
        else:
            creds_dict = dict(st.secrets["gcp_service_account"])
        
        # Fix private key formatting
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
                    df['Status'] = 'Current'  # Set default status
                st.session_state.data = df
                st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success("Data loaded from Google Sheets!")
            else:
                st.info("Google Sheet is empty")
    except Exception as e:
        st.error(f"Error loading from Google Sheets: {e}")

def save_to_gsheet():
    try:
        sheet = get_gsheet_connection()
        if sheet:
            # Ensure Status column exists
            if 'Status' not in st.session_state.data.columns:
                st.session_state.data['Status'] = 'Current'
            
            # Clear existing sheet and write new data
            sheet.clear()
            sheet.append_row(st.session_state.data.columns.tolist())
            for _, row in st.session_state.data.iterrows():
                sheet.append_row(row.tolist())
            
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.success("Data saved to Google Sheets!")
    except Exception as e:
        st.error(f"Error saving to Google Sheets: {e}")

# ====== SYNC BUTTONS ======
st.write("")  # Spacer
sync_col1, sync_col2 = st.columns(2)
with sync_col1:
    if st.button("🔄 Load from Google Sheets", help="Fetch latest data from cloud"):
        load_from_gsheet()
with sync_col2:
    if st.button("💾 Save to Google Sheets", help="Backup data to cloud"):
        save_to_gsheet()
st.caption(f"Last sync: {st.session_state.last_sync}")

# ====== ENTRY FORMS ======
form_tabs = st.tabs(["Current Movement", "Coming Rotors"])

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
        
        if st.form_submit_button("➕ Add Current Movement"):
            new_entry = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'),
                'Size (mm)': rotor_size, 
                'Type': entry_type, 
                'Quantity': quantity, 
                'Remarks': remarks,
                'Status': 'Current'
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            st.rerun()

with form_tabs[1]:  # Coming Rotors
    with st.form("future_form"):
        col1, col2 = st.columns(2)
        with col1:
            future_date = st.date_input("📅 Expected Date", 
                                      min_value=datetime.today() + timedelta(days=1),
                                      key="future_date")
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
            st.rerun()

# ====== STOCK SUMMARY ======
st.subheader("📊 Current Stock Summary")
if not st.session_state.data.empty:
    # Ensure Status column exists
    if 'Status' not in st.session_state.data.columns:
        st.session_state.data['Status'] = 'Current'
    
    try:
        # Current stock
        current_data = st.session_state.data[st.session_state.data['Status'] == 'Current'].copy()
        current_data['Net Quantity'] = current_data.apply(
            lambda row: row['Quantity'] if row['Type'] == 'Inward' else -row['Quantity'], 
            axis=1
        )
        stock_summary = current_data.groupby('Size (mm)')['Net Quantity'].sum().reset_index()
        stock_summary = stock_summary[stock_summary['Net Quantity'] != 0]
        
        # Coming rotors
        future_data = st.session_state.data[st.session_state.data['Status'] == 'Future']
        coming_rotors = future_data.groupby('Size (mm)')['Quantity'].sum().reset_index()
        
        # Merge results
        merged = pd.merge(
            stock_summary,
            coming_rotors,
            on='Size (mm)',
            how='outer'
        ).fillna(0).rename(columns={
            'Net Quantity': 'Current Stock',
            'Quantity': 'Coming Rotors'
        })
        
        st.dataframe(
            merged[['Size (mm)', 'Current Stock', 'Coming Rotors']],
            use_container_width=True,
            hide_index=True
        )
    except Exception as e:
        st.error(f"Error generating stock summary: {e}")
else:
    st.info("No data available yet")

# ====== MOVEMENT LOG WITH SIDE DELETE BUTTONS ======
st.subheader("📋 Movement Log")
if not st.session_state.data.empty:
    # Ensure Status column exists
    if 'Status' not in st.session_state.data.columns:
        st.session_state.data['Status'] = 'Current'
    
    try:
        # Create display dataframe sorted by date
        display_df = st.session_state.data.sort_values(['Date'], ascending=[False])
        
        # Display each entry with delete button on the side
        for idx, row in display_df.iterrows():
            cols = st.columns([3, 2, 2, 2, 4, 1])
            with cols[0]:
                st.write(row['Date'])
            with cols[1]:
                st.write(f"{row['Size (mm)']}mm")
            with cols[2]:
                st.write(row['Type'])
            with cols[3]:
                st.write(row['Quantity'])
            with cols[4]:
                st.write(row['Remarks'])
            with cols[5]:
                if st.button("❌", key=f"delete_{idx}"):
                    st.session_state.data = st.session_state.data.drop(idx).reset_index(drop=True)
                    st.rerun()
            
            st.markdown("---")  # Divider between entries
            
    except Exception as e:
        st.error(f"Error displaying movement log: {e}")
else:
    st.info("No entries to display")
