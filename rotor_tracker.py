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
        scope = [
            "https://spreadsheets.google.com/feeds", 
            "https://www.googleapis.com/auth/drive"
        ]
        if isinstance(st.secrets["gcp_service_account"], str):
            creds_dict = json.loads(st.secrets["gcp_service_account"])
        else:
            creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Rotor Log").sheet1
    except Exception as e:
        st.error(f"Google Sheets connection failed: {e}")
        return None

def save_to_backup_sheet(df):
    """Save a full copy of df into (or create) the 'Backup' worksheet."""
    try:
        sheet = get_gsheet_connection()
        if not sheet:
            return
        ss = sheet.spreadsheet
        try:
            backup = ss.worksheet("Backup")
        except gspread.WorksheetNotFound:
            backup = ss.add_worksheet(title="Backup", rows="1000", cols=str(len(df.columns)))
        backup.clear()
        records = [df.columns.tolist()] + df.values.tolist()
        backup.update(records)
    except Exception as e:
        st.error(f"Backup failed: {e}")

def load_from_gsheet():
    try:
        sheet = get_gsheet_connection()
        if sheet:
            records = sheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
                # ensure required columns exist
                for col, default in [('Status', 'Current'), ('Pending', False)]:
                    if col not in df.columns:
                        df[col] = default
                df = normalize_pending_column(df)
                st.session_state.data = df
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"Error loading data: {e}")

def auto_save_to_gsheet():
    try:
        sheet = get_gsheet_connection()
        if sheet:
            sheet.clear()
            if not st.session_state.data.empty:
                df = st.session_state.data.copy()
                # convert Pending → "TRUE"/"FALSE"
                df['Pending'] = df['Pending'].apply(lambda x: "TRUE" if x else "FALSE")
                # ensure all columns in order
                expected = ['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending']
                for c in expected:
                    if c not in df.columns:
                        df[c] = ""
                df = df[expected]
                sheet.update([df.columns.tolist()] + df.values.tolist())
                # now backup
                # pass a copy with Pending boolean
                backup_df = st.session_state.data.copy()
                save_to_backup_sheet(backup_df)
        st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"Auto-save failed: {e}")

# ====== AUTO-LOAD ON STARTUP ======
if st.session_state.last_sync == "Never":
    load_from_gsheet()

# ====== SYNC BUTTON ======
if st.button("🔄 Sync Now", help="Manually reload data from Google Sheets"):
    load_from_gsheet()

# ====== ENTRY FORMS ======
form_tabs = st.tabs(["Current Movement", "Coming Rotors", "Pending Rotors"])

with form_tabs[0]:
    with st.form("current_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Date", value=datetime.today())
            rotor_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
        with col2:
            entry_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"])
            quantity = st.number_input("🔢 Quantity", min_value=1, step=1)
        remarks = st.text_input("📝 Remarks")
        if st.form_submit_button("➕ Add Entry"):
            new = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'),
                'Size (mm)': rotor_size,
                'Type': entry_type,
                'Quantity': quantity,
                'Remarks': remarks,
                'Status': 'Current',
                'Pending': False
            }])
            st.session_state.data = pd.concat([st.session_state.data, new], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

with form_tabs[1]:
    with st.form("future_form"):
        col1, col2 = st.columns(2)
        with col1:
            future_date = st.date_input(
                "📅 Expected Date", min_value=datetime.today() + timedelta(days=1)
            )
            future_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
        with col2:
            future_qty = st.number_input("🔢 Quantity", min_value=1, step=1)
            future_remarks = st.text_input("📝 Remarks")
        if st.form_submit_button("➕ Add Coming Rotors"):
            new = pd.DataFrame([{
                'Date': future_date.strftime('%Y-%m-%d'),
                'Size (mm)': future_size,
                'Type': 'Inward',
                'Quantity': future_qty,
                'Remarks': future_remarks,
                'Status': 'Future',
                'Pending': False
            }])
            st.session_state.data = pd.concat([st.session_state.data, new], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

with form_tabs[2]:
    with st.form("pending_form"):
        col1, col2 = st.columns(2)
        with col1:
            pending_date = st.date_input("📅 Date", value=datetime.today())
            pending_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
        with col2:
            pending_qty = st.number_input("🔢 Quantity", min_value=1, step=1)
            pending_remarks = st.text_input("📝 Remarks", value="Pending delivery")
        if st.form_submit_button("➕ Add Pending Rotors"):
            new = pd.DataFrame([{
                'Date': pending_date.strftime('%Y-%m-%d'),
                'Size (mm)': pending_size,
                'Type': 'Outgoing',
                'Quantity': pending_qty,
                'Remarks': pending_remarks,
                'Status': 'Current',
                'Pending': True
            }])
            st.session_state.data = pd.concat([st.session_state.data, new], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

# ====== STOCK SUMMARY ======
st.subheader("📊 Current Stock Summary")
if not st.session_state.data.empty:
    try:
        st.session_state.data = normalize_pending_column(st.session_state.data)
        current = st.session_state.data[
            (st.session_state.data['Status'] == 'Current') &
            (~st.session_state.data['Pending'])
        ].copy()
        current['Net'] = current.apply(
            lambda x: x['Quantity'] if x['Type']=='Inward' else -x['Quantity'], axis=1
        )
        stock = current.groupby('Size (mm)')['Net'].sum().reset_index()
        stock = stock[stock['Net'] != 0]

        future = st.session_state.data[st.session_state.data['Status']=='Future']
        coming = future.groupby('Size (mm)')['Quantity'].sum().reset_index()

        pending = st.session_state.data[
            (st.session_state.data['Status']=='Current') &
            (st.session_state.data['Pending'])
        ]
        pending_rotors = pending.groupby('Size (mm)')['Quantity'].sum().reset_index()

        combined = pd.merge(stock, coming, on='Size (mm)', how='outer')
        combined = pd.merge(
            combined, pending_rotors,
            on='Size (mm)', how='outer', suffixes=('','_pending')
        ).fillna(0)
        combined.columns = [
            'Size (mm)', 'Current Stock', 'Coming Rotors', 'Pending Rotors'
        ]
        st.dataframe(combined, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Error generating summary: {e}")
else:
    st.info("No data available yet")

# ====== MOVEMENT LOG WITH FILTERS & INLINE EDIT/DELETE ======
# ====== MOVEMENT LOG WITH FILTERS & INLINE EDIT/DELETE ======
with st.expander("📋 View Movement Log", expanded=True):
    if st.session_state.data.empty:
        st.info("No entries to show yet.")
    else:
        df = st.session_state.data.copy()
        st.markdown("### 🔍 Filter Movement Log")
        c1, c2, c3 = st.columns(3)
        with c1:
            status_f = st.selectbox("📂 Status", ["All","Current","Future"], key="sf")
        with c2:
            size_f = st.multiselect(
                "📐 Size (mm)", options=sorted(df['Size (mm)'].unique()), key="zf"
            )
        with c3:
            pending_f = st.selectbox("❗ Pending", ["All","Yes","No"], key="pf")
        remark_s = st.text_input("📝 Search Remarks", key="rs")
        date_range = st.date_input(
            "📅 Date Range",
            value=[pd.to_datetime(df['Date']).min(), pd.to_datetime(df['Date']).max()],
            key="dr"
        )

        # APPLY FILTERS
        if status_f != "All":
            df = df[df['Status']==status_f]
        if pending_f=="Yes":
            df = df[df['Pending']==True]
        elif pending_f=="No":
            df = df[df['Pending']==False]
        if size_f:
            df = df[df['Size (mm)'].isin(size_f)]
        if remark_s:
            df = df[df['Remarks'].str.contains(remark_s, case=False, na=False)]
        if isinstance(date_range, (list, tuple)) and len(date_range)==2:
            start, end = date_range
            df = df[
                (pd.to_datetime(df['Date']) >= pd.to_datetime(start)) &
                (pd.to_datetime(df['Date']) <= pd.to_datetime(end))
            ]

        df = df.reset_index(drop=True)
        st.markdown("### 📄 Filtered Entries")

        # Convert Pending to Yes/No for display
        display_df = df.copy()
        display_df['Pending'] = display_df['Pending'].apply(lambda x: 'Yes' if x else 'No')

        # Define editable columns configuration
        editable_cols = {
            "Date": st.column_config.DateColumn(
                "Date",
                format="YYYY-MM-DD",
                required=True
            ),
            "Size (mm)": st.column_config.NumberColumn(
                "Size (mm)",
                min_value=1,
                required=True
            ),
            "Type": st.column_config.SelectboxColumn(
                "Type",
                options=["Inward", "Outgoing"],
                required=True
            ),
            "Quantity": st.column_config.NumberColumn(
                "Quantity",
                min_value=1,
                required=True
            ),
            "Remarks": st.column_config.TextColumn(
                "Remarks"
            ),
            "Status": st.column_config.SelectboxColumn(
                "Status",
                options=["Current", "Future"],
                required=True
            ),
            "Pending": st.column_config.SelectboxColumn(
                "Pending",
                options=["Yes", "No"],
                required=True
            )
        }

        # Display the editable dataframe
        edited_df = st.data_editor(
            display_df,
            column_config=editable_cols,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key="movement_log_editor"
        )

        # Check for changes and update session state
        if not edited_df.equals(display_df):
            # Convert Pending back to boolean
            edited_df['Pending'] = edited_df['Pending'].apply(lambda x: x == 'Yes')
            
            # Update the original indices in session state
            for idx in edited_df.index:
                orig_idx = st.session_state.data[
                    (st.session_state.data['Date'] == df.loc[idx, 'Date']) &
                    (st.session_state.data['Size (mm)'] == df.loc[idx, 'Size (mm)']) &
                    (st.session_state.data['Type'] == df.loc[idx, 'Type']) &
                    (st.session_state.data['Quantity'] == df.loc[idx, 'Quantity']) &
                    (st.session_state.data['Remarks'] == df.loc[idx, 'Remarks']) &
                    (st.session_state.data['Status'] == df.loc[idx, 'Status']) &
                    (st.session_state.data['Pending'] == df.loc[idx, 'Pending'])
                ].index
                
                if not orig_idx.empty:
                    orig_idx = orig_idx[0]
                    for col in edited_df.columns:
                        st.session_state.data.at[orig_idx, col] = edited_df.loc[idx, col]
            
            auto_save_to_gsheet()
            st.rerun()

        # Add delete functionality (since data_editor doesn't support row deletion)
        st.markdown("### ❌ Delete Entries")
        to_delete = st.multiselect(
            "Select entries to delete",
            options=[f"{row['Date']} - {row['Size (mm)']}mm - {row['Type']} - Qty: {row['Quantity']}" 
                    for _, row in df.iterrows()],
            key="delete_selector"
        )

        if st.button("Delete Selected"):
            if to_delete:
                # Find the indices of selected entries to delete
                delete_indices = []
                for desc in to_delete:
                    parts = desc.split(" - ")
                    date = parts[0]
                    size = int(parts[1].replace("mm", ""))
                    typ = parts[2]
                    qty = int(parts[3].replace("Qty: ", ""))
                    
                    mask = (
                        (st.session_state.data['Date'] == date) &
                        (st.session_state.data['Size (mm)'] == size) &
                        (st.session_state.data['Type'] == typ) &
                        (st.session_state.data['Quantity'] == qty)
                    )
                    matches = st.session_state.data[mask].index
                    if not matches.empty:
                        delete_indices.extend(matches.tolist())
                
                if delete_indices:
                    st.session_state.data = st.session_state.data.drop(delete_indices).reset_index(drop=True)
                    auto_save_to_gsheet()
                    st.success(f"Deleted {len(delete_indices)} entries")
                    st.rerun()
            else:
                st.warning("Please select entries to delete")
# ====== LAST SYNC STATUS ======
if st.session_state.last_sync != "Never":
    st.caption(f"Last synced: {st.session_state.last_sync}")
