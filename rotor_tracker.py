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

# JavaScript to detect browser/tab close
close_warning_js = """
<script>
window.addEventListener('beforeunload', function(e) {
    if(%s) {
        e.preventDefault();
        e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
    }
});
</script>
""" % ("true" if st.session_state.get("unsaved_changes", False) else "false")

# Inject the JavaScript
st.components.v1.html(close_warning_js, height=0)

# UI Setup
st.set_page_config(page_title="Rotor Inventory", page_icon="🔄", layout="wide")
st.title("🔄 Rotor Inventory Management System")

# Track changes function
def track_changes():
    st.session_state.unsaved_changes = True

# Sync status and buttons
sync_col, status_col = st.columns([1, 3])
with sync_col:
    sync_btn = st.button("🔄 Sync Now", help="Load latest data from Google Sheets")
    if sync_btn:
        load_from_gsheet()
    
    save_btn = st.button("💾 Save to Google Sheets", help="Save current data to Google Sheets")
    if save_btn:
        if save_to_gsheet(st.session_state.data):
            st.success("Data saved successfully to Google Sheets!")

with status_col:
    if st.session_state.sync_status == "loading":
        st.info("Syncing data from Google Sheets...")
    elif st.session_state.last_sync != "Never":
        st.caption(f"Last synced: {st.session_state.last_sync}")
    else:
        st.caption("Never synced")
    
    if st.session_state.unsaved_changes:
        st.warning("You have unsaved changes!")
    
    if st.session_state.sync_status == "error":
        st.error("Sync failed. Please check connection and try again.")

# Entry forms with proper change tracking
form_tabs = st.tabs(["Current Movement", "Coming Rotors", "Pending Outgoing"])

with form_tabs[0]:  # Current Movement
    with st.form("current_form"):
        st.subheader("➕ Add Current Movement")
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Date", value=datetime.today())
            rotor_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, format="%d")
        with col2:
            entry_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"])
            quantity = st.number_input("🔢 Quantity", min_value=1, step=1, format="%d")
        remarks = st.text_input("📝 Remarks")
        
        submitted = st.form_submit_button("➕ Add Entry", use_container_width=True)
        if submitted:
            track_changes()
            new_entry = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'),
                'Size (mm)': rotor_size, 
                'Type': entry_type, 
                'Quantity': quantity, 
                'Remarks': remarks,
                'Status': 'Current'
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            if auto_save_to_gsheet():
                st.success("Entry added and saved!")
            st.rerun()

with form_tabs[1]:  # Coming Rotors
    with st.form("future_form"):
        st.subheader("➕ Add Coming Rotors")
        col1, col2 = st.columns(2)
        with col1:
            future_date = st.date_input("📅 Expected Date", min_value=datetime.today() + timedelta(days=1))
            future_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, format="%d")
        with col2:
            future_qty = st.number_input("🔢 Quantity", min_value=1, step=1, format="%d")
            future_remarks = st.text_input("📝 Remarks")
        
        submitted = st.form_submit_button("➕ Add Coming Rotors", use_container_width=True)
        if submitted:
            track_changes()
            new_entry = pd.DataFrame([{
                'Date': future_date.strftime('%Y-%m-%d'),
                'Size (mm)': future_size, 
                'Type': 'Inward', 
                'Quantity': future_qty, 
                'Remarks': future_remarks,
                'Status': 'Future'
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            if auto_save_to_gsheet():
                st.success("Entry added and saved!")
            st.rerun()

with form_tabs[2]:  # Pending Outgoing
    with st.form("pending_form"):
        st.subheader("➕ Add Pending Outgoing")
        col1, col2 = st.columns(2)
        with col1:
            pending_date = st.date_input("📅 Expected Ship Date", value=datetime.today())
            pending_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, format="%d", key="pending_size")
        with col2:
            pending_qty = st.number_input("🔢 Quantity", min_value=1, step=1, format="%d", key="pending_qty")
            pending_remarks = st.text_input("📝 Remarks", key="pending_remarks")
        
        submitted = st.form_submit_button("➕ Add Pending Outgoing", use_container_width=True)
        if submitted:
            track_changes()
            new_entry = pd.DataFrame([{
                'Date': pending_date.strftime('%Y-%m-%d'),
                'Size (mm)': pending_size, 
                'Type': 'Outgoing', 
                'Quantity': pending_qty, 
                'Remarks': f"[PENDING] {pending_remarks}",
                'Status': 'Pending'
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            if auto_save_to_gsheet():
                st.success("Entry added and saved!")
            st.rerun()

# [Rest of your existing code for Stock Summary and Movement Log...]

# Sidebar with save reminder
with st.sidebar:
    st.subheader("System Controls")
    if st.button("🔄 Reset Session Data"):
        st.session_state.data = pd.DataFrame(columns=[
            'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status'
        ])
        st.session_state.last_sync = "Never"
        st.session_state.editing_index = None
        st.rerun()
    
    st.divider()
    st.caption("*Data Safety Notice:*")
    
    if st.session_state.unsaved_changes:
        st.error("⚠ You have unsaved changes!")
        st.caption("Please save to Google Sheets before closing the app.")
    else:
        st.success("✓ All changes saved")
    
    st.caption(f"Entries in system: *{len(st.session_state.data)}*")
