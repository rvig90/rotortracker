import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# Ensure session state attributes are initialized
if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending'])
if "last_sync" not in st.session_state:
    st.session_state.last_sync = "Never"
if "editing" not in st.session_state:
    st.session_state.editing = None
if "first_load_done" not in st.session_state:
    st.session_state.first_load_done = False

# ==== GSheet Connection ====
def get_gsheet_connection():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(st.secrets["gcp_service_account"]) if isinstance(st.secrets["gcp_service_account"], str) else dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Rotor Log")
    except Exception as e:
        st.error(f"Google Sheets connection failed: {e}")
        return None

def load_from_gsheet():
    try:
        doc = get_gsheet_connection()
        sheet = doc.sheet1
        records = sheet.get_all_records()
        if records:
            df = pd.DataFrame(records)
            df["Pending"] = df.get("Pending", False).astype(bool)
            st.session_state.data = df
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.success("Data loaded successfully!")
        else:
            st.info("No data found in Google Sheet")
    except Exception as e:
        st.error(f"Error loading data: {e}")

def save_to_gsheet():
    try:
        doc = get_gsheet_connection()
        sheet = doc.sheet1
        sheet.clear()
        sheet.append_row(st.session_state.data.columns.tolist())
        for _, row in st.session_state.data.iterrows():
            sheet.append_row(row.astype(str).tolist())
        st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"Auto-save failed: {e}")

def save_to_backup():
    try:
        doc = get_gsheet_connection()
        backup = doc.worksheet("Backup")
        df = st.session_state.data.copy()
        df.insert(0, "Backup Time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        backup.append_rows([df.columns.tolist()] + df.values.tolist())
    except Exception as e:
        st.warning(f"Backup failed: {e}")

# Auto-load data on first run
if not st.session_state.first_load_done:
    load_from_gsheet()
    st.session_state.first_load_done = True

# Sync controls
st.button("🔄 Sync Now", on_click=load_from_gsheet)
st.button("📥 Previously Saved", on_click=load_from_gsheet)

# ====== ENTRY FORMS ======
form_tabs = st.tabs(["Current Movement", "Coming Rotors", "Pending Rotors"])

with form_tabs[0]:
    with st.form("current_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Date", value=datetime.today())
            size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
        with col2:
            qty = st.number_input("🔢 Quantity", min_value=1, step=1)
            typ = st.selectbox("🔄 Type", ["Inward", "Outgoing"])
        remarks = st.text_input("📝 Remarks")

        if st.form_submit_button("➕ Add Entry"):
            new_row = {
                "Date": date.strftime("%Y-%m-%d"),
                "Size (mm)": int(size),
                "Quantity": int(qty),
                "Type": typ,
                "Remarks": remarks,
                "Status": "Current",
                "Pending": False
            }
            st.session_state.data = pd.concat([st.session_state.data, pd.DataFrame([new_row])], ignore_index=True)
            save_to_backup()
            save_to_gsheet()
            st.rerun()

with form_tabs[1]:
    with st.form("future_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Expected Date", value=datetime.today() + timedelta(days=1))
            size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
        with col2:
            qty = st.number_input("🔢 Quantity", min_value=1, step=1)
            remarks = st.text_input("📝 Remarks")

        if st.form_submit_button("➕ Add Coming Rotor"):
            new_row = {
                "Date": date.strftime("%Y-%m-%d"),
                "Size (mm)": int(size),
                "Quantity": int(qty),
                "Type": "Inward",
                "Remarks": remarks,
                "Status": "Future",
                "Pending": False
            }
            st.session_state.data = pd.concat([st.session_state.data, pd.DataFrame([new_row])], ignore_index=True)
            save_to_backup()
            save_to_gsheet()
            st.rerun()

with form_tabs[2]:
    with st.form("pending_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Date", value=datetime.today())
            size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
        with col2:
            qty = st.number_input("🔢 Quantity", min_value=1, step=1)
            remarks = st.text_input("📝 Remarks", value="Pending delivery")

        if st.form_submit_button("➕ Add Pending Rotor"):
            new_row = {
                "Date": date.strftime("%Y-%m-%d"),
                "Size (mm)": int(size),
                "Quantity": int(qty),
                "Type": "Outgoing",
                "Remarks": remarks,
                "Status": "Current",
                "Pending": True
            }
            st.session_state.data = pd.concat([st.session_state.data, pd.DataFrame([new_row])], ignore_index=True)
            save_to_backup()
            save_to_gsheet()
            st.rerun()

# ====== STOCK SUMMARY ======
st.subheader("📊 Stock Summary")
try:
    df = st.session_state.data.copy()
    df["Size (mm)"] = pd.to_numeric(df["Size (mm)"], errors="coerce")
    df["Pending"] = df["Pending"].astype(bool)

    current = df[(df["Status"] == "Current") & (~df["Pending"])]
    current["Net"] = current.apply(lambda x: x["Quantity"] if x["Type"] == "Inward" else -x["Quantity"], axis=1)
    stock = current.groupby("Size (mm)")["Net"].sum().reset_index()

    future = df[df["Status"] == "Future"]
    coming = future.groupby("Size (mm)")["Quantity"].sum().reset_index()

    pending = df[df["Pending"]]
    pending_stock = pending.groupby("Size (mm)")["Quantity"].sum().reset_index()

    summary = pd.merge(stock, coming, on="Size (mm)", how="outer")
    summary = pd.merge(summary, pending_stock, on="Size (mm)", how="outer", suffixes=("", "_pending"))
    summary = summary.fillna(0)
    summary.columns = ["Size (mm)", "Current", "Coming", "Pending"]

    st.dataframe(summary, use_container_width=True, hide_index=True)
except Exception as e:
    st.error(f"Error in stock summary: {e}")

# ====== MOVEMENT LOG ======
with st.expander("📋 View Movement Log", expanded=True):
    st.markdown("### 🔎 Filter Movement Log")
    df = st.session_state.data.copy()
    df["Pending"] = df["Pending"].astype(bool)
    df["Size (mm)"] = pd.to_numeric(df["Size (mm)"], errors="coerce")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        status_filter = st.multiselect("📂 Status", df["Status"].unique().tolist(), default=df["Status"].unique().tolist())
    with col2:
        pending_filter = st.selectbox("⏳ Pending", ["All", "Yes", "No"])
    with col3:
        size_filter = st.multiselect("📐 Size (mm)", sorted(df["Size (mm)"].dropna().unique()))
    with col4:
        remark_filter = st.text_input("📝 Remarks contains")

    filtered = df.copy()
    if status_filter:
        filtered = filtered[filtered["Status"].isin(status_filter)]
    if pending_filter != "All":
        filtered = filtered[filtered["Pending"] == (pending_filter == "Yes")]
    if size_filter:
        filtered = filtered[filtered["Size (mm)"].isin(size_filter)]
    if remark_filter:
        filtered = filtered[filtered["Remarks"].str.contains(remark_filter, case=False, na=False)]

    if not filtered.empty:
        for i, row in filtered.iterrows():
            cols = st.columns([6, 1, 1])
            with cols[0]:
                st.write(f"📅 {row['Date']} | 📐 {row['Size (mm)']} mm | 🔄 {row['Type']} | 🔢 {row['Quantity']} | 📝 {row['Remarks']} | ⏳ Pending: {'Yes' if row['Pending'] else 'No'}")
            with cols[1]:
                if st.button("✏", key=f"edit_{i}"):
                    st.session_state.editing = i
            with cols[2]:
                if st.button("🗑", key=f"delete_{i}"):
                    st.session_state.data.drop(index=i, inplace=True)
                    st.session_state.data.reset_index(drop=True, inplace=True)
                    save_to_gsheet()
                    st.rerun()

        if st.session_state.editing is not None:
            edit = st.session_state.data.loc[st.session_state.editing]
            with st.form("edit_form"):
                c1, c2 = st.columns(2)
                with c1:
                    ed_date = st.date_input("📅", datetime.strptime(edit["Date"], "%Y-%m-%d"))
                    ed_size = st.number_input("📐", value=int(edit["Size (mm)"]), min_value=1)
                with c2:
                    ed_type = st.selectbox("🔄", ["Inward", "Outgoing"], index=0 if edit["Type"] == "Inward" else 1)
                    ed_qty = st.number_input("🔢", value=int(edit["Quantity"]), min_value=1)
                ed_remarks = st.text_input("📝", value=edit["Remarks"])
                ed_pending = st.checkbox("⏳ Pending", value=edit["Pending"])

                if st.form_submit_button("💾 Save"):
                    st.session_state.data.at[st.session_state.editing, "Date"] = ed_date.strftime("%Y-%m-%d")
                    st.session_state.data.at[st.session_state.editing, "Size (mm)"] = ed_size
                    st.session_state.data.at[st.session_state.editing, "Type"] = ed_type
                    st.session_state.data.at[st.session_state.editing, "Quantity"] = ed_qty
                    st.session_state.data.at[st.session_state.editing, "Remarks"] = ed_remarks
                    st.session_state.data.at[st.session_state.editing, "Pending"] = ed_pending
                    st.session_state.editing = None
                    save_to_backup()
                    save_to_gsheet()
                    st.rerun()
    else:
        st.info("No entries match the selected filters.")

# Footer
st.caption(f"Last synced: {st.session_state.last_sync}")
