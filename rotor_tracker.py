import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from PIL import Image
import io
import requests

# ====== INITIALIZE DATA ======
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending'
    ])
    st.session_state.last_sync = "Never"
    st.session_state.editing = None
    st.session_state.filter_reset = False

# ====== APP LOGO ======
def display_logo():
    try:
        # Replace with your actual logo URL or path
        logo_url = "https://via.placeholder.com/200x100?text=Rotor+Tracker"
        logo = Image.open(io.BytesIO(requests.get(logo_url).content))
        st.image(logo, width=200)
    except:
        st.title("Rotor Tracker")

display_logo()

# ====== HELPER FUNCTIONS ======
def normalize_pending_column(df):
    df['Pending'] = df['Pending'].apply(
        lambda x: str(x).lower() == 'true' if isinstance(x, str) else bool(x)
    )
    return df

def safe_delete_entry(orig_idx):
    try:
        if not st.session_state.data.empty and orig_idx in st.session_state.data.index:
            st.session_state.data = st.session_state.data.drop(orig_idx).reset_index(drop=True)
            auto_save_to_gsheet()
            st.success("Entry deleted successfully")
            st.rerun()
        else:
            st.warning("Entry not found or already deleted")
    except Exception as e:
        st.error(f"Error deleting entry: {e}")

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
                df['Pending'] = df['Pending'].apply(lambda x: "TRUE" if x else "FALSE")
                expected = ['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending']
                for c in expected:
                    if c not in df.columns:
                        df[c] = ""
                df = df[expected]
                sheet.update([df.columns.tolist()] + df.values.tolist())
                backup_df = st.session_state.data.copy()
                save_to_backup_sheet(backup_df)
        st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"Auto-save failed: {e}")

# ====== MAIN APP ======
if st.session_state.last_sync == "Never":
    load_from_gsheet()

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
                "📅 Expected Date", 
                min_value=datetime.today() + timedelta(days=1)
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

# ====== MOVEMENT LOG WITH FIXED DELETION ======
with st.expander("📋 View Movement Log", expanded=True):
    if st.session_state.data.empty:
        st.info("No entries to show yet.")
    else:
        df = st.session_state.data.copy()
        st.markdown("### 🔍 Filter Movement Log")

        if st.button("🔄 Reset All Filters"):
            st.session_state.filter_reset = True
            st.rerun()

        if 'filter_reset' not in st.session_state:
            st.session_state.filter_reset = False

        if st.session_state.filter_reset:
            st.session_state.sf = "All"
            st.session_state.zf = []
            st.session_state.pf = "All"
            st.session_state.rs = ""
            min_date = pd.to_datetime(df['Date']).min().date()
            max_date = pd.to_datetime(df['Date']).max().date()
            st.session_state.dr = [min_date, max_date]
            st.session_state.filter_reset = False
            st.rerun()

        c1, c2, c3 = st.columns(3)
        with c1:
            status_f = st.selectbox(
                "📂 Status", 
                ["All", "Current", "Future"], 
                key="sf",
                index=0 if "sf" not in st.session_state else ["All", "Current", "Future"].index(st.session_state.sf)
            )
        with c2:
            size_f = st.multiselect(
                "📐 Size (mm)", 
                options=sorted(df['Size (mm)'].unique()), 
                key="zf",
                default=st.session_state.zf if "zf" in st.session_state else []
            )
        with c3:
            pending_f = st.selectbox(
                "❗ Pending", 
                ["All", "Yes", "No"], 
                key="pf",
                index=0 if "pf" not in st.session_state else ["All", "Yes", "No"].index(st.session_state.pf)
            )

        remark_s = st.text_input(
            "📝 Search Remarks", 
            key="rs",
            value=st.session_state.rs if "rs" in st.session_state else ""
        )
        
        min_date = pd.to_datetime(df['Date']).min().date()
        max_date = pd.to_datetime(df['Date']).max().date()
        date_range = st.date_input(
            "📅 Date Range",
            key="dr",
            value=st.session_state.dr if "dr" in st.session_state else [min_date, max_date]
        )

        try:
            if status_f != "All":
                df = df[df['Status'] == status_f]
            if pending_f == "Yes":
                df = df[df['Pending'] == True]
            elif pending_f == "No":
                df = df[df['Pending'] == False]
            if size_f:
                df = df[df['Size (mm)'].isin(size_f)]
            if remark_s:
                df = df[df['Remarks'].astype(str).str.contains(remark_s, case=False, na=False)]
            if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
                start, end = date_range
                df = df[
                    (pd.to_datetime(df['Date']) >= pd.to_datetime(start)) &
                    (pd.to_datetime(df['Date']) <= pd.to_datetime(end))
                ]
        except Exception as e:
            st.error(f"Error applying filters: {str(e)}")
            df = st.session_state.data.copy()

        df = df.reset_index(drop=True)
        st.markdown("### 📄 Filtered Entries")

        for idx, row in df.iterrows():
            mask = (
                (st.session_state.data['Date'] == row['Date']) &
                (st.session_state.data['Size (mm)'] == row['Size (mm)']) &
                (st.session_state.data['Type'] == row['Type']) &
                (st.session_state.data['Quantity'] == row['Quantity']) &
                (st.session_state.data['Remarks'] == row['Remarks']) &
                (st.session_state.data['Status'] == row['Status']) &
                (st.session_state.data['Pending'] == row['Pending'])
            )
            matching_indices = st.session_state.data[mask].index
            
            if len(matching_indices) == 0:
                continue
                
            orig_idx = matching_indices[0]

            cols = st.columns([10, 1, 1])
            with cols[0]:
                disp = {
                    "Date": row["Date"],
                    "Size (mm)": row["Size (mm)"],
                    "Type": row["Type"],
                    "Quantity": row["Quantity"],
                    "Remarks": row["Remarks"],
                    "Status": row["Status"],
                    "Pending": "Yes" if row["Pending"] else "No"
                }
                st.dataframe(pd.DataFrame([disp]), hide_index=True, use_container_width=True)

            with cols[1]:
                def start_edit(idx=orig_idx):
                    st.session_state.editing = idx
                st.button("✏", key=f"edit_{orig_idx}", on_click=start_edit)

            with cols[2]:
                if st.button("❌", key=f"del_{orig_idx}"):
                    safe_delete_entry(orig_idx)

            if st.session_state.editing == orig_idx:
                er = st.session_state.data.loc[orig_idx]
                with st.form(f"edit_form_{orig_idx}"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        e_date = st.date_input("📅 Date", value=pd.to_datetime(er["Date"]), key=f"e_date_{orig_idx}")
                        e_size = st.number_input("📐 Rotor Size (mm)", min_value=1, value=int(er["Size (mm)"]), key=f"e_size_{orig_idx}")
                    with ec2:
                        e_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"], index=0 if er["Type"] == "Inward" else 1, key=f"e_type_{orig_idx}")
                        e_qty = st.number_input("🔢 Quantity", min_value=1, value=int(er["Quantity"]), key=f"e_qty_{orig_idx}")
                    e_remarks = st.text_input("📝 Remarks", value=er["Remarks"], key=f"e_remark_{orig_idx}")
                    e_status = st.selectbox("📂 Status", ["Current", "Future"], index=0 if er["Status"] == "Current" else 1, key=f"e_status_{orig_idx}")
                    e_pending = st.checkbox("❗ Pending", value=er["Pending"], key=f"e_pending_{orig_idx}")

                    save_col, cancel_col = st.columns(2)
                    with save_col:
                        submit = st.form_submit_button("💾 Save Changes", type="primary")
                    with cancel_col:
                        cancel = st.form_submit_button("❌ Cancel")

                    if submit:
                        for col, val in [
                            ("Date", e_date.strftime("%Y-%m-%d")),
                            ("Size (mm)", e_size),
                            ("Type", e_type),
                            ("Quantity", e_qty),
                            ("Remarks", e_remarks),
                            ("Status", e_status),
                            ("Pending", e_pending)
                        ]:
                            st.session_state.data.at[orig_idx, col] = val
                        st.session_state.editing = None
                        auto_save_to_gsheet()
                        st.rerun()

                    if cancel:
                        st.session_state.editing = None
                        st.rerun()

# ====== LAST SYNC STATUS ======
if st.session_state.last_sync != "Never":
    st.caption(f"Last synced: {st.session_state.last_sync}")
