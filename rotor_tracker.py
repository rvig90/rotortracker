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
from prophet import Prophet
import xgboost as xgb
from sklearn.metrics import mean_squared_error
from forecast_utils import forecast_with_xgboost
from langchain.llms import OpenAI
from langchain_experimental.agents import create_pandas_dataframe_agent
import openai
import re
import pandas as pd
import os

import pandas as pd
from uuid import uuid4

# Session state for logs







    
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

import streamlit as st

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
    
    from datetime import datetime
    from uuid import uuid4
    import pandas as pd
    import streamlit as st
    
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
    tabs = st.tabs(["📊 Stock Summary", "📋 Movement Log", "💬 Rotor Chatbot lite", "Rotor Chatbot", "Rotor Assistant lite", "Planning Dashboard"])
    
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
        
        
        import streamlit as st
        import pandas as pd
        
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
    import re
    import calendar
    from datetime import datetime
    import pandas as pd
    
    with tabs[2]:
        st.subheader("💬 Rotor Chatbot Lite")
        chat_query = st.text_input("Try: 'Buyer A June', '100mm last 5', 'Buyer B pending', 'Outgoing May', '300mm stock', or 'Buyer A weight'")
        
        df = st.session_state.data.copy()
        df["Date"] = pd.to_datetime(df["Date"])
        query = chat_query.lower()
        
        # Estimated rotor weights (kg)
        ROTOR_WEIGHTS = {
            80: 0.5,
            100: 1,
            110: 1.01,
            120: 1.02,
            125: 1.058,
            130: 1.1,
            140: 1.15,
            150: 1.3,
            160: 1.4,
            170: 1.422,
            180: 1.5,
            200: 1.7,
            225: 1.9,
            260: 2.15,
            2403: 1.46,
            1803: 1,
            2003: 1.1,
            # Add more sizes as needed
        }
        
        # ===== Extract Components =====
        month_match = re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", query)
        year_match = re.search(r"(20\d{2})", query)
        month_name = month_match.group(1).capitalize() if month_match else None
        year = int(year_match.group(1)) if year_match else datetime.today().year
        
        rotor_match = re.search(r"(\d{2,6})\s*mm", query)
        rotor_size = int(rotor_match.group(1)) if rotor_match else None
        
        last_n_match = re.search(r"last\s+(\d+)", query)
        entry_count = int(last_n_match.group(1)) if last_n_match else None
        
        type_match = re.search(r"\b(inward|outgoing)\b", query)
        movement_type = type_match.group(1).capitalize() if type_match else None
        
        is_pending = "pending" in query
        
        # Remove known terms to isolate buyer name
        cleaned = re.sub(r"(last\s*\d+|inward|outgoing|pending|\d{2,6}mm|stock|weight|january|february|march|april|may|june|july|august|september|october|november|december|20\d{2})", "", query, flags=re.IGNORECASE)
        buyer_name = cleaned.strip()
        
        # ===== CASE: "coming rotors" =====
        if query.strip() == "coming rotors":
            coming_df = st.session_state.data.copy()
            coming_df["Date"] = pd.to_datetime(coming_df["Date"], errors="coerce").dt.date
            coming_df = coming_df[
                (coming_df["Type"] == "Inward") &
                (coming_df["Status"].str.lower() == "future")
            ][["Date", "Size (mm)", "Quantity"]].sort_values("Date")
        
            if not coming_df.empty:
                st.success("📅 Coming Rotors")
                st.dataframe(coming_df, use_container_width=True, hide_index=True)
            else:
                st.info("✅ No coming rotor entries found.")
            st.stop()
        
        # ===== CASE: Buyer Weight Estimation =====
        if "weight" in query and buyer_name:
            outgoing_df = df[
                (df["Type"] == "Outgoing") &
                (df["Remarks"].str.lower().str.contains(buyer_name.lower()))
            ].copy()
        
            if outgoing_df.empty:
                st.info(f"No outgoing entries found for buyer: {buyer_name.title()}")
                st.stop()
        
            # Calculate weight
            outgoing_df["Estimated Weight (kg)"] = outgoing_df.apply(
                lambda row: ROTOR_WEIGHTS.get(row["Size (mm)"], 0) * row["Quantity"], axis=1
            )
            total_weight = outgoing_df["Estimated Weight (kg)"].sum()
        
            st.success(f"📦 Estimated total weight for **{buyer_name.title()}**: **{total_weight:.2f} kg**")
            st.dataframe(
                outgoing_df[["Date", "Size (mm)", "Quantity", "Estimated Weight (kg)"]],
                use_container_width=True,
                hide_index=True
            )
        
            missing_sizes = outgoing_df[~outgoing_df["Size (mm)"].isin(ROTOR_WEIGHTS.keys())]["Size (mm)"].unique()
            if len(missing_sizes):
                st.warning(f"⚠ No weight data for rotor sizes: {', '.join(map(str, missing_sizes))}")
            st.stop()
        
        # ===== CASE: Pending Orders =====
        if re.search(r"\b(pendings|pending orders?)\b", query):
            pending_df = df[
                (df["Type"] == "Outgoing") &
                (df["Pending"] == True)
            ]
            if not pending_df.empty:
                st.success("📬 Pending Orders Grouped by Buyer and Rotor Size")
                grouped = (
                    pending_df.groupby(["Remarks", "Size (mm)"])["Quantity"]
                    .sum()
                    .reset_index()
                    .rename(columns={
                        "Remarks": "Buyer",
                        "Size (mm)": "Rotor Size (mm)",
                        "Quantity": "Pending Quantity"
                    })
                    .sort_values(["Buyer", "Rotor Size (mm)"])
                )
                st.dataframe(grouped, use_container_width=True, hide_index=True)
            else:
                st.info("✅ No pending orders found.")
            st.stop()
        
        # ===== General Filters =====
        df = df[df["Status"] != "Future"]
        if month_name:
            month_num = list(calendar.month_name).index(month_name)
            start_date = datetime(year, month_num, 1)
            end_date = datetime(year, month_num, calendar.monthrange(year, month_num)[1])
            df = df[(df["Date"] >= start_date) & (df["Date"] <= end_date)]
        
        filtered = df.copy()
        filters = []
        
        if rotor_size:
            filtered = filtered[filtered["Size (mm)"] == rotor_size]
            filters.append(f"{rotor_size}mm")
        
        if movement_type:
            filtered = filtered[filtered["Type"] == movement_type]
            filters.append(movement_type)
        
        if is_pending:
            filtered = filtered[filtered["Pending"] == True]
            filters.append("Pending")
        
        if buyer_name:
            filtered = filtered[filtered["Remarks"].str.contains(buyer_name, case=False, na=False)]
            filters.append(f"Buyer: {buyer_name}")
        
        # ===== Show Last N Entries =====
        if entry_count:
            filtered = filtered.sort_values("Date", ascending=False).head(entry_count)
            title = f"📋 Last {entry_count} entries"
            if filters:
                title += " for " + ", ".join(filters)
            st.success(title)
            st.dataframe(filtered[["Date", "Size (mm)", "Type", "Quantity", "Remarks", "Pending"]], use_container_width=True)
            st.stop()
        
        # ===== Show Stock =====
        if "stock" in query and rotor_size:
            df["Net"] = df.apply(
                lambda x: x["Quantity"] if x["Type"] == "Inward" else -x["Quantity"] if not x["Pending"] else 0,
                axis=1
            )
            stock = df[df["Size (mm)"] == rotor_size]["Net"].sum()
            st.success(f"📦 Current stock for *{rotor_size}mm*: {int(stock)} units")
            st.stop()
        
        # ===== Final Output =====
        if not chat_query.strip():
            st.info("💬 Enter a query to begin.")
            st.stop()
        
        if not filtered.empty:
            title = f"📄 Entries"
            if filters:
                title += " for " + ", ".join(filters)
            st.success(title)
            st.dataframe(filtered[["Date", "Size (mm)", "Type", "Quantity", "Remarks", "Pending"]], use_container_width=True)
        else:
            st.info("❓ No matching entries found. Try: Buyer A June, 250mm stock, Last 5 outgoing")
    
        # === CASE: Buyer weight estimation ===
        
        # CASE: Clitting Left or Balance
        if re.search(r"\b(clitting (left|balance|available|remaining|stock)|how much clitting)\b", query):
            # Total clitting received (in kg)
            total_clitting_inward = 0
            if "clitting_data" in st.session_state and not st.session_state.clitting_data.empty:
                df_clit = st.session_state.clitting_data.copy()
                total_clitting_inward = (df_clit["Bags"] * df_clit["Weight per Bag (kg)"]).sum()
        
            # Total clitting consumed (in kg)
            total_clitting_used = 0
            if "stator_data" in st.session_state and not st.session_state.stator_data.empty:
                df_stat = st.session_state.stator_data.copy()
                total_clitting_used = df_stat["Estimated Clitting (kg)"].sum()
        
            clitting_left = round(total_clitting_inward - total_clitting_used, 2)
        
            st.success(f"🧮 *Clitting Left:* {clitting_left} kg")
            st.info(f"📥 Total Inward: {round(total_clitting_inward, 2)} kg | 🛠 Used: {round(total_clitting_used, 2)} kg")
        
            # Add warning if low
            if clitting_left < 5:
                st.warning("⚠ Clitting stock is running low. Consider reordering.")
            st.stop()
    
        # === CASE: "130mm clitting left" ===
        clitting_left_match = re.search(r"(\d{2,6})\s*mm.*clitting.*", query)
        if clitting_left_match:
            size = int(clitting_left_match.group(1))
            
            # Total clitting added
            total_added = st.session_state.clitting_data[
                st.session_state.clitting_data["Size (mm)"] == size
            ].apply(lambda row: row["Bags"] * row["Weight per Bag (kg)"], axis=1).sum()
        
            # Total clitting used
            total_used = st.session_state.stator_data[
                st.session_state.stator_data["Size (mm)"] == size
            ]["Estimated Clitting (kg)"].sum()
        
            remaining = total_added - total_used
        
            st.success(f"🔩 Remaining clitting for *{size}mm* stators: *{remaining:.2f} kg*")
            st.stop()
      
    with tabs[3]:
        import openai
        import streamlit as st
        
        # Configure OpenRouter
        openai.api_key = st.secrets["openai"]["api_key"]
        openai.base_url = "https://openrouter.ai/api/v1"
        
        st.title("🧠 Rotor Assistant (Streaming Chatbot)")
        
        # Input box for user query
        query = st.chat_input("Ask anything about stock, buyers, sizes...")
        
        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {"role": "system", "content": "You are a helpful rotor assistant."}
            ]
        
        # Show previous messages
        for msg in st.session_state.messages[1:]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        
        # Handle user message
        if query:
            st.session_state.messages.append({"role": "user", "content": query})
            with st.chat_message("user"):
                st.markdown(query)
        
            # Display streaming reply
            with st.chat_message("assistant"):
                stream_response = openai.chat.completions.create(
                    model="mistralai/mistral-7b-instruct:free",  # ✅ You can change this to mistral-7b-instruct or others
                    messages=st.session_state.messages,
                    stream=True,
                )
        
                full_reply = ""
                for chunk in stream_response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        full_reply += chunk.choices[0].delta.content
                        st.write(chunk.choices[0].delta.content, end="")
                st.session_state.messages.append({"role": "assistant", "content": full_reply})
    
                   
      
    with tabs[4]: 
        import re
    
        st.subheader("💬 Ask RotorBot Lite")
        
        query = st.text_input("Ask about stock, pendings, buyers, or sizes", key="chat_query")
        
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
        
        if st.button("🧹 Clear Size History"):
            st.session_state.chat_history = []
            st.success("Size history cleared.")
        
        df = st.session_state.data.copy()
        df["Date"] = pd.to_datetime(df["Date"])
        df["Clean_Remarks"] = df["Remarks"].fillna("").str.lower()
        
        # Extract size from query
        size_match = re.findall(r"(\d{2,4})", query)
        matched_size = int(size_match[0]) if size_match else None
        entry_count_match = re.search(r"last\s+(\d+)", query.lower())
        entry_count = int(entry_count_match.group(1)) if entry_count_match else 5
        
        # Flags
        is_pending = "pending" in query.lower()
        is_entries = "entry" in query.lower() or "entries" in query.lower()
        is_stock = "stock" in query.lower()
        
        # === Buyer Detection from Remarks ===
        buyer_name = None
        for remark in df["Clean_Remarks"].dropna().unique():
            if remark and remark in query.lower():
                buyer_name = remark
                break
        
        # === 1. Show Buyer Pendings ===
        if buyer_name and is_pending:
            buyer_pending = df[
                (df["Clean_Remarks"].str.contains(buyer_name)) &
                (df["Pending"]) &
                (df["Status"] == "Current")
            ]
            if not buyer_pending.empty:
                st.success(f"📦 Pending orders for buyer: **{buyer_name.title()}**")
                st.dataframe(buyer_pending[["Date", "Size (mm)", "Quantity", "Remarks"]])
            else:
                st.info("No pendings found for this buyer.")
        
        # === 2. Show Buyer Last Entries ===
        elif buyer_name and is_entries:
            buyer_entries = df[
                df["Clean_Remarks"].str.contains(buyer_name, na=False)
            ].sort_values("Date", ascending=False)
            st.success(f"🕓 Last {entry_count} entries for buyer: **{buyer_name.title()}**")
            st.dataframe(buyer_entries[["Date", "Size (mm)", "Type", "Quantity", "Remarks"]].head(entry_count))
        
        # === 3. Show Size Pendings ===
        elif matched_size and is_pending:
            size_pending = df[
                (df["Size (mm)"] == matched_size) &
                (df["Pending"]) &
                (df["Status"] == "Current")
            ]
            if not size_pending.empty:
                st.success(f"📦 Pending orders for rotor size **{matched_size} mm**")
                st.dataframe(size_pending[["Date", "Quantity", "Remarks"]])
            else:
                st.info("No pending orders for this size.")
        
        # === 4. Show Last N Entries for Size ===
        elif matched_size and is_entries:
            entries = df[df["Size (mm)"] == matched_size].sort_values("Date", ascending=False)
            st.success(f"📄 Last {entry_count} entries for **{matched_size} mm**")
            st.dataframe(entries[["Date", "Type", "Quantity", "Remarks"]].head(entry_count))
        
        # === 5. Show Actual Current Stock for Size ===
        elif matched_size and is_stock:
            temp = df[
                (df["Status"] == "Current") &
                (df["Size (mm)"] == matched_size)
            ].copy()
        
            inward = temp[temp["Type"] == "Inward"]["Quantity"].sum()
            outward = temp[temp["Type"] == "Outgoing"]["Quantity"].sum()
            stock = inward - outward
        
            st.success(f"📦 Current stock for rotor size **{matched_size} mm**: `{int(stock)}` units")
            st.session_state.chat_history.append(matched_size)
        
        # === 6. General Stock Suggestion Summary ===
        if st.session_state.chat_history:
            st.markdown("---")
            st.markdown("🔎 **Recently Queried Rotor Sizes Stock Summary**")
        
            report = []
            for size in st.session_state.chat_history:
                temp = df[df["Size (mm)"] == size]
                current = temp[temp["Status"] == "Current"]
                inward = current[current["Type"] == "Inward"]["Quantity"].sum()
                outward = current[current["Type"] == "Outgoing"]["Quantity"].sum()
                pending = current[current["Pending"]]["Quantity"].sum()
                future = df[
                    (df["Status"] == "Future") &
                    (df["Size (mm)"] == size) &
                    (df["Type"] == "Inward")
                ]["Quantity"].sum()
        
                stock = inward - outward
                status = "🟢 OK"
                if stock < 5:
                    status = "🔴 Restock Suggested"
        
                report.append({
                    "Size (mm)": size,
                    "Current Stock": int(stock),
                    "Pending Qty": int(pending),
                    "Coming Qty": int(future),
                    "Restock Status": status
                })
        
            st.dataframe(report, use_container_width=True)
        
        # === 7. If nothing matches
        if query and not (buyer_name or matched_size):
            st.info("❓ Couldn’t match your query. Try asking: `250mm stock`, `Buyer XYZ pendings`, `100mm last 5 entries`")
        
        
    with tabs[5]:
        st.title("📅 Interactive Rotor Planning Dashboard")
    
        df = st.session_state.data.copy()
        df["Date"] = pd.to_datetime(df["Date"])
        
        # === Usage (last 60 days)
        cutoff = pd.Timestamp.today() - pd.Timedelta(days=60)
        usage_df = df[
            (df["Type"] == "Outgoing") &
            (df["Status"] == "Current") &
            (~df["Pending"]) &
            (df["Date"] >= cutoff)
        ]
        avg_use = usage_df.groupby("Size (mm)")["Quantity"].mean().reset_index()
        avg_use.columns = ["Size (mm)", "Avg Daily Usage"]
        
        # === Current stock (non-pending)
        current = df[(df["Status"] == "Current") & (~df["Pending"])].copy()
        current["Net"] = current.apply(lambda x: x["Quantity"] if x["Type"] == "Inward" else -x["Quantity"], axis=1)
        stock_now = current.groupby("Size (mm)")["Net"].sum().reset_index().rename(columns={"Net": "Current Stock"})
        
        # === Pending
        pending = df[df["Pending"]].groupby("Size (mm)")["Quantity"].sum().reset_index()
        pending.columns = ["Size (mm)", "Pending Out"]
        
        # === Future inward
        future = df[(df["Status"] == "Future") & (df["Type"] == "Inward")].groupby("Size (mm)")["Quantity"].sum().reset_index()
        future.columns = ["Size (mm)", "Future In"]
        
        # === Merge
        plan = avg_use.merge(stock_now, on="Size (mm)", how="outer") \
                      .merge(pending, on="Size (mm)", how="outer") \
                      .merge(future, on="Size (mm)", how="outer") \
                      .fillna(0)
        
        plan["Forecast (30d)"] = plan["Avg Daily Usage"] * 30
        plan["Projected Stock"] = plan["Current Stock"] - plan["Pending Out"] + plan["Future In"]
        plan["Suggested Reorder"] = (plan["Forecast (30d)"] - plan["Projected Stock"]).clip(lower=0).round(0).astype(int)
        plan["Days Left"] = (plan["Projected Stock"] / plan["Avg Daily Usage"]).replace([float('inf'), -float('inf')], 0).fillna(0).round(0).astype(int)
        
        # Cast types for display
        for col in ["Avg Daily Usage", "Current Stock", "Pending Out", "Future In", "Forecast (30d)", "Projected Stock", "Suggested Reorder", "Days Left"]:
            plan[col] = plan[col].round(0).astype(int)
        
        # === UI
        st.subheader("📦 Rotor Reorder Overview")
        st.dataframe(plan[[
            "Size (mm)", "Avg Daily Usage", "Current Stock", "Pending Out", "Future In",
            "Projected Stock", "Forecast (30d)", "Suggested Reorder", "Days Left"
        ]].sort_values("Suggested Reorder", ascending=False), use_container_width=True)
        
        # === Reorder Alert
        st.subheader("🚨 Urgent Restock Alert")
        urgent = plan[plan["Days Left"] < 10]
        if urgent.empty:
            st.success("✅ No rotor sizes projected to run out soon.")
        else:
            st.warning("⚠️ The following rotors may run out in under 10 days:")
            st.dataframe(urgent[["Size (mm)", "Days Left", "Suggested Reorder"]], use_container_width=True)
        
        # === Export
        csv = plan.to_csv(index=False).encode("utf-8")
        st.download_button("⬇ Download Full Planning Table", data=csv, file_name="rotor_planning.csv", mime="text/csv")


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

    CLITTING_USAGE = {
        100: 0.04,
        120: 0.05,
        125: 0.05,
        130: 0.05,
        140: 0.05,
        150: 0.06,
        160: 0.06,
        170: 0.07,
        180: 0.07,
        190: 0.08,
        200: 0.08,
        225: 0.10,
        260: 0.15,
        300: 0.20,
    }

    # ---------- Section 1: Clitting Inward ----------
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
                    df = st.session_state.clitting_data
                    st.session_state.clitting_data = df[df["ID"] != row["ID"]].reset_index(drop=True)
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

# ---------- Section 2: Laminations Inward ----------
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
            save_lamination_to_sheet("v3" if l_type == "V3" else "v4")
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
                        save_lamination_to_sheet("v3" if lam_type == "V3" else "v4")
                        st.rerun()
                with col2:
                    new_qty = st.number_input("Quantity", value=int(row["Quantity"]), key=f"qty_{row['ID']}")
                    
                    new_remarks = st.text_input("Remarks", value=row["Remarks"], key=f"rem_{row['ID']}")
                    if st.button("💾 Save", key=f"save_lam_{row['ID']}"):
                        st.session_state[lam_key].at[idx, "Quantity"] = new_qty
                       
                        st.session_state[lam_key].at[idx, "Remarks"] = new_remarks
                        save_lamination_to_sheet("v3" if lam_type == "V3" else "v4")
                        st.success("✅ Entry updated.")

st.divider()
st.subheader("📤 Stator Outgoings")

with st.form("stator_form"):
    s_date = st.date_input("📅 Date", value=datetime.today(), key="stat_date")
    s_size = st.number_input("📏 Stator Size (mm)", min_value=1, step=1, key="stat_size")
    s_qty = st.number_input("🔢 Quantity", min_value=1, step=1, key="stat_qty")
    s_type = st.selectbox("🔀 Lamination Type", ["V3", "V4"], key="stat_type")
    s_remarks = st.text_input("📝 Remarks", key="stat_remarks")

    if st.form_submit_button("📋 Log Stator Outgoing"):
        size_key = int(s_size)
        clitting_per_stator = CLITTING_USAGE.get(size_key,size_key * 0.0004)
        clitting_used = clitting_per_stator * int(s_qty)
        laminations_used = int(s_qty) * 2

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
        lam_key = "lamination_v3" if s_type == "V3" else "lamination_v4"
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

# ----- Logs -----
st.subheader("📄 Stator Usage Log")
for idx, row in st.session_state.stator_data.iterrows():
    with st.expander(f"{row['Date']} | {row['Size (mm)']}mm | Qty: {row['Quantity']}"):
        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("🗑 Delete", key=f"del_stator_{row['ID']}"):
                df = st.session_state.stator_data
                st.session_state.stator_data = df[df["ID"] != row["ID"]].reset_index(drop=True)
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

# ----- Inventory Summary -----
st.divider()
st.header("📊 Inventory Summary")

# ----- Clitting Summary -----
st.subheader("🧮 Clitting Left (in kg)")
clitting_summary = {}

# Add all inward
for idx, row in st.session_state.clitting_data.iterrows():
    size = int(row["Size (mm)"])
    total_kg = int(row["Bags"]) * float(row["Weight per Bag (kg)"])
    clitting_summary[size] = clitting_summary.get(size, 0) + total_kg

# Subtract all usage
for idx, row in st.session_state.stator_data.iterrows():
    try:
        size = int(row["Size (mm)"])
        used = float(row.get("Estimated Clitting (kg)", 0)) or 0
        if size in clitting_summary:
            clitting_summary[size] -= used
            clitting_summary[size] = max(clitting_summary[size], 0)  # no negatives
    except (ValueError, TypeError, KeyError):
        continue

# Display
if clitting_summary:
    for size, kg in sorted(clitting_summary.items()):
        st.markdown(f"• **{size}mm** → `{kg:.2f} kg` left")
else:
    st.info("No clitting data available.")

# ----- Lamination Summary -----
st.subheader("🧩 Laminations Left (in Qty)")



def lam_summary(lam_df):
    return lam_df["Quantity"].sum()

v3_total = lam_summary(st.session_state["lamination_v3"])
v4_total = lam_summary(st.session_state["lamination_v4"])

if v3_total > 0:
    st.markdown(f"**🔹 V3 Laminations** → `{v3_total}` left")
else:
    st.info("No V3 lamination data available.")

if v4_total > 0:
    st.markdown(f"**🔹 V4 Laminations** → `{v4_total}` left")
else:
    st.info("No V4 lamination data available.")

# ----- Inventory Summary -----





    # 🔌 Streamlit API endpoint for Swift
    
    # ====== LAST SYNC STATUS ======
       # just do this directly

    
