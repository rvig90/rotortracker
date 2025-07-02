import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ====== SESSION INIT ======
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending'])
    st.session_state.editing = None
    st.session_state.last_sync = "Never"
if 'first_load_done' not in st.session_state:
    st.session_state.first_load_done = False

# ====== GSheet CONNECTION ======
def get_gsheet_connection():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(st.secrets["gcp_service_account"]) if isinstance(st.secrets["gcp_service_account"], str) else dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds).open("Rotor Log")
    except Exception as e:
        st.error(f"Connection failed: {e}")
        return None

# ====== LOAD FROM GSHEET ======
def load_from_gsheet():
    try:
        sheet = get_gsheet_connection().sheet1
        records = sheet.get_all_records()
        if records:
            df = pd.DataFrame(records)
            df['Pending'] = df['Pending'].astype(str).str.lower().map({'true': True, 'false': False}).fillna(False)
            st.session_state.data = df
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"Error loading: {e}")

# ====== BACKUP SHEET ======
def save_to_backup_sheet(df):
    try:
        backup = get_gsheet_connection().worksheet("Backup")
        df.insert(0, 'Backup Time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        backup.append_rows([df.columns.tolist()] + df.astype(str).values.tolist())
    except Exception as e:
        st.warning(f"Backup failed: {e}")

# ====== AUTO SAVE ======
def auto_save_to_gsheet():
    try:
        sheet = get_gsheet_connection().sheet1
        sheet.clear()
        sheet.append_row(st.session_state.data.columns.tolist())
        for _, row in st.session_state.data.iterrows():
            sheet.append_row(row.astype(str).tolist())
        save_to_backup_sheet(st.session_state.data.copy())
        st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"Auto-save failed: {e}")

# ====== AUTO LOAD ON FIRST RUN ======
if not st.session_state.first_load_done:
    load_from_gsheet()
    st.session_state.first_load_done = True

# ====== MANUAL SYNC BUTTON ======
col1, col2 = st.columns([1, 2])
if col1.button("🔄 Sync Now"):
    load_from_gsheet()
if col2.button("📂 Previously Saved"):
    load_from_gsheet()

# ====== ENTRY FORMS ======
form_tabs = st.tabs(["Current Movement", "Coming Rotors", "Pending Rotors"])
with form_tabs[0]:
    with st.form("current_form"):
        d1, d2 = st.columns(2)
        with d1:
            date = st.date_input("📅 Date", datetime.today())
            rotor_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
        with d2:
            typ = st.selectbox("🔄 Type", ["Inward", "Outgoing"])
            qty = st.number_input("🔢 Quantity", min_value=1, step=1)
        remarks = st.text_input("📝 Remarks")
        if st.form_submit_button("➕ Add Entry"):
            new_entry = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'), 'Size (mm)': rotor_size,
                'Type': typ, 'Quantity': qty, 'Remarks': remarks,
                'Status': 'Current', 'Pending': False
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

with form_tabs[1]:
    with st.form("future_form"):
        c1, c2 = st.columns(2)
        with c1:
            fdate = st.date_input("📅 Expected Date", datetime.today() + timedelta(days=1))
            fsize = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
        with c2:
            fqty = st.number_input("🔢 Quantity", min_value=1, step=1)
            fremarks = st.text_input("📝 Remarks")
        if st.form_submit_button("➕ Add Coming Rotors"):
            new_entry = pd.DataFrame([{
                'Date': fdate.strftime('%Y-%m-%d'), 'Size (mm)': fsize,
                'Type': 'Inward', 'Quantity': fqty, 'Remarks': fremarks,
                'Status': 'Future', 'Pending': False
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

with form_tabs[2]:
    with st.form("pending_form"):
        p1, p2 = st.columns(2)
        with p1:
            pdate = st.date_input("📅 Date", datetime.today())
            psize = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
        with p2:
            pqty = st.number_input("🔢 Quantity", min_value=1, step=1)
            premarks = st.text_input("📝 Remarks", "Pending delivery")
        if st.form_submit_button("➕ Add Pending Rotors"):
            new_entry = pd.DataFrame([{
                'Date': pdate.strftime('%Y-%m-%d'), 'Size (mm)': psize,
                'Type': 'Outgoing', 'Quantity': pqty, 'Remarks': premarks,
                'Status': 'Current', 'Pending': True
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

# ====== STOCK SUMMARY ======
st.subheader("📊 Current Stock Summary")
try:
    df = st.session_state.data.copy()
    df['Pending'] = df['Pending'].astype(bool)
    current = df[(df['Status'] == 'Current') & (~df['Pending'])].copy()
    current['Net'] = current.apply(lambda x: x['Quantity'] if x['Type'] == 'Inward' else -x['Quantity'], axis=1)
    stock = current.groupby('Size (mm)')['Net'].sum().reset_index()
    stock = stock[stock['Net'] != 0]

    future = df[df['Status'] == 'Future'].groupby('Size (mm)')['Quantity'].sum().reset_index()
    pending = df[df['Pending']].groupby('Size (mm)')['Quantity'].sum().reset_index()

    combined = pd.merge(stock, future, on='Size (mm)', how='outer', suffixes=('', '_Future'))
    combined = pd.merge(combined, pending, on='Size (mm)', how='outer', suffixes=('', '_Pending'))
    combined.columns = ['Size (mm)', 'Current Stock', 'Coming Rotors', 'Pending Rotors']
    combined = combined.fillna(0)

    st.dataframe(combined, use_container_width=True, hide_index=True)
except Exception as e:
    st.error(f"Error in summary: {e}")

# ====== MOVEMENT LOG ======
with st.expander("📋 View Movement Log", expanded=True):
    st.markdown("### 🔍 Filter Movement Log")
    df = st.session_state.data.copy()
    df['Pending'] = df['Pending'].astype(bool)

    col1, col2, col3, col4 = st.columns(4)
    f_status = col1.selectbox("📂 Status", options=["All"] + sorted(df['Status'].unique().tolist()))
    f_pending = col2.selectbox("⏳ Pending", options=["All", "Yes", "No"])
    f_size = col3.selectbox("📏 Size (mm)", options=["All"] + sorted(df['Size (mm)'].unique().tolist()))
    f_remarks = col4.text_input("🔍 Remarks contains")

    if f_status != "All":
        df = df[df['Status'] == f_status]
    if f_pending != "All":
        df = df[df['Pending'] == (f_pending == "Yes")]
    if f_size != "All":
        df = df[df['Size (mm)'] == f_size]
    if f_remarks:
        df = df[df['Remarks'].str.contains(f_remarks, case=False)]

    if df.empty:
        st.warning("🚫 No entries match the selected filters.")
    else:
        for idx, row in df[::-1].iterrows():
            st.markdown("---")
            if st.session_state.editing == idx:
                with st.form(f"edit_{idx}"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        edate = st.date_input("📅", datetime.strptime(row['Date'], '%Y-%m-%d'))
                        esize = st.number_input("📐", value=int(row['Size (mm)']), min_value=1, key=f"esize_{idx}")
                    with ec2:
                        etype = st.selectbox("🔄", ["Inward", "Outgoing"], index=0 if row['Type'] == 'Inward' else 1, key=f"etype_{idx}")
                        eqty = st.number_input("🔢", value=int(row['Quantity']), min_value=1, key=f"eqty_{idx}")
                    eremarks = st.text_input("📝", value=row['Remarks'], key=f"eremarks_{idx}")
                    epending = st.checkbox("Pending", value=row['Pending'], key=f"epending_{idx}")

                    save_col, cancel_col = st.columns([1, 1])
                    if save_col.form_submit_button("💾 Save"):
                        st.session_state.data.at[idx, 'Date'] = edate.strftime('%Y-%m-%d')
                        st.session_state.data.at[idx, 'Size (mm)'] = esize
                        st.session_state.data.at[idx, 'Type'] = etype
                        st.session_state.data.at[idx, 'Quantity'] = eqty
                        st.session_state.data.at[idx, 'Remarks'] = eremarks
                        st.session_state.data.at[idx, 'Pending'] = epending
                        st.session_state.editing = None
                        auto_save_to_gsheet()
                        st.rerun()
                    if cancel_col.form_submit_button("❌ Cancel"):
                        st.session_state.editing = None
                        st.rerun()
            else:
                st.write(f"📅 *{row['Date']}* | 📐 *{row['Size (mm)']} mm* | 🔄 {row['Type']} | 🔢 {row['Quantity']} | 📝 {row['Remarks']} | ⏳ Pending: {'Yes' if row['Pending'] else 'No'} | 📂 Status: {row['Status']}")
                e_col, d_col = st.columns([1, 1])
                if e_col.button("✏ Edit", key=f"editbtn_{idx}"):
                    st.session_state.editing = idx
                if d_col.button("🗑 Delete", key=f"delbtn_{idx}"):
                    st.session_state.data = st.session_state.data.drop(idx).reset_index(drop=True)
                    auto_save_to_gsheet()
                    st.rerun()

# ====== FOOTER ======
st.caption(f"Last synced: {st.session_state.last_sync}")
