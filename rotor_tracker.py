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
    st.session_state.edit_form_data = None
    st.session_state.log_expanded = True

# Google Sheets integration (keep existing implementation)
# [Previous get_gsheet_connection(), load_from_gsheet(), auto_save_to_gsheet() functions here]

# Sync button
if st.button("🔄 Sync Now", help="Load latest data from Google Sheets"):
    load_from_gsheet()

# Entry forms - UPDATED TO SHOW PENDING FORM
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
                'Status': 'Current'
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

with form_tabs[2]:  # Pending Outgoing (NEW FORM)
    with st.form("pending_form"):
        st.write("### Add Pending Outgoing Rotors")
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
                'Status': 'Current'
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            auto_save_to_gsheet()
            st.rerun()

# Enhanced Stock Summary with Pending Column
st.subheader("📊 Current Stock Summary")
if not st.session_state.data.empty:
    try:
        # Current stock
        current = st.session_state.data[st.session_state.data['Status'] == 'Current'].copy()
        current['Net'] = current.apply(lambda x: x['Quantity'] if x['Type'] == 'Inward' else -x['Quantity'], axis=1)
        stock = current.groupby('Size (mm)')['Net'].sum().reset_index()
        stock = stock[stock['Net'] != 0]
        
        # Coming rotors
        future = st.session_state.data[st.session_state.data['Status'] == 'Future']
        coming = future.groupby('Size (mm)')['Quantity'].sum().reset_index()
        
        # Pending outgoing (Current + Outgoing)
        pending = current[current['Type'] == 'Outgoing']
        pending = pending.groupby('Size (mm)')['Quantity'].sum().reset_index()
        
        # Combined view
        combined = pd.merge(stock, coming, on='Size (mm)', how='outer').fillna(0)
        combined = pd.merge(combined, pending, on='Size (mm)', how='outer').fillna(0)
        combined.columns = ['Size (mm)', 'Current Stock', 'Coming Rotors', 'Pending Outgoing']
        
        # Calculate available stock
        combined['Available Stock'] = combined['Current Stock'] - combined['Pending Outgoing']
        
        # Display with all columns
        st.dataframe(
            combined[['Size (mm)', 'Current Stock', 'Pending Outgoing', 'Available Stock', 'Coming Rotors']],
            use_container_width=True,
            hide_index=True
        )
        
    except Exception as e:
        st.error(f"Error generating summary: {e}")
else:
    st.info("No data available yet")

# [Rest of your existing movement log code remains unchanged]
