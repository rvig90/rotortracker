import streamlit as st
import pandas as pd
from datetime import datetime
import base64

# ====== LOGO IMPLEMENTATION ======
def add_logo():
    st.markdown(
        """
        <style>
            .logo-container {
                display: flex;
                flex-direction: column;
                align-items: center;
                margin-bottom: 2rem;
            }
            .established {
                font-family: 'Arial', sans-serif;
                font-size: 1rem;
                color: #555555;
                letter-spacing: 0.1em;
                margin-bottom: -10px;
            }
            .logo-text {
                font-family: 'Arial Black', sans-serif;
                font-size: 2rem;
                font-weight: 900;
                color: #333333;
                line-height: 1;
                text-align: center;
            }
            .logo-hr {
                width: 80%;
                border: 0;
                height: 2px;
                background: linear-gradient(90deg, transparent, #333333, transparent);
                margin: 0.5rem 0;
            }
        </style>
        <div class="logo-container">
            <div class="established">EST. 1993</div>
            <div class="logo-text">MR<br>M.R ENTERPRISES</div>
            <div class="logo-hr"></div>
        </div>
        """,
        unsafe_allow_html=True
    )

# Initialize app
add_logo()
st.set_page_config(page_title="MR Enterprises - Rotor Tracker", layout="centered")

# Initialize session data
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks'])

# ====== DELETION FUNCTION ======
def delete_entry(index):
    try:
        # Create copy before modification
        df = st.session_state.data.copy()
        # Remove the entry
        df = df.drop(index=index).reset_index(drop=True)
        # Update session state
        st.session_state.data = df
        st.success("Entry deleted successfully!")
        st.rerun()  # Refresh to show changes
    except Exception as e:
        st.error(f"Failed to delete entry: {e}")

# ====== MAIN APP ======
st.title("🔧 Submersible Pump Rotor Tracker")

# Entry Form
with st.form("entry_form"):
    col1, col2 = st.columns(2)
    with col1:
        date = st.date_input("📅 Date", value=datetime.today())
        rotor_size = st.number_input("📐 Rotor Size (in mm)", min_value=1, step=1, format="%d")
    with col2:
        entry_type = st.selectbox("🔄 Entry Type", ["Inward", "Outgoing"])
        quantity = st.number_input("🔢 Quantity (number of rotors)", min_value=1, step=1, format="%d")
    remarks = st.text_input("📝 Remarks")
    
    if st.form_submit_button("➕ Add Entry"):
        new_entry = pd.DataFrame([{
            'Date': date.strftime('%Y-%m-%d'),
            'Size (mm)': rotor_size, 
            'Type': entry_type, 
            'Quantity': quantity, 
            'Remarks': remarks
        }])
        st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
        st.rerun()

# Movement Log Display
st.subheader("📋 Rotor Movement Log")
if not st.session_state.data.empty:
    for i in st.session_state.data.index:
        cols = st.columns([10, 1])
        with cols[0]:
            st.dataframe(st.session_state.data.iloc[[i]], use_container_width=True, hide_index=True)
        with cols[1]:
            if st.button("❌", key=f"delete_{i}"):
                delete_entry(i)
else:
    st.info("No entries to display.")

# Stock Summary
st.subheader("📊 Current Stock by Size (mm)")
if not st.session_state.data.empty:
    summary = st.session_state.data.copy()
    summary['Net Quantity'] = summary.apply(
        lambda row: row['Quantity'] if row['Type'] == 'Inward' else -row['Quantity'], 
        axis=1
    )
    stock_summary = summary.groupby('Size (mm)')['Net Quantity'].sum().reset_index()
    stock_summary = stock_summary[stock_summary['Net Quantity'] != 0]
    st.dataframe(stock_summary, use_container_width=True)
