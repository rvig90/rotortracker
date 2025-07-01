import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ====== INITIALIZE DATA ======
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending'
    ])
    st.session_state.last_sync = "Never"
    st.session_state.editing = None  # Track which row is being edited

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
                else:
                    # Normalize to boolean
                    df['Pending'] = df['Pending'].apply(lambda x: str(x).strip().lower() in ['true', 'yes', '1'])

                st.session_state.data = df
                st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success("Data loaded successfully!")
            else:
                st.info("No data found in Google Sheet")
    except Exception as e:
        st.error(f"Error loading data: {e}")
def auto_save_to_gsheet():
    try:
        sheet = get_gsheet_connection()
        if sheet:
            sheet.clear()  # Clears all values from the sheet

            if not st.session_state.data.empty:
                # Prepare data: convert boolean to string (since Google Sheets stores as text)
                df = st.session_state.data.copy()
                df['Pending'] = df['Pending'].apply(lambda x: "TRUE" if x else "FALSE")
                
                # Prepare as list of lists
                records = [df.columns.tolist()] + df.values.tolist()
                
                # Write data
                sheet.update(records)

            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"Auto-save failed: {e}")
# ====== SINGLE SYNC BUTTON ======
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
    if not st.session_state.data.empty:
        try:
            st.markdown("### 🔍 Filter Movement Log")

            # Add original index column for editing/deleting after filtering
            st.session_state.data['__index__'] = st.session_state.data.index

            # ----- Filter UI -----
            filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)

            with filter_col1:
                size_filter = st.multiselect("📐 Size (mm)", sorted(st.session_state.data['Size (mm)'].unique()), default=[])
            with filter_col2:
                type_filter = st.multiselect("🔄 Type", ["Inward", "Outgoing"], default=[])
            with filter_col3:
                pending_filter = st.selectbox("✅ Pending", options=["All", "Yes", "No"])
            with filter_col4:
                remark_filter = st.text_input("📝 Remarks contains")

            date_start, date_end = st.columns(2)
            with date_start:
                start_date = st.date_input("From Date", value=datetime(2023, 1, 1))
            with date_end:
                end_date = st.date_input("To Date", value=datetime.today())

            # ----- Apply Filters -----
            df = st.session_state.data.copy()
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['__index__'] = df['__index__'].astype(int)  # ensure int

            df = df[(df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))]
            if size_filter:
                df = df[df['Size (mm)'].isin(size_filter)]
            if type_filter:
                df = df[df['Type'].isin(type_filter)]
            if pending_filter == "Yes":
                df = df[df['Pending'] == True]
            elif pending_filter == "No":
                df = df[df['Pending'] == False]
            if remark_filter:
                df = df[df['Remarks'].str.contains(remark_filter, case=False, na=False)]

            df = df.reset_index(drop=True)

            if not df.empty:
                for idx, row in df.iterrows():
                    original_idx = int(row['__index__'])
                    is_editing = st.session_state.editing == original_idx

                    with st.form(f"row_form_{idx}"):
                        row_col1, row_col2, row_col3 = st.columns([8, 1, 1])

                        with row_col1:
                            if is_editing:
                                edit_date = st.date_input("📅 Date", value=row['Date'], key=f"edit_date_{idx}")
                                edit_size = st.number_input("📐 Size (mm)", min_value=1, value=int(row['Size (mm)']), key=f"edit_size_{idx}")
                                edit_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"], index=0 if row['Type'] == 'Inward' else 1, key=f"edit_type_{idx}")
                                edit_qty = st.number_input("🔢 Quantity", min_value=1, value=int(row['Quantity']), key=f"edit_qty_{idx}")
                                edit_remarks = st.text_input("📝 Remarks", value=row['Remarks'], key=f"edit_remarks_{idx}")
                                edit_pending = st.checkbox("Pending", value=row['Pending'], key=f"edit_pending_{idx}")
                            else:
                                display_data = pd.DataFrame([{
                                    'Date': row['Date'].strftime('%Y-%m-%d') if isinstance(row['Date'], pd.Timestamp) else row['Date'],
                                    'Size (mm)': row['Size (mm)'],
                                    'Type': row['Type'],
                                    'Quantity': row['Quantity'],
                                    'Remarks': row['Remarks'],
                                    'Pending': 'Yes' if row['Pending'] else 'No'
                                }])
                                st.dataframe(display_data, hide_index=True, use_container_width=True)

                        with row_col2:
                            if is_editing:
                                if st.form_submit_button("💾 Save"):
                                    st.session_state.data.at[original_idx, 'Date'] = edit_date.strftime('%Y-%m-%d')
                                    st.session_state.data.at[original_idx, 'Size (mm)'] = edit_size
                                    st.session_state.data.at[original_idx, 'Type'] = edit_type
                                    st.session_state.data.at[original_idx, 'Quantity'] = edit_qty
                                    st.session_state.data.at[original_idx, 'Remarks'] = edit_remarks
                                    st.session_state.data.at[original_idx, 'Pending'] = edit_pending
                                    st.session_state.editing = None
                                    auto_save_to_gsheet()
                                    st.rerun()
                            else:
                                if st.form_submit_button("✏️ Edit"):
                                    st.session_state.editing = original_idx

                        with row_col3:
                            if is_editing:
                                if st.form_submit_button("❌ Cancel"):
                                    st.session_state.editing = None
                                    st.rerun()
                            else:
                                if st.form_submit_button("🗑️ Delete"):
                                    st.session_state.data = st.session_state.data.drop(original_idx).reset_index(drop=True)
                                    auto_save_to_gsheet()
                                    st.rerun()
            else:
                st.info("No entries match the selected filters.")
        except Exception as e:
            st.error(f"Error displaying movement log: {e}")
    else:
        st.info("No entries to display.")
# Status footer
if st.session_state.last_sync != "Never":
    st.caption(f"Last synced: {st.session_state.last_sync}")
