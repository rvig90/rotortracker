Python 3.13.5 (tags/v3.13.5:6cb20a2, Jun 11 2025, 16:15:46) [MSC v.1943 64 bit (AMD64)] on win32
Enter "help" below or click "Help" above for more information.
import streamlit as st
import pandas as pd
from datetime import datetime

# Load or initialize data
if 'data' not in st.session_state:
    st.session_state['data'] = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Inward Qty', 'Outward Qty', 'Balance Qty', 'Remarks'
    ])

st.title("🔧 Submersible Pump Rotor Stock Tracker")

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
    st.session_state['data'] = pd.concat([st.session_state['data'], new_row], ignore_index=True)
... 
...     # Recalculate Balance Qty per size
...     df = st.session_state['data']
...     df['Balance Qty'] = df.groupby('Size (mm)')['Inward Qty'].cumsum() - df.groupby('Size (mm)')['Outward Qty'].cumsum()
...     st.session_state['data'] = df
... 
...     st.success("Entry added!")
... 
... # --- Display Table ---
... st.header("📊 Transaction Log")
... if len(st.session_state['data']) > 0:
...     st.dataframe(st.session_state['data'].sort_values(by='Date'))
... 
...     # Download option
...     csv = st.session_state['data'].to_csv(index=False).encode('utf-8')
...     st.download_button("Download as CSV", csv, "rotor_stock.csv", "text/csv")
... else:
...     st.info("No data yet. Add an entry to get started.")
... 
... # --- Filters (Optional) ---
... st.sidebar.header("Filter Data")
... size_filter = st.sidebar.text_input("Filter by Size (mm)")
... date_filter = st.sidebar.date_input("Filter by Date", [])
... 
... filtered = st.session_state['data']
... 
... if size_filter:
...     filtered = filtered[filtered['Size (mm)'] == size_filter]
... 
... if isinstance(date_filter, list) and len(date_filter) == 2:
...     start_date, end_date = date_filter
...     filtered = filtered[(filtered['Date'] >= pd.to_datetime(start_date)) & (filtered['Date'] <= pd.to_datetime(end_date))]
... 
... st.sidebar.write(f"Filtered Entries: {len(filtered)}")
... st.sidebar.dataframe(filtered)
... 
