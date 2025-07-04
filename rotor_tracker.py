import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from streamlit_autorefresh import st_autorefresh

# Normalize the Pending column to boolean True/False
def normalize_pending_column(df):
    df['Pending'] = df['Pending'].apply(
        lambda x: str(x).lower() == 'true' if isinstance(x, str) else bool(x)
    )
    return df

# ====== INITIALIZE SESSION STATE ======
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending'
    ])
    st.session_state.last_sync = "Never"
    st.session_state.editing = None
    st.session_state.loaded = False

# Sheet names
MAIN_SHEET_NAME = "Rotor Log"
BACKUP_SHEET_NAME = "Backup"

# Columns to maintain
COLUMNS = ['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending']

# Connect to Google Sheets
def get_gsheet(sheet_name=MAIN_SHEET_NAME):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"]) if isinstance(st.secrets["gcp_service_account"], str) else dict(st.secrets["gcp_service_account"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open(sheet_name)

# Load data from main Google Sheet
def load_from_gsheet():
    try:
        sheet = get_gsheet().worksheet("Sheet1")
        records = sheet.get_all_records()
        df = pd.DataFrame(records)
        if df.empty:
            df = pd.DataFrame(columns=COLUMNS)
        else:
            if 'Pending' in df.columns:
                df['Pending'] = df['Pending'].apply(lambda x: str(x).lower() == 'true' if isinstance(x, str) else bool(x))
            else:
                df['Pending'] = False
        return df
    except Exception as e:
        st.error(f"❌ Failed to load from Google Sheet: {e}")
        return pd.DataFrame(columns=COLUMNS)

# Save data to main sheet and backup sheet
def save_to_gsheet(data: pd.DataFrame):
    try:
        sheet = get_gsheet()
        main_ws = sheet.worksheet("Sheet1")
        backup_ws = sheet.worksheet(BACKUP_SHEET_NAME)

        # Format data
        df = data.copy()
        df['Pending'] = df['Pending'].apply(lambda x: "TRUE" if x else "FALSE")
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.strftime('%Y-%m-%d')
        df = df[COLUMNS]

        # Prepare for upload
        records = [df.columns.tolist()] + df.values.tolist()

        # Update both sheets
        main_ws.clear()
        main_ws.update('A1', records)

        backup_ws.clear()
        backup_ws.update('A1', records)

        st.success("✅ Saved to Google Sheet and Backup")
        st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"❌ Failed to save to Google Sheet: {e}")
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
