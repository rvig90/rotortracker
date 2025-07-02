import streamlit as st
import pandas as pd
import time
from datetime import datetime
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from google.oauth2.service_account import Credentials

# ----------------------- Google Sheets Setup -----------------------
SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_NAME = "RotorData"  # Your Google Sheet name
SERVICE_ACCOUNT_FILE = "your_credentials.json"  # Replace with your path

def get_gsheet_connection():
    credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPE)
    gc = gspread.authorize(credentials)
    return gc

def load_data_from_gsheet():
    worksheet = get_gsheet_connection().open(SHEET_NAME).worksheet("Main")
    df = get_as_dataframe(worksheet).dropna(how="all")
    if not df.empty:
        df['Pending'] = df['Pending'].apply(lambda x: True if str(x).lower() == 'true' else False)
    return df

def save_data_to_gsheet(df):
    worksheet = get_gsheet_connection().open(SHEET_NAME).worksheet("Main")
    worksheet.clear()
    set_with_dataframe(worksheet, df)

def save_to_backup_sheet(df):
    try:
        backup_sheet = get_gsheet_connection().open(SHEET_NAME).worksheet("Backup")
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        df_copy = df.copy()
        df_copy.insert(0, 'Backup Time', timestamp)
        records = [df_copy.columns.tolist()] + df_copy.values.tolist()
        backup_sheet.append_rows(records)
    except Exception as e:
        st.warning(f"Backup failed: {e}")

# ----------------------- Initialize Session State -----------------------
if "data" not in st.session_state:
    st.session_state.data = load_data_from_gsheet()
if "edit_row" not in st.session_state:
    st.session_state.edit_row = None
if "last_sync" not in st.session_state:
    st.session_state.last_sync = None

# ----------------------- Add New Entry -----------------------
st.title("🔧 Rotor Tracking App")

with st.form("entry_form", clear_on_submit=True):
    st.subheader("➕ Add / Update Rotor Entry")
    col1, col2, col3 = st.columns(3)
    with col1:
        date = st.date_input("Date", value=datetime.today())
    with col2:
        size = st.text_input("Rotor Size (mm)")
    with col3:
        quantity = st.number_input("Quantity", min_value=1, step=1)

    type_ = st.selectbox("Type", ["Inward", "Outward"])
    pending = st.checkbox("Pending?")
    status = st.selectbox("Status", ["Current", "Coming Rotors"])
    remarks = st.text_input("Remarks")

    submitted = st.form_submit_button("💾 Add Entry")

    if submitted:
        new_entry = {
            "Date": pd.to_datetime(date),
            "Size (mm)": size,
            "Quantity": quantity,
            "Type": type_,
            "Pending": pending,
            "Status": status,
            "Remarks": remarks
        }
        st.session_state.data.loc[len(st.session_state.data)] = new_entry
        save_data_to_gsheet(st.session_state.data)
        save_to_backup_sheet(st.session_state.data)
        st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.success("Entry added and saved!")

# ----------------------- Movement Log Filters -----------------------
with st.expander("🔍 Filter Movement Log"):
    col1, col2, col3, col4, col5 = st.columns(5)
    status_filter = col1.selectbox("Status", options=["All"] + st.session_state.data['Status'].dropna().unique().tolist())
    pending_filter = col2.selectbox("Pending", options=["All", "Yes", "No"])
    size_filter = col3.selectbox("Size (mm)", options=["All"] + sorted(st.session_state.data['Size (mm)'].dropna().unique().astype(str)))
    remarks_filter = col4.text_input("Remarks contains")
    date_filter = col5.date_input("Date", value=None)

filtered_data = st.session_state.data.copy()

if status_filter != "All":
    filtered_data = filtered_data[filtered_data["Status"] == status_filter]
if pending_filter != "All":
    val = True if pending_filter == "Yes" else False
    filtered_data = filtered_data[filtered_data["Pending"] == val]
if size_filter != "All":
    filtered_data = filtered_data[filtered_data["Size (mm)"].astype(str) == size_filter]
if remarks_filter:
    filtered_data = filtered_data[filtered_data["Remarks"].str.contains(remarks_filter, case=False, na=False)]
if date_filter:
    filtered_data = filtered_data[filtered_data["Date"].dt.date == date_filter]

# ----------------------- Movement Log Table -----------------------
st.markdown("### 📋 Movement Log")

if filtered_data.empty:
    st.info("No entries match the selected filters.")
else:
    for idx, row in filtered_data.reset_index().iterrows():
        row_index = row['index']
        is_editing = st.session_state.edit_row == row_index

        with st.container():
            col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([1.5, 1.5, 1.5, 1, 1.2, 1.2, 1.5, 1])
            if is_editing:
                new_date = col1.date_input("Date", row["Date"], key=f"edit_date_{row_index}")
                new_size = col2.text_input("Size", row["Size (mm)"], key=f"edit_size_{row_index}")
                new_type = col3.selectbox("Type", ["Inward", "Outward"], index=["Inward", "Outward"].index(row["Type"]), key=f"edit_type_{row_index}")
                new_quantity = col4.number_input("Qty", value=row["Quantity"], min_value=0, step=1, key=f"edit_qty_{row_index}")
                new_pending = col5.checkbox("Pending", value=row["Pending"], key=f"edit_pending_{row_index}")
                new_status = col6.selectbox("Status", ["Current", "Coming Rotors"], index=["Current", "Coming Rotors"].index(row["Status"]), key=f"edit_status_{row_index}")
                new_remarks = col7.text_input("Remarks", value=row["Remarks"], key=f"edit_remarks_{row_index}")

                save_btn = col8.button("💾", key=f"save_{row_index}")
                cancel_btn = col8.button("❌", key=f"cancel_{row_index}")

                if save_btn:
                    st.session_state.data.loc[row_index] = {
                        "Date": pd.to_datetime(new_date),
                        "Size (mm)": new_size,
                        "Quantity": new_quantity,
                        "Type": new_type,
                        "Pending": new_pending,
                        "Status": new_status,
                        "Remarks": new_remarks
                    }
                    save_data_to_gsheet(st.session_state.data)
                    save_to_backup_sheet(st.session_state.data)
                    st.session_state.edit_row = None
                    st.success("Entry updated.")
                if cancel_btn:
                    st.session_state.edit_row = None
            else:
                col1.write(f"📅 {row['Date'].date()}")
                col2.write(f"✏ {row['Size (mm)']}mm")
                col3.write(f"📦 {row['Type']}")
                col4.write(f"🧮 {row['Quantity']}")
                col5.write(f"⏳ {'Yes' if row['Pending'] else 'No'}")
                col6.write(f"📁 {row['Status']}")
                col7.write(f"📝 {row['Remarks']}")
                if col8.button("✏", key=f"edit_{row_index}"):
                    st.session_state.edit_row = row_index
                if col8.button("🗑", key=f"del_{row_index}"):
                    st.session_state.data = st.session_state.data.drop(row_index)
                    st.session_state.data.reset_index(drop=True, inplace=True)
                    save_data_to_gsheet(st.session_state.data)
                    save_to_backup_sheet(st.session_state.data)
                    st.success("Entry deleted.")
                    st.experimental_rerun()

# ----------------------- Current Stock Summary -----------------------
st.markdown("---")
st.subheader("📊 Current Stock Summary")
try:
    current_inward = st.session_state.data[
        (st.session_state.data['Status'] == 'Current') & 
        (st.session_state.data['Type'] == 'Inward') & 
        (~st.session_state.data['Pending'].astype(bool))
    ]
    inward_stock = current_inward.groupby('Size (mm)')['Quantity'].sum().reset_index()
    inward_stock.columns = ['Size (mm)', 'Available Qty']
    st.dataframe(inward_stock)
except Exception as e:
    st.warning(f"Stock summary failed: {e}")

# ----------------------- Sync & Previously Saved -----------------------
colx1, colx2 = st.columns(2)
if colx1.button("🔄 Sync Now"):
    st.session_state.data = load_data_from_gsheet()
    st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.success("Data synced from Google Sheets.")

if colx2.button("🕘 Previously Saved"):
    st.session_state.data = load_data_from_gsheet()
    st.success("Loaded previously saved data.")

if st.session_state.last_sync:
    st.caption(f"Last synced: {st.session_state.last_sync}")
