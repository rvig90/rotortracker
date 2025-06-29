import streamlit as st
import pandas as pd
from datetime import datetime

# Initialize session data
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks'
    ])

st.set_page_config(page_title="Submersible Rotor Tracker", layout="centered")
st.title("🔧 Submersible Pump Rotor Tracker")

# --- Entry Form ---
with st.form("entry_form"):
    col1, col2 = st.columns(2)
    with col1:
        date = st.date_input("📅 Date", value=datetime.today())
        rotor_size = st.number_input("📐 Rotor Size (in mm)", min_value=1)
    with col2:
        entry_type = st.selectbox("🔄 Entry Type", ["Inward", "Outgoing"])
        quantity = st.number_input("🔢 Quantity (number of rotors)", min_value=1, step=1)
    remarks = st.text_input("📝 Remarks")

    submitted = st.form_submit_button("➕ Add Entry")
    if submitted:
        new_entry = pd.DataFrame([{
            'Date': date,
            'Size (mm)': rotor_size,
            'Type': entry_type,
            'Quantity': quantity,
            'Remarks': remarks
        }])
        st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
        st.success("✅ Entry logged!")

# --- Rotor Log Table ---
st.subheader("📋 Rotor Movement Log")
st.dataframe(st.session_state.data, use_container_width=True)

# --- Summary by Size ---
st.subheader("📊 Current Stock by Size (mm)")

if not st.session_state.data.empty:
    summary = st.session_state.data.copy()
    summary['Quantity'] = summary.apply(
        lambda row: row['Quantity'] if row['Type'] == 'Inward' else -row['Quantity'], axis=1
    )
    stock_summary = summary.groupby('Size (mm)')['Quantity'].sum().reset_index()
    stock_summary = stock_summary[stock_summary['Quantity'] != 0]
    st.dataframe(stock_summary, use_container_width=True)
else:
    st.info("No data available yet.")

# --- CSV Download ---

from io import BytesIO

# --- Excel & CSV Export ---
st.subheader("📤 Export Data")

# Export to CSV
csv = st.session_state.data.to_csv(index=False).encode('utf-8')
st.download_button("📥 Download CSV", csv, "submersible_rotor_log.csv", "text/csv")

# Export to Excel
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Rotor Data')
    return output.getvalue()

excel_data = to_excel(st.session_state.data)
st.download_button(
    label="📊 Download Excel",
    data=excel_data,
    file_name="submersible_rotor_log.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
