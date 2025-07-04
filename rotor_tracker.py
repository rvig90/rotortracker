import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from streamlit_autorefresh import st_autorefresh

# ====== INITIALIZE SESSION STATE ======
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending'
    ])
    st.session_state.last_sync = "Never"
    st.session_state.editing = None
    st.session_state.loaded = False

# Refresh every 3 seconds (3000 ms), limit to avoid infinite reloads
count = st_autorefresh(interval=30000, limit=None, key="autorefresh")

# Track the last backup snapshot
if 'last_backup_data' not in st.session_state:
    st.session_state.last_backup_data = None
# ====== NORMALIZE PENDING COLUMN ======
def normalize_pending_column(df):
    df['Pending'] = df['Pending'].apply(
        lambda x: str(x).lower() == 'true' if isinstance(x, str) else bool(x)
    )
    return df

# ====== GOOGLE SHEETS CONNECTION ======
def get_gsheet_connection():
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds_dict = (
            json.loads(st.secrets["gcp_service_account"])
            if isinstance(st.secrets["gcp_service_account"], str)
            else dict(st.secrets["gcp_service_account"])
        )
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Rotor Log").sheet1
    except Exception as e:
        st.error(f"Google Sheets connection failed: {e}")
        return None

# ====== LOAD DATA FROM GOOGLE SHEETS ======
def load_from_gsheet():
    try:
        sheet = get_gsheet_connection()
        if not sheet:
            return
        records = sheet.get_all_records()
        df = pd.DataFrame(records)
        if 'Status' not in df.columns:
            df['Status'] = 'Current'
        if 'Pending' not in df.columns:
            df['Pending'] = False
        df = normalize_pending_column(df)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        st.session_state.data = df
        st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.success("✅ Data loaded from Google Sheet")
    except Exception as e:
        st.error(f"Error loading from Google Sheet: {e}")


# Auto-load once
if not st.session_state.loaded:
    load_from_gsheet()
    st.session_state.loaded = True

def auto_backup_to_sheet():
    try:
        sheet = get_gsheet_connection()
        if sheet:
            df = st.session_state.data.copy()
            if not df.empty:
                df['Pending'] = df['Pending'].apply(lambda x: "TRUE" if x else "FALSE")
                expected_cols = ['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending']
                for col in expected_cols:
                    if col not in df.columns:
                        df[col] = ""
                df = df[expected_cols]

                # Check if data changed since last backup
                if st.session_state.last_backup_data is None or not df.equals(st.session_state.last_backup_data):
                    backup_sheet = get_gsheet_connection()
                    if backup_sheet:
                        backup_sheet.clear()
                        records = [df.columns.tolist()] + df.values.tolist()
                        backup_sheet.update('A1', records)
                        st.session_state.last_backup_data = df.copy()
                        st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        st.toast("🔁 Auto-backup successful.")
    except Exception as e:
        st.error(f"Auto-backup failed: {e}")
        # Auto backup on every refresh (if data changed)

# ====== AUTO-SAVE TO GOOGLE SHEETS ======
def auto_save_to_gsheet():
    try:
        sheet = get_gsheet_connection()
        if not sheet:
            return
        sheet.clear()
        df = st.session_state.data.copy()
        if not df.empty:
            df['Pending'] = df['Pending'].apply(lambda x: "TRUE" if x else "FALSE")
            df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
            expected = ['Date','Size (mm)','Type','Quantity','Remarks','Status','Pending']
            for col in expected:
                if col not in df.columns:
                    df[col] = ""
            df = df[expected]
            sheet.update('A1', [df.columns.tolist()] + df.values.tolist())
        st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"Error saving to Google Sheet: {e}")

# ====== MANUAL SYNC BUTTON ======
if st.button("🔄 Sync Now"):
    load_from_gsheet()

# ====== ENTRY FORMS ======
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
        d = st.date_input("📅 Expected Date", min_value=datetime.today()+timedelta(days=1))
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

# ====== STOCK SUMMARY ======
st.subheader("📊 Stock Summary")
try:
    df_stock = normalize_pending_column(st.session_state.data.copy())
    df_stock['Net'] = df_stock.apply(lambda x: x['Quantity'] if x['Type']=='Inward' else -x['Quantity'], axis=1)
    current = df_stock[(df_stock['Status']=='Current') & (~df_stock['Pending'])]
    stock = current.groupby('Size (mm)')['Net'].sum().reset_index()
    coming = df_stock[df_stock['Status']=='Future'].groupby('Size (mm)')['Quantity'].sum().reset_index()
    pending = df_stock[(df_stock['Status']=='Current') & (df_stock['Pending'])].groupby('Size (mm)')['Quantity'].sum().reset_index()
    merged = pd.merge(stock, coming, on='Size (mm)', how='outer')
    merged = pd.merge(merged, pending, on='Size (mm)', how='outer', suffixes=('','_Pending'))
    merged.columns = ['Size (mm)','Current Stock','Coming Rotors','Pending Rotors']
    merged = merged.fillna(0)
    st.dataframe(merged, use_container_width=True, hide_index=True)
except Exception as e:
    st.error(f"Stock summary error: {e}")

# ====== MOVEMENT LOG ======
st.subheader("📋 Movement Log")
if not st.session_state.data.empty:
    df = st.session_state.data.copy()
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

    st.markdown("### 🔍 Filters")
    c1, c2, c3 = st.columns(3)
    status = c1.selectbox("Status", ["All","Current","Future"])
    pending = c2.selectbox("Pending", ["All","Yes","No"])
    size = c3.multiselect("Size (mm)", sorted(df['Size (mm)'].dropna().unique()))
    remarks = st.text_input("Search Remarks")
    filt_date = st.date_input("Specific Date (optional)", value=None)

    if status!="All":
        df = df[df['Status']==status]
    if pending=="Yes":
        df = df[df['Pending']==True]
    elif pending=="No":
        df = df[df['Pending']==False]
    if size:
        df = df[df['Size (mm)'].isin(size)]
    if remarks:
        df = df[df['Remarks'].str.contains(remarks, case=False)]
    if filt_date:
        df = df[df['Date']==pd.to_datetime(filt_date)]

    if df.empty:
        st.warning("⚠ No entries match filters.")
    else:
        for i,row in df.iterrows():
            idx = st.session_state.data[
                (st.session_state.data['Date']==row['Date']) &
                (st.session_state.data['Size (mm)']==row['Size (mm)']) &
                (st.session_state.data['Type']==row['Type']) &
                (st.session_state.data['Quantity']==row['Quantity']) &
                (st.session_state.data['Remarks']==row['Remarks']) &
                (st.session_state.data['Status']==row['Status']) &
                (st.session_state.data['Pending']==row['Pending'])
            ].index
            if len(idx)==0: continue
            idx=idx[0]
            if st.session_state.editing==idx:
                with st.form(f"edit_{idx}"):
                    a1,a2=st.columns(2)
                    with a1:
                        ed=st.date_input("Date", value=row['Date'], key=f"d_{idx}")
                        es=st.number_input("Size (mm)", value=int(row['Size (mm)']), key=f"s_{idx}")
                    with a2:
                        et=st.selectbox("Type",["Inward","Outgoing"], index=0 if row['Type']=="Inward" else 1, key=f"t_{idx}")
                        eq=st.number_input("Qty", value=int(row['Quantity']), key=f"q_{idx}")
                    er=st.text_input("Remarks", value=row['Remarks'], key=f"r_{idx}")
                    est=st.selectbox("Status",["Current","Future"], index=0 if row['Status']=="Current" else 1, key=f"st_{idx}")
                    ep=st.checkbox("Pending", value=row['Pending'], key=f"p_{idx}")
                    b1,b2=st.columns(2)
                    with b1:
                        if st.form_submit_button("Save"):
                            st.session_state.data.at[idx,"Date"]=ed.strftime('%Y-%m-%d')
                            st.session_state.data.at[idx,"Size (mm)"]=es
                            st.session_state.data.at[idx,"Type"]=et
                            st.session_state.data.at[idx,"Quantity"]=eq
                            st.session_state.data.at[idx,"Remarks"]=er
                            st.session_state.data.at[idx,"Status"]=est
                            st.session_state.data.at[idx,"Pending"]=ep
                            st.session_state.editing=None
                            auto_save_to_gsheet()
                            st.rerun()
                    with b2:
                        if st.form_submit_button("Cancel"):
                            st.session_state.editing=None
                            st.rerun()
            else:
                c1,c2=st.columns([10,1])
                with c1:
                    st.dataframe(pd.DataFrame([{
                        "Date":row['Date'].strftime('%Y-%m-%d'),
                        "Size (mm)":row['Size (mm)'],
                        "Type":row['Type'],
                        "Quantity":row['Quantity'],
                        "Remarks":row['Remarks'],
                        "Status":row['Status'],
                        "Pending":"Yes" if row['Pending'] else "No"
                    }]), hide_index=True, use_container_width=True)
                with c2:
                    if st.button("✏", key=f"e_{idx}"):
                        st.session_state.editing=idx
                    if st.button("🗑", key=f"d_{idx}"):
                        st.session_state.data=st.session_state.data.drop(idx).reset_index(drop=True)
                        auto_save_to_gsheet()
                        st.rerun()
else:
    st.info("ℹ No entries yet.")

# ====== LAST SYNC TIMESTAMP ======
if st.session_state.last_sync!="Never":
    st.caption(f"🕒 Last synced: {st.session_state.last_sync}")
