import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# ====== INITIALIZE DATA ======
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status'
    ])

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

# ====== STOCK SUMMARY WITH ERROR HANDLING ======
st.subheader("📊 Current Stock Summary")
if not st.session_state.data.empty:
    try:
        # Current stock calculation
        current_mask = (st.session_state.data['Status'] == 'Current')
        current_data = st.session_state.data[current_mask].copy()
        
        if not current_data.empty:
            current_data['Net Quantity'] = current_data.apply(
                lambda row: row['Quantity'] if row['Type'] == 'Inward' else -row['Quantity'], 
                axis=1
            )
            stock_summary = current_data.groupby('Size (mm)')['Net Quantity'].sum().reset_index()
            stock_summary = stock_summary[stock_summary['Net Quantity'] != 0]
        else:
            stock_summary = pd.DataFrame(columns=['Size (mm)', 'Net Quantity'])
        
        # Coming rotors calculation
        future_mask = (st.session_state.data['Status'] == 'Future')
        future_data = st.session_state.data[future_mask]
        
        if not future_data.empty:
            coming_rotors = future_data.groupby('Size (mm)')['Quantity'].sum().reset_index()
        else:
            coming_rotors = pd.DataFrame(columns=['Size (mm)', 'Quantity'])
        
        # Merge data with error handling
        if not stock_summary.empty or not coming_rotors.empty:
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
        else:
            st.info("No stock data available")
            
    except KeyError as e:
        st.error(f"Data structure error: {e}. Please check your data columns.")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
else:
    st.info("No data available yet")

# ====== MOVEMENT LOG ======
st.subheader("📋 Movement Log")
if not st.session_state.data.empty:
    try:
        display_cols = ['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status']
        display_df = st.session_state.data[display_cols].sort_values(['Date'], ascending=[False])
        
        # Add delete buttons
        display_df['Action'] = [f"""
        <button onclick="window.deleteIndex={i}" style="
            background: none;
            border: none;
            color: red;
            cursor: pointer;
            font-size: 1.2rem;
        ">❌</button>
        """ for i in display_df.index]
        
        # Convert to HTML
        st.markdown(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)
        
        # JavaScript for delete
        st.markdown("""
        <script>
        const buttons = document.querySelectorAll('button');
        buttons.forEach(button => {
            button.onclick = () => {
                const index = button.parentElement.parentElement.rowIndex - 1;
                fetch('/delete_entry?index=' + index, {method: 'POST'})
                    .then(() => window.location.reload());
            };
        });
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
