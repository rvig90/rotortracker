import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ==== INIT SESSION ====
if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending'])
    st.session_state.editing = None
    st.session_state.loaded = False
    st.session_state.last_sync = "Never"

# ==== NORMALIZE PENDING ====
def normalize_pending_column(df):
    df['Pending'] = df['Pending'].apply(lambda x: str(x).lower() == 'true' if isinstance(x, str) else bool(x))
    return df

# ==== CONNECT TO GOOGLE SHEETS ====
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

# ==== LOAD SHEET DATA ====
def load_from_gsheet():
    try:
        sheet = get_gsheet_connection()
        if sheet:
            records = sheet.get_all_records()
            df = pd.DataFrame(records)
            if 'Status' not in df.columns: df['Status'] = 'Current'
            if 'Pending' not in df.columns: df['Pending'] = False
            df = normalize_pending_column(df)
            st.session_state.data = df
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.success("✅ Data loaded from Google Sheet")
        else:
            st.info("No records found.")
    except Exception as e:
        st.error(f"Error loading data: {e}")

# ==== AUTOLOAD ====
if not st.session_state.loaded:
    load_from_gsheet()
    st.session_state.loaded = True

# ==== SAVE TO SHEET ====
def auto_save_to_gsheet():
    try:
        sheet = get_gsheet_connection()
        if sheet:
            sheet.clear()
            df = st.session_state.data.copy()
            df['Pending'] = df['Pending'].apply(lambda x: "TRUE" if x else "FALSE")
            records = [df.columns.tolist()] + df.values.tolist()
            sheet.update('A1', records)
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"Error saving data: {e}")

# ==== MANUAL SYNC ====
if st.button("🔄 Sync Now"):
    load_from_gsheet()

# ==== ENTRY FORMS ====
form_tabs = st.tabs(["Current Movement", "Coming Rotors", "Pending Rotors"])

with form_tabs[0]:
    with st.form("current_form"):
        d = st.date_input("📅 Date", value=datetime.today())
        s = st.number_input("📐 Size (mm)", min_value=1, step=1)
        t = st.selectbox("🔄 Type", ["Inward", "Outgoing"])
        q = st.number_input("🔢 Quantity", min_value=1, step=1)
        r = st.text_input("📝 Remarks")
        if st.form_submit_button("➕ Add Entry"):
            new = pd.DataFrame([{
                'Date': d.strftime('%Y-%m-%d'), 'Size (mm)': s, 'Type': t,
                'Quantity': q, 'Remarks': r, 'Status': 'Current', 'Pending': False
            }])
            st.session_state.data = pd.concat([st.session_state.data, new], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

with form_tabs[1]:
    with st.form("future_form"):
        d = st.date_input("📅 Expected Date", min_value=datetime.today() + timedelta(days=1))
        s = st.number_input("📐 Size (mm)", min_value=1, step=1, key="f_size")
        q = st.number_input("🔢 Quantity", min_value=1, step=1, key="f_qty")
        r = st.text_input("📝 Remarks", key="f_rem")
        if st.form_submit_button("➕ Add Coming Rotor"):
            new = pd.DataFrame([{
                'Date': d.strftime('%Y-%m-%d'), 'Size (mm)': s, 'Type': 'Inward',
                'Quantity': q, 'Remarks': r, 'Status': 'Future', 'Pending': False
            }])
            st.session_state.data = pd.concat([st.session_state.data, new], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

with form_tabs[2]:
    with st.form("pending_form"):
        d = st.date_input("📅 Date", value=datetime.today(), key="p_date")
        s = st.number_input("📐 Size (mm)", min_value=1, step=1, key="p_size")
        q = st.number_input("🔢 Quantity", min_value=1, step=1, key="p_qty")
        r = st.text_input("📝 Remarks", value="Pending delivery", key="p_rem")
        if st.form_submit_button("➕ Add Pending Rotor"):
            new = pd.DataFrame([{
                'Date': d.strftime('%Y-%m-%d'), 'Size (mm)': s, 'Type': 'Outgoing',
                'Quantity': q, 'Remarks': r, 'Status': 'Current', 'Pending': True
            }])
            st.session_state.data = pd.concat([st.session_state.data, new], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

# ==== STOCK SUMMARY ====
st.subheader("📊 Stock Summary")
try:
    df = normalize_pending_column(st.session_state.data.copy())
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    current = df[(df['Status'] == 'Current') & (~df['Pending'])].copy()
    current['Net'] = current.apply(lambda x: x['Quantity'] if x['Type'] == 'Inward' else -x['Quantity'], axis=1)
    stock = current.groupby('Size (mm)')['Net'].sum().reset_index()
    future = df[df['Status'] == 'Future'].groupby('Size (mm)')['Quantity'].sum().reset_index()
    pending = df[(df['Status'] == 'Current') & (df['Pending'])].groupby('Size (mm)')['Quantity'].sum().reset_index()
    merged = pd.merge(stock, future, on='Size (mm)', how='outer')
    merged = pd.merge(merged, pending, on='Size (mm)', how='outer', suffixes=('', '_Pending'))
    merged.columns = ['Size (mm)', 'Current Stock', 'Coming Rotors', 'Pending Rotors']
    merged = merged.fillna(0)
    st.dataframe(merged, use_container_width=True, hide_index=True)
except Exception as e:
    st.error(f"Stock summary error: {e}")

# ==== MOVEMENT LOG ====
st.subheader("📋 Movement Log")
df = st.session_state.data.copy()
df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

st.markdown("### 🔎 Filters (Optional)")
c1, c2, c3 = st.columns(3)
status = c1.selectbox("Status", ["All", "Current", "Future"])
pending = c2.selectbox("Pending", ["All", "Yes", "No"])
size = c3.multiselect("Size (mm)", sorted(df['Size (mm)'].dropna().unique()))
remarks = st.text_input("Search in Remarks")
filter_date = st.date_input("Specific Date Filter", value=None)

# Apply filters
if filter_date:
    df = df[df['Date'] == pd.to_datetime(filter_date)]
if status != "All":
    df = df[df["Status"] == status]
if pending == "Yes":
    df = df[df["Pending"] == True]
elif pending == "No":
    df = df[df["Pending"] == False]
if size:
    df = df[df["Size (mm)"].isin(size)]
if remarks:
    df = df[df["Remarks"].str.contains(remarks, case=False)]

if df.empty:
    st.warning("⚠️ No entries match the selected filters.")
    if not st.session_state.data.empty:
        with st.expander("🛠 Show Raw Data (Unfiltered)", expanded=False):
            st.dataframe(st.session_state.data, use_container_width=True)
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
        if len(idx) == 0: continue
        idx = idx[0]

        if st.session_state.editing == idx:
            with st.form(f"edit_{idx}"):
                c1, c2 = st.columns(2)
                with c1:
                    d = st.date_input("📅 Date", value=row['Date'], key=f"d_{idx}")
                    s = st.number_input("📐 Size (mm)", value=int(row['Size (mm)']), key=f"s_{idx}")
                with c2:
                    t = st.selectbox("🔄 Type", ["Inward", "Outgoing"], index=0 if row["Type"]=="Inward" else 1, key=f"t_{idx}")
                    q = st.number_input("🔢 Quantity", value=int(row["Quantity"]), key=f"q_{idx}")
                r = st.text_input("📝 Remarks", value=row["Remarks"], key=f"r_{idx}")
                stt = st.selectbox("📂 Status", ["Current", "Future"], index=0 if row["Status"]=="Current" else 1, key=f"stt_{idx}")
                p = st.checkbox("❗ Pending", value=row["Pending"], key=f"p_{idx}")
                colA, colB = st.columns(2)
                with colA:
                    if st.form_submit_button("💾 Save"):
                        st.session_state.data.at[idx, "Date"] = d.strftime("%Y-%m-%d")
                        st.session_state.data.at[idx, "Size (mm)"] = s
                        st.session_state.data.at[idx, "Type"] = t
                        st.session_state.data.at[idx, "Quantity"] = q
                        st.session_state.data.at[idx, "Remarks"] = r
                        st.session_state.data.at[idx, "Status"] = stt
                        st.session_state.data.at[idx, "Pending"] = p
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
                    "Date": row["Date"], "Size (mm)": row["Size (mm)"], "Type": row["Type"],
                    "Quantity": row["Quantity"], "Remarks": row["Remarks"], "Status": row["Status"],
                    "Pending": "Yes" if row["Pending"] else "No"
                }]), use_container_width=True, hide_index=True)
            with col2:
                if st.button("✏", key=f"edit_{idx}"): st.session_state.editing = idx
                if st.button("❌", key=f"del_{idx}"):
                    st.session_state.data = st.session_state.data.drop(idx).reset_index(drop=True)
                    auto_save_to_gsheet()
                    st.rerun()

# ==== LAST SYNC ====
if st.session_state.last_sync != "Never":
    st.caption(f"🕒 Last synced: {st.session_state.last_sync}")
