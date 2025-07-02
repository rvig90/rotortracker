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

# ====== HELPER FUNCTION TO NORMALIZE BOOLEAN ======
def normalize_pending_column(df):
    df['Pending'] = df['Pending'].apply(
        lambda x: str(x).lower() == 'true' if isinstance(x, str) else bool(x)
    )
    return df

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
                df = normalize_pending_column(df)
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

# ====== SYNC BUTTON ======
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
                'Pending': False
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
                'Pending': False
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
                'Type': 'Outgoing',
                'Quantity': pending_qty, 
                'Remarks': pending_remarks,
                'Status': 'Current',
                'Pending': True
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

# ====== STOCK SUMMARY ======
# ====== STOCK SUMMARY ======
st.subheader("📊 Current Stock Summary")
if not st.session_state.data.empty:
    try:
        # ✅ Ensure Pending column is boolean
        st.session_state.data = normalize_pending_column(st.session_state.data)

        # Current inward stock (excluding pending)
        current = st.session_state.data[
            (st.session_state.data['Status'] == 'Current') & 
            (~st.session_state.data['Pending'])
        ].copy()
        current['Net'] = current.apply(lambda x: x['Quantity'] if x['Type'] == 'Inward' else -x['Quantity'], axis=1)
        stock = current.groupby('Size (mm)')['Net'].sum().reset_index()
        stock = stock[stock['Net'] != 0]

        # Future rotors (coming rotors)
        future = st.session_state.data[st.session_state.data['Status'] == 'Future']
        coming = future.groupby('Size (mm)')['Quantity'].sum().reset_index()

        # ✅ Pending rotors (only if marked Pending and Status = Current)
        pending = st.session_state.data[
            (st.session_state.data['Status'] == 'Current') & 
            (st.session_state.data['Pending'])
        ]
        pending_rotors = pending.groupby('Size (mm)')['Quantity'].sum().reset_index()

        # Merge all
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
# ====== MOVEMENT LOG WITH EDIT/DELETE ======
# ====== MOVEMENT LOG WITH TABLE LAYOUT, FILTERS, INLINE EDIT ======
with st.expander("📋 View Movement Log", expanded=True):
    if not st.session_state.data.empty:
        try:
            df = st.session_state.data.copy()
            df = normalize_pending_column(df)

            st.markdown("### 🔍 Filters")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                selected_status = st.multiselect("📌 Status", options=df['Status'].unique().tolist(), default=df['Status'].unique().tolist())
            with col2:
                selected_pending = st.selectbox("⏳ Pending?", options=["All", "Yes", "No"])
            with col3:
                selected_size = st.multiselect("📐 Size (mm)", options=sorted(df['Size (mm)'].unique()), default=sorted(df['Size (mm)'].unique()))
            with col4:
                search_remarks = st.text_input("📝 Remarks contains")

            date1, date2 = st.columns(2)
            with date1:
                start_date = st.date_input("From Date", value=pd.to_datetime(df['Date']).min())
            with date2:
                end_date = st.date_input("To Date", value=pd.to_datetime(df['Date']).max())

            # Apply filters
            filtered = df[
                (df['Status'].isin(selected_status)) &
                (df['Size (mm)'].isin(selected_size)) &
                (pd.to_datetime(df['Date']) >= pd.to_datetime(start_date)) &
                (pd.to_datetime(df['Date']) <= pd.to_datetime(end_date))
            ]
            if selected_pending != "All":
                filtered = filtered[filtered['Pending'] == (selected_pending == "Yes")]
            if search_remarks:
                filtered = filtered[filtered['Remarks'].str.contains(search_remarks, case=False, na=False)]

            if filtered.empty:
                st.warning("No entries match the selected filters.")
            else:
                st.markdown("### 📋 Filtered Movement Log")

                for idx, row in filtered.sort_values("Date", ascending=False).iterrows():
                    is_editing = st.session_state.editing == idx
                    if not is_editing:
                        # Show table row view
                        row_df = pd.DataFrame([{
                            "Date": row['Date'],
                            "Size (mm)": row['Size (mm)'],
                            "Type": row['Type'],
                            "Quantity": row['Quantity'],
                            "Remarks": row['Remarks'],
                            "Pending": "Yes" if row['Pending'] else "No"
                        }])
                        st.dataframe(row_df, hide_index=True, use_container_width=True)

                        col_edit, col_del = st.columns([1, 1])
                        with col_edit:
                            if st.button("✏ Edit", key=f"edit_{idx}"):
                                st.session_state.editing = idx
                        with col_del:
                            if st.button("🗑 Delete", key=f"delete_{idx}"):
                                st.session_state.data = st.session_state.data.drop(idx).reset_index(drop=True)
                                auto_save_to_gsheet()
                                st.rerun()

                    else:
                        st.markdown("### ✏ Edit Entry")
                        with st.form(f"edit_form_{idx}"):
                            col1, col2 = st.columns(2)
                            with col1:
                                edit_date = st.date_input("📅 Date", value=pd.to_datetime(row['Date']), key=f"edit_date_{idx}")
                                edit_size = st.number_input("📐 Size (mm)", min_value=1, value=int(row['Size (mm)']), key=f"edit_size_{idx}")
                            with col2:
                                edit_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"], index=0 if row['Type'] == "Inward" else 1, key=f"edit_type_{idx}")
                                edit_qty = st.number_input("🔢 Quantity", min_value=1, value=int(row['Quantity']), key=f"edit_qty_{idx}")
                            edit_remarks = st.text_input("📝 Remarks", value=row['Remarks'], key=f"edit_remarks_{idx}")
                            edit_pending = st.checkbox("⏳ Pending?", value=row['Pending'], key=f"edit_pending_{idx}")

                            save_col, cancel_col = st.columns(2)
                            with save_col:
                                if st.form_submit_button("💾 Save"):
                                    st.session_state.data.at[idx, 'Date'] = edit_date.strftime('%Y-%m-%d')
                                    st.session_state.data.at[idx, 'Size (mm)'] = edit_size
                                    st.session_state.data.at[idx, 'Type'] = edit_type
                                    st.session_state.data.at[idx, 'Quantity'] = edit_qty
                                    st.session_state.data.at[idx, 'Remarks'] = edit_remarks
                                    st.session_state.data.at[idx, 'Pending'] = edit_pending
                                    st.session_state.editing = None
                                    auto_save_to_gsheet()
                                    st.rerun()
                            with cancel_col:
                                if st.form_submit_button("❌ Cancel"):
                                    st.session_state.editing = None
                                    st.rerun()
        except Exception as e:
            st.error(f"Error in movement log: {e}")
    else:
        st.info("No entries available.")
# ====== LAST SYNC STATUS ======
if st.session_state.last_sync != "Never":
    st.caption(f"Last synced: {st.session_state.last_sync}")
