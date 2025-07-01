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
form_tabs = st.tabs(["Current Movement", "Coming Rotors"])

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
            status = 'Pending' if entry_type == 'Outgoing' else 'Current'
            new_entry = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'),
                'Size (mm)': rotor_size, 
                'Type': entry_type, 
                'Quantity': quantity, 
                'Remarks': remarks,
                'Status': status
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

# Stock Summary
st.subheader("📊 Current Stock Summary")
if not st.session_state.data.empty:
    try:
        # Current stock (inward)
        current_inward = st.session_state.data[
            (st.session_state.data['Status'] == 'Current') & 
            (st.session_state.data['Type'] == 'Inward')
        ]
        inward_stock = current_inward.groupby('Size (mm)')['Quantity'].sum().reset_index()
        
        # Pending outgoing
        pending_outgoing = st.session_state.data[
            (st.session_state.data['Status'] == 'Pending') & 
            (st.session_state.data['Type'] == 'Outgoing')
        ]
        pending = pending_outgoing.groupby('Size (mm)')['Quantity'].sum().reset_index()
        
        # Coming rotors
        future = st.session_state.data[st.session_state.data['Status'] == 'Future']
        coming = future.groupby('Size (mm)')['Quantity'].sum().reset_index()
        
        # Combine all data
        combined = pd.merge(inward_stock, pending, on='Size (mm)', how='outer', suffixes=('_inward', '_pending'))
        combined = pd.merge(combined, coming, on='Size (mm)', how='outer')
        combined = combined.fillna(0)
        
        # Calculate available stock
        combined['Current Stock'] = combined['Quantity_inward'] - combined['Quantity_pending']
        combined['Pending Outgoing'] = combined['Quantity_pending']
        combined['Coming Rotors'] = combined['Quantity']
        
        # Display
        st.dataframe(
            combined[['Size (mm)', 'Current Stock', 'Pending Outgoing', 'Coming Rotors']],
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
                        st.session_state.edit_form_data = row.to_dict()
                
                # Delete button
                with cols[2]:
                    if st.button("❌", key=f"del_{idx}"):
                        st.session_state.data = st.session_state.data.drop(idx)
                        auto_save_to_gsheet()
                        st.rerun()
                
                # Edit form
                if st.session_state.editing_index == idx:
                    with st.form(key=f"edit_form_{idx}"):
                        edited_data = st.session_state.edit_form_data.copy()
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            edited_data['Date'] = st.date_input(
                                "Date",
                                value=datetime.strptime(edited_data['Date'], '%Y-%m-%d')
                            ).strftime('%Y-%m-%d')
                            edited_data['Size (mm)'] = st.number_input(
                                "Size (mm)",
                                value=edited_data['Size (mm)'],
                                min_value=1
                            )
                        with col2:
                            edited_data['Type'] = st.selectbox(
                                "Type",
                                ["Inward", "Outgoing"],
                                index=0 if edited_data['Type'] == 'Inward' else 1
                            )
                            edited_data['Quantity'] = st.number_input(
                                "Quantity",
                                value=edited_data['Quantity'],
                                min_value=1
                            )
                        
                        edited_data['Remarks'] = st.text_input(
                            "Remarks",
                            value=edited_data['Remarks']
                        )
                        edited_data['Status'] = st.selectbox(
                            "Status",
                            ["Current", "Pending", "Future"],
                            index=["Current", "Pending", "Future"].index(edited_data['Status'])
                        )
                        
                        if st.form_submit_button("💾 Save Changes"):
                            st.session_state.data.loc[idx] = edited_data
                            auto_save_to_gsheet()
                            st.session_state.editing_index = None
                            st.rerun()
                        
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
