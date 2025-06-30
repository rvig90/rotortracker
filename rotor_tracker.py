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

# ====== GOOGLE SHEETS INTEGRATION ======
def get_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = json.loads(st.secrets["gcp_service_account"]) if isinstance(st.secrets["gcp_service_account"], str) else dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Rotor Log").sheet1
    except Exception as e:
        st.error(f"Google Sheets connection failed: {str(e)}")
        return None

def sync_with_gsheet():
    try:
        sheet = get_gsheet()
        if sheet:
            records = sheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
                if 'Modified' not in df.columns:
                    df['Modified'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                st.session_state.data = df
            else:
                st.session_state.data = pd.DataFrame(columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Modified'])
    except Exception as e:
        st.error(f"Sync error: {e}")

def update_gsheet():
    try:
        sheet = get_gsheet()
        if sheet:
            st.session_state.data['Modified'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            sheet.clear()
            sheet.append_row(st.session_state.data.columns.tolist())
            for _, row in st.session_state.data.iterrows():
                sheet.append_row(row.tolist())
    except Exception as e:
        st.error(f"Update error: {e}")

# Initialize data
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Modified'])
    sync_with_gsheet()

# ====== DELETION FUNCTION ======
def delete_entry(index):
    try:
        st.session_state.data = st.session_state.data.drop(index).reset_index(drop=True)
        update_gsheet()
        st.success("Entry deleted successfully!")
        st.rerun()
    except Exception as e:
        st.error(f"Failed to delete entry: {e}")

# ====== FUTURE INBOUND CALCULATION ======
def get_future_inbound():
    future_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')  # Next 7 days
    future_inbound = st.session_state.data[
        (st.session_state.data['Type'] == 'Inward') & 
        (st.session_state.data['Date'] > datetime.now().strftime('%Y-%m-%d')) &
        (st.session_state.data['Date'] <= future_date)
    ]
    return future_inbound.groupby('Size (mm)')['Quantity'].sum().reset_index()

# ====== MAIN APP ======
st.title("🔧 Submersible Pump Rotor Tracker")

# Entry Form
with st.form("entry_form"):
    col1, col2 = st.columns(2)
    with col1:
        date = st.date_input("📅 Date", value=datetime.today())
        rotor_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, format="%d")
    with col2:
        entry_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"])
        quantity = st.number_input("🔢 Quantity", min_value=1, step=1, format="%d")
    remarks = st.text_input("📝 Remarks")
    
    if st.form_submit_button("➕ Add Entry"):
        new_entry = pd.DataFrame([{
            'Date': date.strftime('%Y-%m-%d'),
            'Size (mm)': rotor_size, 
            'Type': entry_type, 
            'Quantity': quantity, 
            'Remarks': remarks,
            'Modified': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }])
        st.session_state.data = pd.concat([st.session_state.data, new_entry], ignore_index=True)
        update_gsheet()
        st.rerun()

# ====== ENHANCED STOCK SUMMARY ======
st.subheader("📊 Current Stock Summary")
if not st.session_state.data.empty:
    # Current stock calculation
    summary = st.session_state.data.copy()
    summary['Net Quantity'] = summary.apply(
        lambda row: row['Quantity'] if row['Type'] == 'Inward' else -row['Quantity'], 
        axis=1
    )
    stock_summary = summary.groupby('Size (mm)')['Net Quantity'].sum().reset_index()
    stock_summary = stock_summary[stock_summary['Net Quantity'] != 0]
    
    # Future inbound calculation
    future_inbound = get_future_inbound()
    
    # Merge current stock with future inbound
    stock_summary = pd.merge(
        stock_summary,
        future_inbound,
        on='Size (mm)',
        how='left'
    ).rename(columns={'Quantity': 'Coming Rotors'}).fillna(0)
    
    # Format display
    stock_summary['Coming Rotors'] = stock_summary['Coming Rotors'].astype(int)
    st.dataframe(
        stock_summary[['Size (mm)', 'Net Quantity', 'Coming Rotors']]
        .rename(columns={'Size (mm)': 'Size (mm)', 'Net Quantity': 'Current Stock'}),
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No data available yet.")

# ====== STANDARD TABLE MOVEMENT LOG ======
st.subheader("📋 Movement Log")
if not st.session_state.data.empty:
    # Display full table with delete buttons
    display_df = st.session_state.data.sort_values('Modified', ascending=False).copy()
    display_df = display_df[['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks']]
    
    # Add delete buttons column
    display_df['Action'] = [f"""
    <button onclick="window.deleteIndex={i}" style="
        background: none;
        border: none;
        color: red;
        cursor: pointer;
        font-size: 1.2rem;
    ">❌</button>
    """ for i in display_df.index]
    
    # Display the table
    st.markdown(
        display_df.to_html(escape=False, index=False), 
        unsafe_allow_html=True
    )
    
    # JavaScript for delete functionality
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
    
    # Alternative delete method for Streamlit buttons
    for i in st.session_state.data.index:
        if st.button(f"Delete Entry {i+1}", key=f"delete_{i}"):
            delete_entry(i)
            st.rerun()
else:
    st.info("No entries to display.")

if st.button("🔄 Sync with Google Sheets"):
    sync_with_gsheet()
    st.rerun()
