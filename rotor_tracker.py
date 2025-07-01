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
                    # Fix pending values to boolean
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
        if sheet and not st.session_state.data.empty:
            sheet.clear()
            sheet.append_row(st.session_state.data.columns.tolist())
            for _, row in st.session_state.data.iterrows():
                sheet.append_row(row.tolist())
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"Auto-save failed: {e}")

# ====== SINGLE SYNC BUTTON ======
if st.button("🔄 Sync Now", help="Load latest data from Google Sheets"):
    load_from_gsheet()

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

            filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)

            with filter_col1:
                size_filter = st.multiselect("📐 Size (mm)", options=sorted(st.session_state.data['Size (mm)'].unique()), default=[])
            with filter_col2:
                type_filter = st.multiselect("🔄 Type", options=["Inward", "Outgoing"], default=[])
            with filter_col3:
                pending_filter = st.selectbox("✅ Pending", options=["All", "Yes", "No"])
            with filter_col4:
                remark_filter = st.text_input("📝 Remarks contains")

            # Date filter
            date_start, date_end = st.columns(2)
            with date_start:
                start_date = st.date_input("From Date", value=datetime(2023, 1, 1))
            with date_end:
                end_date = st.date_input("To Date", value=datetime.today())

            # ----- APPLY FILTERS -----
            df = st.session_state.data.copy()
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

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
                    cols = st.columns([10, 1, 1])
                    with cols[0]:
                        row_display = pd.DataFrame([{
                            'Date': row['Date'].strftime('%Y-%m-%d') if isinstance(row['Date'], pd.Timestamp) else row['Date'],
                            'Size (mm)': row['Size (mm)'],
                            'Type': row['Type'],
                            'Quantity': row['Quantity'],
                            'Remarks': row['Remarks'],
                            'Pending': 'Yes' if row['Pending'] else 'No'
                        }])
                        st.dataframe(row_display, use_container_width=True, hide_index=True)

                    with cols[1]:
                        if st.button("✏", key=f"edit_{idx}"):
                            st.session_state.editing = df.index[idx]  # map back to original index
                    with cols[2]:
                        if st.button("❌", key=f"del_{idx}"):
                            st.session_state.data = st.session_state.data.drop(df.index[idx]).reset_index(drop=True)
                            auto_save_to_gsheet()
                            st.rerun()

                # Edit Form
                if st.session_state.editing is not None:
                    original_idx = st.session_state.editing
                    edit_row = st.session_state.data.loc[original_idx]

                    with st.form("edit_form"):
                        col1, col2 = st.columns(2)
                        with col1:
                            edit_date = st.date_input("📅 Date", 
                                value=datetime.strptime(edit_row['Date'], '%Y-%m-%d') 
                                if isinstance(edit_row['Date'], str) else edit_row['Date'])
                            edit_size = st.number_input("📐 Rotor Size (mm)", min_value=1, value=int(edit_row['Size (mm)']))
                        with col2:
                            edit_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"], index=0 if edit_row['Type'] == 'Inward' else 1)
                            edit_qty = st.number_input("🔢 Quantity", min_value=1, value=int(edit_row['Quantity']))
                        edit_remarks = st.text_input("📝 Remarks", value=edit_row['Remarks'])
                        edit_pending = st.checkbox("Pending", value=edit_row['Pending'])

                        save_col, cancel_col = st.columns(2)
                        with save_col:
                            if st.form_submit_button("💾 Save Changes"):
                                st.session_state.data.at[original_idx, 'Date'] = edit_date.strftime('%Y-%m-%d')
                                st.session_state.data.at[original_idx, 'Size (mm)'] = edit_size
                                st.session_state.data.at[original_idx, 'Type'] = edit_type
                                st.session_state.data.at[original_idx, 'Quantity'] = edit_qty
                                st.session_state.data.at[original_idx, 'Remarks'] = edit_remarks
                                st.session_state.data.at[original_idx, 'Pending'] = edit_pending
                                st.session_state.editing = None
                                auto_save_to_gsheet()
                                st.rerun()
                        with cancel_col:
                            if st.form_submit_button("❌ Cancel"):
                                st.session_state.editing = None
                                st.rerun()
            else:
                st.info("No data matching the filters.")
        except Exception as e:
            st.error(f"Error displaying movement log: {e}")
    else:
        st.info("No entries to display.")
# Status footer
if st.session_state.last_sync != "Never":
    st.caption(f"Last synced: {st.session_state.last_sync}")
