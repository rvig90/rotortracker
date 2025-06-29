import streamlit as st
import pandas as pd
from datetime import datetime

# Initialize data on first load
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=['Date', 'Quantity (mm)', 'Remarks'])

st.set_page_config(page_title="Rotor Tracker", layout="centered")
st.title("🔧 Rotor Stock Tracker")

# --- Data Entry Form ---
with st.form("entry_form"):
    col1, col2 = st.columns(2)
    with col1:
        date = st.date_input("📅 Date", value=datetime.today())
    with col2:
        quantity = st.number_input("📏 Quantity (in mm)", min_value=1, step=1)
    remarks = st.text_input("📝 Remarks")

    submitted = st.form_submit_button("➕ Add Entry")
    if submitted:
        new_entry = pd.DataFrame([[date, quantity, remarks]],
                                 columns=['Date', 'Quantity (mm)', 'Remarks'])
        st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
        st.success("✅ Entry added successfully!")

# --- Display Table ---
st.subheader("📋 Rotor Log")
st.dataframe(st.session_state.data, use_container_width=True)

# --- Summary Section ---
st.subheader("📊 Stock Summary")
total_quantity = st.session_state.data['Quantity (mm)'].sum()
st.metric("Total Stock", f"{total_quantity} mm")

# --- Download Section ---
csv = st.session_state.data.to_csv(index=False).encode('utf-8')
st.download_button("📥 Download as CSV", csv, "rotor_data.csv", "text/csv")
