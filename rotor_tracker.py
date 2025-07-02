import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import time

# ====== SESSION STATE INITIALIZATION ======
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending'
    ])
    st.session_state.last_sync = "Never"
    st.session_state.editing = None

if 'first_load_done' not in st.session_state:
    st.session_state.first_load_done = False

# ====== GOOGLE SHEETS INTEGRATION ======
def get_gsheet_connection():
    try:
        scope = ["https://spreadsheets.google.com/feeds", 
                 "https://www.googleapis.com/auth/drive"]
        
        if isinstance(st.secrets["gcp_service_account"], str):
            creds_dict = json.loads(st.secrets["gcp_service_account"])
        else:
            creds_dict = dict(st.secrets["gcp_service_account"])
        
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
                if 'Status' not in df.columns:
                    df['Status'] = 'Current'
                if 'Pending' not in df.columns:
                    df['Pending'] = False
                df['Pending'] = df['Pending'].apply(lambda x: True if str(x).strip().lower() == 'true' else False)
                st.session_state.data = df
                st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success("✅ Data loaded from Google Sheets")
            else:
                st.info("No data found in Google Sheet")
    except Exception as e:
        st.error(f"Error loading data: {e}")

def save_to_backup_sheet(df):
    try:
        spreadsheet = get_gsheet_connection().spreadsheet
        try:
            backup_sheet = spreadsheet.worksheet("Backup")
        except gspread.exceptions.WorksheetNotFound:
            backup_sheet = spreadsheet.add_worksheet(title="Backup", rows="1000", cols="20")

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        df.insert(0, 'Backup Time', timestamp)
        records = [df.columns.tolist()] + df.values.tolist()
        backup_sheet.append_rows(records)
    except Exception as e:
        st.warning(f"Backup failed: {e}")  # ensure this is imported at top of your file

def auto_save_to_gsheet(retries=3, delay=2):
    attempt = 1
    while attempt <= retries:
        try:
            sheet = get_gsheet_connection()
            if sheet:
                sheet.clear()

                if not st.session_state.data.empty:
                    df = st.session_state.data.copy()

                    # Convert Pending boolean to string for Google Sheets
                    df['Pending'] = df['Pending'].apply(lambda x: "TRUE" if x else "FALSE")

                    # Ensure expected columns
                    expected_cols = ['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending']
                    for col in expected_cols:
                        if col not in df.columns:
                            df[col] = ""
                    df = df[expected_cols]

                    # Push to sheet
                    records = [df.columns.tolist()] + df.values.tolist()
                    sheet.update(records)

                    # Also backup
                    save_to_backup_sheet(df.copy())

                st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                return  # ✅ Success, exit function
        except Exception as e:
            if attempt < retries:
                time.sleep(delay)
                attempt += 1
            else:
                st.error(f"❌ Auto-save failed after {retries} attempts: {e}")
                return

# ====== AUTO-LOAD DATA ON FIRST RUN ======
if not st.session_state.first_load_done:
    load_from_gsheet()
    st.session_state.first_load_done = True

# ====== SYNC BUTTONS ======
col_sync, col_saved = st.columns(2)

with col_sync:
    if st.button("🔄 Sync Now", help="Save current data to Google Sheets"):
        auto_save_to_gsheet()

with col_saved:
    if st.button("📂 Load Previously Saved", help="Load the last saved version from Google Sheets"):
        load_from_gsheet()
        st.rerun()
# ====== ENTRY FORMS ======
form_tabs = st.tabs(["Current Movement", "Coming Rotors", "Pending Rotors"])

with form_tabs[0]:  # Current Movement
    with st.form("current_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Date", value=datetime.today())
            rotor_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, format="%d")
        with col2:
            entry_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"])
            quantity = st.number_input("🔢 Quantity", min_value=1, step=1, format="%d")
        remarks = st.text_input("📝 Remarks")
        
        if st.form_submit_button("➕ Add Entry"):
            new_entry = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'),
                'Size (mm)': rotor_size, 
                'Type': entry_type, 
                'Quantity': quantity, 
                'Remarks': remarks,
                'Status': 'Current',
                'Pending': False  # Default to not pending
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

with form_tabs[1]:  # Coming Rotors
    with st.form("future_form"):
        col1, col2 = st.columns(2)
        with col1:
            future_date = st.date_input("📅 Expected Date", min_value=datetime.today() + timedelta(days=1))
            future_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, format="%d")
        with col2:
            future_qty = st.number_input("🔢 Quantity", min_value=1, step=1, format="%d")
            future_remarks = st.text_input("📝 Remarks")
        
        if st.form_submit_button("➕ Add Coming Rotors"):
            new_entry = pd.DataFrame([{
                'Date': future_date.strftime('%Y-%m-%d'),
                'Size (mm)': future_size, 
                'Type': 'Inward', 
                'Quantity': future_qty, 
                'Remarks': future_remarks,
                'Status': 'Future',
                'Pending': False  # Coming rotors are not pending by default
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

with form_tabs[2]:  # Pending Rotors
    with st.form("pending_form"):
        col1, col2 = st.columns(2)
        with col1:
            pending_date = st.date_input("📅 Date", value=datetime.today())
            pending_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, format="%d")
        with col2:
            pending_qty = st.number_input("🔢 Quantity", min_value=1, step=1, format="%d")
            pending_remarks = st.text_input("📝 Remarks", value="Pending delivery")
        
        if st.form_submit_button("➕ Add Pending Rotors"):
            new_entry = pd.DataFrame([{
                'Date': pending_date.strftime('%Y-%m-%d'),
                'Size (mm)': pending_size, 
                'Type': 'Outgoing',  # Typically pending would be outgoing
                'Quantity': pending_qty, 
                'Remarks': pending_remarks,
                'Status': 'Current',
                'Pending': True  # Mark as pending
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

# ====== STOCK SUMMARY ======
st.subheader("📊 Current Stock Summary")
if not st.session_state.data.empty:
    try:
        # Current stock (non-pending items)
        current = st.session_state.data[
            (st.session_state.data['Status'] == 'Current') & 
            (~st.session_state.data['Pending'])  # Exclude pending items
        ].copy()
        current['Net'] = current.apply(lambda x: x['Quantity'] if x['Type'] == 'Inward' else -x['Quantity'], axis=1)
        stock = current.groupby('Size (mm)')['Net'].sum().reset_index()
        stock = stock[stock['Net'] != 0]
        
        # Coming rotors
        future = st.session_state.data[st.session_state.data['Status'] == 'Future']
        coming = future.groupby('Size (mm)')['Quantity'].sum().reset_index()
        
        # Pending rotors
        pending = st.session_state.data[st.session_state.data['Pending']]
        pending_rotors = pending.groupby('Size (mm)')['Quantity'].sum().reset_index()
        
        # Combined view
        combined = pd.merge(stock, coming, on='Size (mm)', how='outer')
        combined = pd.merge(combined, pending_rotors, on='Size (mm)', how='outer', suffixes=('', '_pending'))
        combined = combined.fillna(0)
        combined.columns = ['Size (mm)', 'Current Stock', 'Coming Rotors', 'Pending Rotors']
        
        st.dataframe(
            combined,
            use_container_width=True,
            hide_index=True
        )
    except Exception as e:
        st.error(f"Error generating summary: {e}")
else:
    st.info("No data available yet")

# ====== MOVEMENT LOG WITH EDIT FUNCTIONALITY ======
with st.expander("📋 View Movement Log", expanded=False):
    df = st.session_state.data.copy()
    
    if not df.empty:
        try:
            # Ensure correct types
            df['Date'] = pd.to_datetime(df['Date'])
            df['Pending'] = df['Pending'].astype(bool)
            df['Size (mm)'] = pd.to_numeric(df['Size (mm)'], errors='coerce')

            st.markdown("### 🔍 Filter Movement Log")
            fc1, fc2, fc3, fc4 = st.columns(4)
            with fc1:
                status_filter = st.multiselect("📂 Status", options=df["Status"].unique(), default=df["Status"].unique())
            with fc2:
                pending_filter = st.selectbox("❗ Pending", ["All", "Yes", "No"])
            with fc3:
                size_filter = st.multiselect("📐 Size (mm)", options=sorted(df["Size (mm)"].dropna().unique()), default=sorted(df["Size (mm)"].dropna().unique()))
            with fc4:
                remarks_filter = st.text_input("📝 Remarks contains", "")

            # Apply filters
            filtered_df = df[df["Status"].isin(status_filter)]
            filtered_df = filtered_df[filtered_df["Size (mm)"].isin(size_filter)]

            if pending_filter != "All":
                is_pending = True if pending_filter == "Yes" else False
                filtered_df = filtered_df[filtered_df["Pending"] == is_pending]

            if remarks_filter:
                filtered_df = filtered_df[filtered_df["Remarks"].str.contains(remarks_filter, case=False, na=False)]

            filtered_df = filtered_df.sort_values("Date", ascending=False).reset_index(drop=True)

            if filtered_df.empty:
                st.info("No entries match the selected filters.")
            else:
                for idx, row in filtered_df.iterrows():
                    original_index = df[
                        (df["Date"] == row["Date"]) &
                        (df["Size (mm)"] == row["Size (mm)"]) &
                        (df["Type"] == row["Type"]) &
                        (df["Quantity"] == row["Quantity"]) &
                        (df["Remarks"] == row["Remarks"]) &
                        (df["Status"] == row["Status"]) &
                        (df["Pending"] == row["Pending"])
                    ].index
                    if original_index.empty:
                        continue
                    original_index = original_index[0]

                    cols = st.columns([10, 1, 1])
                    with cols[0]:
                        display_data = {
                            "Date": row["Date"].strftime("%Y-%m-%d"),
                            "Size (mm)": row["Size (mm)"],
                            "Type": row["Type"],
                            "Quantity": row["Quantity"],
                            "Remarks": row["Remarks"],
                            "Status": row["Status"],
                            "Pending": "Yes" if row["Pending"] else "No"
                        }
                        st.dataframe(pd.DataFrame([display_data]), hide_index=True, use_container_width=True)

                    with cols[1]:
                        if st.button("✏", key=f"edit_{original_index}"):
                            st.session_state.editing = original_index

                    with cols[2]:
                        if st.button("❌", key=f"del_{original_index}"):
                            st.session_state.data = st.session_state.data.drop(original_index).reset_index(drop=True)
                            auto_save_to_gsheet()
                            st.rerun()

                    # Inline Edit Form
                    if st.session_state.editing == original_index:
                        edit_row = st.session_state.data.loc[original_index]
                        with st.form(f"edit_form_{original_index}"):
                            ec1, ec2 = st.columns(2)
                            with ec1:
                                edit_date = st.date_input("📅 Date", value=pd.to_datetime(edit_row["Date"]), key=f"date_{original_index}")
                                edit_size = st.number_input("📐 Rotor Size (mm)", value=int(edit_row["Size (mm)"]), min_value=1, key=f"size_{original_index}")
                            with ec2:
                                edit_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"], index=0 if edit_row["Type"] == "Inward" else 1, key=f"type_{original_index}")
                                edit_qty = st.number_input("🔢 Quantity", value=int(edit_row["Quantity"]), min_value=1, key=f"qty_{original_index}")
                            edit_remarks = st.text_input("📝 Remarks", value=edit_row["Remarks"], key=f"remarks_{original_index}")
                            edit_status = st.selectbox("📂 Status", ["Current", "Future"], index=0 if edit_row["Status"] == "Current" else 1, key=f"status_{original_index}")
                            edit_pending = st.checkbox("❗ Pending", value=edit_row["Pending"], key=f"pending_{original_index}")

                            sc, cc = st.columns(2)
                            with sc:
                                if st.form_submit_button("💾 Save"):
                                    st.session_state.data.at[original_index, "Date"] = edit_date.strftime("%Y-%m-%d")
                                    st.session_state.data.at[original_index, "Size (mm)"] = edit_size
                                    st.session_state.data.at[original_index, "Type"] = edit_type
                                    st.session_state.data.at[original_index, "Quantity"] = edit_qty
                                    st.session_state.data.at[original_index, "Remarks"] = edit_remarks
                                    st.session_state.data.at[original_index, "Status"] = edit_status
                                    st.session_state.data.at[original_index, "Pending"] = edit_pending
                                    st.session_state.editing = None
                                    auto_save_to_gsheet()
                                    st.rerun()
                            with cc:
                                if st.form_submit_button("❌ Cancel"):
                                    st.session_state.editing = None
                                    st.rerun()

        except Exception as e:
            st.error(f"Error in movement log: {e}")
    else:
        st.info("No data available.")
# Status footer
if st.session_state.last_sync != "Never":
    st.caption(f"Last synced: {st.session_state.last_sync}")
