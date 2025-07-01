import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# Initialize session state
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status'
    ])
    st.session_state.last_sync = "Never"
    st.session_state.editing_index = None
    st.session_state.log_expanded = True

# Google Sheets integration
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

# Sync button
if st.button("🔄 Sync Now", help="Load latest data from Google Sheets"):
    load_from_gsheet()

# Entry forms
form_tabs = st.tabs(["Current Movement", "Coming Rotors", "Pending Outgoing"])

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
                'Status': 'Current'  # All current movements are 'Current' status
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
                'Status': 'Future'
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

with form_tabs[2]:  # Pending Outgoing
    with st.form("pending_form"):
        col1, col2 = st.columns(2)
        with col1:
            pending_date = st.date_input("📅 Expected Ship Date", value=datetime.today())
            pending_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, format="%d", key="pending_size")
        with col2:
            pending_qty = st.number_input("🔢 Quantity", min_value=1, step=1, format="%d", key="pending_qty")
            pending_remarks = st.text_input("📝 Remarks", key="pending_remarks")
        
        if st.form_submit_button("➕ Add Pending Outgoing"):
            new_entry = pd.DataFrame([{
                'Date': pending_date.strftime('%Y-%m-%d'),
                'Size (mm)': pending_size, 
                'Type': 'Outgoing', 
                'Quantity': pending_qty, 
                'Remarks': f"[PENDING] {pending_remarks}",
                'Status': 'Pending'  # Special status for pending shipments
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

# Stock Summary
st.subheader("📊 Current Stock Summary")
if not st.session_state.data.empty:
    try:
        # Current inward stock
        current_inward = st.session_state.data[
            (st.session_state.data['Status'] == 'Current') & 
            (st.session_state.data['Type'] == 'Inward')
        ]
        inward_stock = current_inward.groupby('Size (mm)')['Quantity'].sum().reset_index()
        
        # Current outgoing (immediate deductions)
        current_outgoing = st.session_state.data[
            (st.session_state.data['Status'] == 'Current') & 
            (st.session_state.data['Type'] == 'Outgoing')
        ]
        outgoing = current_outgoing.groupby('Size (mm)')['Quantity'].sum().reset_index()
        
        # Pending outgoing (future deductions)
        pending_outgoing = st.session_state.data[
            (st.session_state.data['Status'] == 'Pending') & 
            (st.session_state.data['Type'] == 'Outgoing')
        ]
        pending = pending_outgoing.groupby('Size (mm)')['Quantity'].sum().reset_index()
        
        # Coming rotors
        future = st.session_state.data[st.session_state.data['Status'] == 'Future']
        coming = future.groupby('Size (mm)')['Quantity'].sum().reset_index()
        
        # Combine all data
        combined = pd.merge(inward_stock, outgoing, on='Size (mm)', how='outer', suffixes=('_inward', '_outgoing'))
        combined = pd.merge(combined, pending, on='Size (mm)', how='outer')
        combined = pd.merge(combined, coming, on='Size (mm)', how='outer')
        combined = combined.fillna(0)
        
        # Calculate stock levels
        combined['Current Stock'] = combined['Quantity_inward'] - combined['Quantity_outgoing']
        combined['Current Outgoing'] = combined['Quantity_outgoing']
        combined['Pending Outgoing'] = combined['Quantity']
        combined['Coming Rotors'] = combined['Quantity_y']
        
        # Display
        st.dataframe(
            combined[['Size (mm)', 'Current Stock', 'Current Outgoing', 'Pending Outgoing', 'Coming Rotors']],
            use_container_width=True,
            hide_index=True
        )
        
    except Exception as e:
        st.error(f"Error generating summary: {e}")
else:
    st.info("No data available yet")

# Movement Log with working edit
with st.expander("📋 View Movement Log", expanded=True):
    if not st.session_state.data.empty:
        try:
            for idx, row in st.session_state.data.sort_values('Date', ascending=False).iterrows():
                st.markdown("---")
                
                # Display entry
                cols = st.columns([8, 1, 1])
                with cols[0]:
                    st.dataframe(
                        pd.DataFrame(row).T,
                        use_container_width=True,
                        hide_index=True
                    )
                
                # Edit button
                with cols[1]:
                    if st.button("✏", key=f"edit_{idx}"):
                        st.session_state.editing_index = idx
                
                # Delete button
                with cols[2]:
                    if st.button("❌", key=f"del_{idx}"):
                        st.session_state.data = st.session_state.data.drop(idx)
                        auto_save_to_gsheet()
                        st.rerun()
                
                # Edit form
                if st.session_state.editing_index == idx:
                    with st.form(key=f"edit_form_{idx}"):
                        # Get current values
                        current_date = datetime.strptime(row['Date'], '%Y-%m-%d').date()
                        current_size = row['Size (mm)']
                        current_type = row['Type']
                        current_qty = row['Quantity']
                        current_remarks = row['Remarks']
                        current_status = row['Status']
                        
                        # Create editable fields
                        col1, col2 = st.columns(2)
                        with col1:
                            new_date = st.date_input("Date", value=current_date)
                            new_size = st.number_input("Size (mm)", value=current_size, min_value=1)
                        with col2:
                            new_type = st.selectbox(
                                "Type",
                                ["Inward", "Outgoing"],
                                index=0 if current_type == 'Inward' else 1
                            )
                            new_qty = st.number_input("Quantity", value=current_qty, min_value=1)
                        
                        new_remarks = st.text_input("Remarks", value=current_remarks)
                        new_status = st.selectbox(
                            "Status",
                            ["Current", "Pending", "Future"],
                            index=["Current", "Pending", "Future"].index(current_status)
                        )
                        
                        # Form buttons
                        save_col, cancel_col = st.columns(2)
                        with save_col:
                            if st.form_submit_button("💾 Save Changes"):
                                st.session_state.data.at[idx, 'Date'] = new_date.strftime('%Y-%m-%d')
                                st.session_state.data.at[idx, 'Size (mm)'] = new_size
                                st.session_state.data.at[idx, 'Type'] = new_type
                                st.session_state.data.at[idx, 'Quantity'] = new_qty
                                st.session_state.data.at[idx, 'Remarks'] = new_remarks
                                st.session_state.data.at[idx, 'Status'] = new_status
                                auto_save_to_gsheet()
                                st.session_state.editing_index = None
                                st.rerun()
                        with cancel_col:
                            if st.form_submit_button("❌ Cancel"):
                                st.session_state.editing_index = None
                                st.rerun()
                
            st.markdown("---")
        except Exception as e:
            st.error(f"Error displaying log: {e}")
    else:
        st.info("No entries to display")

# Status footer
if st.session_state.last_sync != "Never":
    st.caption(f"Last synced: {st.session_state.last_sync}")
