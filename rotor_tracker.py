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
# --- MOVEMENT LOG ---
with st.expander("📋 Movement Log", expanded=True):
    df = st.session_state.data.copy()
    df['Date'] = pd.to_datetime(df['Date'])
    df['Pending'] = df['Pending'].astype(bool)

    st.markdown("### 🔍 Filters")
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        status_choices = ["All"] + df['Status'].unique().tolist()
        f_status = st.selectbox("Status", status_choices, index=status_choices.index("All"))
    with f2:
        min_date = df['Date'].min()
        max_date = df['Date'].max()
        f_dates = st.date_input("Date range", [min_date, max_date])
    with f3:
        size_choices = ["All"] + sorted(df['Size (mm)'].astype(str).unique().tolist())
        f_size = st.selectbox("Size (mm)", size_choices, index=0)
    with f4:
        f_remarks = st.text_input("Remarks contains")

    # Apply filters
    filt = df.copy()
    if f_status != "All":
        filt = filt[filt['Status'] == f_status]
    if f_size != "All":
        filt = filt[filt['Size (mm)'].astype(str) == f_size]
    if f_remarks:
        filt = filt[filt['Remarks'].str.contains(f_remarks, case=False, na=False)]
    if len(f_dates) == 2:
        start_d, end_d = map(pd.to_datetime, f_dates)
        filt = filt[(filt['Date'] >= start_d) & (filt['Date'] <= end_d)]

    if filt.empty:
        st.info("⚠ No entries match the filters")
    else:
        st.dataframe(filt.reset_index(drop=True), use_container_width=True)

        for idx, row in filt.iterrows():
            orig_idx = df.index[df.index == row.name][0]

            cols = st.columns([6,1,1])
            with cols[0]:
                st.write(f"📅 {row['Date'].strftime('%Y-%m-%d')} | 📏 {row['Size (mm)']}mm | 🔄 {row['Type']} | 🧰 {row['Quantity']} | 📝 {row['Remarks']} | ⏳ {'Yes' if row['Pending'] else 'No'} | 📁 {row['Status']}")

            with cols[1]:
                if st.button("✏", key=f"edit_{orig_idx}"):
                    st.session_state.editing = orig_idx
            with cols[2]:
                if st.button("🗑", key=f"del_{orig_idx}"):
                    st.session_state.data = st.session_state.data.drop(orig_idx).reset_index(drop=True)
                    auto_save_to_gsheet()
                    st.rerun()

            if st.session_state.editing == orig_idx:
                with st.form(f"form_{orig_idx}", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    edate = st.date_input("📅", row['Date'], key=f"edate_{orig_idx}")
                    esize = st.number_input("📏 Rotor Size", value=int(row['Size (mm)']), min_value=1, key=f"esize_{orig_idx}")
                    etype = st.selectbox("🔄 Type", ["Inward","Outgoing"], index=0 if row['Type']=="Inward" else 1, key=f"etype_{orig_idx}")
                    eqty = st.number_input("🔢 Quantity", value=int(row['Quantity']), min_value=1, key=f"eqty_{orig_idx}")
                    eremark = st.text_input("📝 Remarks", value=row['Remarks'], key=f"eremark_{orig_idx}")
                    epending = st.checkbox("⏳ Pending", value=row['Pending'], key=f"epending_{orig_idx}")
                    estatus = st.selectbox("📁 Status", ["Current","Future"], index=0 if row['Status']=="Current" else 1, key=f"estatus_{orig_idx}")

                    sb, cb = st.columns(2)
                    if sb.form_submit_button("💾 Save"):
                        st.session_state.data.at[orig_idx, 'Date'] = edate.strftime("%Y-%m-%d")
                        st.session_state.data.at[orig_idx, 'Size (mm)'] = esize
                        st.session_state.data.at[orig_idx, 'Type'] = etype
                        st.session_state.data.at[orig_idx, 'Quantity'] = eqty
                        st.session_state.data.at[orig_idx, 'Remarks'] = eremark
                        st.session_state.data.at[orig_idx, 'Pending'] = epending
                        st.session_state.data.at[orig_idx, 'Status'] = estatus
                        st.session_state.editing = None
                        auto_save_to_gsheet()
                        st.rerun()
                    if cb.form_submit_button("❌ Cancel"):
                        st.session_state.editing = None
                        st.rerun()
# ====== FOOTER ======
if st.session_state.last_sync != "Never":
    st.caption(f"Last synced: {st.session_state.last_sync}")
