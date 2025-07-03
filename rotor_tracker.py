# Full working version with specific date filter and indentation fixes

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# Initialize session state
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending'
    ])
    st.session_state.last_sync = "Never"
    st.session_state.editing = None
    st.session_state.loaded = False

# Normalize pending
def normalize_pending_column(df):
    df['Pending'] = df['Pending'].apply(
        lambda x: str(x).lower() == 'true' if isinstance(x, str) else bool(x)
    )
    return df

# Google Sheet connection
def get_gsheet_connection():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(st.secrets["gcp_service_account"]) if isinstance(st.secrets["gcp_service_account"], str) else dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Rotor Log").sheet1
    except Exception as e:
        st.error(f"Google Sheets connection failed: {str(e)}")
        return None

# Load from Google Sheet
def load_from_gsheet():
    try:
        sheet = get_gsheet_connection()
        if sheet:
            records = sheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
                if 'Status' not in df.columns: df['Status'] = 'Current'
                if 'Pending' not in df.columns: df['Pending'] = False
                df = normalize_pending_column(df)
                st.session_state.data = df
                st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success("✅ Data loaded from Google Sheet")
            else:
                st.info("ℹ No records found in Google Sheet.")
    except Exception as e:
        st.error(f"❌ Error loading from Google Sheet: {e}")

# Auto-load
if not st.session_state.loaded:
    load_from_gsheet()
    st.session_state.loaded = True

# Auto-save
def auto_save_to_gsheet():
    try:
        sheet = get_gsheet_connection()
        if sheet:
            sheet.clear()
            df = st.session_state.data.copy()
            if not df.empty:
                df['Pending'] = df['Pending'].apply(lambda x: "TRUE" if x else "FALSE")
                expected_cols = ['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending']
                for col in expected_cols:
                    if col not in df.columns:
                        df[col] = ""
                df = df[expected_cols]
                records = [df.columns.tolist()] + df.values.tolist()
                sheet.update('A1', records)
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"❌ Auto-save failed: {e}")

# Sync button
if st.button("🔄 Sync Now"):
    load_from_gsheet()

# Entry Forms
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
            new_entry = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'),
                'Size (mm)': rotor_size,
                'Type': entry_type,
                'Quantity': quantity,
                'Remarks': remarks,
                'Status': 'Current',
                'Pending': False
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

with form_tabs[1]:
    with st.form("future_form"):
        col1, col2 = st.columns(2)
        with col1:
            future_date = st.date_input("📅 Expected Date", min_value=datetime.today() + timedelta(days=1))
            future_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
        with col2:
            future_qty = st.number_input("🔢 Quantity", min_value=1, step=1)
            future_remarks = st.text_input("📝 Remarks")

        if st.form_submit_button("➕ Add Coming Rotors"):
            new_entry = pd.DataFrame([{
                'Date': future_date.strftime('%Y-%m-%d'),
                'Size (mm)': future_size,
                'Type': 'Inward',
                'Quantity': future_qty,
                'Remarks': future_remarks,
                'Status': 'Future',
                'Pending': False
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

with form_tabs[2]:
    with st.form("pending_form"):
        col1, col2 = st.columns(2)
        with col1:
            pending_date = st.date_input("📅 Date", value=datetime.today())
            pending_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
        with col2:
            pending_qty = st.number_input("🔢 Quantity", min_value=1, step=1)
            pending_remarks = st.text_input("📝 Remarks", value="Pending delivery")

        if st.form_submit_button("➕ Add Pending Rotors"):
            new_entry = pd.DataFrame([{
                'Date': pending_date.strftime('%Y-%m-%d'),
                'Size (mm)': pending_size,
                'Type': 'Outgoing',
                'Quantity': pending_qty,
                'Remarks': pending_remarks,
                'Status': 'Current',
                'Pending': True
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

# Stock Summary
st.subheader("📊 Current Stock Summary")
if not st.session_state.data.empty:
    try:
        st.session_state.data = normalize_pending_column(st.session_state.data)
        df = st.session_state.data
        current = df[(df['Status'] == 'Current') & (~df['Pending'])].copy()
        current['Net'] = current.apply(lambda x: x['Quantity'] if x['Type'] == 'Inward' else -x['Quantity'], axis=1)
        stock = current.groupby('Size (mm)')['Net'].sum().reset_index()
        future = df[df['Status'] == 'Future'].groupby('Size (mm)')['Quantity'].sum().reset_index()
        pending = df[(df['Status'] == 'Current') & (df['Pending'])].groupby('Size (mm)')['Quantity'].sum().reset_index()
        combined = pd.merge(stock, future, on='Size (mm)', how='outer')
        combined = pd.merge(combined, pending, on='Size (mm)', how='outer', suffixes=('', '_Pending'))
        combined.columns = ['Size (mm)', 'Current Stock', 'Coming Rotors', 'Pending Rotors']
        combined = combined.fillna(0)
        st.dataframe(combined, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Error generating summary: {e}")
else:
    st.info("No data available")

# Movement Log
with st.expander("📋 View Movement Log", expanded=True):
    if not st.session_state.data.empty:
        df = st.session_state.data.copy()

        st.markdown("### 🔍 Filter Movement Log")
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.selectbox("📂 Status", ["All", "Current", "Future"])
        with col2:
            size_filter = st.multiselect("📐 Size (mm)", sorted(df['Size (mm)'].dropna().unique()))
        with col3:
            pending_filter = st.selectbox("❗ Pending", ["All", "Yes", "No"])

        remark_search = st.text_input("📝 Search Remarks")
        selected_date = st.date_input("📅 Filter by Specific Date (optional)", value=None)

        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        if selected_date:
        df = df[df['Date'] == pd.to_datetime(selected_date)]

        if status_filter != "All":
            df = df[df["Status"] == status_filter]
        if size_filter:
            df = df[df["Size (mm)"].isin(size_filter)]
        if pending_filter == "Yes":
            df = df[df["Pending"] == True]
        elif pending_filter == "No":
            df = df[df["Pending"] == False]
        if remark_search:
            df = df[df["Remarks"].str.contains(remark_search, case=False)]

        for i, row in df.iterrows():
            actual_idx = st.session_state.data[
                (st.session_state.data['Date'] == row['Date']) &
                (st.session_state.data['Size (mm)'] == row['Size (mm)']) &
                (st.session_state.data['Type'] == row['Type']) &
                (st.session_state.data['Quantity'] == row['Quantity']) &
                (st.session_state.data['Remarks'] == row['Remarks']) &
                (st.session_state.data['Status'] == row['Status']) &
                (st.session_state.data['Pending'] == row['Pending'])
            ].index
            if len(actual_idx) == 0:
                continue
            actual_idx = actual_idx[0]

            if st.session_state.editing == actual_idx:
                with st.form(f"edit_{actual_idx}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        edit_date = st.date_input("📅 Date", value=pd.to_datetime(row["Date"]), key=f"date_{actual_idx}")
                        edit_size = st.number_input("📐 Size (mm)", value=int(row["Size (mm)"]), key=f"size_{actual_idx}")
                    with col2:
                        edit_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"], index=0 if row["Type"] == "Inward" else 1, key=f"type_{actual_idx}")
                        edit_qty = st.number_input("🔢 Quantity", value=int(row["Quantity"]), key=f"qty_{actual_idx}")
                    edit_remarks = st.text_input("📝 Remarks", value=row["Remarks"], key=f"rem_{actual_idx}")
                    edit_status = st.selectbox("📂 Status", ["Current", "Future"], index=0 if row["Status"] == "Current" else 1, key=f"status_{actual_idx}")
                    edit_pending = st.checkbox("❗ Pending", value=row["Pending"], key=f"pend_{actual_idx}")
                    colA, colB = st.columns(2)
                    with colA:
                        if st.form_submit_button("💾 Save"):
                            st.session_state.data.at[actual_idx, "Date"] = edit_date.strftime('%Y-%m-%d')
                            st.session_state.data.at[actual_idx, "Size (mm)"] = edit_size
                            st.session_state.data.at[actual_idx, "Type"] = edit_type
                            st.session_state.data.at[actual_idx, "Quantity"] = edit_qty
                            st.session_state.data.at[actual_idx, "Remarks"] = edit_remarks
                            st.session_state.data.at[actual_idx, "Status"] = edit_status
                            st.session_state.data.at[actual_idx, "Pending"] = edit_pending
                            st.session_state.editing = None
                            auto_save_to_gsheet()
                            st.rerun()
                    with colB:
                        if st.form_submit_button("❌ Cancel"):
                            st.session_state.editing = None
                            st.rerun()
            else:
                col1, col2 = st.columns([10, 1])
                with col1:
                    st.dataframe(pd.DataFrame([{
                        "Date": row["Date"],
                        "Size (mm)": row["Size (mm)"],
                        "Type": row["Type"],
                        "Quantity": row["Quantity"],
                        "Remarks": row["Remarks"],
                        "Status": row["Status"],
                        "Pending": "Yes" if row["Pending"] else "No"
                    }]), hide_index=True, use_container_width=True)
                with col2:
                    if st.button("✏", key=f"edit_{actual_idx}"):
                        st.session_state.editing = actual_idx
                    if st.button("❌", key=f"del_{actual_idx}"):
                        st.session_state.data = st.session_state.data.drop(actual_idx).reset_index(drop=True)
                        auto_save_to_gsheet()
                        st.rerun()

# Sync time
if st.session_state.last_sync != "Never":
    st.caption(f"🕒 Last synced: {st.session_state.last_sync}")
