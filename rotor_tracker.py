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
    tabs = st.tabs(["📊 Stock Summary", "📋 Movement Log", "💬 Rotor Chatbot lite"])
    
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
    with tabs[2]:
        st.subheader("💬 Rotor Chatbot Lite")
        
        # Fixed prices for specific sizes (in Rupees)
        FIXED_PRICES = {
            1803: 430,    # ₹430 per rotor
            2003: 478,    # ₹478 per rotor
            35: 200,      # ₹200 per rotor
            40: 220,      # ₹220 per rotor
            50: 278,      # ₹278 per rotor
            70: 378       # ₹378 per rotor
        }
        
        # Base rate per mm for other sizes
        BASE_RATE_PER_MM = 3.8
        
        # Display fixed prices
        with st.expander("💰 Fixed Prices"):
            st.write("Size (mm) → Price per rotor:")
            for size, price in sorted(FIXED_PRICES.items()):
                st.write(f"- {size}mm: ₹{price}")
            st.write(f"- Other sizes: ₹{BASE_RATE_PER_MM} per mm")
        
        # Display example queries
        with st.expander("📋 Example Queries"):
            st.markdown("""
            **Query Examples:**
            - `ravi pending` - Show all pending rotors for Ravi
            - `ravi january` - Show Ravi's transactions in January
            - `outgoing february` - Show all outgoing rotors in February
            - `incoming may` - Show all incoming rotors in May
            - `coming rotors` - Show all future incoming rotors (date-wise)
            - `size pending 1803` - Show pending rotors for size 1803mm
            - `size summary 2003` - Show all transactions for size 2003mm
            - `ravi summary 2024` - Show Ravi's yearly summary
            - `all buyers` - List all buyers with their total transactions
            - `stock alert` - Show stock alerts
            - `price list` - Show fixed prices
            """)
        
        chat_query = st.text_input(
            "💬 Ask about rotors:",
            placeholder="e.g., size pending 1803 | coming rotors | all buyers"
        )
        
        if not chat_query:
            st.info("👆 Enter a query above to get started")
            st.stop()
        
        # =========================
        # IMPROVED DATA PREPARATION
        # =========================
        df = st.session_state.data.copy()
        
        # Clean and prepare data
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['Remarks'] = df['Remarks'].astype(str).str.strip()
        df['Type'] = df['Type'].astype(str).str.strip()
        df['Status'] = df['Status'].astype(str).str.strip()
        df['Size (mm)'] = pd.to_numeric(df['Size (mm)'], errors='coerce')
        df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce')
        
        # Drop rows with invalid dates
        df = df.dropna(subset=['Date'])
        
        query = chat_query.lower().strip()
        
        # =========================
        # DETECT SIZE IN QUERY
        # =========================
        target_size = None
        # Look for size numbers in the query
        size_matches = re.findall(r'\b(\d+)\b', query)
        for size_str in size_matches:
            size_num = int(size_str)
            # Check if this looks like a rotor size (common sizes or > 20mm)
            if size_num in FIXED_PRICES or size_num > 20:
                target_size = size_num
                break
        
        # =========================
        # SPECIAL COMMAND: PRICE LIST
        # =========================
        if 'price list' in query or 'prices' in query:
            st.subheader("💰 Fixed Price List")
            
            price_data = []
            for size, price in sorted(FIXED_PRICES.items()):
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
        year_num = datetime.now().year  # Default to current year
        
        # Check for month names (full and abbreviated)
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
        
        # Check for year in query (e.g., "2024", "2025")
        year_match = re.search(r'\b(20\d{2})\b', query)
        if year_match:
            year_num = int(year_match.group(1))
        
        # =========================
        # IMPROVED BUYER DETECTION
        # =========================
        buyers = sorted([b for b in df['Remarks'].unique() if b and b.strip() and b.lower() not in ['', 'nan', 'none']])
        
        buyer = None
        
        for b in buyers:
            b_lower = b.lower()
            if b_lower in query and len(b_lower) > 2:
                buyer = b
                break
        
        show_all_buyers = 'all buyers' in query or 'buyers list' in query
        
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
        # NEW ESTIMATION FUNCTION WITH FIXED PRICES
        # =========================
        def calculate_value(size_mm, quantity):
            """Calculate value based on fixed prices or base rate"""
            if pd.isna(size_mm) or pd.isna(quantity):
                return 0
            
            size_int = int(size_mm)
            
            # Check if size has fixed price
            if size_int in FIXED_PRICES:
                return FIXED_PRICES[size_int] * quantity
            else:
                # Use base rate for other sizes
                return BASE_RATE_PER_MM * size_int * quantity
        
        def get_price_per_rotor(size_mm):
            """Get price per rotor for a given size"""
            if pd.isna(size_mm):
                return 0
            
            size_int = int(size_mm)
            if size_int in FIXED_PRICES:
                return FIXED_PRICES[size_int]
            else:
                return BASE_RATE_PER_MM * size_int
        
        # =========================
        # SPECIAL CASE: SIZE PENDING
        # =========================
        if target_size and ('pending' in query or 'size pending' in query):
            st.subheader(f"📊 Pending Rotors for Size {target_size}mm")
            
            # Get pending rotors for the specific size
            pending_df = df[
                (df['Size (mm)'] == target_size) &
                (df['Pending'] == True) &
                (df['Status'] == 'Current') &
                (df['Type'] == 'Outgoing')
            ].copy()
            
            if pending_df.empty:
                st.info(f"No pending rotors found for size {target_size}mm")
                
                # Check if we have any rotors of this size
                any_size_df = df[df['Size (mm)'] == target_size]
                if not any_size_df.empty:
                    total_stock = any_size_df[
                        (any_size_df['Type'] == 'Inward') & 
                        (~any_size_df['Pending'])
                    ]['Quantity'].sum() - any_size_df[
                        (any_size_df['Type'] == 'Outgoing') & 
                        (~any_size_df['Pending'])
                    ]['Quantity'].sum()
                    
                    if total_stock > 0:
                        st.success(f"✅ We have {int(total_stock)} rotors of size {target_size}mm in stock (no pending)")
                    else:
                        st.warning(f"⚠️ No stock available for size {target_size}mm")
                
                st.stop()
            
            # Sort by date
            pending_df = pending_df.sort_values('Date')
            
            # Calculate totals
            total_pending_qty = pending_df['Quantity'].sum()
            price_per = get_price_per_rotor(target_size)
            total_value = calculate_value(target_size, total_pending_qty)
            
            # Display summary
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Pending", f"{int(total_pending_qty)} rotors")
            with col2:
                st.metric("Price per Rotor", f"₹{price_per}")
            with col3:
                st.metric("Total Value", f"₹{total_value:,.2f}")
            
            # Group by buyer
            st.subheader("📋 Pending by Buyer")
            buyer_summary = []
            
            for buyer_name in pending_df['Remarks'].unique():
                buyer_data = pending_df[pending_df['Remarks'] == buyer_name]
                buyer_qty = buyer_data['Quantity'].sum()
                buyer_value = calculate_value(target_size, buyer_qty)
                
                buyer_summary.append({
                    'Buyer': buyer_name,
                    'Quantity': int(buyer_qty),
                    'Total Value': f"₹{buyer_value:,.2f}",
                    'First Order Date': buyer_data['Date'].min().strftime('%Y-%m-%d'),
                    'Latest Order Date': buyer_data['Date'].max().strftime('%Y-%m-%d')
                })
            
            if buyer_summary:
                buyer_df = pd.DataFrame(buyer_summary)
                st.dataframe(buyer_df, use_container_width=True, hide_index=True)
            
            # Show current stock for this size
            st.subheader("📦 Current Stock Status")
            
            # Calculate current stock
            current_stock_df = df[
                (df['Size (mm)'] == target_size) &
                (df['Status'] == 'Current')
            ].copy()
            
            current_stock_df['Net'] = current_stock_df.apply(
                lambda x: x['Quantity'] if x['Type'] == 'Inward' else -x['Quantity'], axis=1
            )
            
            # Separate pending and non-pending
            current_stock = current_stock_df[~current_stock_df['Pending']]['Net'].sum()
            available_after_pending = current_stock - total_pending_qty
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Current Stock", f"{int(current_stock)}")
            with col2:
                st.metric("Pending Orders", f"{int(total_pending_qty)}")
            with col3:
                status_color = "🟢" if available_after_pending >= 0 else "🔴"
                st.metric("After Pending", f"{status_color} {int(available_after_pending)}")
            
            if available_after_pending < 0:
                st.error(f"⚠️ Shortage: Need {abs(int(available_after_pending))} more rotors to fulfill all pending orders")
            
            # Check for future incoming of this size
            future_incoming = df[
                (df['Size (mm)'] == target_size) &
                (df['Status'] == 'Future') &
                (df['Type'] == 'Inward')
            ]['Quantity'].sum()
            
            if future_incoming > 0:
                st.info(f"📅 Future incoming: {int(future_incoming)} rotors expected")
                if available_after_pending < 0:
                    total_after_incoming = available_after_pending + future_incoming
                    if total_after_incoming >= 0:
                        st.success(f"✅ Future incoming will cover the shortage")
                    else:
                        st.warning(f"⚠️ Still short by {abs(int(total_after_incoming))} even after future incoming")
            
            st.stop()
        
        # =========================
        # SPECIAL CASE: SIZE SUMMARY
        # =========================
        if target_size and ('summary' in query or 'size summary' in query):
            st.subheader(f"📊 Complete Summary for Size {target_size}mm")
            
            # Filter for the specific size
            size_df = df[df['Size (mm)'] == target_size].copy()
            
            if size_df.empty:
                st.info(f"No transactions found for size {target_size}mm")
                st.stop()
            
            price_per = get_price_per_rotor(target_size)
            
            # Overall metrics
            total_inward = size_df[size_df['Type'] == 'Inward']['Quantity'].sum()
            total_outgoing = size_df[size_df['Type'] == 'Outgoing']['Quantity'].sum()
            current_stock = total_inward - total_outgoing
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Inward", f"{int(total_inward)}")
            with col2:
                st.metric("Total Outgoing", f"{int(total_outgoing)}")
            with col3:
                st.metric("Current Stock", f"{int(current_stock)}")
            with col4:
                st.metric("Price/Rotor", f"₹{price_per}")
            
            # Monthly breakdown
            st.subheader("📅 Monthly Transactions")
            size_df['MonthYear'] = size_df['Date'].dt.strftime('%b %Y')
            
            monthly_summary = size_df.groupby(['MonthYear', 'Type']).agg({
                'Quantity': 'sum',
                'Remarks': lambda x: ', '.join(sorted(set([str(r) for r in x if str(r) not in ['', 'nan']])))
            }).reset_index()
            
            # Pivot for better display
            monthly_pivot = monthly_summary.pivot_table(
                index='MonthYear',
                columns='Type',
                values='Quantity',
                aggfunc='sum',
                fill_value=0
            ).reset_index()
            
            # Add net column
            if 'Inward' in monthly_pivot.columns and 'Outgoing' in monthly_pivot.columns:
                monthly_pivot['Net'] = monthly_pivot['Inward'] - monthly_pivot['Outgoing']
            elif 'Inward' in monthly_pivot.columns:
                monthly_pivot['Net'] = monthly_pivot['Inward']
            elif 'Outgoing' in monthly_pivot.columns:
                monthly_pivot['Net'] = -monthly_pivot['Outgoing']
            
            st.dataframe(monthly_pivot, use_container_width=True, hide_index=True)
            
            # Buyer-wise summary
            st.subheader("👥 Buyer-wise Summary")
            buyer_data = []
            
            for buyer_name in size_df['Remarks'].unique():
                if buyer_name in ['', 'nan']:
                    continue
                    
                buyer_transactions = size_df[size_df['Remarks'] == buyer_name]
                buyer_inward = buyer_transactions[buyer_transactions['Type'] == 'Inward']['Quantity'].sum()
                buyer_outgoing = buyer_transactions[buyer_transactions['Type'] == 'Outgoing']['Quantity'].sum()
                buyer_pending = buyer_transactions[
                    (buyer_transactions['Type'] == 'Outgoing') & 
                    (buyer_transactions['Pending'] == True)
                ]['Quantity'].sum()
                
                buyer_value = calculate_value(target_size, buyer_outgoing)
                
                buyer_data.append({
                    'Buyer': buyer_name,
                    'Inward': int(buyer_inward),
                    'Outgoing': int(buyer_outgoing),
                    'Pending': int(buyer_pending),
                    'Total Value': f"₹{buyer_value:,.2f}",
                    'First Transaction': buyer_transactions['Date'].min().strftime('%Y-%m-%d'),
                    'Last Transaction': buyer_transactions['Date'].max().strftime('%Y-%m-%d')
                })
            
            if buyer_data:
                buyer_df = pd.DataFrame(buyer_data)
                st.dataframe(buyer_df, use_container_width=True, hide_index=True)
            
            # Recent transactions
            st.subheader("🔄 Recent Transactions (Last 30 days)")
            recent_cutoff = datetime.now() - timedelta(days=30)
            recent_df = size_df[size_df['Date'] >= recent_cutoff].sort_values('Date', ascending=False)
            
            if not recent_df.empty:
                display_recent = recent_df[['Date', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending']].copy()
                display_recent['Date'] = display_recent['Date'].dt.strftime('%Y-%m-%d')
                display_recent['Pending'] = display_recent['Pending'].apply(lambda x: 'Yes' if x else 'No')
                
                st.dataframe(
                    display_recent.rename(columns={
                        'Type': 'Movement',
                        'Quantity': 'Qty'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No transactions in the last 30 days")
            
            st.stop()
        
        # =========================
        # SPECIAL CASE: COMING ROTORS DATE-WISE
        # =========================
        if movement == 'coming_datewise':
            st.subheader("📅 Coming Rotors - Date-wise")
            
            # Filter for future incoming rotors
            coming_df = df[
                (df['Status'] == 'Future') & 
                (df['Type'] == 'Inward')
            ].copy()
            
            if coming_df.empty:
                st.info("No future rotors expected")
                st.stop()
            
            # Sort by date
            coming_df = coming_df.sort_values('Date')
            
            # Group by date
            date_summary = []
            for date, group in coming_df.groupby('Date'):
                date_str = date.strftime('%Y-%m-%d (%A)')
                
                # Group by size within each date
                size_details = []
                for _, row in group.iterrows():
                    size = int(row['Size (mm)']) if not pd.isna(row['Size (mm)']) else 0
                    qty = int(row['Quantity'])
                    price_per = get_price_per_rotor(size)
                    total_value = calculate_value(size, qty)
                    
                    size_details.append({
                        'Size': size,
                        'Quantity': qty,
                        'Price per Rotor': f"₹{price_per}",
                        'Total Value': f"₹{total_value:,.2f}"
                    })
                
                date_total_qty = group['Quantity'].sum()
                date_total_value = sum(calculate_value(row['Size (mm)'], row['Quantity']) 
                                     for _, row in group.iterrows())
                
                date_summary.append({
                    'Date': date_str,
                    'Total Quantity': date_total_qty,
                    'Total Value': f"₹{date_total_value:,.2f}",
                    'Size Details': size_details
                })
            
            # Display date-wise summary
            for date_info in date_summary:
                with st.expander(f"📅 **{date_info['Date']}** - {date_info['Total Quantity']} rotors (₹{date_info['Total Value'][1:].replace(',', '')})"):
                    # Create a DataFrame for size details
                    details_df = pd.DataFrame(date_info['Size Details'])
                    st.dataframe(details_df, use_container_width=True, hide_index=True)
                    
                    # Add remarks if available
                    date_remarks = coming_df[coming_df['Date'] == pd.to_datetime(date_info['Date'].split()[0])]['Remarks'].unique()
                    if len(date_remarks) > 0 and not all(str(r) in ['', 'nan'] for r in date_remarks):
                        st.write(f"**Remarks:** {', '.join([str(r) for r in date_remarks if str(r) not in ['', 'nan']])}")
            
            # Overall summary
            st.subheader("📊 Coming Rotors Summary")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                total_coming = coming_df['Quantity'].sum()
                st.metric("Total Rotors Coming", f"{int(total_coming):,}")
            
            with col2:
                total_value = sum(calculate_value(row['Size (mm)'], row['Quantity']) 
                                for _, row in coming_df.iterrows())
                st.metric("Total Value", f"₹{total_value:,.2f}")
            
            with col3:
                unique_dates = coming_df['Date'].nunique()
                st.metric("Delivery Days", unique_dates)
            
            with col4:
                avg_per_day = total_coming / unique_dates if unique_dates > 0 else 0
                st.metric("Avg per Day", f"{avg_per_day:.1f}")
            
            # Size-wise summary of all coming rotors
            st.subheader("📈 Size-wise Distribution")
            size_dist = coming_df.groupby('Size (mm)').agg({
                'Quantity': 'sum',
            }).reset_index()
            
            # Calculate value for each size
            size_dist['Total Value'] = size_dist.apply(
                lambda x: calculate_value(x['Size (mm)'], x['Quantity']), axis=1
            )
            size_dist['Price per Rotor'] = size_dist['Size (mm)'].apply(get_price_per_rotor)
            
            # Sort by quantity
            size_dist = size_dist.sort_values('Quantity', ascending=False)
            
            # Format for display
            display_size = size_dist.copy()
            display_size['Total Value'] = display_size['Total Value'].apply(lambda x: f"₹{x:,.2f}")
            display_size['Price per Rotor'] = display_size['Price per Rotor'].apply(lambda x: f"₹{x:,.0f}")
            
            st.dataframe(
                display_size.rename(columns={
                    'Size (mm)': 'Size',
                    'Quantity': 'Total Qty',
                    'Price per Rotor': 'Price/Rotor',
                    'Total Value': 'Total Value'
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
            st.subheader("📋 All Buyers List")
            
            buyer_summary = []
            for b in buyers:
                buyer_data = df[df['Remarks'] == b]
                total_rotors = buyer_data['Quantity'].sum()
                
                # Calculate total value with new pricing logic
                total_value = 0
                for _, row in buyer_data.iterrows():
                    total_value += calculate_value(row['Size (mm)'], row['Quantity'])
                
                buyer_summary.append({
                    'Buyer': b,
                    'Total Rotors': int(total_rotors),
                    'Total Value': f"₹{total_value:,.2f}",
                    'Avg Value per Rotor': f"₹{total_value/total_rotors:,.2f}" if total_rotors > 0 else "₹0",
                    'First Transaction': buyer_data['Date'].min().strftime('%Y-%m-%d') if not buyer_data.empty else 'N/A',
                    'Last Transaction': buyer_data['Date'].max().strftime('%Y-%m-%d') if not buyer_data.empty else 'N/A'
                })
            
            if buyer_summary:
                summary_df = pd.DataFrame(buyer_summary)
                st.dataframe(summary_df, use_container_width=True, hide_index=True)
            else:
                st.info("No buyer data available")
            
            st.stop()
        
        # CASE 2: STOCK ALERTS
        elif movement == 'stock_alert':
            st.subheader("🚨 Stock Alerts")
            
            # Calculate current stock
            current_df = df[
                (df['Status'] == 'Current') & 
                (~df['Pending'])
            ].copy()
            current_df['Net'] = current_df.apply(
                lambda x: x['Quantity'] if x['Type'] == 'Inward' else -x['Quantity'], axis=1
            )
            stock = current_df.groupby('Size (mm)')['Net'].sum().reset_index()
            
            # Calculate pending
            pending_df = df[(df['Pending'] == True) & (df['Status'] == 'Current')]
            pending_out = pending_df.groupby('Size (mm)')['Quantity'].sum().reset_index()
            
            # Merge and calculate alerts
            merged = stock.merge(pending_out, on='Size (mm)', how='outer', suffixes=('_stock', '_pending')).fillna(0)
            
            # Add current stock value
            merged['Stock Value'] = merged.apply(
                lambda x: calculate_value(x['Size (mm)'], x['Net']), axis=1
            )
            
            # Check for low stock (less than 50)
            low_stock = merged[merged['Net'] < 50]
            if not low_stock.empty:
                st.warning("⚠️ Low Stock Alert (less than 50):")
                display_df = low_stock[['Size (mm)', 'Net', 'Stock Value']].copy()
                display_df['Stock Value'] = display_df['Stock Value'].apply(lambda x: f"₹{x:,.2f}")
                st.dataframe(display_df.rename(columns={'Net': 'Current Stock'}), 
                            use_container_width=True, hide_index=True)
            else:
                st.success("✅ No low stock issues")
            
            # Check if pending exceeds stock
            risky = merged[merged['Quantity'] > merged['Net']]
            if not risky.empty:
                st.error("🔴 Pending exceeds available stock:")
                display_risky = risky[['Size (mm)', 'Net', 'Quantity']].copy()
                display_risky['Value at Risk'] = display_risky.apply(
                    lambda x: calculate_value(x['Size (mm)'], x['Quantity'] - x['Net']), axis=1
                )
                display_risky['Value at Risk'] = display_risky['Value at Risk'].apply(lambda x: f"₹{x:,.2f}")
                st.dataframe(display_risky.rename(
                    columns={'Net': 'Available', 'Quantity': 'Pending'}), 
                    use_container_width=True, hide_index=True)
            
            st.stop()
        
        # CASE 3: REGULAR QUERIES
        filtered = df.copy()
        
        # Apply buyer filter
        if buyer:
            filtered = filtered[filtered['Remarks'].str.lower() == buyer.lower()]
        
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
                similar_buyers = [b for b in buyers if buyer.lower() in b.lower()]
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
            title_parts.append(f"**{movement.upper()}**")
        
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
            method = "Fixed Price" if target_size in FIXED_PRICES else f"₹{BASE_RATE_PER_MM}/mm × {target_size}mm"
            st.info(f"**Pricing:** {target_size}mm = ₹{price} ({method})")
        elif len(filtered['Size (mm)'].unique()) <= 5:
            st.info("**Pricing Used:**")
            for size in sorted(filtered['Size (mm)'].unique()):
                price = get_price_per_rotor(size)
                method = "Fixed Price" if size in FIXED_PRICES else f"₹{BASE_RATE_PER_MM}/mm × {size}mm"
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
   

# ----- Inventory Summary -----





    # 🔌 Streamlit API endpoint for Swift
    
    # ====== LAST SYNC STATUS ======
       # just do this directly

    
