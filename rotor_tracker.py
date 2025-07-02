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
# Fix Pending type
if 'Pending' in st.session_state.data.columns:
    st.session_state.data['Pending'] = st.session_state.data['Pending'].astype(str).str.lower().isin(['true', 'yes'])
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
def render_complete_movement_log(data):
    import streamlit as st
    from datetime import datetime
    import pandas as pd

    st.markdown("### 📄 View Movement Log")
    with st.expander("🔎 Filter Movement Log", expanded=True):
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            status_filter = st.selectbox("🗂 Status", ["All", "Current", "Coming Rotors"])
        with col2:
            pending_filter = st.selectbox("⏳ Pending", ["All", "Yes", "No"])
        with col3:
            size_filter = st.selectbox("📏 Size (mm)", ["All"] + sorted(data["Size (mm)"].dropna().unique().astype(str)))
        with col4:
            remark_filter = st.text_input("📝 Remarks contains", "")
        with col5:
            date_filter = st.date_input("📅 Date", [])

    # Apply filters
    df_filtered = data.copy()

    if status_filter != "All":
        df_filtered = df_filtered[df_filtered["Status"] == status_filter]

    if pending_filter != "All":
        df_filtered = df_filtered[df_filtered["Pending"] == (pending_filter == "Yes")]

    if size_filter != "All":
        df_filtered = df_filtered[df_filtered["Size (mm)"].astype(str) == size_filter]

    if remark_filter:
        df_filtered = df_filtered[df_filtered["Remarks"].str.contains(remark_filter, case=False, na=False)]

    if isinstance(date_filter, list) and len(date_filter) == 2:
        start_date, end_date = date_filter
        df_filtered = df_filtered[
            (pd.to_datetime(df_filtered["Date"]).dt.date >= start_date)
            & (pd.to_datetime(df_filtered["Date"]).dt.date <= end_date)
        ]

    if df_filtered.empty:
        st.info("🔍 No entries match the selected filters.")
    else:
        for idx, row in df_filtered.iterrows():
            if st.session_state.get(f"edit_{idx}", False):
                with st.form(f"edit_form_{idx}", clear_on_submit=False):
                    edit_cols = st.columns(7)
                    new_date = edit_cols[0].date_input("Date", pd.to_datetime(row["Date"]), key=f"date_{idx}")
                    new_size = edit_cols[1].text_input("Size (mm)", row["Size (mm)"], key=f"size_{idx}")
                    new_type = edit_cols[2].selectbox("Type", ["Inward", "Outward"], index=["Inward", "Outward"].index(row["Type"]), key=f"type_{idx}")
                    new_qty = edit_cols[3].number_input("Quantity", value=int(row["Quantity"]), step=1, key=f"qty_{idx}")
                    new_pending = edit_cols[4].selectbox("Pending", ["Yes", "No"], index=int(row["Pending"]), key=f"pending_{idx}")
                    new_status = edit_cols[5].selectbox("Status", ["Current", "Coming Rotors"], index=["Current", "Coming Rotors"].index(row["Status"]), key=f"status_{idx}")
                    new_remarks = edit_cols[6].text_input("Remarks", row["Remarks"], key=f"remarks_{idx}")

                    save_col, cancel_col = st.columns([1, 1])
                    if save_col.form_submit_button("✅ Save"):
                        st.session_state.data.at[idx, "Date"] = new_date.strftime("%Y-%m-%d")
                        st.session_state.data.at[idx, "Size (mm)"] = new_size
                        st.session_state.data.at[idx, "Type"] = new_type
                        st.session_state.data.at[idx, "Quantity"] = new_qty
                        st.session_state.data.at[idx, "Pending"] = new_pending == "Yes"
                        st.session_state.data.at[idx, "Status"] = new_status
                        st.session_state.data.at[idx, "Remarks"] = new_remarks
                        st.session_state[f"edit_{idx}"] = False
                        st.rerun()
                    if cancel_col.form_submit_button("❌ Cancel"):
                        st.session_state[f"edit_{idx}"] = False
                        st.rerun()
            else:
                # Display mode
                row_display = f"📅 {row['Date']} | 🖊 {row['Size (mm)']}mm | 🔄 {row['Type']} | 📦 {row['Quantity']} | ⏳ {'Yes' if row['Pending'] else 'No'} | 📁 {row['Status']} | 📝 {row['Remarks']}"
                with st.container():
                    st.markdown(row_display)
                    col_edit, col_delete = st.columns([0.1, 0.1])
                    if col_edit.button("✏", key=f"edit_button_{idx}"):
                        st.session_state[f"edit_{idx}"] = True
                    if col_delete.button("🗑", key=f"delete_button_{idx}"):
                        st.session_state.data.drop(idx, inplace=True)
                        st.rerun()
# ====== FOOTER ======
if st.session_state.last_sync != "Never":
    st.caption(f"Last synced: {st.session_state.last_sync}")
