import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# ------------------- Google Sheets Setup -------------------
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "RotorData"

@st.cache_resource
def get_gsheet_connection():
    credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPE)
    client = gspread.authorize(credentials)
    return client.open(SHEET_NAME)

# ------------------- Load and Save Functions -------------------
def load_data():
    worksheet = get_gsheet_connection().worksheet("Main")
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
        df["Pending"] = df["Pending"].astype(str).str.lower() == "true"
    return df

def save_data_to_gsheet(df):
    worksheet = get_gsheet_connection().worksheet("Main")
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

def save_to_backup_sheet(df):
    try:
        backup_sheet = get_gsheet_connection().worksheet("Backup")
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        df.insert(0, 'Backup Time', timestamp)
        backup_sheet.append_rows([df.columns.tolist()] + df.values.tolist())
    except Exception as e:
        st.warning(f"Backup failed: {e}")

# ------------------- Initialize Session State -------------------
if "data" not in st.session_state:
    st.session_state.data = load_data()
if "edit_row" not in st.session_state:
    st.session_state.edit_row = None
if "first_load_done" not in st.session_state:
    st.session_state.first_load_done = True

# ------------------- UI: New Entry Form -------------------
st.title("🌀 Rotor Tracking System")
st.markdown("### ➕ Add Rotor Entry")
with st.form("entry_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        date = st.date_input("Date", value=datetime.today())
        rotor_size = st.text_input("Rotor Size (mm)")
        quantity = st.number_input("Quantity", min_value=1, step=1)
    with col2:
        movement_type = st.selectbox("Type", ["Inward", "Outward"])
        status = st.selectbox("Status", ["Current", "Coming Rotors"])
        pending = st.checkbox("Pending")
    remarks = st.text_input("Remarks")

    submitted = st.form_submit_button("Add Entry")
    if submitted:
        new_row = {
            "Date": pd.to_datetime(date),
            "Size (mm)": rotor_size,
            "Type": movement_type,
            "Quantity": quantity,
            "Pending": pending,
            "Remarks": remarks,
            "Status": status
        }
        st.session_state.data = pd.concat([st.session_state.data, pd.DataFrame([new_row])], ignore_index=True)
        save_data_to_gsheet(st.session_state.data)
        save_to_backup_sheet(pd.DataFrame([new_row]))
        st.success("Entry added and saved successfully.")

# ------------------- UI: Sync and Reload Buttons -------------------
col_sync, col_prev = st.columns([1, 1])
with col_sync:
    if st.button("🔄 Sync Now"):
        save_data_to_gsheet(st.session_state.data)
        save_to_backup_sheet(st.session_state.data)
        st.success("Data synced and backed up!")

with col_prev:
    if st.button("🕒 Previously Saved"):
        st.session_state.data = load_data()
        st.success("Reloaded from Google Sheet.")

# ------------------- UI: Filters -------------------
st.markdown("### 🔍 Filter Movement Log")
f1, f2, f3, f4 = st.columns(4)
status_filter = f1.selectbox("Status", options=["All", "Current", "Coming Rotors"])
pending_filter = f2.selectbox("Pending", options=["All", "Yes", "No"])
size_filter = f3.selectbox("Size (mm)", options=["All"] + sorted(st.session_state.data["Size (mm)"].astype(str).unique()))
remarks_filter = f4.text_input("Remarks contains")

# ------------------- Filtering Logic -------------------
filtered_data = st.session_state.data.copy()

if status_filter != "All":
    filtered_data = filtered_data[filtered_data["Status"] == status_filter]
if pending_filter != "All":
    filtered_data = filtered_data[filtered_data["Pending"] == (pending_filter == "Yes")]
if size_filter != "All":
    filtered_data = filtered_data[filtered_data["Size (mm)"].astype(str) == size_filter]
if remarks_filter:
    filtered_data = filtered_data[filtered_data["Remarks"].str.contains(remarks_filter, case=False, na=False)]

# ------------------- Movement Log Table with Inline Edit/Delete -------------------
st.markdown("### 📋 Movement Log")

if filtered_data.empty:
    st.info("No entries match the selected filters.")
else:
    for idx, row in filtered_data.iterrows():
        actual_index = st.session_state.data[(st.session_state.data["Date"] == row["Date"]) &
                                             (st.session_state.data["Size (mm)"] == row["Size (mm)"]) &
                                             (st.session_state.data["Type"] == row["Type"]) &
                                             (st.session_state.data["Quantity"] == row["Quantity"]) &
                                             (st.session_state.data["Status"] == row["Status"])].index

        if st.session_state.edit_row == idx:
            with st.form(f"edit_form_{idx}", clear_on_submit=False):
                edate = st.date_input("Date", value=row["Date"], key=f"edate_{idx}")
                esize = st.text_input("Rotor Size (mm)", value=row["Size (mm)"], key=f"esize_{idx}")
                etype = st.selectbox("Type", ["Inward", "Outward"], index=["Inward", "Outward"].index(row["Type"]), key=f"etype_{idx}")
                equantity = st.number_input("Quantity", value=int(row["Quantity"]), min_value=1, key=f"equantity_{idx}")
                epending = st.checkbox("Pending", value=row["Pending"], key=f"epending_{idx}")
                eremarks = st.text_input("Remarks", value=row["Remarks"], key=f"eremarks_{idx}")
                estatus = st.selectbox("Status", ["Current", "Coming Rotors"], index=["Current", "Coming Rotors"].index(row["Status"]), key=f"estatus_{idx}")

                col_save, col_cancel = st.columns(2)
                if col_save.form_submit_button("💾 Save"):
                    st.session_state.data.loc[actual_index, ["Date", "Size (mm)", "Type", "Quantity", "Pending", "Remarks", "Status"]] = [
                        pd.to_datetime(edate), esize, etype, equantity, epending, eremarks, estatus
                    ]
                    save_data_to_gsheet(st.session_state.data)
                    st.session_state.edit_row = None
                    st.success("Entry updated successfully.")
                if col_cancel.form_submit_button("❌ Cancel"):
                    st.session_state.edit_row = None
        else:
            row_display = f"📅 {row['Date'].date()} | 📝 {row['Size (mm)']}mm | 🔄 {row['Type']} | 📦 {row['Quantity']} | ⏳ {'Yes' if row['Pending'] else 'No'} | 🗂 {row['Status']}"
            if row["Remarks"]:
                row_display += f" | 📝 {row['Remarks']}"
            cols = st.columns([6, 1, 1])
            cols[0].markdown(row_display)
            if cols[1].button("✏", key=f"edit_{idx}"):
                st.session_state.edit_row = idx
            if cols[2].button("🗑", key=f"del_{idx}"):
                st.session_state.data.drop(actual_index, inplace=True)
                st.session_state.data.reset_index(drop=True, inplace=True)
                save_data_to_gsheet(st.session_state.data)
                st.success("Entry deleted.")

# ------------------- Current Stock Summary (Optional) -------------------
st.markdown("---")
st.subheader("📊 Current Stock Summary")
try:
    current_inward = st.session_state.data[
        (st.session_state.data['Status'] == 'Current') & 
        (~st.session_state.data['Pending']) & 
        (st.session_state.data['Type'] == 'Inward')
    ]
    summary = current_inward.groupby('Size (mm)')['Quantity'].sum().reset_index()
    summary.columns = ['Rotor Size (mm)', 'Total Quantity']
    st.dataframe(summary)
except Exception as e:
    st.error(f"Stock Summary Error: {e}")
