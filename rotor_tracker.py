import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import time

# ====== INITIALIZE SESSION STATE ======
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending'
    ])
    st.session_state.last_sync = "Never"
    st.session_state.editing = None
    st.session_state.first_load_done = False

# ====== GOOGLE SHEETS INTEGRATION ======
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

def load_from_gsheet():
    try:
        sheet = get_gsheet_connection()
        if sheet:
            records = sheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
                df['Status'] = df.get('Status', 'Current')
                df['Pending'] = df.get('Pending', False)
                st.session_state.data = df
                st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success("Data loaded successfully!")
            else:
                st.info("No data found in Google Sheet")
    except Exception as e:
        st.error(f"Error loading data: {e}")

def auto_save_to_gsheet():
    try:
        sheet = get_gsheet_connection()
        if sheet is None:
            return
        sheet.clear()
        sheet.append_row(st.session_state.data.columns.tolist())
        for _, row in st.session_state.data.iterrows():
            sheet.append_row(row.tolist())
        st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.warning(f"Auto-save failed: {e}")

def save_to_backup_sheet(df):
    try:
        backup_sheet = get_gsheet_connection().spreadsheet.worksheet("Backup")
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        df.insert(0, 'Backup Time', timestamp)
        records = [df.columns.tolist()] + df.values.tolist()
        backup_sheet.append_rows(records)
    except Exception as e:
        st.warning(f"Backup failed: {e}")

# Load data on first app open
if not st.session_state.first_load_done:
    load_from_gsheet()
    st.session_state.first_load_done = True

# ====== SYNC / RESTORE BUTTONS ======
col_sync, col_reload = st.columns(2)
with col_sync:
    if st.button("🔄 Sync Now"):
        load_from_gsheet()

with col_reload:
    if st.button("🕘 Previously Saved"):
        load_from_gsheet()

# ====== ENTRY FORMS ======
form_tabs = st.tabs(["Current Movement", "Coming Rotors", "Pending Rotors"])

def add_entry(new_entry):
    st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
    save_to_backup_sheet(st.session_state.data.copy())
    auto_save_to_gsheet()
    st.rerun()

# === Current Movement ===
with form_tabs[0]:
    with st.form("current_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Date", value=datetime.today())
            rotor_size = st.number_input("📐 Rotor Size (mm)", min_value=1)
        with col2:
            entry_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"])
            quantity = st.number_input("🔢 Quantity", min_value=1)
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
            add_entry(new_entry)

# === Coming Rotors ===
with form_tabs[1]:
    with st.form("future_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Expected Date", min_value=datetime.today() + timedelta(days=1))
            size = st.number_input("📐 Rotor Size (mm)", min_value=1)
        with col2:
            qty = st.number_input("🔢 Quantity", min_value=1)
            remarks = st.text_input("📝 Remarks")
        if st.form_submit_button("➕ Add Coming Rotors"):
            new_entry = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'),
                'Size (mm)': size,
                'Type': 'Inward',
                'Quantity': qty,
                'Remarks': remarks,
                'Status': 'Future',
                'Pending': False
            }])
            add_entry(new_entry)

# === Pending Rotors ===
with form_tabs[2]:
    with st.form("pending_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Date", value=datetime.today())
            size = st.number_input("📐 Rotor Size (mm)", min_value=1)
        with col2:
            qty = st.number_input("🔢 Quantity", min_value=1)
            remarks = st.text_input("📝 Remarks", value="Pending delivery")
        if st.form_submit_button("➕ Add Pending Rotors"):
            new_entry = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'),
                'Size (mm)': size,
                'Type': 'Outgoing',
                'Quantity': qty,
                'Remarks': remarks,
                'Status': 'Current',
                'Pending': True
            }])
            add_entry(new_entry)

# ====== STOCK SUMMARY ======
st.subheader("📊 Current Stock Summary")
if not st.session_state.data.empty:
    current = st.session_state.data[
        (st.session_state.data['Status'] == 'Current') & (~st.session_state.data['Pending'])
    ].copy()
    current['Net'] = current.apply(lambda x: x['Quantity'] if x['Type'] == 'Inward' else -x['Quantity'], axis=1)
    stock = current.groupby('Size (mm)')['Net'].sum().reset_index()
    stock = stock[stock['Net'] != 0]

    future = st.session_state.data[st.session_state.data['Status'] == 'Future']
    coming = future.groupby('Size (mm)')['Quantity'].sum().reset_index()

    pending = st.session_state.data[st.session_state.data['Pending']]
    pending_rotors = pending.groupby('Size (mm)')['Quantity'].sum().reset_index()

    combined = pd.merge(stock, coming, on='Size (mm)', how='outer')
    combined = pd.merge(combined, pending_rotors, on='Size (mm)', how='outer', suffixes=('', '_pending'))
    combined = combined.fillna(0)
    combined.columns = ['Size (mm)', 'Current Stock', 'Coming Rotors', 'Pending Rotors']
    st.dataframe(combined, use_container_width=True, hide_index=True)
else:
    st.info("No data available yet")

# ====== MOVEMENT LOG ======
with st.expander("📋 View Movement Log", expanded=False):
    if not st.session_state.data.empty:
        st.markdown("### 🔍 Filter Movement Log")
        filt_col1, filt_col2, filt_col3, filt_col4 = st.columns(4)
        status_filter = filt_col1.selectbox("📂 Status", ["All", "Current", "Future"])
        pending_filter = filt_col2.selectbox("⏳ Pending", ["All", "Yes", "No"])
        size_filter = filt_col3.selectbox("📐 Size (mm)", ["All"] + sorted(st.session_state.data['Size (mm)'].astype(str).unique().tolist()))
        remarks_filter = filt_col4.text_input("📝 Remarks contains")

        filtered = st.session_state.data.copy()
        if status_filter != "All":
            filtered = filtered[filtered['Status'] == status_filter]
        if pending_filter != "All":
            filtered = filtered[filtered['Pending'] == (pending_filter == "Yes")]
        if size_filter != "All":
            filtered = filtered[filtered['Size (mm)'].astype(str) == size_filter]
        if remarks_filter:
            filtered = filtered[filtered['Remarks'].str.contains(remarks_filter, case=False, na=False)]

        if filtered.empty:
            st.info("No entries match the selected filters.")
        else:
            for idx, row in filtered.iterrows():
                if st.session_state.editing == idx:
                    with st.form(f"edit_form_{idx}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            edit_date = st.date_input("📅 Date", value=pd.to_datetime(row['Date']))
                            edit_size = st.number_input("📐 Size", value=int(row['Size (mm)']), min_value=1)
                        with col2:
                            edit_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"], index=0 if row['Type'] == "Inward" else 1)
                            edit_qty = st.number_input("🔢 Quantity", value=int(row['Quantity']), min_value=1)
                        edit_remarks = st.text_input("📝 Remarks", value=row['Remarks'])
                        edit_pending = st.checkbox("Pending", value=row['Pending'])

                        save_col, cancel_col = st.columns(2)
                        with save_col:
                            if st.form_submit_button("💾 Save"):
                                st.session_state.data.at[idx, 'Date'] = edit_date.strftime('%Y-%m-%d')
                                st.session_state.data.at[idx, 'Size (mm)'] = edit_size
                                st.session_state.data.at[idx, 'Type'] = edit_type
                                st.session_state.data.at[idx, 'Quantity'] = edit_qty
                                st.session_state.data.at[idx, 'Remarks'] = edit_remarks
                                st.session_state.data.at[idx, 'Pending'] = edit_pending
                                st.session_state.editing = None
                                auto_save_to_gsheet()
                                st.rerun()
                        with cancel_col:
                            if st.form_submit_button("❌ Cancel"):
                                st.session_state.editing = None
                                st.rerun()
                else:
                    cols = st.columns([7, 1, 1])
                    with cols[0]:
                        st.dataframe(pd.DataFrame([row]), use_container_width=True, hide_index=True)
                    with cols[1]:
                        if st.button("✏", key=f"edit_{idx}"):
                            st.session_state.editing = idx
                    with cols[2]:
                        if st.button("🗑", key=f"del_{idx}"):
                            st.session_state.data.drop(index=idx, inplace=True)
                            st.session_state.data.reset_index(drop=True, inplace=True)
                            auto_save_to_gsheet()
                            st.rerun()
    else:
        st.info("No entries to display.")

# ====== FOOTER ======
if st.session_state.last_sync != "Never":
    st.caption(f"Last synced: {st.session_state.last_sync}")
