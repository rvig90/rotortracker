import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ====== LOGO IMPLEMENTATION ======
def add_logo():
    st.markdown("""
    <style>
        .logo-container { display: flex; flex-direction: column; align-items: center; margin-bottom: 1rem; }
        .established { font-family: 'Arial', sans-serif; font-size: 0.9rem; color: #555555; letter-spacing: 0.1em; margin-bottom: -8px; }
        .logo-text { font-family: 'Arial Black', sans-serif; font-size: 1.8rem; font-weight: 900; color: #333333; line-height: 1; text-align: center; }
        .logo-hr { width: 70%; border: 0; height: 1px; background: linear-gradient(90deg, transparent, #333333, transparent); margin: 0.5rem 0; }
        .log-table { width: 100%; border-collapse: collapse; }
        .log-table th, .log-table td { padding: 8px 12px; border: 1px solid #ddd; text-align: left; }
        .log-table th { background-color: #f2f2f2; }
        .delete-btn { color: red; background: none; border: none; cursor: pointer; }
    </style>
    <div class="logo-container">
        <div class="established">EST. 1993</div>
        <div class="logo-text">MR<br>M.R ENTERPRISES</div>
        <div class="logo-hr"></div>
    </div>
    """, unsafe_allow_html=True)

# Initialize app
add_logo()
st.set_page_config(page_title="MR Enterprises - Rotor Tracker", layout="centered")

# ====== DATA STRUCTURE ======
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Modified', 'Status'
    ])

# ====== ENTRY FORM ======
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
                'Modified': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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
                'Modified': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Status': 'Future'
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
            st.rerun()

# ====== STOCK SUMMARY ======
st.subheader("📊 Current Stock Summary")
if not st.session_state.data.empty:
    # Current stock
    current_data = st.session_state.data[st.session_state.data['Status'] == 'Current']
    if not current_data.empty:
        current_data['Net Quantity'] = current_data.apply(
            lambda row: row['Quantity'] if row['Type'] == 'Inward' else -row['Quantity'], 
            axis=1
        )
        stock_summary = current_data.groupby('Size (mm)')['Net Quantity'].sum().reset_index()
        stock_summary = stock_summary[stock_summary['Net Quantity'] != 0]
    else:
        stock_summary = pd.DataFrame(columns=['Size (mm)', 'Net Quantity'])
    
    # Coming rotors
    future_data = st.session_state.data[st.session_state.data['Status'] == 'Future']
    if not future_data.empty:
        coming_rotors = future_data.groupby('Size (mm)')['Quantity'].sum().reset_index()
    else:
        coming_rotors = pd.DataFrame(columns=['Size (mm)', 'Quantity'])
    
    # Merge data
    merged = pd.merge(
        stock_summary,
        coming_rotors,
        on='Size (mm)',
        how='outer'
    ).fillna(0).rename(columns={
        'Net Quantity': 'Current Stock',
        'Quantity': 'Coming Rotors'
    })
    
    if not merged.empty:
        st.dataframe(
            merged[['Size (mm)', 'Current Stock', 'Coming Rotors']],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No stock data available")
else:
    st.info("No data available yet")

# ====== MOVEMENT LOG ======
st.subheader("📋 Movement Log")
if not st.session_state.data.empty:
    # Display data
    display_cols = ['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status']
    display_df = st.session_state.data[display_cols].sort_values(['Date', 'Modified'], ascending=[False, False])
    
    # Convert to HTML with styling
    html = f"""
    <table class="log-table">
        <thead>
            <tr>
                <th>Date</th>
                <th>Size (mm)</th>
                <th>Type</th>
                <th>Quantity</th>
                <th>Remarks</th>
                <th>Status</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for idx, row in display_df.iterrows():
        html += f"""
        <tr>
            <td>{row['Date']}</td>
            <td>{row['Size (mm)']}</td>
            <td>{row['Type']}</td>
            <td>{row['Quantity']}</td>
            <td>{row['Remarks']}</td>
            <td>{row['Status']}</td>
            <td><button class="delete-btn" onclick="window.deleteIndex={idx}">❌</button></td>
        </tr>
        """
    
    html += """
        </tbody>
    </table>
    <script>
    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.onclick = (e) => {
            const index = e.target.getAttribute('onclick').split('=')[1];
            fetch(/delete_entry?index=${index}, {method: 'POST'})
                .then(() => window.location.reload());
        };
    });
    </script>
    """
    
    st.markdown(html, unsafe_allow_html=True)
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
