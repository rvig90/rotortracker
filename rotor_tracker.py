import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ========== SESSION STATE INITIALIZATION ==========
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending'
    ])
    st.session_state.editing = None
    st.session_state.loaded = False
    st.session_state.last_sync = "Never"

# ========== GOOGLE SHEETS ==========
def get_gsheet_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"]) if isinstance(st.secrets["gcp_service_account"], str) else dict(st.secrets["gcp_service_account"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def normalize_pending_column(df):
    df["Pending"] = df["Pending"].apply(lambda x: str(x).lower() == "true" if isinstance(x, str) else bool(x))
    return df

def load_from_gsheet():
    try:
        client = get_gsheet_connection()
        sheet = client.open("Rotor Log").sheet1
        records = sheet.get_all_records()
        if records:
            df = pd.DataFrame(records)
            if 'Pending' not in df.columns:
                df['Pending'] = False
            df = normalize_pending_column(df)
            st.session_state.data = df
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.success("✅ Data loaded from Google Sheet")
        else:
            st.info("Google Sheet is empty.")
    except Exception as e:
        st.error(f"Failed to load from Google Sheets: {e}")

def auto_save_to_gsheet():
    try:
        client = get_gsheet_connection()
        sheet = client.open("Rotor Log").sheet1
        backup = client.open("Rotor Log").worksheet("Backup")

        df = st.session_state.data.copy()
        df['Pending'] = df['Pending'].apply(lambda x: "TRUE" if x else "FALSE")
        expected_cols = ['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending']
        for col in expected_cols:
            if col not in df.columns:
                df[col] = ""
        df = df[expected_cols]

        sheet.clear()
        backup.clear()

        records = [df.columns.tolist()] + df.values.tolist()
        sheet.update(records)
        backup.update(records)

        st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"❌ Auto-save failed: {e}")

# ========== AUTO-LOAD ON FIRST RUN ==========
if not st.session_state.loaded:
    load_from_gsheet()
    st.session_state.loaded = True

# ========== SYNC BUTTON ==========
if st.button("🔄 Sync Now"):
    load_from_gsheet()

# ========== ENTRY FORMS ==========
form_tabs = st.tabs(["Current Movement", "Coming Rotors", "Pending Rotors"])

with form_tabs[0]:
    with st.form("current_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Date", value=datetime.today())
            size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
        with col2:
            type_ = st.selectbox("🔄 Type", ["Inward", "Outgoing"])
            qty = st.number_input("🔢 Quantity", min_value=1, step=1)
        remarks = st.text_input("📝 Remarks")
        if st.form_submit_button("➕ Add Entry"):
            new = pd.DataFrame([{
                'Date': date.strftime("%Y-%m-%d"),
                'Size (mm)': size, 'Type': type_, 'Quantity': qty,
                'Remarks': remarks, 'Status': 'Current', 'Pending': False
            }])
            st.session_state.data = pd.concat([st.session_state.data, new], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

with form_tabs[1]:
    with st.form("future_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Expected Date", min_value=datetime.today() + timedelta(days=1))
            size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
        with col2:
            qty = st.number_input("🔢 Quantity", min_value=1, step=1)
            remarks = st.text_input("📝 Remarks")
        if st.form_submit_button("➕ Add Coming Rotors"):
            new = pd.DataFrame([{
                'Date': date.strftime("%Y-%m-%d"),
                'Size (mm)': size, 'Type': 'Inward', 'Quantity': qty,
                'Remarks': remarks, 'Status': 'Future', 'Pending': False
            }])
            st.session_state.data = pd.concat([st.session_state.data, new], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

with form_tabs[2]:
    with st.form("pending_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Date", value=datetime.today())
            size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
        with col2:
            qty = st.number_input("🔢 Quantity", min_value=1, step=1)
            remarks = st.text_input("📝 Remarks", value="Pending delivery")
        if st.form_submit_button("➕ Add Pending Rotors"):
            new = pd.DataFrame([{
                'Date': date.strftime("%Y-%m-%d"),
                'Size (mm)': size, 'Type': 'Outgoing', 'Quantity': qty,
                'Remarks': remarks, 'Status': 'Current', 'Pending': True
            }])
            st.session_state.data = pd.concat([st.session_state.data, new], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

# ========== STOCK SUMMARY ==========
st.subheader("📊 Current Stock Summary")
try:
    df = normalize_pending_column(st.session_state.data.copy())

    current = df[(df['Status'] == 'Current') & (~df['Pending'])].copy()
    current['Net'] = current.apply(lambda x: x['Quantity'] if x['Type'] == 'Inward' else -x['Quantity'], axis=1)
    stock = current.groupby('Size (mm)')['Net'].sum().reset_index()

    future = df[df['Status'] == 'Future']
    coming = future.groupby('Size (mm)')['Quantity'].sum().reset_index()

    pending = df[(df['Status'] == 'Current') & (df['Pending'])]
    pending_group = pending.groupby('Size (mm)')['Quantity'].sum().reset_index()

    combined = pd.merge(stock, coming, on='Size (mm)', how='outer')
    combined = pd.merge(combined, pending_group, on='Size (mm)', how='outer', suffixes=('', '_pending'))
    combined = combined.fillna(0)
    combined.columns = ['Size (mm)', 'Current Stock', 'Coming Rotors', 'Pending Rotors']

    st.dataframe(combined, use_container_width=True, hide_index=True)
except Exception as e:
    st.error(f"Stock summary error: {e}")

# ========== MOVEMENT LOG ==========
with st.expander("📋 View Movement Log", expanded=True):
    try:
        df = normalize_pending_column(st.session_state.data.copy())
        df["Parsed_Date"] = pd.to_datetime(df["Date"], errors="coerce")

        st.markdown("### 🔍 Filter Movement Log")
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.selectbox("📂 Status", ["All", "Current", "Future"])
        with col2:
            size_filter = st.multiselect("📐 Size (mm)", sorted(df['Size (mm)'].unique()))
        with col3:
            pending_filter = st.selectbox("❗ Pending", ["All", "Yes", "No"])
        remark_search = st.text_input("📝 Search Remarks")
        date_range = st.date_input("📅 Date Range", value=[
            df["Parsed_Date"].min().date(),
            df["Parsed_Date"].max().date()
        ])

        if status_filter != "All":
            df = df[df["Status"] == status_filter]
        if pending_filter == "Yes":
            df = df[df["Pending"] == True]
        elif pending_filter == "No":
            df = df[df["Pending"] == False]
        if size_filter:
            df = df[df["Size (mm)"].isin(size_filter)]
        if remark_search:
            df = df[df["Remarks"].str.contains(remark_search, case=False, na=False)]
        if isinstance(date_range, list) and len(date_range) == 2:
            start_date, end_date = date_range
            df = df[(df["Parsed_Date"].dt.date >= start_date) & (df["Parsed_Date"].dt.date <= end_date)]

        df = df.reset_index(drop=True)

        for idx, row in df.iterrows():
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
                with st.form(f"edit_form_{actual_idx}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        date = st.date_input("📅", value=pd.to_datetime(row["Date"]), key=f"date_{actual_idx}")
                        size = st.number_input("📐", value=row["Size (mm)"], key=f"size_{actual_idx}")
                    with col2:
                        type_ = st.selectbox("🔄", ["Inward", "Outgoing"], index=0 if row["Type"] == "Inward" else 1, key=f"type_{actual_idx}")
                        qty = st.number_input("🔢", value=row["Quantity"], key=f"qty_{actual_idx}")
                    remarks = st.text_input("📝", value=row["Remarks"], key=f"rem_{actual_idx}")
                    status = st.selectbox("📂", ["Current", "Future"], index=0 if row["Status"] == "Current" else 1, key=f"status_{actual_idx}")
                    pending = st.checkbox("❗", value=row["Pending"], key=f"pend_{actual_idx}")

                    colA, colB = st.columns(2)
                    with colA:
                        if st.form_submit_button("💾 Save"):
                            st.session_state.data.at[actual_idx, "Date"] = date.strftime("%Y-%m-%d")
                            st.session_state.data.at[actual_idx, "Size (mm)"] = size
                            st.session_state.data.at[actual_idx, "Type"] = type_
                            st.session_state.data.at[actual_idx, "Quantity"] = qty
                            st.session_state.data.at[actual_idx, "Remarks"] = remarks
                            st.session_state.data.at[actual_idx, "Status"] = status
                            st.session_state.data.at[actual_idx, "Pending"] = pending
                            st.session_state.editing = None
                            auto_save_to_gsheet()
                            st.rerun()
                    with colB:
                        if st.form_submit_button("❌ Cancel"):
                            st.session_state.editing = None
                            st.rerun()
            else:
                col1, col2 = st.columns([9, 1])
                with col1:
                    st.dataframe(pd.DataFrame([row.drop("Parsed_Date")]), use_container_width=True, hide_index=True)
                with col2:
                    if st.button("✏", key=f"edit_{actual_idx}"):
                        st.session_state.editing = actual_idx
                    if st.button("🗑", key=f"del_{actual_idx}"):
                        st.session_state.data.drop(actual_idx, inplace=True)
                        st.session_state.data.reset_index(drop=True, inplace=True)
                        auto_save_to_gsheet()
                        st.rerun()

    except Exception as e:
        st.error(f"❌ Error in movement log: {e}")

# ========== LAST SYNC ==========
if st.session_state.last_sync:
    st.caption(f"Last synced: {st.session_state.last_sync}")
