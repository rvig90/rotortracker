
import streamlit as st
import pandas as pd
from datetime import datetime
import os

# File path for persistent storage
DATA_FILE = "rotor_stock_log.xlsx"

# Initialize or load data
def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_excel(DATA_FILE)
    else:
        return pd.DataFrame(columns=[
            'Date', 'Size (mm)', 'Inward Qty', 'Outward Qty', 'Balance Qty', 'Remarks'
        ])

def save_data(df):
    df.to_excel(DATA_FILE, index=False)

st.title("🔧 Submersible Pump Rotor Stock Tracker with Auto Save")

data = load_data()

# --- Data Entry ---
st.header("Add New Entry")
date = st.date_input("Date", datetime.today())
size = st.text_input("Rotor Size (mm)")
inward = st.number_input("Inward Quantity", min_value=0, value=0, step=1)
outward = st.number_input("Outward Quantity", min_value=0, value=0, step=1)
remarks = st.text_input("Remarks")

if st.button("Add Entry"):
    new_row = pd.DataFrame({
        'Date': [date],
        'Size (mm)': [size],
        'Inward Qty': [inward],
        'Outward Qty': [outward],
        'Balance Qty': [0],  # Will recalculate below
        'Remarks': [remarks]
    })
    data = pd.concat([data, new_row], ignore_index=True)

    # Recalculate Balance Qty per size
    data['Balance Qty'] = data.groupby('Size (mm)')['Inward Qty'].cumsum() - data.groupby('Size (mm)')['Outward Qty'].cumsum()

    save_data(data)
    st.success("Entry added and saved to Excel.")

# --- Display Table ---
st.header("📊 Transaction Log")
if len(data) > 0:
    st.dataframe(data.sort_values(by='Date'))
    # Download option
    csv = data.to_csv(index=False).encode('utf-8')
    st.download_button("Download as CSV", csv, "rotor_stock.csv", "text/csv")
else:
    st.info("No data yet. Add an entry to get started.")

# --- Filters (Optional) ---
st.sidebar.header("Filter Data")
size_filter = st.sidebar.text_input("Filter by Size (mm)")
date_filter = st.sidebar.date_input("Filter by Date Range", [])

filtered = data

if size_filter:
    filtered = filtered[filtered['Size (mm)'] == size_filter]

if isinstance(date_filter, list) and len(date_filter) == 2:
    start_date, end_date = date_filter
    filtered = filtered[(filtered['Date'] >= pd.to_datetime(start_date)) & (filtered['Date'] <= pd.to_datetime(end_date))]

st.sidebar.write(f"Filtered Entries: {len(filtered)}")
st.sidebar.dataframe(filtered)
