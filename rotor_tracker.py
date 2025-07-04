import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ========== INITIALIZE ==========
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending'
    ])
    st.session_state.last_sync = "Never"
    st.session_state.loaded = False
    st.session_state.editing = None

# ========== HELPERS ==========
def normalize_pending_column(df):
    df['Pending'] = df['Pending'].apply(
        lambda x: str(x).lower() == 'true' if isinstance(x, str) else bool(x)
    )
    return df

# ========== GOOGLE SHEETS ==========
def get_gsheet_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"]) if isinstance(st.secrets["gcp_service_account"], str) else dict(st.secrets["gcp_service_account"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Rotor Log")
    return sheet.worksheet("Sheet1"), sheet.worksheet("Backup")

def load_from_gsheet():
    try:
        sheet, _ = get_gsheet_connection()
        records = sheet.get_all_records()
        if records:
            df = pd.DataFrame(records)
            df = normalize_pending_column(df)
            st.session_state.data = df
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.success("✅ Data loaded from Google Sheet.")
        else:
            st.info("No records found.")
    except Exception as e:
        st.error(f"❌ Load failed: {e}")

def auto_save_to_gsheet():
    try:
        sheet, backup = get_gsheet_connection()
        df = st.session_state.data.copy()
        df['Pending'] = df['Pending'].apply(lambda x: "TRUE" if x else "FALSE")

        cols = ['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending']
        for col in cols:
            if col not in df.columns:
                df[col] = ""
        df = df[cols]

        records = [df.columns.tolist()] + df.values.tolist()
        sheet.clear()
        sheet.update(records)
        backup.clear()
        backup.update(records)

        st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"❌ Auto-save failed: {e}")

# ========== LOAD ON START ==========
if not st.session_state.loaded:
    load_from_gsheet()
    st.session_state.loaded = True

# ========== ADD ENTRY ==========
st.header("➕ Add Rotor Entry")
col1, col2 = st.columns(2)
with col1:
    date = st.date_input("📅 Date", value=datetime.today())
    size = st.number_input("📏 Size (mm)", min_value=1, step=1)
    entry_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"])
with col2:
    qty = st.number_input("🔢 Quantity", min_value=1, step=1)
    status = st.selectbox("📁 Status", ["Current", "Future"])
    pending = st.checkbox("❗ Pending")
remarks = st.text_input("📝 Remarks")

if st.button("✅ Add Entry"):
    new_row = {
        "Date": date.strftime("%Y-%m-%d"),
        "Size (mm)": size,
        "Type": entry_type,
        "Quantity": qty,
        "Remarks": remarks,
        "Status": status,
        "Pending": pending
    }
    st.session_state.data = pd.concat([st.session_state.data, pd.DataFrame([new_row])], ignore_index=True)
    auto_save_to_gsheet()
    st.success("Entry added.")
    st.rerun()

# ========== STOCK SUMMARY ==========
st.subheader("📊 Stock Summary")
try:
    df = normalize_pending_column(st.session_state.data.copy())
    df['Net'] = df.apply(lambda x: x['Quantity'] if x['Type'] == 'Inward' else -x['Quantity'], axis=1)
    current_stock = df[(df['Status'] == 'Current') & (~df['Pending'])].groupby('Size (mm)')['Net'].sum().reset_index(name='Current Stock')
    coming = df[df['Status'] == 'Future'].groupby('Size (mm)')['Quantity'].sum().reset_index(name='Coming Rotors')
    pending_stock = df[(df['Status'] == 'Current') & (df['Pending'])].groupby('Size (mm)')['Quantity'].sum().reset_index(name='Pending Rotors')

    summary = pd.merge(current_stock, coming, on='Size (mm)', how='outer')
    summary = pd.merge(summary, pending_stock, on='Size (mm)', how='outer').fillna(0)
    st.dataframe(summary, use_container_width=True)
except Exception as e:
    st.error(f"Stock summary error: {e}")

# ========== MOVEMENT LOG ==========
# ========== MOVEMENT LOG ==========
st.subheader("📋 Filter Movement Log")
df = st.session_state.data.copy()
df = normalize_pending_column(df)

# Convert 'Date' to datetime - handle errors and timezone-naive dates
df["Date"] = pd.to_datetime(df["Date"], errors='coerce', format='%Y-%m-%d')

# First apply all non-date filters
col1, col2, col3 = st.columns(3)
with col1:
    status_filter = st.selectbox("📁 Status", ["All", "Current", "Future"])
with col2:
    size_filter = st.multiselect("📏 Size (mm)", sorted(df["Size (mm)"].dropna().unique()))
with col3:
    type_filter = st.selectbox("🔄 Type", ["All", "Inward", "Outgoing"])

col4, col5 = st.columns(2)
with col4:
    pending_filter = st.selectbox("❗ Pending", ["All", "Yes", "No"])
with col5:
    remarks_search = st.text_input("🔍 Search Remarks")

# Apply non-date filters first
if status_filter != "All":
    df = df[df["Status"] == status_filter]
if type_filter != "All":
    df = df[df["Type"] == type_filter]
if pending_filter == "Yes":
    df = df[df["Pending"] == True]
elif pending_filter == "No":
    df = df[df["Pending"] == False]
if size_filter:
    df = df[df["Size (mm)"].isin(size_filter)]
if remarks_search:
    df = df[df["Remarks"].str.contains(remarks_search, case=False, na=False)]

# Now calculate date range based on filtered data
valid_dates = df["Date"].dropna()
if not valid_dates.empty:
    min_date = valid_dates.min().to_pydatetime().date()
    max_date = valid_dates.max().to_pydatetime().date()
else:
    min_date = datetime.today().date() - timedelta(days=30)
    max_date = datetime.today().date()

# Use session state to maintain date range selection
if 'date_range' not in st.session_state:
    st.session_state.date_range = [min_date, max_date]

# Date range picker - now using session state
new_date_range = st.date_input(
    "📅 Date Range",
    value=st.session_state.date_range,
    min_value=min_date,
    max_value=max_date
)

# Update session state if date range changed
if new_date_range != st.session_state.date_range:
    st.session_state.date_range = new_date_range
    st.rerun()

# Apply date filter if two dates are selected
if len(st.session_state.date_range) == 2:
    start_date, end_date = st.session_state.date_range
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())
    df = df[df["Date"].between(start_dt, end_dt, inclusive='both')]

# Display results
if not df.empty:
    # Format date for display while keeping original for sorting
    display_df = df.copy()
    display_df["Date"] = display_df["Date"].dt.strftime('%Y-%m-%d')
    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.warning("No entries match the filters.")
# ========== SYNC INFO ==========
st.caption(f"📤 Last synced: {st.session_state.last_sync}")
