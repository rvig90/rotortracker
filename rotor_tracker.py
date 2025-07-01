import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import time

# Initialize session state
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status'
    ])
    st.session_state.last_sync = "Never"
    st.session_state.editing_index = None
    st.session_state.log_expanded = True
    st.session_state.sync_status = "idle"
    st.session_state.delete_trigger = None
    st.session_state.unsaved_changes = False

# [Previous Google Sheets functions remain the same...]

# UI Setup
st.set_page_config(page_title="Rotor Inventory", page_icon="🔄", layout="wide")
st.title("🔄 Rotor Inventory Management System")

# [Previous sync controls and form sections remain the same...]

# Movement Log - Fixed Implementation
st.subheader("📋 Movement Log")
with st.expander("View/Edit Entries", expanded=st.session_state.log_expanded):
    if not st.session_state.data.empty:
        try:
            # Display all entries sorted by date (newest first)
            sorted_df = st.session_state.data.sort_values('Date', ascending=False)
            
            # Add search functionality
            search_query = st.text_input("🔍 Search entries", 
                                       placeholder="Search by size, type, remarks...",
                                       key="log_search")
            
            if search_query:
                search_df = sorted_df[
                    sorted_df['Size (mm)'].astype(str).str.contains(search_query) |
                    sorted_df['Type'].str.contains(search_query, case=False) |
                    sorted_df['Remarks'].str.contains(search_query, case=False) |
                    sorted_df['Status'].str.contains(search_query, case=False)
                ]
            else:
                search_df = sorted_df
            
            if not search_df.empty:
                # Display each entry with edit/delete options
                for idx, row in search_df.iterrows():
                    # Create a card-like container for each entry
                    with st.container():
                        cols = st.columns([0.5, 1, 1, 1, 2, 1, 0.5, 0.5])
                        
                        # Display entry data
                        with cols[0]:
                            st.markdown(f"{idx+1}")
                        with cols[1]:
                            st.markdown(f"{row['Date']}")
                        with cols[2]:
                            st.markdown(f"{row['Size (mm)']} mm")
                        with cols[3]:
                            st.markdown(f"{row['Type']}")
                        with cols[4]:
                            st.markdown(f"{row['Quantity']} units")
                        with cols[5]:
                            st.markdown(f"{row['Status']}")
                        
                        # Edit button
                        with cols[6]:
                            if st.button("✏", key=f"edit_{idx}"):
                                st.session_state.editing_index = idx
                        
                        # Delete button
                        with cols[7]:
                            if st.button("❌", key=f"del_{idx}"):
                                st.session_state.delete_trigger = idx
                                st.session_state.unsaved_changes = True
                        
                        # Edit form (appears when edit button is clicked)
                        if st.session_state.editing_index == idx:
                            with st.form(key=f"edit_form_{idx}"):
                                st.subheader("Edit Entry")
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    new_date = st.date_input(
                                        "Date",
                                        value=datetime.strptime(row['Date'], '%Y-%m-%d').date()
                                    )
                                    new_size = st.number_input(
                                        "Size (mm)",
                                        value=row['Size (mm)'],
                                        min_value=1
                                    )
                                with col2:
                                    new_type = st.selectbox(
                                        "Type",
                                        ["Inward", "Outgoing"],
                                        index=0 if row['Type'] == 'Inward' else 1
                                    )
                                    new_qty = st.number_input(
                                        "Quantity",
                                        value=row['Quantity'],
                                        min_value=1
                                    )
                                
                                new_remarks = st.text_input("Remarks", value=row['Remarks'])
                                new_status = st.selectbox(
                                    "Status",
                                    ["Current", "Pending", "Future"],
                                    index=["Current", "Pending", "Future"].index(row['Status'])
                                )
                                
                                save_col, cancel_col = st.columns(2)
                                with save_col:
                                    if st.form_submit_button("💾 Save Changes"):
                                        st.session_state.data.at[idx, 'Date'] = new_date.strftime('%Y-%m-%d')
                                        st.session_state.data.at[idx, 'Size (mm)'] = new_size
                                        st.session_state.data.at[idx, 'Type'] = new_type
                                        st.session_state.data.at[idx, 'Quantity'] = new_qty
                                        st.session_state.data.at[idx, 'Remarks'] = new_remarks
                                        st.session_state.data.at[idx, 'Status'] = new_status
                                        if auto_save_to_gsheet():
                                            st.success("Changes saved!")
                                        st.session_state.editing_index = None
                                        st.rerun()
                                with cancel_col:
                                    if st.form_submit_button("❌ Cancel"):
                                        st.session_state.editing_index = None
                                        st.rerun()
                        
                        st.markdown("---")  # Divider between entries
                
                # Handle deletion after button press
                if st.session_state.get('delete_trigger') is not None:
                    idx_to_delete = st.session_state.delete_trigger
                    st.session_state.data = st.session_state.data.drop(idx_to_delete)
                    st.session_state.data = st.session_state.data.reset_index(drop=True)
                    if auto_save_to_gsheet():
                        st.success("Entry deleted successfully!")
                    st.session_state.delete_trigger = None
                    st.rerun()
            else:
                st.info("No entries match your search")
        except Exception as e:
            st.error(f"Error displaying movement log: {str(e)}")
    else:
        st.info("No entries to display")

# [Rest of your code remains the same...]
