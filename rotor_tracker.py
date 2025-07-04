import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

st.set_page_config(layout="wide")

# Initialize session state
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending'
    ])
    st.session_state.editing = None
    st.session_state.loaded = False
    st.session_state.last_sync = "Never"

# Normalize Pending column
def normalize_pending_column(df):
    df['Pending'] = df['Pending'].apply(
        lambda x: str(x).lower() == 'true' if isinstance(x, str) else bool(x)
    )
    return df

# Connect to Google Sheets
def get_gsheet_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"]) if isinstance(st.secrets["gcp_service_account"], str) else dict(st.secrets["gcp_service_account"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# Load data from sheet
def load_from_gsheet():
    try:
        sheet = get_gsheet_connection().open("Rotor Log").worksheet("Sheet1")
        records = sheet.get_all_records()
        df = pd.DataFrame(records)
        if not df.empty:
            if 'Status' not in df.columns: df['Status'] = 'Current'
            if 'Pending' not in df.columns: df['Pending'] = False
            df = normalize_pending_column(df)
            st.session_state.data = df
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.success("✅ Data loaded from Google Sheet")
        else:
            st.info("ℹ No records found in Google Sheet.")
    except Exception as e:
        st.error(f"❌ Error loading: {e}")

# Save to both main sheet and backup
def auto_save_to_gsheet():
    try:
        client = get_gsheet_connection()
        df = st.session_state.data.copy()

        if not df.empty:
            df['Pending'] = df['Pending'].apply(lambda x: "TRUE" if x else "FALSE")
            df['Date'] = df['Date'].astype(str)  # ensure all date is string

            expected_cols = ['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending']
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = ""

            df = df[expected_cols]
            data_values = [df.columns.tolist()] + df.values.tolist()

            # Update main sheet
            main_ws = client.open("Rotor Log").worksheet("Sheet1")
            main_ws.clear()
            main_ws.update('A1', data_values)

            # Update backup sheet
            try:
                backup_ws = client.open("Rotor Log").worksheet("Backup")
            except:
                backup_ws = client.open("Rotor Log").add_worksheet(title="Backup", rows="1000", cols="20")
            backup_ws.clear()
            backup_ws.update('A1', data_values)

        st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"❌ Auto-save failed: {e}")

# Load on startup
if not st.session_state.loaded:
    load_from_gsheet()
    st.session_state.loaded = True

# Sync manually
if st.button("🔄 Sync Now"):
    load_from_gsheet()

st.title("🔧 Rotor Tracker")

# Entry Forms
tabs = st.tabs(["➕ Current", "🚚 Coming Rotors", "📦 Pending"])

with tabs[0]:
    with st.form("current_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Date", value=datetime.today())
            rotor_size = st.number_input("📐 Size (mm)", min_value=1, step=1)
        with col2:
            entry_type = st.selectbox("🔁 Type", ["Inward", "Outgoing"])
            quantity = st.number_input("🔢 Quantity", min_value=1, step=1)
        remarks = st.text_input("📝 Remarks")
        if st.form_submit_button("➕ Add Entry"):
            new_row = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'),
                'Size (mm)': rotor_size,
                'Type': entry_type,
                'Quantity': quantity,
                'Remarks': remarks,
                'Status': 'Current',
                'Pending': False
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_row], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

with tabs[1]:
    with st.form("future_form"):
        col1, col2 = st.columns(2)
        with col1:
            f_date = st.date_input("📅 Expected Date", value=datetime.today() + timedelta(days=1))
            f_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
        with col2:
            f_qty = st.number_input("🔢 Quantity", min_value=1, step=1)
            f_remarks = st.text_input("📝 Remarks")
        if st.form_submit_button("➕ Add Coming Rotors"):
            new_row = pd.DataFrame([{
                'Date': f_date.strftime('%Y-%m-%d'),
                'Size (mm)': f_size,
                'Type': 'Inward',
                'Quantity': f_qty,
                'Remarks': f_remarks,
                'Status': 'Future',
                'Pending': False
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_row], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

with tabs[2]:
    with st.form("pending_form"):
        col1, col2 = st.columns(2)
        with col1:
            p_date = st.date_input("📅 Date", value=datetime.today())
            p_size = st.number_input("📐 Size (mm)", min_value=1, step=1)
        with col2:
            p_qty = st.number_input("🔢 Quantity", min_value=1, step=1)
            p_remarks = st.text_input("📝 Remarks", value="Pending delivery")
        if st.form_submit_button("➕ Add Pending Rotor"):
            new_row = pd.DataFrame([{
                'Date': p_date.strftime('%Y-%m-%d'),
                'Size (mm)': p_size,
                'Type': 'Outgoing',
                'Quantity': p_qty,
                'Remarks': p_remarks,
                'Status': 'Current',
                'Pending': True
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_row], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

# Stock Summary
st.subheader("📊 Stock Summary")
try:
    df = normalize_pending_column(st.session_state.data.copy())
    df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce')
    df = df.dropna(subset=['Quantity'])
    df['Net'] = df.apply(lambda x: x['Quantity'] if x['Type'] == 'Inward' else -x['Quantity'], axis=1)
    current = df[(df['Status'] == 'Current') & (~df['Pending'])]
    summary = current.groupby('Size (mm)')['Net'].sum().reset_index(name='Current Stock')
    future = df[df['Status'] == 'Future'].groupby('Size (mm)')['Quantity'].sum().reset_index(name='Coming Rotors')
    pending = df[(df['Status'] == 'Current') & (df['Pending'])].groupby('Size (mm)')['Quantity'].sum().reset_index(name='Pending Rotors')
    result = pd.merge(summary, future, on='Size (mm)', how='outer')
    result = pd.merge(result, pending, on='Size (mm)', how='outer')
    result = result.fillna(0)
    st.dataframe(result, use_container_width=True, hide_index=True)
except Exception as e:
    st.error(f"Stock summary error: {e}")

# Movement Log
st.subheader("📋 Movement Log")

df = st.session_state.data.copy()

# Filters
with st.expander("🔍 Filters", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.selectbox("📂 Status", ["All", "Current", "Future"])
    with col2:
        size_filter = st.multiselect("📐 Size (mm)", sorted(df['Size (mm)'].dropna().unique()))
    with col3:
        pending_filter = st.selectbox("⏳ Pending", ["All", "Yes", "No"])
    remarks_filter = st.text_input("📝 Search Remarks")
    date_filter = st.date_input("📅 Filter by Date (optional)", value=None)
    if st.button("🧹 Clear Filters"):
        st.rerun()

# Apply filters
df['Date'] = df['Date'].astype(str)
if date_filter:
    df = df[df['Date'] == date_filter.strftime('%Y-%m-%d')]
if status_filter != "All":
    df = df[df['Status'] == status_filter]
if size_filter:
    df = df[df['Size (mm)'].isin(size_filter)]
if pending_filter == "Yes":
    df = df[df['Pending'] == True]
elif pending_filter == "No":
    df = df[df['Pending'] == False]
if remarks_filter:
    df = df[df['Remarks'].str.contains(remarks_filter, case=False)]

# Display log with inline editing
if df.empty:
    st.warning("No entries match the filters.")
else:
    for i, row in df.iterrows():
        idx = st.session_state.data[
            (st.session_state.data['Date'] == row['Date']) &
            (st.session_state.data['Size (mm)'] == row['Size (mm)']) &
            (st.session_state.data['Type'] == row['Type']) &
            (st.session_state.data['Quantity'] == row['Quantity']) &
            (st.session_state.data['Remarks'] == row['Remarks']) &
            (st.session_state.data['Status'] == row['Status']) &
            (st.session_state.data['Pending'] == row['Pending'])
        ].index
        if len(idx) == 0:
            continue
        idx = idx[0]
        if st.session_state.editing == idx:
            with st.form(f"edit_{idx}"):
                col1, col2 = st.columns(2)
                with col1:
                    edate = st.date_input("📅 Date", value=datetime.strptime(row['Date'], "%Y-%m-%d"))
                    esize = st.number_input("📐 Size (mm)", value=row["Size (mm)"])
                with col2:
                    etype = st.selectbox("🔁 Type", ["Inward", "Outgoing"], index=0 if row["Type"] == "Inward" else 1)
                    eqty = st.number_input("🔢 Quantity", value=row["Quantity"])
                eremarks = st.text_input("📝 Remarks", value=row["Remarks"])
                estatus = st.selectbox("📂 Status", ["Current", "Future"], index=0 if row["Status"] == "Current" else 1)
                epending = st.checkbox("⏳ Pending", value=row["Pending"])
                colA, colB = st.columns(2)
                with colA:
                    if st.form_submit_button("💾 Save"):
                        st.session_state.data.at[idx, "Date"] = edate.strftime('%Y-%m-%d')
                        st.session_state.data.at[idx, "Size (mm)"] = esize
                        st.session_state.data.at[idx, "Type"] = etype
                        st.session_state.data.at[idx, "Quantity"] = eqty
                        st.session_state.data.at[idx, "Remarks"] = eremarks
                        st.session_state.data.at[idx, "Status"] = estatus
                        st.session_state.data.at[idx, "Pending"] = epending
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
                st.write(f"📅 {row['Date']} | 📐 {row['Size (mm)']}mm | 🔁 {row['Type']} | 🔢 {row['Quantity']} | 📝 {row['Remarks']} | 📂 {row['Status']} | ⏳ {'Yes' if row['Pending'] else 'No'}")
            with col2:
                if st.button("✏", key=f"edit_{idx}"):
                    st.session_state.editing = idx
                if st.button("🗑", key=f"del_{idx}"):
                    st.session_state.data = st.session_state.data.drop(idx).reset_index(drop=True)
                    auto_save_to_gsheet()
                    st.rerun()

# Last sync info
st.caption(f"🕒 Last synced: {st.session_state.last_sync}")
