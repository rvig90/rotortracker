import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# ====== INITIALIZE DATA WITH STATUS COLUMN ======
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status'
    ])
    # Initialize with default 'Current' status if migrating old data
    if not st.session_state.data.empty and 'Status' not in st.session_state.data.columns:
        st.session_state.data['Status'] = 'Current'

# ====== ENTRY FORMS ======
form_tabs = st.tabs(["Current Movement", "Coming Rotors"])

with form_tabs[0]:  # Current Movement
    with st.form("current_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Date", value=datetime.today(), key="current_date")
            rotor_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, format="%d", key="current_size")
        with col2:
            entry_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"], key="current_type")
            quantity = st.number_input("🔢 Quantity", min_value=1, step=1, format="%d", key="current_qty")
        remarks = st.text_input("📝 Remarks", key="current_remarks")
        
        if st.form_submit_button("➕ Add Current Movement"):
            new_entry = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'),
                'Size (mm)': rotor_size, 
                'Type': entry_type, 
                'Quantity': quantity, 
                'Remarks': remarks,
                'Status': 'Current'
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            st.rerun()

with form_tabs[1]:  # Coming Rotors
    with st.form("future_form"):
        col1, col2 = st.columns(2)
        with col1:
            future_date = st.date_input("📅 Expected Date", 
                                      min_value=datetime.today() + timedelta(days=1),
                                      key="future_date")
            future_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, format="%d", key="future_size")
        with col2:
            future_qty = st.number_input("🔢 Quantity", min_value=1, step=1, format="%d", key="future_qty")
            future_remarks = st.text_input("📝 Remarks", key="future_remarks")
        
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
            st.rerun()

# ====== STOCK SUMMARY ======
st.subheader("📊 Current Stock Summary")
if not st.session_state.data.empty:
    # Ensure Status column exists
    if 'Status' not in st.session_state.data.columns:
        st.session_state.data['Status'] = 'Current'
    
    try:
        # Current stock
        current_data = st.session_state.data[st.session_state.data['Status'] == 'Current'].copy()
        current_data['Net Quantity'] = current_data.apply(
            lambda row: row['Quantity'] if row['Type'] == 'Inward' else -row['Quantity'], 
            axis=1
        )
        stock_summary = current_data.groupby('Size (mm)')['Net Quantity'].sum().reset_index()
        stock_summary = stock_summary[stock_summary['Net Quantity'] != 0]
        
        # Coming rotors
        future_data = st.session_state.data[st.session_state.data['Status'] == 'Future']
        coming_rotors = future_data.groupby('Size (mm)')['Quantity'].sum().reset_index()
        
        # Merge results
        merged = pd.merge(
            stock_summary,
            coming_rotors,
            on='Size (mm)',
            how='outer'
        ).fillna(0).rename(columns={
            'Net Quantity': 'Current Stock',
            'Quantity': 'Coming Rotors'
        })
        
        st.dataframe(
            merged[['Size (mm)', 'Current Stock', 'Coming Rotors']],
            use_container_width=True,
            hide_index=True
        )
    except Exception as e:
        st.error(f"Error generating stock summary: {e}")
else:
    st.info("No data available yet")

# ====== MOVEMENT LOG ======
st.subheader("📋 Movement Log")
if not st.session_state.data.empty:
    # Ensure Status column exists
    if 'Status' not in st.session_state.data.columns:
        st.session_state.data['Status'] = 'Current'
    
    try:
        display_cols = ['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status']
        display_df = st.session_state.data[display_cols].sort_values(['Date'], ascending=[False])
        
        # Add index for deletion
        display_df['Delete'] = [f"<button onclick='deleteEntry({i})'>❌</button>" for i in display_df.index]
        
        # Display as HTML table
        st.markdown(
            display_df.to_html(escape=False, index=False),
            unsafe_allow_html=True
        )
        
        # JavaScript for deletion
        st.markdown("""
        <script>
        function deleteEntry(index) {
            fetch(/delete_entry?index=${index}, {method: 'POST'})
                .then(() => window.location.reload());
        }
        </script>
        """, unsafe_allow_html=True)
        
    except Exception as e:
        st.error(f"Error displaying movement log: {e}")
else:
    st.info("No entries to display")

# ====== DELETE FUNCTION ======
def delete_entry(index):
    try:
        st.session_state.data = st.session_state.data.drop(index).reset_index(drop=True)
        st.success("Entry deleted successfully!")
        st.rerun()
    except Exception as e:
        st.error(f"Failed to delete entry: {e}")

# Handle delete requests
if 'delete_index' in st.query_params:
    delete_entry(int(st.query_params['delete_index']))
