# rotor_tracker.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from PIL import Image
import io
import requests
from uuid import uuid4
import altair as alt
import re


import os
import os
# Add this at the very top of your app

# =========================
# PERSISTENT CHAT WIDGET
# =========================

import streamlit as st
import os
import json
from datetime import datetime, timedelta
import pandas as pd

# =========================
# FLOATING AI ASSISTANT
# =========================

# Initialize session state
if 'show_assistant' not in st.session_state:
    st.session_state.show_assistant = False

if 'assistant_messages' not in st.session_state:
    st.session_state.assistant_messages = [
        {"role": "assistant", "content": "👋 Hi! I'm your AI inventory assistant. How can I help?"}
    ]

# Custom CSS for floating widget - FIXED
st.markdown("""
<style>
/* Floating button container */
.floating-btn-container {
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 9999;
}

.floating-btn {
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 50px;
    padding: 15px 25px;
    font-size: 16px;
    font-weight: bold;
    cursor: pointer;
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    transition: all 0.3s;
    border: none;
}

.floating-btn:hover {
    background-color: #45a049;
    transform: scale(1.05);
}

/* Assistant widget */
.assistant-widget {
    position: fixed;
    bottom: 90px;
    right: 20px;
    width: 350px;
    height: 500px;
    background-color: white;
    border-radius: 10px;
    box-shadow: 0 5px 20px rgba(0,0,0,0.2);
    z-index: 9998;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border: 1px solid #e0e0e0;
    padding: 10px;
}

/* Make sure Streamlit elements don't overflow */
.stButton > button {
    width: 100%;
}

/* Chat messages area */
.chat-messages {
    flex-grow: 1;
    overflow-y: auto;
    padding: 10px;
    background-color: #f9f9f9;
    border-radius: 5px;
    margin-bottom: 10px;
}

.user-msg {
    background-color: #4CAF50;
    color: white;
    padding: 8px 12px;
    border-radius: 15px 15px 0 15px;
    margin: 5px 0;
    max-width: 80%;
    float: right;
    clear: both;
    word-wrap: break-word;
}

.assistant-msg {
    background-color: #e0e0e0;
    color: black;
    padding: 8px 12px;
    border-radius: 15px 15px 15px 0;
    margin: 5px 0;
    max-width: 80%;
    float: left;
    clear: both;
    word-wrap: break-word;
}

/* Clear fix */
.clearfix::after {
    content: "";
    clear: both;
    display: table;
}
</style>
""", unsafe_allow_html=True)

# =========================
# SARVAM AI SETUP
# =========================
def setup_sarvam_ai():
    """Initialize Sarvam AI with secure API key handling"""
    try:
        # Try to get from secrets
        api_key = st.secrets["SARVAM_API_KEY"]
        return api_key
    except:
        # Fallback to environment variable
        import os
        return os.getenv("SARVAM_API_KEY")

# Initialize Sarvam
api_key = setup_sarvam_ai()
SARVAM_AVAILABLE = False
llm = None

if api_key:
    try:
        from langchain_sarvam import ChatSarvam
        from langchain_core.messages import HumanMessage, SystemMessage
        llm = ChatSarvam(
            model="sarvam-m",
            temperature=0.2,
            sarvam_api_key=api_key,
            max_tokens=512
        )
        SARVAM_AVAILABLE = True
    except Exception as e:
        st.sidebar.error(f"Sarvam import error: {str(e)}")

# =========================
# MAIN APP CONTENT
# =========================
st.title("🚀 Rotor Inventory Management System")

# Your existing tabs
tab1, tab2, tab3 = st.tabs(["Dashboard", "Transactions", "Settings"])

with tab1:
    st.write("### Dashboard")
    # Sample data for testing
    if 'data' not in st.session_state:
        st.session_state.data = pd.DataFrame({
            'Date': [datetime.now() - timedelta(days=x) for x in range(10)],
            'Type': ['Inward', 'Outgoing'] * 5,
            'Size (mm)': [1803, 2003, 35, 40, 50] * 2,
            'Quantity': [10, 5, 20, 15, 8] * 2,
            'Remarks': ['Enova', 'Ajji', 'Alpha', 'Beta', 'Gamma'] * 2,
            'Status': ['Current', 'Future'] * 5,
            'Pending': [False, True] * 5
        })
    
    st.dataframe(st.session_state.data.head())

with tab2:
    st.write("### Transactions")
    st.info("Your transactions content here")

with tab3:
    st.write("### Settings")
    st.info("Your settings content here")

# =========================
# FLOATING BUTTON (Outside tabs)
# =========================
st.markdown('<div class="floating-btn-container">', unsafe_allow_html=True)

# Use columns to create the button
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("🤖 AI Assistant", key="floating_btn"):
        st.session_state.show_assistant = not st.session_state.show_assistant
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# =========================
# ASSISTANT WIDGET (Outside tabs)
# =========================
if st.session_state.show_assistant:
    st.markdown('<div class="assistant-widget">', unsafe_allow_html=True)
    
    # Header with close button
    col1, col2 = st.columns([6, 1])
    with col1:
        st.markdown("### 🤖 AI Assistant")
    with col2:
        if st.button("✖️", key="close_btn"):
            st.session_state.show_assistant = False
            st.rerun()
    
    st.divider()
    
    # API Status
    if not SARVAM_AVAILABLE:
        st.warning("⚠️ AI not configured")
        st.code("""
# In .streamlit/secrets.toml:
SARVAM_API_KEY = "your_key_here"
        """)
        
        # Demo mode
        st.markdown("### Demo Mode")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📦 Stock", key="demo_stock"):
                st.info("Demo: Stock levels would show here")
        with col2:
            if st.button("⏳ Pending", key="demo_pending"):
                st.info("Demo: Pending orders would show here")
        
        st.markdown('</div>', unsafe_allow_html=True)
        st.stop()
    
    # Chat messages
    st.markdown('<div class="chat-messages">', unsafe_allow_html=True)
    
    for msg in st.session_state.assistant_messages:
        if msg["role"] == "user":
            st.markdown(f'<div class="user-msg">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="assistant-msg">{msg["content"]}</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="clearfix"></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Quick actions
    st.markdown("### Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📦", key="qa_stock", help="Stock levels"):
            query = "Show current stock levels"
    with col2:
        if st.button("⏳", key="qa_pending", help="Pending orders"):
            query = "Show pending orders"
    with col3:
        if st.button("📅", key="qa_coming", help="Coming rotors"):
            query = "Show future incoming rotors"
    with col4:
        if st.button("💰", key="qa_price", help="Price list"):
            query = "Show price list"
    
    # Handle quick actions
    if 'query' in locals():
        st.session_state.assistant_messages.append({"role": "user", "content": query})
        
        try:
            # Prepare context
            context = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'total_sizes': len(st.session_state.data['Size (mm)'].unique()) if 'data' in st.session_state else 0
            }
            
            messages = [
                SystemMessage(content="You are an inventory assistant. Be concise."),
                HumanMessage(content=f"Context: {json.dumps(context)}\n\nQuestion: {query}")
            ]
            response = llm.invoke(messages)
            st.session_state.assistant_messages.append({"role": "assistant", "content": response.content})
        except Exception as e:
            st.session_state.assistant_messages.append({"role": "assistant", "content": f"Error: {str(e)}"})
        
        st.rerun()
    
    # Chat input
    user_input = st.text_input("Type your question...", key="chat_input")
    
    col1, col2 = st.columns([5, 1])
    with col2:
        if st.button("Send", key="send_btn"):
            if user_input:
                st.session_state.assistant_messages.append({"role": "user", "content": user_input})
                
                try:
                    context = {
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'total_sizes': len(st.session_state.data['Size (mm)'].unique()) if 'data' in st.session_state else 0
                    }
                    
                    messages = [
                        SystemMessage(content="You are an inventory assistant. Be concise."),
                        HumanMessage(content=f"Context: {json.dumps(context)}\n\nQuestion: {user_input}")
                    ]
                    response = llm.invoke(messages)
                    st.session_state.assistant_messages.append({"role": "assistant", "content": response.content})
                except Exception as e:
                    st.session_state.assistant_messages.append({"role": "assistant", "content": f"Error: {str(e)}"})
                
                st.rerun()
    
    # Clear chat button
    if st.button("🗑️ Clear Chat", key="clear_chat"):
        st.session_state.assistant_messages = [
            {"role": "assistant", "content": "👋 Hi! I'm your AI inventory assistant. How can I help?"}
        ]
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# SIDEBAR STATUS
# =========================
with st.sidebar:
    st.markdown("### System Status")
    if SARVAM_AVAILABLE:
        st.success("✅ AI Assistant: Connected")
    else:
        st.error("❌ AI Assistant: Not configured")
        if api_key:
            st.info(f"API Key found: {api_key[:10]}...")
        else:
            st.warning("No API key found")

# =========================
# YOUR MAIN APP CONTENT
# =========================


# Stop here, don't show the rest of the app # Stop here, don't show the rest of the app
ROTOR_WEIGHTS = { 80: 0.5, 100: 1, 110: 1.01, 120: 1.02, 125: 1.058, 130: 1.1, 140: 1.15, 150: 1.3, 160: 1.4, 170: 1.422, 180: 1.5, 200: 1.7, 225: 1.9, 260: 2.15, 2403: 1.46, 1803: 1, 2003: 1.1 }
from uuid import uuid4

# Session state for logs

# Ensure session state dataframes exist before chatbot
if "clitting_data" not in st.session_state:
    st.session_state["clitting_data"] = pd.DataFrame(columns=[
        "Date", "Size (mm)", "Bags", "Weight per Bag (kg)", "Remarks", "ID"
    ])
if "lamination_v3" not in st.session_state:
    st.session_state["lamination_v3"] = pd.DataFrame(columns=[
        "Date", "Quantity", "Remarks", "ID"
    ])
if "lamination_v4" not in st.session_state:
    st.session_state["lamination_v4"] = pd.DataFrame(columns=[
        "Date", "Quantity", "Remarks", "ID"
    ])
if "stator_data" not in st.session_state:
    st.session_state["stator_data"] = pd.DataFrame(columns=[
        "Date", "Size (mm)", "Quantity", "Remarks",
        "Estimated Clitting (kg)", "Laminations Used",
        "Lamination Type", "ID"
    ])





    
# ====== INITIALIZE DATA ======
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending', 'ID'
    ])
    st.session_state.last_sync = "Never"
    st.session_state.editing = None
    st.session_state.filter_reset = False



# ====== APP LOGO ======
import streamlit as st
import requests
from PIL import Image
import io

def display_logo():
    try:
        logo_url = "https://ik.imagekit.io/zmv7kjha8x/D936A070-DB06-4439-B642-854E6510A701.PNG?updatedAt=1752629786861"
        response = requests.get(logo_url, timeout=5)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        logo = Image.open(io.BytesIO(response.content))
        st.image(logo, width=200)
    except requests.exceptions.RequestException as e:
        st.warning(f"Couldn't load logo from URL: {e}")
        st.title("Rotor Tracker")
    except Exception as e:
        st.warning(f"An error occurred: {e}")
        st.title("Rotor Tracker")

display_logo()

# ====== HELPER FUNCTIONS ======
def normalize_pending_column(df):
    df['Pending'] = df['Pending'].apply(
        lambda x: str(x).lower() == 'true' if isinstance(x, str) else bool(x)
    )
    return df



def safe_delete_entry(id_to_delete):
    try:
        df = st.session_state.data
        st.session_state.data = df[df['ID'] != id_to_delete].reset_index(drop=True)
        auto_save_to_gsheet()
        st.success("Entry deleted successfully")
        st.rerun()
    except Exception as e:
        st.error(f"Error deleting entry: {e}")

# ====== GOOGLE SHEETS INTEGRATION ======
def get_gsheet_connection():
    try:
        scope = [
            "https://spreadsheets.google.com/feeds", 
            "https://www.googleapis.com/auth/drive"
        ]
        if isinstance(st.secrets["gcp_service_account"], str):
            creds_dict = json.loads(st.secrets["gcp_service_account"])
        else:
            creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Rotor Log").sheet1
    except Exception as e:
        st.error(f"Google Sheets connection failed: {e}")
        return None

def save_to_backup_sheet(df):
    try:
        sheet = get_gsheet_connection()
        if not sheet:
            return
        ss = sheet.spreadsheet
        try:
            backup = ss.worksheet("Backup")
        except gspread.WorksheetNotFound:
            backup = ss.add_worksheet(title="Backup", rows="1000", cols=str(len(df.columns)))
        backup.clear()
        records = [df.columns.tolist()] + df.values.tolist()
        backup.update(records)
    except Exception as e:
        st.error(f"Backup failed: {e}")

def load_from_gsheet():
    try:
        sheet = get_gsheet_connection()
        if sheet:
            records = sheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
                for col, default in [('Status', 'Current'), ('Pending', False)]:
                    if col not in df.columns:
                        df[col] = default
                df = normalize_pending_column(df)
                if 'ID' not in df.columns:
                    df['ID'] = [str(uuid4()) for _ in range(len(df))]
                st.session_state.data = df
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"Error loading data: {e}")

def auto_save_to_gsheet():
    try:
        sheet = get_gsheet_connection()
        if sheet:
            sheet.clear()
            if not st.session_state.data.empty:
                df = st.session_state.data.copy()
                df['Pending'] = df['Pending'].apply(lambda x: "TRUE" if x else "FALSE")
                expected = ['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending', 'ID']
                for c in expected:
                    if c not in df.columns:
                        df[c] = ""
                df = df[expected]
                sheet.update([df.columns.tolist()] + df.values.tolist())
                save_to_backup_sheet(df)
        st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"Auto-save failed: {e}")




# ====== MAIN APP ======
if st.session_state.get("last_sync") == "Never":
    load_from_gsheet()

if st.button("🔄 Sync Now", help="Manually reload data from Google Sheets"):
    load_from_gsheet()

# App title
st.set_page_config(page_title="Rotor + Stator Tracker", layout="wide")

# Sidebar tab switch
tab_choice = st.sidebar.radio("📊 Choose Tab", ["🔁 Rotor Tracker", "🧰 Clitting + Laminations + Stators"])

if tab_choice == "🔁 Rotor Tracker":
    st.title("🔁 Rotor Tracker")
    
    # ... keep your existing rotor tracker code here ...


# ====== ENTRY FORMS ======
    form_tabs = st.tabs([
        "Current Movement", 
        "Coming Rotors", 
        "Pending Rotors",
    ])
    
    def add_entry(data_dict):
        data_dict['ID'] = str(uuid4())
        new = pd.DataFrame([data_dict])
        st.session_state.data = pd.concat([st.session_state.data, new], ignore_index=True)
        st.session_state.last_entry = data_dict
        st.session_state.undo_confirm = False
        auto_save_to_gsheet()
        st.rerun()
    
    
    
    # Ensure session keys
    
    # --- Session keys ---
    for key in ["conflict_resolved", "selected_idx", "future_matches"]:
        if key not in st.session_state:
            st.session_state[key] = None if "idx" in key else False if "conflict" in key else pd.DataFrame()
    
    with form_tabs[0]:
        st.subheader("📥 Add Rotor Movement")
    
        # === Form fields ===
        with st.form("current_form"):
            col1, col2 = st.columns(2)
            with col1:
                date = st.date_input("📅 Date", value=datetime.today())
                rotor_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
            with col2:
                entry_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"])
                quantity = st.number_input("🔢 Quantity", min_value=1, step=1)
            remarks = st.text_input("📝 Remarks")
    
            submit_form = st.form_submit_button("📋 Submit Entry Info")
    
        if submit_form:
            df = st.session_state.data.copy()
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
    
            new_entry = {
                'Date': date.strftime('%Y-%m-%d'),
                'Size (mm)': int(rotor_size),
                'Type': entry_type,
                'Quantity': int(quantity),
                'Remarks': remarks.strip(),
                'Status': 'Current',
                'Pending': False,
                'ID': str(uuid4())
            }
    
            st.session_state["new_entry"] = new_entry
            st.session_state["conflict_resolved"] = True  # assume no conflict initially
            st.session_state["action_required"] = False
    
            # Inward with no remarks → check future status entries
            if entry_type == "Inward" and remarks.strip() == "":
                matches = df[
                    (df["Type"] == "Inward") &
                    (df["Size (mm)"] == int(rotor_size)) &
                    (df["Remarks"].str.strip() == "") &
                    (df["Status"].str.lower() == "future")
                ].sort_values("Date")
    
                if not matches.empty:
                    st.warning("⚠ Matching future rotor(s) found.")
                    st.session_state["conflict_resolved"] = False
                    st.session_state["action_required"] = True
                    st.session_state["future_matches"] = matches
                    st.session_state["selected_idx"] = matches.index[0]  # default selection
    
        # If conflict exists and user needs to choose what to do
        if st.session_state.get("action_required") and not st.session_state.get("conflict_resolved"):
    
            matches = st.session_state["future_matches"]
            st.dataframe(matches[["Date", "Quantity", "Status"]], use_container_width=True)
    
            selected = st.selectbox(
                "Select a future entry to act on:",
                options=matches.index,
                index=0,
                format_func=lambda i: f"{matches.at[i, 'Date']} → Qty: {matches.at[i, 'Quantity']}"
            )
            st.session_state["selected_idx"] = selected
    
            col1, col2, col3 = st.columns(3)
            if col1.button("🗑 Delete Selected Entry"):
                st.session_state.data = st.session_state.data.drop(selected)
                st.session_state["conflict_resolved"] = True
                st.session_state["action_required"] = False
                st.success("✅ Selected Entry deleted. Please Save!.")
    
            if col2.button("➖ Deduct from Selected Entry"):
                qty = st.session_state["new_entry"]["Quantity"]
                future_qty = int(st.session_state.data.at[selected, "Quantity"])
                if qty >= future_qty:
                    st.session_state.data = st.session_state.data.drop(selected)
                else:
                    st.session_state.data.at[selected, "Quantity"] = future_qty - qty
                st.session_state["conflict_resolved"] = True
                st.session_state["action_required"] = False
                st.success("✅ Selected Entry deducted. Please Save!")
    
            if col3.button("Do Nothing"):
                st.session_state["conflict_resolved"] = True
                st.session_state["action_required"] = False
                st.success("No Changes will Be Made. Please Save!")
                
    
        # Final save button — only shown if conflict is resolved and entry is ready
        if st.session_state.get("conflict_resolved") and st.session_state.get("new_entry"):
            if st.button("💾 Save Entry"):
                with st.spinner("saving you entry..."):
                    df = st.session_state.data.copy()
                    new_entry = st.session_state["new_entry"]
        
                    # Outgoing deduction from pending
                    if new_entry["Type"] == "Outgoing" and new_entry["Remarks"]:
                        buyer = new_entry["Remarks"].lower()
                        size = new_entry["Size (mm)"]
                        qty = new_entry["Quantity"]
                        pending = df[
                            (df["Size (mm)"] == size) &
                            (df["Remarks"].str.lower().str.contains(buyer)) &
                            (df["Pending"] == True) &
                            (df["Status"] == "Current")
                        ].sort_values("Date")
                        for idx, row in pending.iterrows():
                            if qty <= 0:
                                break
                            pending_qty = int(row["Quantity"])
                            if qty >= pending_qty:
                                df.at[idx, "Quantity"] = 0
                                df.at[idx, "Pending"] = False
                                qty -= pending_qty
                            else:
                                df.at[idx, "Quantity"] = pending_qty - qty
                                qty = 0
                        df = df[df["Quantity"] > 0]
        
                    # Append new entry
                    df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
                    df["Date"] = df["Date"].astype(str)
                    st.session_state.data = df.reset_index(drop=True)
        
                    try:
                        auto_save_to_gsheet()
                        st.success("✅ Entry saved to Google Sheets.")
                    except Exception as e:
                        st.error(f"❌ Failed to save: {e}")
        
                    # Clear all session temp
                    st.session_state["new_entry"] = None
                    st.session_state["future_matches"] = None
                    st.session_state["selected_idx"] = None
                    st.session_state["conflict_resolved"] = False
                    st.session_state["action_required"] = False
    
        if st.session_state.get("last_snapshot") is not None:
            if st.button(" undo last action"):
                st.session_state.data = st.session_state.last_snapshot.copy()
                st.success(f"undid:{st.session_state.last_action_note}")
                auto_save_to_gsheet()
    with form_tabs[1]:
        with st.form("future_form"):
            col1, col2 = st.columns(2)
            with col1:
                future_date = st.date_input("📅 Expected Date", min_value=datetime.today() + timedelta(days=1))
                future_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
            with col2:
                future_qty = st.number_input("🔢 Quantity", min_value=1, step=1)
                future_remarks = st.text_input("📝 Remarks")
            if st.form_submit_button("➕ Add Coming Rotors"):
                add_entry({
                    'Date': future_date.strftime('%Y-%m-%d'),
                    'Size (mm)': future_size,
                    'Type': 'Inward',
                    'Quantity': future_qty,
                    'Remarks': future_remarks,
                    'Status': 'Future',
                    'Pending': False
                })
                st.session_state["data"].to_csv("rotordata.csv", index=False)
                st.success("Entry added!")
    
    with form_tabs[2]:
        with st.form("pending_form"):
            col1, col2 = st.columns(2)
            with col1:
                pending_date = st.date_input("📅 Date", value=datetime.today())
                pending_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
            with col2:
                pending_qty = st.number_input("🔢 Quantity", min_value=1, step=1)
                pending_remarks = st.text_input("📝 Remarks", value="")
            if st.form_submit_button("➕ Add Pending Rotors"):
                add_entry({
                    'Date': pending_date.strftime('%Y-%m-%d'),
                    'Size (mm)': pending_size,
                    'Type': 'Outgoing',
                    'Quantity': pending_qty,
                    'Remarks': pending_remarks,
                    'Status': 'Current',
                    'Pending': True
                })
                st.session_state["data"].to_csv("rotordata.csv", index=False)
                st.success("Entry added!")
    
    # ✂ (Remaining part like stock summary, movement log, edit form is unchanged but should use 'ID' for match/edit)
                st.session_state.data = pd.concat([st.session_state.data, new], ignore_index=True)
                auto_save_to_gsheet()
                st.rerun()
    
    
    # ====== STOCK SUMMARY ======
    tabs = st.tabs(["📊 Stock Summary", "📋 Movement Log", "💬 Rotor Chatbot lite", "AI Assistant"])
    
    # === TAB 1: Stock Summary ===
    with tabs[0]:
        st.subheader("📊 Current Stock Summary")
        if not st.session_state.data.empty:
            try:
                st.session_state.data = normalize_pending_column(st.session_state.data)
                current = st.session_state.data[
                    (st.session_state.data['Status'] == 'Current') &
                    (~st.session_state.data['Pending'])
                ].copy()
                current['Net'] = current.apply(
                    lambda x: x['Quantity'] if x['Type'] == 'Inward' else -x['Quantity'], axis=1
                )
                stock = current.groupby('Size (mm)')['Net'].sum().reset_index()
                stock = stock[stock['Net'] != 0]
    
                future = st.session_state.data[st.session_state.data['Status'] == 'Future']
                coming = future.groupby('Size (mm)')['Quantity'].sum().reset_index()
    
                pending = st.session_state.data[
                    (st.session_state.data['Status'] == 'Current') &
                    (st.session_state.data['Pending'])
                ]
                pending_rotors = pending.groupby('Size (mm)')['Quantity'].sum().reset_index()
    
                combined = pd.merge(stock, coming, on='Size (mm)', how='outer')
                combined = pd.merge(
                    combined, pending_rotors,
                    on='Size (mm)', how='outer', suffixes=('', '_pending')
                ).fillna(0)
                combined.columns = [
                    'Size (mm)', 'Current Stock', 'Coming Rotors', 'Pending Rotors'
                ]
                st.dataframe(combined, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Error generating summary: {e}")
        else:
            st.info("No data available yet.")
        # Stock alerts
           
        
        from prophet import Prophet
        from datetime import datetime, timedelta
        import pandas as pd
        import streamlit as st
        
        
        
        st.subheader("🚨 Stock Risk Alerts")
        
        # Load current data
        df = st.session_state.data.copy()
        df["Date"] = pd.to_datetime(df["Date"])
        df["Remarks"] = df["Remarks"].fillna("").astype(str)
        
        # ===== GROUPING STOCK METRICS =====
        # 1. Current Stock (Inward - Outgoing, excluding Pending)
        current_df = df[
            (df["Status"] == "Current") & (~df["Pending"])
        ].copy()
        current_df["Net"] = current_df.apply(
            lambda x: x["Quantity"] if x["Type"] == "Inward" else -x["Quantity"], axis=1
        )
        stock = current_df.groupby("Size (mm)")["Net"].sum().reset_index().rename(columns={"Net": "Stock"})
        
        # 2. Pending Outgoing
        pending_df = df[(df["Pending"] == True) & (df["Status"] == "Current")]
        pending_out = pending_df.groupby("Size (mm)")["Quantity"].sum().reset_index().rename(columns={"Quantity": "Pending Out"})
        
        # 3. Future Inward
        future_df = df[(df["Status"] == "Future") & (df["Type"] == "Inward")]
        coming_in = future_df.groupby("Size (mm)")["Quantity"].sum().reset_index().rename(columns={"Quantity": "Coming In"})
        
        # ===== MERGE ALL SOURCES =====
        merged = stock.merge(pending_out, on="Size (mm)", how="outer") \
                      .merge(coming_in, on="Size (mm)", how="outer") \
                      .fillna(0)
        
        # Ensure all values are integers
        for col in ["Stock", "Pending Out", "Coming In"]:
            merged[col] = merged[col].astype(int)
        
        # ===== ALERTS SECTION =====
        
        # 1️⃣ Low stock with no incoming rotors
        low_stock = merged[(merged["Stock"] < 100) & (merged["Coming In"] == 0)]
        
        if not low_stock.empty:
            st.warning("🟠 Low stock (less than 100) with **no incoming rotors**:")
            st.dataframe(low_stock[["Size (mm)", "Stock"]], use_container_width=True, hide_index=True)
        else:
            st.success("✅ No low stock issues detected.")
        
        # 2️⃣ Pending orders exceed available supply (stock + incoming)
        risky_pending = merged[merged["Pending Out"] > (merged["Stock"] + merged["Coming In"])]
        
        if not risky_pending.empty:
            st.error("🔴 Pending exceeds total available rotors (Stock + Incoming):")
            st.dataframe(
                risky_pending[["Size (mm)", "Stock", "Coming In", "Pending Out"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.success("✅ All pending orders can be fulfilled with available and incoming stock.")
    # ====== MOVEMENT LOG WITH FIXED FILTERS ======
    # ====== MOVEMENT LOG WITH FIXED FILTERS ======
    with tabs[1]:
        st.subheader("📋 Movement Log")
        if st.session_state.data.empty:
            st.info("No entries to show yet.")
        else:
            df = st.session_state.data.copy()
            st.markdown("### 🔍 Filter Movement Log")
    
            # Ensure filter keys exist in session state
            if "sf" not in st.session_state: st.session_state.sf = "All"
            if "zf" not in st.session_state: st.session_state.zf = []
            if "pf" not in st.session_state: st.session_state.pf = "All"
            if "tf" not in st.session_state: st.session_state.tf = "All"
            if "rs" not in st.session_state: st.session_state.rs = ""
            if "dr" not in st.session_state:
                min_date = pd.to_datetime(df['Date']).min().date()
                max_date = pd.to_datetime(df['Date']).max().date()
                st.session_state.dr = [max_date, max_date]
    
            # Filter Reset Button
            if st.button("🔄 Reset All Filters"):
                st.session_state.sf = "All"
                st.session_state.zf = []
                st.session_state.pf = "All"
                st.session_state.tf = "All"
                st.session_state.rs = ""
                min_date = pd.to_datetime(df['Date']).min().date()
                max_date = pd.to_datetime(df['Date']).max().date()
                st.session_state.dr = [max_date, max_date]
                st.rerun()
    
            # Filter Controls
            c1, c2, c3,c4 = st.columns(4)
            with c1:
                status_f = st.selectbox("📂 Status", ["All", "Current", "Future"], key="sf")
            with c2:
                size_options = sorted(df['Size (mm)'].dropna().unique())
                size_f = st.multiselect("📐 Size (mm)", options=size_options, key="zf")
            with c3:
                pending_f = st.selectbox("❗ Pending", ["All", "Yes", "No"], key="pf")
    
            with c4:
                type_f = st.selectbox("Type", ["All", "Inward", "Outgoing"], key="tf")
    
            remark_s = st.text_input("📝 Search Remarks", key="rs")
    
            date_range = st.date_input("📅 Date Range", key="dr")
    
            # Apply filters
            try:
                if status_f != "All":
                    df = df[df['Status'] == status_f]
                if pending_f == "Yes":
                    df = df[df['Pending'] == True]
                elif pending_f == "No":
                    df = df[df['Pending'] == False]
                if size_f:
                    df = df[df['Size (mm)'].isin(size_f)]
                if remark_s:
                    df = df[df['Remarks'].astype(str).str.contains(remark_s, case=False, na=False)]
    
                if type_f !="All":
                    df = df[df["Type"] == type_f]
                if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
                    start, end = date_range
                    df = df[
                        (pd.to_datetime(df['Date']) >= pd.to_datetime(start)) &
                        (pd.to_datetime(df['Date']) <= pd.to_datetime(end))
                    ]
            except Exception as e:
                st.error(f"Error applying filters: {str(e)}")
                df = st.session_state.data.copy()
    
            df = df.reset_index(drop=True)
            st.markdown("### 📄 Filtered Entries")
    
            for idx, row in df.iterrows():
                entry_id = row['ID']
                match = st.session_state.data[st.session_state.data['ID'] == entry_id]
                if match.empty:
                    continue  # Skip rendering this row
                match_idx = match.index[0]            
                cols = st.columns([10, 1, 1])
                with cols[0]:
                    disp = row.drop(labels="ID").to_dict()
                    disp["Pending"] = "Yes" if row["Pending"] else "No"
                    st.dataframe(pd.DataFrame([disp]), hide_index=True, use_container_width=True)
    
                with cols[1]:
                    def start_edit(idx=match_idx):
                        st.session_state.editing = idx
                    st.button("✏", key=f"edit_{entry_id}", on_click=start_edit)
    
                with cols[2]:
                    if st.button("❌", key=f"del_{entry_id}"):
                        safe_delete_entry(entry_id)
    
                if st.session_state.get("editing") == match_idx:
                    er = st.session_state.data.loc[match_idx]
                    with st.form(f"edit_form_{entry_id}"):
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            e_date = st.date_input("📅 Date", value=pd.to_datetime(er["Date"]), key=f"e_date_{entry_id}")
                            e_size = st.number_input("📐 Rotor Size (mm)", min_value=1, value=int(er["Size (mm)"]), key=f"e_size_{entry_id}")
                        with ec2:
                            e_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"], index=0 if er["Type"] == "Inward" else 1, key=f"e_type_{entry_id}")
                            e_qty = st.number_input("🔢 Quantity", min_value=1, value=int(er["Quantity"]), key=f"e_qty_{entry_id}")
                        e_remarks = st.text_input("📝 Remarks", value=er["Remarks"], key=f"e_remark_{entry_id}")
                        e_status = st.selectbox("📂 Status", ["Current", "Future"], index=0 if er["Status"] == "Current" else 1, key=f"e_status_{entry_id}")
                        e_pending = st.checkbox("❗ Pending", value=er["Pending"], key=f"e_pending_{entry_id}")
    
                        save_col, cancel_col = st.columns(2)
                        with save_col:
                            submit = st.form_submit_button("💾 Save Changes", type="primary")
                        with cancel_col:
                            cancel = st.form_submit_button("❌ Cancel")
    
                        if submit:
                            for col, val in [
                                ("Date", e_date.strftime("%Y-%m-%d")),
                                ("Size (mm)", e_size),
                                ("Type", e_type),
                                ("Quantity", e_qty),
                                ("Remarks", e_remarks),
                                ("Status", e_status),
                                ("Pending", e_pending)
                            ]:
                                st.session_state.data.at[match_idx, col] = val
                            st.session_state.editing = None
                            auto_save_to_gsheet()
                            st.rerun()
    
                        if cancel:
                            st.session_state.editing = None
                            st.rerun()
    # === TAB 3: Rotor Trend ===

        
      
      
        # === TAB 3: Rotor Chatbot ===
    # === TAB 3: Rotor Chatbot ===
    # === TAB 3: Rotor Chatbot ===
    # === TAB 3: Rotor Chatbot ===
   # === TAB 3: Rotor Chatbot ===
    with tabs[2]:
      st.subheader("💬 Rotor Chatbot Lite")
      
      # =========================
      # FIXED RATES MANAGEMENT
      # =========================
      if 'fixed_prices' not in st.session_state:
          st.session_state.fixed_prices = {
              1803: 460,    # ₹460 per rotor
              2003: 511,    # ₹511 per rotor
              35: 210,      # ₹210 per rotor
              40: 265,      # ₹265 per rotor
              50: 293,      # ₹293 per rotor
              70: 398       # ₹398 per rotor
          }
      
      if 'base_rate_per_mm' not in st.session_state:
          st.session_state.base_rate_per_mm = 4.10
      
      BASE_RATE_PER_MM = st.session_state.base_rate_per_mm
      
      with st.expander("⚙️ Edit Fixed Rates", expanded=False):
          st.write("Edit fixed prices for specific rotor sizes:")
          
          rates_data = []
          for size, price in sorted(st.session_state.fixed_prices.items()):
              rates_data.append({
                  'Size (mm)': size,
                  'Price (₹)': price
              })
          
          rates_df = pd.DataFrame(rates_data)
          
          edited_df = st.data_editor(
              rates_df,
              num_rows="dynamic",
              column_config={
                  "Size (mm)": st.column_config.NumberColumn(
                      "Size (mm)",
                      help="Rotor size in mm",
                      min_value=1,
                      step=1
                  ),
                  "Price (₹)": st.column_config.NumberColumn(
                      "Price (₹)",
                      help="Price per rotor in Rupees",
                      min_value=0,
                      step=10
                  )
              },
              hide_index=True,
              use_container_width=True
          )
          
          # Base Rate Per MM editing
          st.divider()
          st.write("**Edit Base Rate Per MM:**")
          new_base_rate = st.number_input(
              "Base Rate (₹ per mm)",
              value=float(st.session_state.base_rate_per_mm),
              min_value=0.00,
              step=0.2,
              format="%.2f",
              key="base_rate_editor"
          )
          
          col1, col2 = st.columns(2)
          
          with col1:
              if st.button("💾 Update All Rates", type="primary"):
                  try:
                      # Update fixed rates with validation
                      new_prices = {}
                      valid_rows = 0
                      
                      for _, row in edited_df.iterrows():
                          # Check if both values are numeric
                          try:
                              size_val = row['Size (mm)']
                              price_val = row['Price (₹)']
                              
                              # Skip rows with NaN or None values
                              if pd.isna(size_val) or pd.isna(price_val):
                                  continue
                                  
                              # Convert to appropriate types
                              size = int(float(size_val))
                              price = int(float(price_val))
                              
                              # Validate positive values
                              if size > 0 and price >= 0:
                                  new_prices[size] = price
                                  valid_rows += 1
                              else:
                                  st.warning(f"Skipping row with invalid values: Size={size_val}, Price={price_val}")
                                  
                          except (ValueError, TypeError) as e:
                              st.warning(f"Skipping row with invalid data: {row.to_dict()}")
                              continue
                      
                      # Only update if we have valid data
                      if valid_rows > 0 or len(new_prices) > 0:
                          st.session_state.fixed_prices = new_prices
                      
                      # Update base rate
                      st.session_state.base_rate_per_mm = new_base_rate
                      
                      if valid_rows > 0:
                          st.success(f"✅ Updated {len(new_prices)} fixed rates and base rate to ₹{new_base_rate:.1f} per mm!")
                      else:
                          st.success(f"✅ Updated base rate to ₹{new_base_rate:.1f} per mm (no valid fixed rates to update)")
                      
                      st.rerun()
                      
                  except Exception as e:
                      st.error(f"Error updating rates: {str(e)}")
                      st.info("Please check that all inputs are valid numbers")
          
          with col2:
              if st.button("🔄 Reset to Default Rates"):
                  st.session_state.fixed_prices = {
                      1803: 430,
                      2003: 478,
                      35: 200,
                      40: 220,
                      50: 278,
                      70: 378
                  }
                  st.session_state.base_rate_per_mm = 3.8
                  st.success("✅ Reset to default rates!")
                  st.rerun()
      
      with st.expander("💰 Current Pricing", expanded=True):
          st.write("**Fixed Prices:**")
          for size, price in sorted(st.session_state.fixed_prices.items()):
              st.write(f"- {size}mm: ₹{price} per rotor")
          st.write(f"**Other sizes:** ₹{st.session_state.base_rate_per_mm:.2f} per mm × size")
      
      
      
      # =========================
      # CHAT INPUT
      # =========================
      chat_query = st.text_input(
          "💬 Ask about rotors:",
          placeholder="e.g., history 1803 | size summary 2003 | coming rotors"
      )
      
      if not chat_query:
          st.info("👆 Enter a query above to get started")
          st.stop()
      
      # =========================
      # IMPROVED DATA PREPARATION
      # =========================
      df = st.session_state.data.copy()
      
      # Ensure required columns exist
      required_columns = ['Date', 'Remarks', 'Type', 'Status', 'Size (mm)', 'Quantity']
      for col in required_columns:
          if col not in df.columns:
              df[col] = None
      
      df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
      df['Remarks'] = df['Remarks'].astype(str).str.strip()
      df['Type'] = df['Type'].astype(str).str.strip()
      df['Status'] = df['Status'].astype(str).str.strip()
      df['Size (mm)'] = pd.to_numeric(df['Size (mm)'], errors='coerce')
      df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce')
      
      # Add Pending column if not exists
      if 'Pending' not in df.columns:
          df['Pending'] = False
      
      df = df.dropna(subset=['Date'])
      
      
      query = chat_query.lower().strip()
      
      
      # =========================
      # DETECT SIZE IN QUERY
      # =========================
      target_size = None
      size_matches = re.findall(r'\b(\d+)\b', query)
      for size_str in size_matches:
          size_num = int(size_str)
          if size_num in st.session_state.fixed_prices or size_num > 20:
              target_size = size_num
              break
      
      # =========================
      # DETECT TIME PERIOD IN QUERY
      # =========================
      days_filter = None
      time_patterns = [
          (r'last\s+(\d+)\s+days', 1),  # "last 30 days"
          (r'past\s+(\d+)\s+days', 1),   # "past 30 days"
          (r'(\d+)\s+days', 1),          # "30 days"
          (r'last\s+month', 30),         # "last month"
          (r'this\s+month', 0),          # "this month" (month to date)
          (r'last\s+week', 7),           # "last week"
          (r'this\s+week', 0),           # "this week" (week to date)
          (r'year\s+to\s+date', 0),      # "year to date"
          (r'ytd', 0),                   # "ytd"
      ]
      
      for pattern, default_days in time_patterns:
          match = re.search(pattern, query)
          if match:
              if default_days == 0:  # Special cases
                  if 'month' in pattern:
                      days_filter = 'month_to_date'
                  elif 'week' in pattern:
                      days_filter = 'week_to_date'
                  elif 'year' in pattern or 'ytd' in pattern:
                      days_filter = 'year_to_date'
              else:
                  days_filter = int(match.group(1)) if match.groups() else default_days
              break
      
      # =========================
      # DETECT HISTORY COMMAND
      # =========================
      is_history_query = 'history' in query or 'transactions' in query or 'log' in query
      
      # =========================
      # SPECIAL COMMAND: PRICE LIST
      # =========================
      if 'price list' in query or 'prices' in query:
          st.subheader("💰 Fixed Price List")
          price_data = []
          for size, price in sorted(st.session_state.fixed_prices.items()):
              price_data.append({
                  'Size (mm)': size,
                  'Price per Rotor': f"₹{price}",
                  'Calculation': 'Fixed Price'
              })
          price_df = pd.DataFrame(price_data)
          st.dataframe(price_df, use_container_width=True, hide_index=True)
          st.info(f"For other sizes: ₹{BASE_RATE_PER_MM} per mm × size")
          st.stop()
      
      # =========================
      # IMPROVED MONTH/YEAR DETECTION
      # =========================
      month_name = None
      month_num = None
      year_num = datetime.now().year
      
      month_mapping = {
          'january': 1, 'jan': 1,
          'february': 2, 'feb': 2,
          'march': 3, 'mar': 3,
          'april': 4, 'apr': 4,
          'may': 5,
          'june': 6, 'jun': 6,
          'july': 7, 'jul': 7,
          'august': 8, 'aug': 8,
          'september': 9, 'sep': 9,
          'october': 10, 'oct': 10,
          'november': 11, 'nov': 11,
          'december': 12, 'dec': 12
      }
      
      for month_str, month_val in month_mapping.items():
          if month_str in query:
              month_name = month_str.capitalize()
              month_num = month_val
              break
      
      year_match = re.search(r'\b(20\d{2})\b', query)
      if year_match:
          year_num = int(year_match.group(1))
      
      # =========================
      # IMPROVED BUYER DETECTION
      # =========================
      # =========================
      # IMPROVED BUYER DETECTION
      # =========================
      # =========================
      # SIMPLE BUT EFFECTIVE BUYER DETECTION
      # =========================
      buyers = sorted([b for b in df['Remarks'].unique() if b and str(b).strip() and str(b).lower() not in ['', 'nan', 'none']])
      
      # Convert buyers to lowercase for matching
      buyers_lower = [str(b).lower().strip() for b in buyers]
      
      buyer = None
      buyer_name = None
      clean_query = query.lower().strip()
      
      # Check each buyer name against the query
      for i, b_lower in enumerate(buyers_lower):
          # Split buyer name into words
          buyer_words = b_lower.split()
          
          # Check if any buyer word is in the query
          for buyer_word in buyer_words:
              if len(buyer_word) > 1 and buyer_word in clean_query:
                  buyer = buyers[i]
                  buyer_name = b_lower
                  break
          if buyer:
              break
      
      # If still not found, check the opposite - if any query word is in buyer name
      if not buyer:
          query_words = clean_query.split()
          for word in query_words:
              if len(word) > 2:
                  for i, b_lower in enumerate(buyers_lower):
                      if word in b_lower:
                          buyer = buyers[i]
                          buyer_name = b_lower
                          break
                  if buyer:
                      break
      
      # Debug display
      if buyer:
          st.info(f"🔍 Detected buyer: **{buyer}**")
          
      show_all_buyers = 'all buyers' in clean_query or 'buyers list' in clean_query
      
      # =========================
      # SIMPLE FILTERING
      # =========================
      filtered = df.copy()
      
      if buyer:
          # First filter by buyer
          mask = filtered['Remarks'].notna() & filtered['Remarks'].astype(str).str.lower().str.strip().str.contains(buyer_name, na=False)
          filtered = filtered[mask]
          
          # Show what we found
          if len(filtered) == 0:
              st.warning(f"No transactions found for buyer containing '{buyer_name}'")
              # Try alternative search
              possible_matches = [b for b in buyers if buyer_name in str(b).lower()]
              if possible_matches:
                  st.info(f"Possible matches: {', '.join(possible_matches[:5])}")
      
      # =========================
      # MOVEMENT TYPE DETECTION
      # =========================
      movement = None
      
      if 'pending' in query:
          movement = 'pending'
      elif 'incoming' in query or 'inward' in query:
          movement = 'incoming'
      elif 'outgoing' in query or 'outward' in query:
          movement = 'outgoing'
      elif ('coming' in query and 'rotors' in query) or ('future' in query and 'inward' in query):
          movement = 'coming_datewise'
      elif 'coming' in query or 'future' in query:
          movement = 'coming'
      elif 'stock' in query and 'alert' in query:
          movement = 'stock_alert'
      elif 'summary' in query:
          movement = 'summary'
      
      # =========================
      # NEW ESTIMATION FUNCTIONS
      # =========================
      def calculate_value(size_mm, quantity):
          if pd.isna(size_mm) or pd.isna(quantity):
              return 0
          size_int = int(size_mm)
          if size_int in st.session_state.fixed_prices:
              return st.session_state.fixed_prices[size_int] * quantity
          else:
              return BASE_RATE_PER_MM * size_int * quantity
      
      def get_price_per_rotor(size_mm):
          if pd.isna(size_mm):
              return 0
          size_int = int(size_mm)
          if size_int in st.session_state.fixed_prices:
              return st.session_state.fixed_prices[size_int]
          else:
              return BASE_RATE_PER_MM * size_int
      
      # =========================
      # SPECIAL CASE: TRANSACTION HISTORY BY SIZE
      # =========================
      # =========================
      # TRANSACTION HISTORY BY SIZE (COMPREHENSIVE)
      # =========================
      if target_size:  # Just check for target_size, no need for is_history_query
          st.subheader(f"📜 Transaction History for Size {target_size}mm")
          
          # Filter for the specific size
          history_df = df[df['Size (mm)'] == target_size].copy()
          
          if history_df.empty:
              st.info(f"No transaction history found for size {target_size}mm")
              st.stop()
          
          # Apply time filter if specified
          if days_filter:
              if isinstance(days_filter, int):
                  cutoff_date = datetime.now() - timedelta(days=days_filter)
                  history_df = history_df[history_df['Date'] >= cutoff_date]
                  time_desc = f"Last {days_filter} days"
              elif days_filter == 'month_to_date':
                  today = datetime.now()
                  first_day = today.replace(day=1)
                  history_df = history_df[history_df['Date'] >= first_day]
                  time_desc = "This month (to date)"
              elif days_filter == 'week_to_date':
                  today = datetime.now()
                  start_of_week = today - timedelta(days=today.weekday())
                  history_df = history_df[history_df['Date'] >= start_of_week]
                  time_desc = "This week (to date)"
              elif days_filter == 'year_to_date':
                  today = datetime.now()
                  first_day_year = today.replace(month=1, day=1)
                  history_df = history_df[history_df['Date'] >= first_day_year]
                  time_desc = "Year to date"
          else:
              time_desc = "All time"
          
          # Sort by date (newest first)
          history_df = history_df.sort_values('Date', ascending=False)
          
          price_per = get_price_per_rotor(target_size)
          
          # Calculate summary metrics
          total_inward = history_df[history_df['Type'] == 'Inward']['Quantity'].sum()
          total_outgoing = history_df[history_df['Type'] == 'Outgoing']['Quantity'].sum()
          total_transactions = len(history_df)
          
          col1, col2, col3, col4 = st.columns(4)
          with col1:
              st.metric("Total Inward", f"{int(total_inward)}")
          with col2:
              st.metric("Total Outgoing", f"{int(total_outgoing)}")
          with col3:
              st.metric("Net Change", f"{int(total_inward - total_outgoing)}")
          with col4:
              st.metric("Transactions", total_transactions)
          
          st.info(f"**{time_desc}** · Price: ₹{price_per} per rotor")
          
          # Display filters
          col1, col2, col3 = st.columns(3)
          with col1:
              show_type = st.selectbox(
                  "Filter by type:",
                  ["All", "Inward", "Outgoing"],
                  key="history_type"
              )
          with col2:
              show_status = st.selectbox(
                  "Filter by status:",
                  ["All", "Current", "Future"],
                  key="history_status"
              )
          with col3:
              show_pending = st.selectbox(
                  "Filter pending:",
                  ["All", "Pending Only", "Non-Pending Only"],
                  key="history_pending"
              )
          
          # Apply filters
          filtered_history = history_df.copy()
          
          if show_type != "All":
              filtered_history = filtered_history[filtered_history['Type'] == show_type]
          
          if show_status != "All":
              filtered_history = filtered_history[filtered_history['Status'] == show_status]
          
          if show_pending == "Pending Only":
              filtered_history = filtered_history[filtered_history['Pending'] == True]
          elif show_pending == "Non-Pending Only":
              filtered_history = filtered_history[filtered_history['Pending'] == False]
          
          # Calculate value for each transaction
          filtered_history['Value'] = filtered_history.apply(
              lambda row: calculate_value(row['Size (mm)'], row['Quantity']), axis=1
          )
          
          # Format for display
          display_history = filtered_history.copy()
          display_history['Date'] = display_history['Date'].dt.strftime('%Y-%m-%d')
          display_history['Value'] = display_history['Value'].apply(lambda x: f"₹{x:,.2f}")
          display_history['Pending'] = display_history['Pending'].apply(lambda x: 'Yes' if x else 'No')
          
          # Display transaction history
          st.subheader(f"📋 Transaction Details ({len(filtered_history)} records)")
          
          st.dataframe(
              display_history[['Date', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending', 'Value']]
              .rename(columns={
                  'Type': 'Movement',
                  'Quantity': 'Qty',
                  'Remarks': 'Buyer',
                  'Pending': 'Is Pending',
                  'Value': 'Total Value'
              }),
              use_container_width=True,
              hide_index=True
          )
          
          # Monthly summary
          st.subheader("📅 Monthly Summary")
          
          # Create monthly pivot
          history_df['MonthYear'] = history_df['Date'].dt.strftime('%b %Y')
          monthly_pivot = history_df.pivot_table(
              index='MonthYear',
              columns='Type',
              values='Quantity',
              aggfunc='sum',
              fill_value=0
          ).reset_index()
          
          if 'Inward' in monthly_pivot.columns and 'Outgoing' in monthly_pivot.columns:
              monthly_pivot['Net'] = monthly_pivot['Inward'] - monthly_pivot['Outgoing']
              monthly_pivot['Net'] = monthly_pivot['Net'].astype(int)
          elif 'Inward' in monthly_pivot.columns:
              monthly_pivot['Net'] = monthly_pivot['Inward']
          elif 'Outgoing' in monthly_pivot.columns:
              monthly_pivot['Net'] = -monthly_pivot['Outgoing']
          
          monthly_pivot = monthly_pivot.sort_values('MonthYear', ascending=False)
          
          # Add value columns
          if 'Inward' in monthly_pivot.columns:
              monthly_pivot['Inward Value'] = monthly_pivot['Inward'] * price_per
          if 'Outgoing' in monthly_pivot.columns:
              monthly_pivot['Outgoing Value'] = monthly_pivot['Outgoing'] * price_per
          
          # Format for display
          display_monthly = monthly_pivot.copy()
          if 'Inward Value' in display_monthly.columns:
              display_monthly['Inward Value'] = display_monthly['Inward Value'].apply(lambda x: f"₹{x:,.0f}")
          if 'Outgoing Value' in display_monthly.columns:
              display_monthly['Outgoing Value'] = display_monthly['Outgoing Value'].apply(lambda x: f"₹{x:,.0f}")
          
          st.dataframe(display_monthly, use_container_width=True, hide_index=True)
          
          # Top buyers
          st.subheader("👥 Top Buyers")
          
          if 'Outgoing' in history_df.columns:
              buyer_summary = history_df[history_df['Type'] == 'Outgoing'].groupby('Remarks').agg({
                  'Quantity': 'sum',
                  'Date': ['min', 'max']
              }).reset_index()
              
              buyer_summary.columns = ['Buyer', 'Total Qty', 'First Purchase', 'Last Purchase']
              buyer_summary = buyer_summary.sort_values('Total Qty', ascending=False)
              
              # Calculate total value
              buyer_summary['Total Value'] = buyer_summary['Total Qty'] * price_per
              buyer_summary['Total Value'] = buyer_summary['Total Value'].apply(lambda x: f"₹{x:,.0f}")
              buyer_summary['First Purchase'] = pd.to_datetime(buyer_summary['First Purchase']).dt.strftime('%Y-%m-%d')
              buyer_summary['Last Purchase'] = pd.to_datetime(buyer_summary['Last Purchase']).dt.strftime('%Y-%m-%d')
              
              st.dataframe(buyer_summary, use_container_width=True, hide_index=True)
          
          # Stock timeline visualization
          st.subheader("📈 Stock Timeline")
          
          # Calculate cumulative stock
          timeline_df = history_df.sort_values('Date').copy()
          timeline_df['Net Qty'] = timeline_df.apply(
              lambda x: x['Quantity'] if x['Type'] == 'Inward' else -x['Quantity'], axis=1
          )
          timeline_df['Cumulative Stock'] = timeline_df['Net Qty'].cumsum()
          
          # Resample to monthly for cleaner chart
          timeline_df.set_index('Date', inplace=True)
          monthly_stock = timeline_df.resample('M')['Cumulative Stock'].last().reset_index()
          
          if not monthly_stock.empty:
              chart = alt.Chart(monthly_stock).mark_line(point=True).encode(
                  x=alt.X('Date:T', title='Date'),
                  y=alt.Y('Cumulative Stock:Q', title='Stock Level'),
                  tooltip=['Date', 'Cumulative Stock']
              ).properties(
                  height=300,
                  title=f'Stock Level Over Time for {target_size}mm'
              )
              st.altair_chart(chart, use_container_width=True)
          
          st.stop()
      
      # =========================
      # SPECIAL CASE: SIZE PENDING
      # =========================
      if target_size and ('pending' in query or 'size pending' in query):
          st.subheader(f"⏳ Pending Orders for Size {target_size}mm")
          
          pending_df = df[
              (df['Size (mm)'] == target_size) &
              (df['Type'] == 'Outgoing') &
              (df['Pending'] == True)
          ].copy()
          
          if pending_df.empty:
              st.info(f"No pending orders found for size {target_size}mm")
              st.stop()
          
          # Calculate value
          pending_df['Value'] = pending_df.apply(
              lambda row: calculate_value(row['Size (mm)'], row['Quantity']), axis=1
          )
          
          price_per = get_price_per_rotor(target_size)
          total_qty = pending_df['Quantity'].sum()
          total_value = pending_df['Value'].sum()
          
          col1, col2, col3 = st.columns(3)
          with col1:
              st.metric("Total Pending Qty", f"{int(total_qty)}")
          with col2:
              st.metric("Total Value", f"₹{total_value:,.0f}")
          with col3:
              st.metric("Price per Rotor", f"₹{price_per}")
          
          # Format for display
          display_df = pending_df.copy()
          display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
          display_df['Value'] = display_df['Value'].apply(lambda x: f"₹{x:,.0f}")
          
          st.dataframe(
              display_df[['Date', 'Remarks', 'Quantity', 'Status', 'Value']]
              .rename(columns={
                  'Remarks': 'Buyer',
                  'Quantity': 'Qty',
                  'Value': 'Total Value'
              }),
              use_container_width=True,
              hide_index=True
          )
          
          # Group by buyer
          buyer_summary = pending_df.groupby('Remarks').agg({
              'Quantity': 'sum',
              'Value': 'sum'
          }).reset_index()
          
          buyer_summary['Value'] = buyer_summary['Value'].apply(lambda x: f"₹{x:,.0f}")
          
          st.subheader("📊 Buyer-wise Summary")
          st.dataframe(
              buyer_summary.rename(columns={
                  'Remarks': 'Buyer',
                  'Quantity': 'Total Qty',
                  'Value': 'Total Value'
              }),
              use_container_width=True,
              hide_index=True
          )
          
          st.stop()
      
      # =========================
      # SPECIAL CASE: SIZE SUMMARY
      # =========================
      if target_size and ('summary' in query or 'size summary' in query) and not is_history_query:
          st.subheader(f"📊 Summary for Size {target_size}mm")
          
          # Filter for the specific size
          summary_df = df[df['Size (mm)'] == target_size].copy()
          
          if summary_df.empty:
              st.info(f"No data found for size {target_size}mm")
              st.stop()
          
          # Apply time filter if specified
          if days_filter:
              if isinstance(days_filter, int):
                  cutoff_date = datetime.now() - timedelta(days=days_filter)
                  summary_df = summary_df[summary_df['Date'] >= cutoff_date]
                  time_desc = f"Last {days_filter} days"
              elif days_filter == 'month_to_date':
                  today = datetime.now()
                  first_day = today.replace(day=1)
                  summary_df = summary_df[summary_df['Date'] >= first_day]
                  time_desc = "This month (to date)"
              elif days_filter == 'week_to_date':
                  today = datetime.now()
                  start_of_week = today - timedelta(days=today.weekday())
                  summary_df = summary_df[summary_df['Date'] >= start_of_week]
                  time_desc = "This week (to date)"
              elif days_filter == 'year_to_date':
                  today = datetime.now()
                  first_day_year = today.replace(month=1, day=1)
                  summary_df = summary_df[summary_df['Date'] >= first_day_year]
                  time_desc = "Year to date"
          else:
              time_desc = "All time"
          
          price_per = get_price_per_rotor(target_size)
          
          # Calculate metrics
          total_inward = summary_df[summary_df['Type'] == 'Inward']['Quantity'].sum()
          total_outgoing = summary_df[summary_df['Type'] == 'Outgoing']['Quantity'].sum()
          total_pending = summary_df[
              (summary_df['Type'] == 'Outgoing') & 
              (summary_df['Pending'] == True)
          ]['Quantity'].sum()
          
          net_stock = total_inward - total_outgoing + total_pending
          
          col1, col2, col3, col4 = st.columns(4)
          with col1:
              st.metric("Total Inward", f"{int(total_inward)}")
          with col2:
              st.metric("Total Outgoing", f"{int(total_outgoing)}")
          with col3:
              st.metric("Pending Orders", f"{int(total_pending)}")
          with col4:
              st.metric("Net Stock", f"{int(net_stock)}")
          
          st.info(f"**{time_desc}** · Price: ₹{price_per} per rotor")
          
          # Value calculations
          inward_value = calculate_value(target_size, total_inward)
          outgoing_value = calculate_value(target_size, total_outgoing)
          pending_value = calculate_value(target_size, total_pending)
          
          col1, col2, col3 = st.columns(3)
          with col1:
              st.metric("Inward Value", f"₹{inward_value:,.0f}")
          with col2:
              st.metric("Outgoing Value", f"₹{outgoing_value:,.0f}")
          with col3:
              st.metric("Pending Value", f"₹{pending_value:,.0f}")
          
          # Top buyers
          st.subheader("👥 Top Buyers")
          
          if len(summary_df[summary_df['Type'] == 'Outgoing']) > 0:
              buyer_summary = summary_df[summary_df['Type'] == 'Outgoing'].groupby('Remarks').agg({
                  'Quantity': 'sum'
              }).reset_index()
              
              buyer_summary['Value'] = buyer_summary['Quantity'] * price_per
              buyer_summary = buyer_summary.sort_values('Quantity', ascending=False)
              buyer_summary['Value'] = buyer_summary['Value'].apply(lambda x: f"₹{x:,.0f}")
              
              st.dataframe(
                  buyer_summary.rename(columns={
                      'Remarks': 'Buyer',
                      'Quantity': 'Total Qty',
                      'Value': 'Total Value'
                  }),
                  use_container_width=True,
                  hide_index=True
              )
          
          st.stop()
      
      # =========================
      # =========================
      # SIZE-SPECIFIC COMING ROTORS
      # =========================
      if target_size and 'coming' in query and 'size' in query:
          st.subheader(f"📅 Coming Rotors for Size {target_size}mm")
          
          coming_df = df[
              (df['Size (mm)'] == target_size) &
              (df['Status'] == 'Future') &
              (df['Type'] == 'Inward')
          ].copy()
          
          if coming_df.empty:
              st.info(f"No future rotors coming for size {target_size}mm")
              st.stop()
          
          # Sort by date
          coming_df = coming_df.sort_values('Date')
          
          # Calculate value
          coming_df['Value'] = coming_df.apply(
              lambda row: calculate_value(row['Size (mm)'], row['Quantity']), axis=1
          )
          
          price_per = get_price_per_rotor(target_size)
          
          # Summary metrics
          total_qty = coming_df['Quantity'].sum()
          total_value = coming_df['Value'].sum()
          unique_dates = coming_df['Date'].nunique()
          unique_suppliers = coming_df['Remarks'].nunique()
          
          col1, col2, col3, col4 = st.columns(4)
          with col1:
              st.metric("Total Coming", f"{int(total_qty)}")
          with col2:
              st.metric("Total Value", f"₹{total_value:,.0f}")
          with col3:
              st.metric("Delivery Dates", unique_dates)
          with col4:
              st.metric("Suppliers", unique_suppliers)
          
          st.info(f"**Price:** ₹{price_per} per rotor")
          
          # Date-wise summary
          st.subheader("📆 Date-wise Schedule")
          
          date_summary = coming_df.groupby('Date').agg({
              'Quantity': 'sum',
              'Value': 'sum',
              'Remarks': lambda x: ', '.join(sorted(set([str(r) for r in x if str(r).strip()])))
          }).reset_index()
          
          date_summary = date_summary.sort_values('Date')
          date_summary['Date'] = date_summary['Date'].dt.strftime('%Y-%m-%d')
          date_summary['Value'] = date_summary['Value'].apply(lambda x: f"₹{x:,.0f}")
          
          st.dataframe(
              date_summary.rename(columns={
                  'Date': 'Expected Date',
                  'Quantity': 'Qty',
                  'Value': 'Total Value',
                  'Remarks': 'Suppliers'
              }),
              use_container_width=True,
              hide_index=True
          )
          
          # Supplier-wise breakdown
          st.subheader("🏢 Supplier-wise Breakdown")
          
          supplier_summary = coming_df.groupby('Remarks').agg({
              'Quantity': 'sum',
              'Value': 'sum',
              'Date': lambda x: ', '.join(sorted(set([d.strftime('%Y-%m-%d') for d in x])))
          }).reset_index()
          
          supplier_summary = supplier_summary.sort_values('Quantity', ascending=False)
          supplier_summary['Value'] = supplier_summary['Value'].apply(lambda x: f"₹{x:,.0f}")
          
          st.dataframe(
              supplier_summary.rename(columns={
                  'Remarks': 'Supplier',
                  'Quantity': 'Total Qty',
                  'Value': 'Total Value',
                  'Date': 'Delivery Dates'
              }),
              use_container_width=True,
              hide_index=True
          )
          
          # Detailed transactions
          with st.expander("📋 View All Transactions"):
              display_df = coming_df.copy()
              display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
              display_df['Value'] = display_df['Value'].apply(lambda x: f"₹{x:,.0f}")
              
              st.dataframe(
                  display_df[['Date', 'Quantity', 'Remarks', 'Status', 'Value']]
                  .rename(columns={
                      'Date': 'Expected Date',
                      'Quantity': 'Qty',
                      'Remarks': 'Supplier',
                      'Value': 'Total Value'
                  }),
                  use_container_width=True,
                  hide_index=True
              )
          
          # Timeline visualization
          if len(coming_df) > 1:
              st.subheader("📈 Delivery Timeline")
              
              timeline_data = coming_df.groupby('Date')['Quantity'].sum().reset_index()
              timeline_data = timeline_data.sort_values('Date')
              
              chart = alt.Chart(timeline_data).mark_bar().encode(
                  x=alt.X('Date:T', title='Expected Date'),
                  y=alt.Y('Quantity:Q', title='Quantity'),
                  tooltip=['Date', 'Quantity']
              ).properties(
                  height=300,
                  title=f'Delivery Schedule for Size {target_size}mm'
              )
              st.altair_chart(chart, use_container_width=True)
          
          st.stop()
      
      # =========================
      # COMING ROTORS TRANSACTION HISTORY
      # =========================
      elif movement == 'coming_datewise' or (movement == 'coming' and 'history' in query):
          # ... existing coming rotors transaction history code ...
      # SPECIAL CASE: COMING ROTORS DATE-WISE
      # =========================
     # =========================
      # COMING ROTORS TRANSACTION HISTORY
      # =========================
      
          st.subheader("📜 Coming Rotors Transaction History")
          
          coming_df = df[
              (df['Status'] == 'Future') &
              (df['Type'] == 'Inward')
          ].copy()
          
          if coming_df.empty:
              st.info("No future rotors coming")
              st.stop()
          
          # Sort by date
          coming_df = coming_df.sort_values('Date')
          
          # Calculate value for each transaction
          coming_df['Value'] = coming_df.apply(
              lambda row: calculate_value(row['Size (mm)'], row['Quantity']), axis=1
          )
          
          # Summary metrics
          total_qty = coming_df['Quantity'].sum()
          total_value = coming_df['Value'].sum()
          unique_sizes = coming_df['Size (mm)'].nunique()
          unique_suppliers = coming_df['Remarks'].nunique()
          
          col1, col2, col3, col4 = st.columns(4)
          with col1:
              st.metric("Total Coming", f"{int(total_qty)}")
          with col2:
              st.metric("Total Value", f"₹{total_value:,.0f}")
          with col3:
              st.metric("Different Sizes", unique_sizes)
          with col4:
              st.metric("Suppliers", unique_suppliers)
          
          # Filters
          col1, col2 = st.columns(2)
          with col1:
              # Size filter
              all_sizes = sorted(coming_df['Size (mm)'].unique())
              size_filter = st.multiselect(
                  "Filter by Size:",
                  options=all_sizes,
                  default=all_sizes,
                  key="coming_size_filter"
              )
          with col2:
              # Supplier filter
              all_suppliers = sorted([s for s in coming_df['Remarks'].unique() if s and str(s).strip()])
              supplier_filter = st.multiselect(
                  "Filter by Supplier:",
                  options=all_suppliers,
                  default=all_suppliers,
                  key="coming_supplier_filter"
              )
          
          # Apply filters
          filtered_coming = coming_df[
              (coming_df['Size (mm)'].isin(size_filter)) &
              (coming_df['Remarks'].isin(supplier_filter))
          ].copy()
          
          if filtered_coming.empty:
              st.warning("No transactions match your filters")
              st.stop()
          
          # Display transaction history
          st.subheader(f"📋 Transaction Details ({len(filtered_coming)} records)")
          
          display_coming = filtered_coming.copy()
          display_coming['Date'] = display_coming['Date'].dt.strftime('%Y-%m-%d')
          display_coming['Value'] = display_coming['Value'].apply(lambda x: f"₹{x:,.0f}")
          display_coming['Price per Rotor'] = display_coming['Size (mm)'].apply(get_price_per_rotor)
          display_coming['Price per Rotor'] = display_coming['Price per Rotor'].apply(lambda x: f"₹{x:,.0f}")
          
          st.dataframe(
              display_coming[['Date', 'Size (mm)', 'Quantity', 'Price per Rotor', 'Remarks', 'Value']]
              .rename(columns={
                  'Size (mm)': 'Size',
                  'Quantity': 'Qty',
                  'Remarks': 'Supplier',
                  'Value': 'Total Value'
              }),
              use_container_width=True,
              hide_index=True
          )
          
          # Group by date
          st.subheader("📅 Date-wise Summary")
          
          date_summary = filtered_coming.groupby('Date').agg({
              'Size (mm)': lambda x: ', '.join(map(str, sorted(set(x)))),
              'Quantity': 'sum',
              'Value': 'sum',
              'Remarks': lambda x: ', '.join(sorted(set([str(r) for r in x if str(r).strip()])))
          }).reset_index()
          
          date_summary = date_summary.sort_values('Date')
          date_summary['Date'] = date_summary['Date'].dt.strftime('%Y-%m-%d')
          date_summary['Value'] = date_summary['Value'].apply(lambda x: f"₹{x:,.0f}")
          
          st.dataframe(
              date_summary.rename(columns={
                  'Date': 'Arrival Date',
                  'Size (mm)': 'Sizes',
                  'Quantity': 'Total Qty',
                  'Value': 'Total Value',
                  'Remarks': 'Suppliers'
              }),
              use_container_width=True,
              hide_index=True
          )
          
          # Size-wise breakdown
          st.subheader("📊 Size-wise Summary")
          
          size_summary = filtered_coming.groupby('Size (mm)').agg({
              'Quantity': 'sum',
              'Value': 'sum'
          }).reset_index()
          
          size_summary = size_summary.sort_values('Size (mm)')
          size_summary['Value'] = size_summary['Value'].apply(lambda x: f"₹{x:,.0f}")
          size_summary['Price per Rotor'] = size_summary['Size (mm)'].apply(get_price_per_rotor)
          size_summary['Price per Rotor'] = size_summary['Price per Rotor'].apply(lambda x: f"₹{x:,.0f}")
          
          st.dataframe(
              size_summary.rename(columns={
                  'Size (mm)': 'Size',
                  'Quantity': 'Total Qty',
                  'Value': 'Total Value'
              }),
              use_container_width=True,
              hide_index=True
          )
          
          # Supplier-wise breakdown
          st.subheader("🏢 Supplier-wise Summary")
          
          supplier_summary = filtered_coming.groupby('Remarks').agg({
              'Quantity': 'sum',
              'Value': 'sum',
              'Size (mm)': lambda x: ', '.join(map(str, sorted(set(x)))),
              'Date': ['min', 'max']
          }).reset_index()
          
          supplier_summary.columns = ['Supplier', 'Total Qty', 'Total Value', 'Sizes', 'Earliest', 'Latest']
          supplier_summary = supplier_summary.sort_values('Total Qty', ascending=False)
          supplier_summary['Total Value'] = supplier_summary['Total Value'].apply(lambda x: f"₹{x:,.0f}")
          supplier_summary['Earliest'] = pd.to_datetime(supplier_summary['Earliest']).dt.strftime('%Y-%m-%d')
          supplier_summary['Latest'] = pd.to_datetime(supplier_summary['Latest']).dt.strftime('%Y-%m-%d')
          
          st.dataframe(supplier_summary, use_container_width=True, hide_index=True)
          
          st.stop()

      
      elif movement == 'coming':
          st.subheader("📅 Coming Rotors Summary")
          
          coming_df = df[
              (df['Status'] == 'Future') &
              (df['Type'] == 'Inward')
          ].copy()
          
          if coming_df.empty:
              st.info("No future rotors coming")
              st.stop()
          
          # Calculate value
          coming_df['Value'] = coming_df.apply(
              lambda row: calculate_value(row['Size (mm)'], row['Quantity']), axis=1
          )
          
          # Group by date
          coming_df['Date'] = pd.to_datetime(coming_df['Date'])
          date_summary = coming_df.groupby('Date').agg({
              'Size (mm)': lambda x: ', '.join(map(str, sorted(set(x)))),
              'Quantity': 'sum',
              'Value': 'sum',
              'Remarks': lambda x: ', '.join(sorted(set([str(r) for r in x if str(r).strip()])))
          }).reset_index()
          
          date_summary = date_summary.sort_values('Date')
          
          total_qty = date_summary['Quantity'].sum()
          total_value = date_summary['Value'].sum()
          
          col1, col2 = st.columns(2)
          with col1:
              st.metric("Total Coming Rotors", f"{int(total_qty)}")
          with col2:
              st.metric("Total Value", f"₹{total_value:,.0f}")
          
          # Format for display
          display_df = date_summary.copy()
          display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
          display_df['Value'] = display_df['Value'].apply(lambda x: f"₹{x:,.0f}")
          
          st.dataframe(
              display_df.rename(columns={
                  'Date': 'Arrival Date',
                  'Size (mm)': 'Sizes',
                  'Quantity': 'Total Qty',
                  'Value': 'Total Value',
                  'Remarks': 'Suppliers'
              }),
              use_container_width=True,
              hide_index=True
          )
          
          # Size-wise breakdown
          st.subheader("📊 Size-wise Breakdown")
          
          size_summary = coming_df.groupby('Size (mm)').agg({
              'Quantity': 'sum',
              'Value': 'sum'
          }).reset_index()
          
          size_summary['Value'] = size_summary['Value'].apply(lambda x: f"₹{x:,.0f}")
          
          st.dataframe(
              size_summary.rename(columns={
                  'Size (mm)': 'Size',
                  'Quantity': 'Total Qty',
                  'Value': 'Total Value'
              }),
              use_container_width=True,
              hide_index=True
          )
          
          st.stop()
      
      # =========================
      # QUERY PROCESSING LOGIC FOR OTHER CASES
      # =========================
      
      # CASE 1: ALL BUYERS LIST
      if show_all_buyers:
          st.subheader("👥 All Buyers List")
          
          # Get unique buyers with their activity
          buyer_activity = df[df['Type'] == 'Outgoing'].groupby('Remarks').agg({
              'Date': ['min', 'max', 'count'],
              'Quantity': 'sum'
          }).reset_index()
          
          buyer_activity.columns = ['Buyer', 'First Purchase', 'Last Purchase', 'Transactions', 'Total Qty']
          
          # Calculate total value for each buyer
          buyer_activity['Total Value'] = 0
          for idx, row in buyer_activity.iterrows():
              buyer_df = df[df['Remarks'] == row['Buyer']]
              total_value = 0
              for _, trans in buyer_df.iterrows():
                  total_value += calculate_value(trans['Size (mm)'], trans['Quantity'])
              buyer_activity.at[idx, 'Total Value'] = total_value
          
          # Sort by total value
          buyer_activity = buyer_activity.sort_values('Total Value', ascending=False)
          
          # Format for display
          display_buyers = buyer_activity.copy()
          display_buyers['First Purchase'] = pd.to_datetime(display_buyers['First Purchase']).dt.strftime('%Y-%m-%d')
          display_buyers['Last Purchase'] = pd.to_datetime(display_buyers['Last Purchase']).dt.strftime('%Y-%m-%d')
          display_buyers['Total Value'] = display_buyers['Total Value'].apply(lambda x: f"₹{x:,.0f}")
          
          st.dataframe(display_buyers, use_container_width=True, hide_index=True)
          
          # Summary stats
          col1, col2, col3 = st.columns(3)
          with col1:
              st.metric("Total Buyers", len(buyer_activity))
          with col2:
              total_buyer_qty = buyer_activity['Total Qty'].sum()
              st.metric("Total Rotors Sold", f"{int(total_buyer_qty)}")
          with col3:
              total_buyer_value = sum([float(v.replace('₹', '').replace(',', '')) for v in display_buyers['Total Value']])
              st.metric("Total Sales Value", f"₹{total_buyer_value:,.0f}")
          
          st.stop()
      
      # CASE 2: STOCK ALERTS
      elif movement == 'stock_alert':
          st.subheader("⚠️ Stock Alerts")
          
          # Calculate current stock for each size
          stock_data = []
          
          for size in df['Size (mm)'].unique():
              if pd.isna(size):
                  continue
                  
              size_df = df[df['Size (mm)'] == size]
              
              # Calculate net stock (inward - outgoing where not pending)
              total_inward = size_df[size_df['Type'] == 'Inward']['Quantity'].sum()
              total_outgoing = size_df[(size_df['Type'] == 'Outgoing') & (~size_df['Pending'])]['Quantity'].sum()
              current_stock = total_inward - total_outgoing
              
              # Calculate pending outgoing
              pending_outgoing = size_df[(size_df['Type'] == 'Outgoing') & (size_df['Pending'])]['Quantity'].sum()
              
              # Calculate incoming
              incoming = size_df[(size_df['Type'] == 'Inward') & (size_df['Status'] == 'Future')]['Quantity'].sum()
              
              stock_data.append({
                  'Size (mm)': size,
                  'Current Stock': current_stock,
                  'Pending Orders': pending_outgoing,
                  'Incoming': incoming,
                  'Available After Pending': current_stock - pending_outgoing
              })
          
          stock_df = pd.DataFrame(stock_data)
          
          # Filter for low stock (less than 10)
          low_stock = stock_df[stock_df['Current Stock'] < 10].copy()
          
          if low_stock.empty:
              st.success("✅ All stock levels are healthy!")
          else:
              st.warning(f"⚠️ {len(low_stock)} sizes have low stock!")
              
              # Calculate value for low stock items
              low_stock['Value'] = low_stock.apply(
                  lambda row: calculate_value(row['Size (mm)'], row['Current Stock']), axis=1
              )
              
              # Format for display
              display_low = low_stock.copy()
              display_low['Value'] = display_low['Value'].apply(lambda x: f"₹{x:,.0f}")
              
              st.dataframe(
                  display_low[['Size (mm)', 'Current Stock', 'Pending Orders', 'Incoming', 'Available After Pending', 'Value']]
                  .rename(columns={
                      'Size (mm)': 'Size',
                      'Current Stock': 'Current',
                      'Pending Orders': 'Pending',
                      'Available After Pending': 'Available'
                  }),
                  use_container_width=True,
                  hide_index=True
              )
          
          # Show all stock levels
          with st.expander("📊 View All Stock Levels"):
              stock_df['Value'] = stock_df.apply(
                  lambda row: calculate_value(row['Size (mm)'], row['Current Stock']), axis=1
              )
              
              display_all = stock_df.sort_values('Current Stock').copy()
              display_all['Value'] = display_all['Value'].apply(lambda x: f"₹{x:,.0f}")
              
              st.dataframe(
                  display_all[['Size (mm)', 'Current Stock', 'Pending Orders', 'Incoming', 'Available After Pending', 'Value']]
                  .rename(columns={
                      'Size (mm)': 'Size',
                      'Current Stock': 'Current',
                      'Pending Orders': 'Pending',
                      'Available After Pending': 'Available'
                  }),
                  use_container_width=True,
                  hide_index=True
              )
          
          st.stop()
      
      # CASE 3: REGULAR QUERIES
      filtered = df.copy()
      
      # Apply buyer filter
      if buyer:
          filtered = filtered[filtered['Remarks'].str.lower() == str(buyer).lower()]
      
      # Apply movement filter
      if movement == 'pending':
          filtered = filtered[
              (filtered['Type'] == 'Outgoing') & 
              (filtered['Pending'] == True)
          ]
      elif movement == 'incoming':
          filtered = filtered[filtered['Type'] == 'Inward']
      elif movement == 'outgoing':
          filtered = filtered[filtered['Type'] == 'Outgoing']
      elif movement == 'coming':
          filtered = filtered[filtered['Status'] == 'Future']
      
      # Apply size filter if specified
      if target_size:
          filtered = filtered[filtered['Size (mm)'] == target_size]
      
      # Apply date filters
      if month_num:
          start_date = datetime(year_num, month_num, 1)
          if month_num == 12:
              end_date = datetime(year_num, month_num, 31)
          else:
              end_date = datetime(year_num, month_num + 1, 1) - timedelta(days=1)
          
          filtered = filtered[
              (filtered['Date'] >= start_date) &
              (filtered['Date'] <= end_date)
          ]
      
      # If user asks for yearly summary
      elif 'summary' in query and year_num:
          start_date = datetime(year_num, 1, 1)
          end_date = datetime(year_num, 12, 31)
          filtered = filtered[
              (filtered['Date'] >= start_date) &
              (filtered['Date'] <= end_date)
          ]
      
      # Filter out invalid data
      filtered = filtered.dropna(subset=['Size (mm)', 'Quantity'])
      
      if filtered.empty:
          st.warning(f"❌ No matching records found for: '{chat_query}'")
          
          # Suggest similar buyers
          if buyer:
              similar_buyers = [b for b in buyers if str(buyer).lower() in str(b).lower()]
              if similar_buyers:
                  st.info(f"Did you mean: {', '.join(similar_buyers[:3])}")
          
          st.stop()
      
      # =========================
      # CALCULATIONS & DISPLAY WITH NEW PRICING
      # =========================
      # Apply the new pricing logic
      filtered['Estimated Value'] = filtered.apply(
          lambda row: calculate_value(row['Size (mm)'], row['Quantity']), axis=1
      )
      
      # Add price per rotor for display
      filtered['Price per Rotor'] = filtered['Size (mm)'].apply(get_price_per_rotor)
      
      total_rotors = filtered['Quantity'].sum()
      total_value = filtered['Estimated Value'].sum()
      
      # Build informative title
      title_parts = ["📊"]
      
      if buyer:
          title_parts.append(f"**{buyer}**")
      
      if movement:
          movement_display = {
              'pending': 'PENDING ORDERS',
              'incoming': 'INCOMING',
              'outgoing': 'OUTGOING',
              'coming': 'FUTURE ROTORS',
              'summary': 'SUMMARY'
          }
          title_parts.append(f"**{movement_display.get(movement, movement.upper())}**")
      
      if target_size:
          title_parts.append(f"**Size {target_size}mm**")
      
      if month_num:
          title_parts.append(f"**{month_name} {year_num}**")
      elif 'summary' in query:
          title_parts.append(f"**Year {year_num} Summary**")
      
      if not buyer and not movement and not month_num and not target_size:
          title_parts.append("**All Transactions**")
      
      title = " | ".join(title_parts)
      st.markdown(f"## {title}")
      
      # Summary metrics
      col1, col2, col3 = st.columns(3)
      with col1:
          st.metric("Total Rotors", f"{int(total_rotors):,}")
      with col2:
          st.metric("Total Value", f"₹{total_value:,.2f}")
      with col3:
          if not filtered.empty:
              avg_size = filtered['Size (mm)'].mean()
              st.metric("Avg Size", f"{avg_size:.0f} mm")
          else:
              st.metric("Avg Size", "0 mm")
      
      # Show pricing information if size is specified
      if target_size:
          price = get_price_per_rotor(target_size)
          method = "Fixed Price" if target_size in st.session_state.fixed_prices else f"₹{BASE_RATE_PER_MM}/mm × {target_size}mm"
          st.info(f"**Pricing:** {target_size}mm = ₹{price} ({method})")
      elif len(filtered['Size (mm)'].unique()) <= 5:
          st.info("**Pricing Used:**")
          for size in sorted(filtered['Size (mm)'].unique()):
              price = get_price_per_rotor(size)
              method = "Fixed Price" if size in st.session_state.fixed_prices else f"₹{BASE_RATE_PER_MM}/mm × {size}mm"
              st.write(f"- {size}mm: ₹{price} ({method})")
      
      # Grouped display
      if buyer:
          # For single buyer, show detailed breakdown
          display_df = filtered.copy()
          display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
          display_df['Total Value'] = display_df['Estimated Value'].apply(lambda x: f"₹{x:,.2f}")
          display_df['Unit Price'] = display_df['Price per Rotor'].apply(lambda x: f"₹{x:,.0f}")
          
          st.subheader("📋 Detailed Transactions")
          st.dataframe(
              display_df[['Date', 'Type', 'Size (mm)', 'Quantity', 'Unit Price', 'Status', 'Pending', 'Total Value']]
              .rename(columns={
                  'Type': 'Movement',
                  'Size (mm)': 'Size',
                  'Quantity': 'Qty',
                  'Pending': 'Is Pending',
                  'Unit Price': 'Price/Rotor'
              }),
              use_container_width=True,
              hide_index=True
          )
          
          # Size-wise summary for the buyer
          if not target_size:  # Only if size wasn't already filtered
              size_summary = filtered.groupby('Size (mm)').agg({
                  'Quantity': 'sum',
                  'Estimated Value': 'sum'
              }).reset_index()
              
              st.subheader("📊 Size-wise Summary")
              display_size = size_summary.copy()
              display_size['Estimated Value'] = display_size['Estimated Value'].apply(lambda x: f"₹{x:,.2f}")
              st.dataframe(
                  display_size.rename(columns={
                      'Size (mm)': 'Size',
                      'Quantity': 'Total Qty',
                      'Estimated Value': 'Total Value'
                  }),
                  use_container_width=True,
                  hide_index=True
              )
          
      else:
          # For multiple buyers or general queries
          grouped = filtered.groupby(['Remarks', 'Size (mm)']).agg({
              'Quantity': 'sum',
              'Estimated Value': 'sum'
          }).reset_index()
          
          # Calculate price per rotor for each size
          grouped['Price per Rotor'] = grouped['Size (mm)'].apply(get_price_per_rotor)
          grouped['Total Value'] = grouped['Estimated Value'].apply(lambda x: f"₹{x:,.2f}")
          
          st.dataframe(
              grouped[['Remarks', 'Size (mm)', 'Quantity', 'Price per Rotor', 'Total Value']]
              .rename(columns={
                  'Remarks': 'Buyer',
                  'Size (mm)': 'Size (mm)',
                  'Quantity': 'Total Qty',
                  'Price per Rotor': 'Price/Rotor'
              }),
              use_container_width=True,
              hide_index=True
          )
      
      # Additional insights
      with st.expander("📈 Insights"):
          if buyer and movement == 'pending':
              total_pending = filtered[filtered['Pending']]['Quantity'].sum()
              pending_value = filtered[filtered['Pending']]['Estimated Value'].sum()
              st.info(f"**{buyer}** has **{int(total_pending)}** rotors pending worth **₹{pending_value:,.2f}**")
          
          if month_num:
              month_volume = filtered['Quantity'].sum()
              month_value = filtered['Estimated Value'].sum()
              st.info(f"**{month_name} {year_num}**: **{int(month_volume)}** rotors worth **₹{month_value:,.2f}**")
          
          if target_size:
              # Show stock status for this size
              current_stock_df = df[
                  (df['Size (mm)'] == target_size) &
                  (df['Status'] == 'Current')
              ].copy()
              
              current_stock_df['Net'] = current_stock_df.apply(
                  lambda x: x['Quantity'] if x['Type'] == 'Inward' else -x['Quantity'], axis=1
              )
              
              current_stock = current_stock_df[~current_stock_df['Pending']]['Net'].sum()
              pending_qty = current_stock_df[current_stock_df['Pending']]['Quantity'].sum()
              
              st.info(f"**Stock status for {target_size}mm:**")
              st.write(f"- Current stock: {int(current_stock)} rotors")
              st.write(f"- Pending orders: {int(pending_qty)} rotors")
              st.write(f"- Available after pending: {int(current_stock - pending_qty)} rotors")
          
          # Most valuable size
          if not filtered.empty and not target_size:
              value_by_size = filtered.groupby('Size (mm)')['Estimated Value'].sum()
              most_valuable_size = value_by_size.idxmax()
              most_valuable_value = value_by_size.max()
              st.info(f"Most valuable size: **{most_valuable_size}mm** (₹{most_valuable_value:,.2f})")

# =========================
# SARVAM AI ASSISTANT TAB
# =========================

# Add this at the top of your file with other imports


# =========================
# SARVAM AI SETUP (SECURE)
# =========================
def setup_sarvam_ai():
    """Initialize Sarvam AI with secure API key handling"""
    
    # Try to get API key from environment variable
    api_key = os.getenv("SARVAM_API_KEY")
    
    # If not in environment, try Streamlit secrets
    if not api_key:
        try:
            api_key = st.secrets.get("SARVAM_API_KEY", "")
        except:
            pass
    
    return api_key

# =========================
# INVENTORY CONTEXT FUNCTIONS
# =========================
def get_current_stock_data(df):
    """Get current stock levels from dataframe"""
    stock_data = []
    for size in df['Size (mm)'].unique():
        if pd.isna(size):
            continue
        
        size_df = df[df['Size (mm)'] == size]
        
        # Calculate net stock
        total_inward = size_df[size_df['Type'] == 'Inward']['Quantity'].sum()
        total_outgoing = size_df[(size_df['Type'] == 'Outgoing') & (~size_df['Pending'])]['Quantity'].sum()
        current_stock = total_inward - total_outgoing
        
        # Pending orders
        pending = size_df[(size_df['Type'] == 'Outgoing') & (size_df['Pending'])]['Quantity'].sum()
        
        # Future incoming
        future = size_df[(size_df['Type'] == 'Inward') & (size_df['Status'] == 'Future')]['Quantity'].sum()
        
        # Calculate value
        if size in st.session_state.fixed_prices:
            value = st.session_state.fixed_prices[size] * current_stock
        else:
            value = st.session_state.base_rate_per_mm * size * current_stock
        
        stock_data.append({
            'size': int(size),
            'current_stock': int(current_stock),
            'pending_orders': int(pending),
            'future_incoming': int(future),
            'value': float(value)
        })
    
    return stock_data

def get_pending_orders_data(df):
    """Get pending orders summary"""
    pending_df = df[(df['Type'] == 'Outgoing') & (df['Pending'] == True)]
    
    if pending_df.empty:
        return []
    
    pending_data = []
    for _, row in pending_df.iterrows():
        if pd.isna(row['Size (mm)']) or pd.isna(row['Quantity']):
            continue
            
        size = int(row['Size (mm)'])
        if size in st.session_state.fixed_prices:
            value = st.session_state.fixed_prices[size] * row['Quantity']
        else:
            value = st.session_state.base_rate_per_mm * size * row['Quantity']
        
        pending_data.append({
            'date': row['Date'].strftime('%Y-%m-%d') if pd.notna(row['Date']) else 'Unknown',
            'size': size,
            'quantity': int(row['Quantity']),
            'buyer': str(row['Remarks']),
            'value': float(value)
        })
    
    return pending_data

def get_future_incoming_data(df):
    """Get future incoming rotors data"""
    future_df = df[(df['Type'] == 'Inward') & (df['Status'] == 'Future')]
    
    if future_df.empty:
        return []
    
    future_data = []
    for _, row in future_df.iterrows():
        if pd.isna(row['Size (mm)']) or pd.isna(row['Quantity']):
            continue
            
        size = int(row['Size (mm)'])
        if size in st.session_state.fixed_prices:
            value = st.session_state.fixed_prices[size] * row['Quantity']
        else:
            value = st.session_state.base_rate_per_mm * size * row['Quantity']
        
        future_data.append({
            'date': row['Date'].strftime('%Y-%m-%d') if pd.notna(row['Date']) else 'Unknown',
            'size': size,
            'quantity': int(row['Quantity']),
            'supplier': str(row['Remarks']),
            'value': float(value)
        })
    
    return future_data

def get_recent_transactions_data(df, days=30):
    """Get recent transactions"""
    cutoff = datetime.now() - timedelta(days=days)
    recent_df = df[df['Date'] >= cutoff].copy()
    
    if recent_df.empty:
        return []
    
    recent_data = []
    for _, row in recent_df.iterrows():
        if pd.isna(row['Size (mm)']) or pd.isna(row['Quantity']):
            continue
            
        size = int(row['Size (mm)'])
        if size in st.session_state.fixed_prices:
            value = st.session_state.fixed_prices[size] * row['Quantity']
        else:
            value = st.session_state.base_rate_per_mm * size * row['Quantity']
        
        recent_data.append({
            'date': row['Date'].strftime('%Y-%m-%d'),
            'type': str(row['Type']),
            'size': size,
            'quantity': int(row['Quantity']),
            'party': str(row['Remarks']),
            'status': str(row['Status']),
            'pending': bool(row['Pending']),
            'value': float(value)
        })
    
    return recent_data

def prepare_ai_context():
    """Prepare inventory context for AI"""
    df = st.session_state.data.copy()
    
    # Handle date column
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    
    # Get all data summaries
    context = {
        'as_of_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'stock_summary': get_current_stock_data(df),
        'pending_orders': get_pending_orders_data(df),
        'future_incoming': get_future_incoming_data(df),
        'recent_transactions': get_recent_transactions_data(df, days=30),
        'fixed_prices': st.session_state.fixed_prices,
        'base_rate_per_mm': st.session_state.base_rate_per_mm,
        'total_sizes_tracked': len(df['Size (mm)'].unique()),
        'total_buyers': len(df[df['Type'] == 'Outgoing']['Remarks'].unique()),
        'total_suppliers': len(df[df['Type'] == 'Inward']['Remarks'].unique())
    }
    
    return context

# =========================
# THE AI ASSISTANT TAB
# =========================
# Add this as a new tab in your existing tabs
# For example, if you have tabs[0], tabs[1], tabs[2], make this tabs[3]
        
# =========================
# SARVAM AI ASSISTANT TAB
# =========================

# Add this at the top of your file with other imports
import os
import json
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

try:
    from langchain_sarvam import ChatSarvam
    from langchain_core.messages import HumanMessage, SystemMessage
    SARVAM_AVAILABLE = True
except ImportError:
    SARVAM_AVAILABLE = False

# =========================
# SARVAM AI SETUP (SECURE)
# =========================
def setup_sarvam_ai():
    """Initialize Sarvam AI with secure API key handling"""
    
    # Try to get API key from environment variable
    api_key = os.getenv("SARVAM_API_KEY")
    
    # If not in environment, try Streamlit secrets
    if not api_key:
        try:
            api_key = st.secrets.get("SARVAM_API_KEY", "")
        except:
            pass
    
    return api_key

# =========================
# INVENTORY CONTEXT FUNCTIONS
# =========================
def get_current_stock_data(df):
    """Get current stock levels from dataframe"""
    stock_data = []
    for size in df['Size (mm)'].unique():
        if pd.isna(size):
            continue
        
        size_df = df[df['Size (mm)'] == size]
        
        # Calculate net stock
        total_inward = size_df[size_df['Type'] == 'Inward']['Quantity'].sum()
        total_outgoing = size_df[(size_df['Type'] == 'Outgoing') & (~size_df['Pending'])]['Quantity'].sum()
        current_stock = total_inward - total_outgoing
        
        # Pending orders
        pending = size_df[(size_df['Type'] == 'Outgoing') & (size_df['Pending'])]['Quantity'].sum()
        
        # Future incoming
        future = size_df[(size_df['Type'] == 'Inward') & (size_df['Status'] == 'Future')]['Quantity'].sum()
        
        # Calculate value
        if size in st.session_state.fixed_prices:
            value = st.session_state.fixed_prices[size] * current_stock
        else:
            value = st.session_state.base_rate_per_mm * size * current_stock
        
        if current_stock > 0 or pending > 0 or future > 0:
            stock_data.append({
                'size': int(size),
                'current_stock': int(current_stock),
                'pending_orders': int(pending),
                'future_incoming': int(future),
                'value': float(value)
            })
    
    return sorted(stock_data, key=lambda x: x['size'])

def get_pending_orders_data(df):
    """Get pending orders summary"""
    pending_df = df[(df['Type'] == 'Outgoing') & (df['Pending'] == True)]
    
    if pending_df.empty:
        return []
    
    pending_data = []
    for _, row in pending_df.iterrows():
        if pd.isna(row['Size (mm)']) or pd.isna(row['Quantity']):
            continue
            
        size = int(row['Size (mm)'])
        if size in st.session_state.fixed_prices:
            value = st.session_state.fixed_prices[size] * row['Quantity']
        else:
            value = st.session_state.base_rate_per_mm * size * row['Quantity']
        
        pending_data.append({
            'date': row['Date'].strftime('%Y-%m-%d') if pd.notna(row['Date']) else 'Unknown',
            'size': size,
            'quantity': int(row['Quantity']),
            'buyer': str(row['Remarks']),
            'value': float(value)
        })
    
    return pending_data

def get_future_incoming_data(df):
    """Get future incoming rotors data"""
    future_df = df[(df['Type'] == 'Inward') & (df['Status'] == 'Future')]
    
    if future_df.empty:
        return []
    
    future_data = []
    for _, row in future_df.iterrows():
        if pd.isna(row['Size (mm)']) or pd.isna(row['Quantity']):
            continue
            
        size = int(row['Size (mm)'])
        if size in st.session_state.fixed_prices:
            value = st.session_state.fixed_prices[size] * row['Quantity']
        else:
            value = st.session_state.base_rate_per_mm * size * row['Quantity']
        
        future_data.append({
            'date': row['Date'].strftime('%Y-%m-%d') if pd.notna(row['Date']) else 'Unknown',
            'size': size,
            'quantity': int(row['Quantity']),
            'supplier': str(row['Remarks']),
            'value': float(value)
        })
    
    return future_data

def prepare_ai_context():
    """Prepare inventory context for AI"""
    df = st.session_state.data.copy()
    
    # Handle date column
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    
    # Get all data summaries
    context = {
        'as_of_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'stock_summary': get_current_stock_data(df),
        'pending_orders': get_pending_orders_data(df),
        'future_incoming': get_future_incoming_data(df),
        'fixed_prices': st.session_state.fixed_prices,
        'base_rate_per_mm': st.session_state.base_rate_per_mm,
        'total_sizes_tracked': len(df['Size (mm)'].unique()),
        'total_buyers': len(df[df['Type'] == 'Outgoing']['Remarks'].unique()),
        'total_suppliers': len(df[df['Type'] == 'Inward']['Remarks'].unique())
    }
    
    return context

# =========================
# THE AI ASSISTANT TAB
# =========================
# Assuming you have tabs defined somewhere, this should be one of them
# For example: tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "Chat", "Rates", "AI Assistant"])

# Use the correct tab variable name from your existing code
# If your tabs are named differently, replace 'tab4' with your actual tab variable

# For this example, I'll use a generic approach - you'll need to replace this with your actual tab
# Let's assume your tabs are: tab1, tab2, tab3, tab4

# First, check if we're in the right context
    with tab3:
        
        st.subheader("AI Inventory Assistant")
        
        # Check if Sarvam is available
        if not SARVAM_AVAILABLE:
            st.warning("""
            ⚠️ LangChain Sarvam package not installed.
            
            To enable AI features, install:
            ```bash
            pip install langchain-sarvam
            ```
            """)
            st.stop()
        
        # Get API key securely
        api_key = setup_sarvam_ai()
        
        if not api_key:
            st.info("""
            ### 🔒 Setup Sarvam AI API Key
            
            To use the AI assistant, you need to add your Sarvam API key to your environment.
            
            **Option 1: Environment Variable (Recommended)**
            ```bash
            export SARVAM_API_KEY=your_api_key_here
            ```
            
            **Option 2: Streamlit Secrets**
            Add to `.streamlit/secrets.toml`:
            ```toml
            SARVAM_API_KEY = "your_api_key_here"
            ```
            
            **Option 3: .env file**
            Create a `.env` file:
            ```
            SARVAM_API_KEY=your_api_key_here
            ```
            
            Get your free API key from [dashboard.sarvam.ai](https://dashboard.sarvam.ai)
            
            🔐 **Your API key stays on your computer and is never shared!**
            """)
            
            # Show a preview of what the assistant can do
            with st.expander("👀 Preview what the AI Assistant can do"):
                st.markdown("""
                Once you set up your API key, you can ask questions like:
                
                - "What's the current stock of 1803mm rotors?"
                - "Show me all pending orders for Enova"
                - "When are the 130mm rotors coming?"
                - "How many rotors do we have in total?"
                - "What's the value of all 50mm rotors in stock?"
                - "Which buyers have pending orders?"
                - "Give me a low stock alert"
                - "What's the price of 2003mm rotors?"
                """)
            st.stop()
        
        # Initialize Sarvam LLM
        try:
            llm = ChatSarvam(
                model="sarvam-m",
                temperature=0.2,
                sarvam_api_key=api_key,
                max_tokens=1024
            )
            st.success("✅ Sarvam AI connected successfully!")
        except Exception as e:
            st.error(f"❌ Failed to initialize Sarvam AI: {str(e)}")
            st.stop()
        
        # System prompt for the AI
        system_prompt = """You are an AI inventory assistant for a rotor manufacturing company. 
        You have access to real-time inventory data and can help with:
        
        1. Stock checks for specific sizes
        2. Pending orders information by buyer
        3. Future incoming rotors by date
        4. Transaction history
        5. Price calculations using fixed rates or base rate
        6. Low stock alerts
        7. Buyer/supplier information
        
        Current inventory context is provided below. Use this data to answer questions accurately.
        
        Guidelines:
        - Be concise and helpful
        - Format numbers clearly (e.g., "1,234 rotors")
        - Show calculations when relevant
        - If asked about something not in the data, politely say you don't have that information
        - For stock levels, mention both quantity and value when appropriate
        - For pending orders, mention the buyer and expected dates
        
        Current Date: {current_date}
        """
        
        # Prepare context
        context = prepare_ai_context()
        current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Initialize chat history
        if 'ai_chat_history' not in st.session_state:
            st.session_state.ai_chat_history = []
        
        # Welcome message if chat is empty
        if len(st.session_state.ai_chat_history) == 0:
            welcome_msg = f"""👋 Hello! I'm your AI Inventory Assistant. I can see you have **{len(context['stock_summary'])}** rotor sizes in stock with a total of **{sum(item['current_stock'] for item in context['stock_summary'])}** rotors.
        
        Try asking me:
        - "Show me current stock levels"
        - "What pending orders do we have?"
        - "When are new rotors coming?"
        - "Check stock of size 1803mm"
        """
            st.session_state.ai_chat_history.append({"role": "assistant", "content": welcome_msg})
        
        # Quick action buttons
        st.markdown("### 🚀 Quick Actions")
        col1, col2, col3, col4 = st.columns(4)
        
        # Use session state to store button clicks
        if 'button_pressed' not in st.session_state:
            st.session_state.button_pressed = None
        
        with col1:
            if st.button("📦 Check Stock", use_container_width=True):
                st.session_state.button_pressed = "Show me current stock levels for all sizes"
        with col2:
            if st.button("⏳ Pending Orders", use_container_width=True):
                st.session_state.button_pressed = "Show all pending orders with buyer names"
        with col3:
            if st.button("📅 Coming Rotors", use_container_width=True):
                st.session_state.button_pressed = "Show future incoming rotors with expected dates"
        with col4:
            if st.button("💰 Price List", use_container_width=True):
                st.session_state.button_pressed = "What are the current prices for all rotor sizes?"
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("⚠️ Low Stock", use_container_width=True):
                st.session_state.button_pressed = "Which sizes have low stock (less than 10 units)?"
        with col2:
            if st.button("📊 Summary", use_container_width=True):
                st.session_state.button_pressed = "Give me a quick summary of current inventory"
        with col3:
            if st.button("🏭 Top Buyers", use_container_width=True):
                st.session_state.button_pressed = "Who are the top buyers by quantity?"
        with col4:
            if st.button("📈 Recent Activity", use_container_width=True):
                st.session_state.button_pressed = "Show recent transactions from last 30 days"
        
        st.divider()
        
        # Display chat history
        chat_container = st.container()
        with chat_container:
            for message in st.session_state.ai_chat_history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
        
        # Handle button press
        if st.session_state.button_pressed:
            prompt = st.session_state.button_pressed
            st.session_state.button_pressed = None  # Reset
            
            # Add user message to history
            st.session_state.ai_chat_history.append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Get AI response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        # Prepare the full context for this query
                        full_context = prepare_ai_context()
                        
                        # Create messages
                        messages = [
                            SystemMessage(content=system_prompt.format(current_date=current_date)),
                            HumanMessage(content=f"Current Inventory Context:\n{json.dumps(full_context, indent=2, default=str)}\n\nUser Query: {prompt}")
                        ]
                        
                        # Get response from Sarvam AI
                        response = llm.invoke(messages)
                        
                        # Display response
                        st.markdown(response.content)
                        
                        # Add to chat history
                        st.session_state.ai_chat_history.append({"role": "assistant", "content": response.content})
                        
                    except Exception as e:
                        error_msg = f"❌ Error getting response: {str(e)}"
                        st.error(error_msg)
                        st.session_state.ai_chat_history.append({"role": "assistant", "content": error_msg})
            
            st.rerun()
        
        # Chat input
        if prompt := st.chat_input("Ask me anything about your inventory..."):
            # Add user message to history
            st.session_state.ai_chat_history.append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Get AI response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        # Prepare the full context for this query
                        full_context = prepare_ai_context()
                        
                        # Create messages
                        messages = [
                            SystemMessage(content=system_prompt.format(current_date=current_date)),
                            HumanMessage(content=f"Current Inventory Context:\n{json.dumps(full_context, indent=2, default=str)}\n\nUser Query: {prompt}")
                        ]
                        
                        # Get response from Sarvam AI
                        response = llm.invoke(messages)
                        
                        # Display response
                        st.markdown(response.content)
                        
                        # Add to chat history
                        st.session_state.ai_chat_history.append({"role": "assistant", "content": response.content})
                        
                    except Exception as e:
                        error_msg = f"❌ Error getting response: {str(e)}"
                        st.error(error_msg)
                        st.session_state.ai_chat_history.append({"role": "assistant", "content": error_msg})
            
            st.rerun()
        
        # Sidebar controls for the AI tab
        with st.sidebar:
            st.markdown("### 🎛️ AI Assistant Controls")
            
            if st.button("🗑️ Clear Chat History", use_container_width=True):
                st.session_state.ai_chat_history = []
                st.rerun()
            
            if st.button("🔄 Refresh Context", use_container_width=True):
                st.rerun()
            
            st.divider()
            
            # Show context stats
            st.markdown("### 📊 Current Stats")
            context = prepare_ai_context()
            
            total_stock = sum(item['current_stock'] for item in context['stock_summary'])
            total_value = sum(item['value'] for item in context['stock_summary'])
            total_pending = len(context['pending_orders'])
            total_future = len(context['future_incoming'])
            
            st.metric("Total Rotors in Stock", f"{total_stock:,}")
            st.metric("Total Stock Value", f"₹{total_value:,.0f}")
            st.metric("Pending Orders", total_pending)
            st.metric("Future Incoming", total_future)
            
            st.divider()
            
            # Debug expander
            with st.expander("🔍 View Raw Context"):
                st.json(context, default=str)

        # === CASE: Buyer weight estimation ===
        
      
          
          
    
               
        
      
    


import streamlit as st
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from uuid import uuid4
import pandas as pd

# ==== SESSION STATE INITIALIZATION ====
if "clitting_data" not in st.session_state:
    st.session_state["clitting_data"] = pd.DataFrame(columns=[
        "Date", "Size (mm)", "Bags", "Weight per Bag (kg)", "Remarks", "ID"
    ])

if "lamination_v3" not in st.session_state:
    st.session_state["lamination_v3"] = pd.DataFrame(columns=[
        "Date", "Quantity", "Remarks", "ID"
    ])

if "lamination_v4" not in st.session_state:
    st.session_state["lamination_v4"] = pd.DataFrame(columns=[
        "Date", "Quantity", "Remarks", "ID"
    ])

if "stator_data" not in st.session_state:
    st.session_state["stator_data"] = pd.DataFrame(columns=[
        "Date", "Size (mm)", "Quantity", "Remarks",
        "Estimated Clitting (kg)", "Laminations Used",
        "Lamination Type", "ID"
    ])

# ==== GOOGLE SHEETS CONNECTION ====
def get_gsheet_connection():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\\\n", "\n")
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds).open("Rotor Log")

def save_to_sheet(dataframe, sheet_title):
    try:
        ss = get_gsheet_connection()
        try:
            ws = ss.worksheet(sheet_title)
        except gspread.WorksheetNotFound:
            ws = ss.add_worksheet(title=sheet_title, rows="1000", cols="20")
        ws.clear()
        if not dataframe.empty:
            ws.update([dataframe.columns.tolist()] + dataframe.values.tolist())
    except Exception as e:
        st.error(f"❌ Error saving to {sheet_title}: {e}")

def load_from_sheet(sheet_title, default_columns):
    try:
        ss = get_gsheet_connection()
        ws = ss.worksheet(sheet_title)
        records = ws.get_all_records()
        if records:
            return pd.DataFrame(records)
    except gspread.WorksheetNotFound:
        pass
    except Exception as e:
        st.error(f"❌ Error loading from sheet '{sheet_title}': {e}")
    return pd.DataFrame(columns=default_columns)

def clean_for_editor(df):
    return df.astype(str).fillna("")

def save_clitting_to_sheet():
    save_to_sheet(st.session_state.clitting_data.copy(), "Clitting")

def save_v3_laminations_to_sheet():
    save_to_sheet(st.session_state.lamination_v3.copy(), "V3 Laminations")

def save_v4_laminations_to_sheet():
    save_to_sheet(st.session_state.lamination_v4.copy(), "V4 Laminations")

def save_stator_to_sheet():
    save_to_sheet(st.session_state.stator_data.copy(), "Stator Usage")

def save_lamination_to_sheet(l_type):
    if l_type == "v3":
        save_v3_laminations_to_sheet()
    elif l_type == "v4":
        save_v4_laminations_to_sheet()

if st.session_state["clitting_data"].empty:
    st.session_state["clitting_data"] = load_from_sheet("Clitting", st.session_state["clitting_data"].columns)

if st.session_state["lamination_v3"].empty:
    st.session_state["lamination_v3"] = load_from_sheet("V3 Laminations", st.session_state["lamination_v3"].columns)

if st.session_state["lamination_v4"].empty:
    st.session_state["lamination_v4"] = load_from_sheet("V4 Laminations", st.session_state["lamination_v4"].columns)

if st.session_state["stator_data"].empty:
    st.session_state["stator_data"] = load_from_sheet("Stator Usage", st.session_state["stator_data"].columns)


if tab_choice == ("🧰 Clitting + Laminations + Stators"):
    st.title("🧰 Clitting + Laminations + Stator Outgoings")

    tab1, tab2, tab3, tab4 = st.tabs(["📥 Clitting", "🧩 Laminations", "📤 Stator Outgoings", "📊 Summary"])

    CLITTING_USAGE = {
        100: 0.04,
        120: 0.05,
        125: 0.05,
        130: 0.05,
        140: 0.06,
        150: 0.06,
        160: 0.07,
        170: 0.08,
        180: 0.09,
        190: 0.10,
        200: 0.11,
        225: 0.12,
        260: 0.13,
        300: 0.14,
    }
    
    # ---------- TAB 1: Clitting ----------
    with tab1:
        st.subheader("📥 Clitting Inward")
        with st.form("clitting_form"):
            c_date = st.date_input("📅 Date", value=datetime.today())
            c_size = st.number_input("📏 Stator Size (mm)", min_value=1, step=1)
            c_bags = st.number_input("🧮 Bags", min_value=1, step=1)
            c_weight = st.number_input("⚖ Weight per Bag (kg)", value=25.0, step=0.5)
            c_remarks = st.text_input("📝 Remarks")
            if st.form_submit_button("➕ Add Clitting"):
                entry = {
                    "Date": c_date.strftime("%Y-%m-%d"),
                    "Size (mm)": int(c_size),
                    "Bags": int(c_bags),
                    "Weight per Bag (kg)": float(c_weight),
                    "Remarks": c_remarks.strip(),
                    "ID": str(uuid4())
                }
                st.session_state.clitting_data = pd.concat(
                    [st.session_state.clitting_data, pd.DataFrame([entry])],
                    ignore_index=True
                )
                save_clitting_to_sheet()
                st.success("✅ Clitting entry added.")
    
        st.subheader("📄 Clitting Log")
        for idx, row in st.session_state.clitting_data.iterrows():
            with st.expander(f"{row['Date']} | {row['Size (mm)']}mm | {row['Bags']} bags"):
                col1, col2 = st.columns([1, 2])
                with col1:
                    if st.button("🗑 Delete", key=f"del_clit_{row['ID']}"):
                        st.session_state.clitting_data = st.session_state.clitting_data[st.session_state.clitting_data["ID"] != row["ID"]].reset_index(drop=True)
                        save_clitting_to_sheet()
                        st.rerun()
                with col2:
                    new_bags = st.number_input("🧮 Bags", value=int(row["Bags"]), key=f"edit_bags_{row['ID']}")
                    new_weight = st.number_input("⚖ Weight/Bag", value=float(row["Weight per Bag (kg)"]), key=f"edit_weight_{row['ID']}")
                    new_remarks = st.text_input("📝 Remarks", value=row["Remarks"], key=f"edit_remarks_{row['ID']}")
                    if st.button("💾 Save", key=f"save_clit_{row['ID']}"):
                        st.session_state.clitting_data.at[idx, "Bags"] = new_bags
                        st.session_state.clitting_data.at[idx, "Weight per Bag (kg)"] = new_weight
                        st.session_state.clitting_data.at[idx, "Remarks"] = new_remarks
                        save_clitting_to_sheet()
                        st.success("✅ Entry updated.")
    
    # ---------- TAB 2: Laminations ----------
    with tab2:
        st.subheader("📥 Laminations Inward (V3 / V4)")
        with st.form("lamination_form"):
            l_date = st.date_input("📅 Date", value=datetime.today(), key="lam_date")
            l_type = st.selectbox("🔀 Lamination Type", ["V3", "V4"])
            l_qty = st.number_input("🔢 Quantity", min_value=1, step=1)
            l_remarks = st.text_input("📝 Remarks", key="lam_remarks")
            if st.form_submit_button("➕ Add Laminations"):
                entry = {
                    "Date": l_date.strftime("%Y-%m-%d"),
                    "Quantity": int(l_qty),
                    "Remarks": l_remarks.strip(),
                    "ID": str(uuid4())
                }
                lam_key = "lamination_v3" if l_type == "V3" else "lamination_v4"
                st.session_state[lam_key] = pd.concat(
                    [st.session_state[lam_key], pd.DataFrame([entry])],
                    ignore_index=True
                )
                if l_type == "V3":
                    save_v3_laminations_to_sheet()
                else:
                    save_v4_laminations_to_sheet()
                st.success(f"✅ {l_type} Lamination entry added.")
    
        for lam_type in ["V3", "V4"]:
            st.markdown(f"### 📄 {lam_type} Lamination Log")
            lam_key = "lamination_v3" if lam_type == "V3" else "lamination_v4"
            lam_df = st.session_state[lam_key].copy()
    
            for idx, row in lam_df.iterrows():
                with st.expander(f"{row['Date']} | Qty: {row['Quantity']}"):
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        if st.button("🗑", key=f"del_lam_{lam_type}_{row['ID']}"):
                            st.session_state[lam_key] = lam_df[lam_df["ID"] != row["ID"]].reset_index(drop=True)
                            if lam_type == "V3":
                                save_v3_laminations_to_sheet()
                            else:
                                save_v4_laminations_to_sheet()
                            st.rerun()
                    with col2:
                        new_qty = st.number_input("Quantity", value=int(row["Quantity"]), key=f"qty_{row['ID']}")
                        new_remarks = st.text_input("Remarks", value=row["Remarks"], key=f"rem_{row['ID']}")
                        if st.button("💾 Save", key=f"save_lam_{row['ID']}"):
                            st.session_state[lam_key].at[idx, "Quantity"] = new_qty
                            st.session_state[lam_key].at[idx, "Remarks"] = new_remarks
                            if lam_type == "V3":
                                save_v3_laminations_to_sheet()
                            else:
                                save_v4_laminations_to_sheet()
                            st.success("✅ Entry updated.")
    
    # ---------- TAB 3: Stator Outgoings ----------
    with tab3:
        st.subheader("📤 Stator Outgoings")
        with st.form("stator_form"):
            s_date = st.date_input("📅 Date", value=datetime.today(), key="stat_date")
            s_size = st.number_input("📏 Stator Size (mm)", min_value=1, step=1, key="stat_size")
            s_qty = st.number_input("🔢 Quantity", min_value=1, step=1, key="stat_qty")
            s_type = st.selectbox("🔀 Lamination Type", ["V3", "V4"], key="stat_type")
            s_remarks = st.text_input("📝 Remarks", key="stat_remarks")
        
            if st.form_submit_button("📋 Log Stator Outgoing"):
                size_key = int(s_size)
                clitting_used = CLITTING_USAGE.get(size_key, 0) * int(s_qty)
                laminations_used = int(s_qty) * 2
        
                # ==== Check clitting stock ====
                current_clitting_stock = 0
                for _, r in st.session_state["clitting_data"].iterrows():
                    if int(r["Size (mm)"]) == size_key:
                        current_clitting_stock += int(r["Bags"]) * float(r["Weight per Bag (kg)"])
                for _, r in st.session_state["stator_data"].iterrows():
                    if int(r["Size (mm)"]) == size_key:
                        current_clitting_stock -= float(r.get("Estimated Clitting (kg)", 0) or 0)
        
                if current_clitting_stock < clitting_used:
                    st.warning(f"⚠ Not enough clitting for size {size_key}mm. Stock: {current_clitting_stock:.2f} kg, Needed: {clitting_used:.2f} kg.")
        
                # ==== Check lamination stock ====
                lam_key = "lamination_v3" if s_type == "V3" else "lamination_v4"
                current_lam_stock = st.session_state[lam_key]["Quantity"].sum()
        
                if current_lam_stock < laminations_used:
                    st.warning(f"⚠ Not enough {s_type} laminations. Stock: {current_lam_stock}, Needed: {laminations_used}")
        
                # ==== Add entry anyway ====
                new_entry = {
                    "Date": s_date.strftime("%Y-%m-%d"),
                    "Size (mm)": size_key,
                    "Quantity": int(s_qty),
                    "Remarks": s_remarks.strip(),
                    "Estimated Clitting (kg)": round(clitting_used, 2),
                    "Laminations Used": laminations_used,
                    "Lamination Type": s_type,
                    "ID": str(uuid4())
                }
        
                st.session_state.stator_data = pd.concat(
                    [st.session_state.stator_data, pd.DataFrame([new_entry])],
                    ignore_index=True
                )
                save_stator_to_sheet()
        
                # Deduct laminations
                lam_df = st.session_state[lam_key].copy()
                total_needed = laminations_used
                for idx, row in lam_df.iterrows():
                    if total_needed <= 0:
                        break
                    available = int(row["Quantity"])
                    if total_needed >= available:
                        total_needed -= available
                        lam_df.at[idx, "Quantity"] = 0
                    else:
                        lam_df.at[idx, "Quantity"] = available - total_needed
                        total_needed = 0
                lam_df = lam_df[lam_df["Quantity"] > 0].reset_index(drop=True)
                st.session_state[lam_key] = lam_df
                save_lamination_to_sheet("v3" if s_type == "V3" else "v4")
        
                st.success(f"✅ Stator logged. Clitting used: {clitting_used:.2f} kg | Laminations used: {laminations_used}")
                st.rerun()
    
        st.subheader("📄 Stator Usage Log")
        for idx, row in st.session_state.stator_data.iterrows():
            with st.expander(f"{row['Date']} | {row['Size (mm)']}mm | Qty: {row['Quantity']}"):
                col1, col2 = st.columns([1, 2])
                with col1:
                    if st.button("🗑 Delete", key=f"del_stator_{row['ID']}"):
                        st.session_state.stator_data = st.session_state.stator_data[st.session_state.stator_data["ID"] != row["ID"]].reset_index(drop=True)
                        save_stator_to_sheet()
                        st.rerun()
                with col2:
                    new_qty = st.number_input("Quantity", value=int(row["Quantity"]), key=f"qty_stator_{row['ID']}")
                    new_remarks = st.text_input("Remarks", value=row["Remarks"], key=f"rem_stator_{row['ID']}")
                    if st.button("💾 Save", key=f"save_stator_{row['ID']}"):
                        st.session_state.stator_data.at[idx, "Quantity"] = new_qty
                        st.session_state.stator_data.at[idx, "Remarks"] = new_remarks
                        save_stator_to_sheet()
                        st.success("✅ Entry updated.")
    
    # ---------- TAB 4: Summary ----------

# rotor_tracker.py



# REMOVE THIS SECTION (lines 50-52):
# if 'data' not in st.session_state:
#     st.session_state.data = pd.DataFrame()
#     
#     df = st.session_state.data.copy()

# ====== APPLE WATCH COMPATIBLE MODE ======
# Add this at the end of your existing app, right before the last line

# Detect if accessing from mobile/watch
user_agent = st.query_params.get("user_agent", "").lower()
is_mobile = any(x in user_agent for x in ['mobile', 'iphone', 'ipod', 'android', 'blackberry', 'windows phone'])
is_watch = 'watch' in user_agent or 'wearable' in user_agent

# Add a query parameter to force watch mode
watch_mode = st.query_params.get("watch", "false").lower() == "true"

# If on watch or mobile, show simplified view
if is_watch or watch_mode or is_mobile:
    # Override the entire app with watch view
    st.set_page_config(
        page_title="Rotor Stock ⌚",
        page_icon="⌚",
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    
    # Simple CSS for watch
    st.markdown("""
    <style>
    .stock-card {
        background: white;
        border: 2px solid #007AFF;
        border-radius: 15px;
        padding: 15px;
        margin: 10px 0;
        text-align: center;
    }
    .stock-number {
        font-size: 48px;
        font-weight: bold;
        color: #007AFF;
        margin: 10px 0;
    }
    .stock-label {
        font-size: 18px;
        color: #666;
    }
    .watch-button {
        font-size: 20px;
        height: 60px;
        margin: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.title("⌚ Rotor Stock")
    
    # Quick size selection
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("1803", key="w_1803", use_container_width=True):
            size = 1803
    with col2:
        if st.button("2003", key="w_2003", use_container_width=True):
            size = 2003
    with col3:
        if st.button("70", key="w_70", use_container_width=True):
            size = 70
    
    col4, col5, col6 = st.columns(3)
    with col4:
        if st.button("50", key="w_50", use_container_width=True):
            size = 50
    with col5:
        if st.button("40", key="w_40", use_container_width=True):
            size = 40
    with col6:
        if st.button("35", key="w_35", use_container_width=True):
            size = 35
    
    # Or enter custom size
    custom_size = st.number_input("Or enter size:", min_value=1, step=1, key="watch_size")
    
    if custom_size:
        size = custom_size
    
    # Check if size is selected
    if 'size' in locals():
        # Calculate stock (using your existing data)
        # FIRST, ensure data is initialized
        if 'data' not in st.session_state:
            st.session_state.data = pd.DataFrame(columns=[
                'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending', 'ID'
            ])
            
        df = st.session_state.data.copy()
        
        size_df = df[df['Size (mm)'] == size]
        
        # Simple calculation
        current_df = size_df[
            (size_df['Status'] == 'Current') & 
            (~size_df['Pending'])
        ].copy()
        current_df['Net'] = current_df.apply(
            lambda x: x['Quantity'] if x['Type'] == 'Inward' else -x['Quantity'], axis=1
        )
        stock = current_df['Net'].sum()
        
        # Display
        st.markdown(f"""
        <div class="stock-card">
            <div class="stock-label">{size}mm Stock</div>
            <div class="stock-number">{int(stock)}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Status
        if stock > 100:
            st.success("✅ Good stock")
        elif stock > 50:
            st.warning("⚠️ Medium stock")
        elif stock > 10:
            st.error("🟠 Low stock")
        else:
            st.error("🔴 Very low stock")
        
        # Simple refresh
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    st.stop()
   

# ----- Inventory Summary -----





    # 🔌 Streamlit API endpoint for Swift
    
    # ====== LAST SYNC STATUS ======
       # just do this directly

    
