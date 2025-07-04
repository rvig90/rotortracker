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
    # Auto-load data when first opened
    load_from_gsheet()

# ====== HELPER FUNCTIONS ======
def normalize_pending_column(df):
    df['Pending'] = df['Pending'].apply(
        lambda x: str(x).lower() == 'true' if isinstance(x, str) else bool(x)
    )
    return df

def convert_to_date(date_str):
    try:
        return pd.to_datetime(date_str).date()
    except:
        return pd.to_datetime(date_str)

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
                
                # Ensure Date column is in proper format
                df['Date'] = pd.to_datetime(df['Date']).dt.date
                
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
            sheet.clear()

            if not st.session_state.data.empty:
                df = st.session_state.data.copy()
                df['Pending'] = df['Pending'].apply(lambda x: "TRUE" if x else "FALSE")
                expected_cols = ['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending']
                for col in expected_cols:
                    if col not in df.columns:
                        df[col] = ""
                
                # Convert date back to string for Google Sheets
                df['Date'] = df['Date'].astype(str)
                
                df = df[expected_cols]
                records = [df.columns.tolist()] + df.values.tolist()
                sheet.update(records)
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"❌ Auto-save failed: {e}")

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
                'Date': date,
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
                'Date': future_date,
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
                'Date': pending_date,
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
st.subheader("📊 Current Stock Summary")
if not st.session_state.data.empty:
    try:
        st.session_state.data = normalize_pending_column(st.session_state.data)
        current = st.session_state.data[
            (st.session_state.data['Status'] == 'Current') & 
            (~st.session_state.data['Pending'])
        ].copy()
        current['Net'] = current.apply(lambda x: x['Quantity'] if x['Type'] == 'Inward' else -x['Quantity'], axis=1)
        stock = current.groupby('Size (mm)')['Net'].sum().reset_index()
        stock = stock[stock['Net'] != 0]

        future = st.session_state.data[st.session_state.data['Status'] == 'Future']
        coming = future.groupby('Size (mm)')['Quantity'].sum().reset_index()

        pending = st.session_state.data[
            (st.session_state.data['Status'] == 'Current') & 
            (st.session_state.data['Pending'])
        ]
        pending_rotors = pending.groupby('Size (mm)')['Quantity'].sum().reset_index()

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

# ====== MOVEMENT LOG WITH INLINE EDITING ======
with st.expander("📋 View Movement Log", expanded=True):
    if not st.session_state.data.empty:
        try:
            df = st.session_state.data.copy()

            st.markdown("### 🔍 Filter Movement Log")
            col1, col2, col3 = st.columns(3)

            with col1:
                status_filter = st.selectbox("📂 Status", ["All", "Current", "Future"])
            with col2:
                size_filter = st.multiselect("📐 Size (mm)", options=sorted(df['Size (mm)'].unique()))
            with col3:
                pending_filter = st.selectbox("❗ Pending", ["All", "Yes", "No"])

            remark_search = st.text_input("📝 Search Remarks")
            
            # Date range filter with proper date handling
            min_date = df['Date'].min()
            max_date = df['Date'].max()
            date_range = st.date_input(
                "📅 Date Range",
                value=[min_date, max_date],
                min_value=min_date,
                max_value=max_date
            )

            # Apply filters
            if status_filter != "All":
                df = df[df["Status"] == status_filter]
            if pending_filter == "Yes":
                df = df[df["Pending"] == True]
            elif pending_filter == "No":
                df = df[df["Pending"] == False]
            if size_filter:
                df = df[df["Size (mm)"].isin(size_filter)]
            if remark_search:
                df = df[df["Remarks"].str.contains(remark_search, case=False, na=False)]
            if len(date_range) == 2:
                start_date, end_date = date_range
                df = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]

            # Display editable table
            st.markdown("### 📄 Filtered Entries")
            
            # Convert date to string for display and editing
            display_df = df.copy()
            display_df['Date'] = display_df['Date'].astype(str)
            
            # Create editable dataframe
            edited_df = st.data_editor(
                display_df,
                key="movement_log_editor",
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Date": st.column_config.DateColumn("Date"),
                    "Size (mm)": st.column_config.NumberColumn("Size (mm)", format="%d"),
                    "Quantity": st.column_config.NumberColumn("Quantity", format="%d"),
                    "Pending": st.column_config.CheckboxColumn("Pending")
                },
                disabled=["Status"]  # Make Status non-editable
            )
            
            # Check for changes and update session state
            if not edited_df.equals(display_df):
                # Convert date back to date object
                edited_df['Date'] = pd.to_datetime(edited_df['Date']).dt.date
                
                # Update the original dataframe with changes
                for idx, row in edited_df.iterrows():
                    original_idx = df.index[idx]
                    st.session_state.data.loc[original_idx] = row
                
                auto_save_to_gsheet()
                st.rerun()

        except Exception as e:
            st.error(f"❌ Error showing movement log: {e}")
    else:
        st.info("No entries to show yet.")

# ====== LAST SYNC STATUS ======
if st.session_state.last_sync != "Never":
    st.caption(f"Last synced: {st.session_state.last_sync}")
