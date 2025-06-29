import streamlit as st
import pandas as pd
from datetime import datetime

# Initialize data
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=['Date', 'Type', 'Quantity (mm)', 'Remarks'])

st.title("🔧 Rotor Inward & Outgoing Tracker")

# Data Entry Form
with st.form("entry_form"):
    col1, col2 = st.columns(2)
    with col1:
        date = st.date_input("📅 Date", value=datetime.today())
    with col2:
        entry_type = st.selectbox("🔁 Type", ["Inward", "Outgoing"])
    quantity = st.number_input("📏 Quantity (in mm)", min_value=1, step=1)
    remarks = st.text_input("📝 Remarks")
    submitted = st.form_submit_button("➕ Add Entry")

    if submitted:
        new_entry = pd.DataFrame([[date, entry_type, quantity, remarks]],
                                 columns=['Date', 'Type', 'Quantity (mm)', 'Remarks'])
        st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
        st.success("✅ Entry added successfully!")

# Show the log
st.subheader("📋 Transaction Log")
st.dataframe(st.session_state.data, use_container_width=True)

# Summary Metrics
st.subheader("📊 Stock Summary")
inward_total = st.session_state.data.query("Type == 'Inward'")['Quantity (mm)'].sum()
outgoing_total = st.session_state.data.query("Type == 'Outgoing'")['Quantity (mm)'].sum()
current_stock = inward_total - outgoing_total

st.metric("Total Inward", f"{inward_total} mm")
st.metric("Total Outgoing", f"{outgoing_total} mm")
st.metric("Current Stock", f"{current_stock} mm")

# Download data
csv = st.session_state.data.to_csv(index=False).encode('utf-8')
st.download_button("📥 Download CSV", csv, "rotor_data.csv", "text/csv")
