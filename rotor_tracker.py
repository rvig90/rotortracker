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
if st.session_state.last_sync == "Never":
    load_from_gsheet()

if st.button("🔄 Sync Now", help="Manually reload data from Google Sheets"):
    load_from_gsheet()

# ====== ENTRY FORMS ======
form_tabs = st.tabs(["Current Movement", "Coming Rotors", "Pending Rotors"])

def add_entry(data_dict):
    data_dict['ID'] = str(uuid4())
    new = pd.DataFrame([data_dict])
    st.session_state.data = pd.concat([st.session_state.data, new], ignore_index=True)
    auto_save_to_gsheet()
    st.rerun()

with form_tabs[0]:
    with st.form("current_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Date", value=datetime.today())
            rotor_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
        with col2:
            entry_type = st.selectbox("🔄 Type", ["Inward", "Outgoing"])
            quantity = st.number_input("🔢 Quantity", min_value=1, step=1)
        remarks = st.text_input("📝 Remarks")
        if st.form_submit_button("➕ Add Entry"):
            add_entry({
                'Date': date.strftime('%Y-%m-%d'),
                'Size (mm)': rotor_size,
                'Type': entry_type,
                'Quantity': quantity,
                'Remarks': remarks,
                'Status': 'Current',
                'Pending': False
            })

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

with form_tabs[2]:
    with st.form("pending_form"):
        col1, col2 = st.columns(2)
        with col1:
            pending_date = st.date_input("📅 Date", value=datetime.today())
            pending_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
        with col2:
            pending_qty = st.number_input("🔢 Quantity", min_value=1, step=1)
            pending_remarks = st.text_input("📝 Remarks", value="Pending delivery")
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
    st.subheader("🔔 Stock Alerts")

    df = st.session_state.data.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    
    # Filter current entries and calculate stock
    current = df[
        (df["Status"] == "Current") &
        (~df["Pending"])
    ].copy()
    
    current["Net"] = current.apply(
        lambda x: x["Quantity"] if x["Type"] == "Inward" else -x["Quantity"],
        axis=1
    )
    
    stock = current.groupby("Size (mm)")["Net"].sum().reset_index()
    stock.columns = ["Size (mm)", "Current Stock"]
    
    # Get future rotors (inward)
    future = df[
        (df["Status"] == "Future") &
        (df["Type"] == "Inward")
    ].groupby("Size (mm)")["Quantity"].sum().reset_index()
    future.columns = ["Size (mm)", "Coming Qty"]
    
    # Merge to identify which ones have no incoming
    combined = pd.merge(stock, future, on="Size (mm)", how="left").fillna(0)
    
    # Alert if stock < 100 and no future quantity
    alert_df = combined[
        (combined["Current Stock"] < 100) &
        (combined["Coming Qty"] == 0)
    ]
    
    if not alert_df.empty:
        st.warning("⚠ Low Stock Rotors with No Incoming Orders:")
        st.dataframe(alert_df, use_container_width=True, hide_index=True)
    else:
        st.success("✅ All rotor sizes have sufficient stock or incoming orders.")

    # Alert: Pending > 7 days
    pending = st.session_state.data[
        (st.session_state.data['Status'] == 'Current') &
        (st.session_state.data['Pending'])
    ].copy()
    pending['Days Pending'] = (pd.Timestamp.today() - pd.to_datetime(pending['Date'])).dt.days
    overdue = pending[pending['Days Pending'] > 7]

    if not overdue.empty:
        st.error("🚨 Overdue Pending Rotors (Pending > 7 days):")
        st.dataframe(overdue[['Date', 'Size (mm)', 'Quantity', 'Remarks', 'Days Pending']], use_container_width=True, hide_index=True)     
    
    st.subheader("🧠 AI-Powered Reorder Suggestions (with Pending & Future Awareness)")
    
    df = st.session_state.data.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    
    # === 1. Recent Outgoing Usage ===
    cutoff = pd.Timestamp.today() - pd.Timedelta(days=60)
    outgoing = df[
        (df["Type"] == "Outgoing") &
        (df["Status"] == "Current") &
        (~df["Pending"]) &
        (df["Date"] >= cutoff)
    ].copy()
    
    usage = (
        outgoing.groupby(["Date", "Size (mm)"])["Quantity"]
        .sum()
        .groupby("Size (mm)").mean()
        .reset_index()
        .rename(columns={"Quantity": "Avg Daily Usage"})
    )
    
    # === 2. Current Stock (Inward - Outgoing, not pending) ===
    current = df[
        (df["Status"] == "Current") & (~df["Pending"])
    ].copy()
    current["Net"] = current.apply(
        lambda x: x["Quantity"] if x["Type"] == "Inward" else -x["Quantity"], axis=1
    )
    stock_now = current.groupby("Size (mm)")["Net"].sum().reset_index().rename(columns={"Net": "Stock Now"})
    
    # === 3. Pending Outgoing Rotors ===
    pending = df[(df["Status"] == "Current") & (df["Pending"])].copy()
    pending_sum = pending.groupby("Size (mm)")["Quantity"].sum().reset_index().rename(columns={"Quantity": "Pending Out"})
    
    # === 4. Future Inward Rotors ===
    future = df[(df["Status"] == "Future") & (df["Type"] == "Inward")].copy()
    future_sum = future.groupby("Size (mm)")["Quantity"].sum().reset_index().rename(columns={"Quantity": "Coming In"})
    
    # === 5. Merge All Sources ===
    df_all = usage.merge(stock_now, on="Size (mm)", how="outer") \
                  .merge(pending_sum, on="Size (mm)", how="outer") \
                  .merge(future_sum, on="Size (mm)", how="outer") \
                  .fillna(0)
    
    # === 6. Calculations ===
    df_all["Projected Stock"] = df_all["Stock Now"] - df_all["Pending Out"] + df_all["Coming In"]
    df_all["Forecast (30d)"] = df_all["Avg Daily Usage"] * 30
    df_all["Safety Buffer"] = df_all["Avg Daily Usage"] * 7
    df_all["Target Stock"] = df_all["Forecast (30d)"] + df_all["Safety Buffer"]
    df_all["Suggested Reorder"] = (df_all["Target Stock"] - df_all["Projected Stock"]).clip(lower=0)
    
    # === 7. Round All Quantities to Int ===
    cols_to_round = [
        "Avg Daily Usage", "Stock Now", "Pending Out", "Coming In",
        "Projected Stock", "Forecast (30d)", "Suggested Reorder"
    ]
    for col in cols_to_round:
        df_all[col] = df_all[col].round(0).astype(int)
    
    # === 8. Filter and Show Reorder List ===
    reorder = df_all[df_all["Suggested Reorder"] > 0]
    
    if reorder.empty:
        st.success("✅ All rotor sizes are sufficiently stocked with pending and future accounted for.")
    else:
        st.warning("🔄 The following rotor sizes may run short in the next 30 days:")
        st.dataframe(
            reorder[[
                "Size (mm)", "Avg Daily Usage", "Stock Now", "Pending Out", "Coming In",
                "Projected Stock", "Forecast (30d)", "Suggested Reorder"
            ]].sort_values("Suggested Reorder", ascending=False),
            use_container_width=True,
            hide_index=True
        )

    from prophet import Prophet
    
    st.subheader("🔮 Forecasted Rotor Demand (Next 6 Months)")
    
    # Choose a rotor size
    available_sizes = sorted(outgoing["Size (mm)"].unique())
    selected_size = st.selectbox("Select Rotor Size to Forecast", available_sizes)
    
    # Filter data for selected size
    df_size = outgoing[outgoing["Size (mm)"] == selected_size]
    daily = df_size.groupby("Date")["Quantity"].sum().reset_index()
    daily.columns = ["ds", "y"]
    
    if len(daily) < 4:
        st.info("Not enough data to forecast this size.")
    else:
        m = Prophet()
        m.fit(daily)
    
        future = m.make_future_dataframe(periods=180)  # Next 6 months
        forecast = m.predict(future)
    
        # Monthly summary
        forecast["Month"] = forecast["ds"].dt.to_period("M")
        monthly = forecast.groupby("Month")["yhat"].mean().reset_index()
        monthly.columns = ["Month", "Forecasted Quantity"]
        monthly["Forecasted Quantity"] = monthly["Forecasted Quantity"].round(0).astype(int)
       
    
        st.dataframe(monthly.tail(6), use_container_width=True)
    
        # Chart
        import altair as alt
        chart = alt.Chart(monthly.tail(6)).mark_bar().encode(
            x=alt.X("Month:T", title="Month"),
            y=alt.Y("Forecasted Quantity:Q", title="Forecasted Avg Quantity"),
            tooltip=["Month", "Forecasted Quantity"]
        ).properties(
            title=f"Forecasted Monthly Demand for {selected_size}mm Rotor",
            width="container",
            height=300
        )
        st.altair_chart(chart, use_container_width=True)
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
        if "rs" not in st.session_state: st.session_state.rs = ""
        if "dr" not in st.session_state:
            min_date = pd.to_datetime(df['Date']).min().date()
            max_date = pd.to_datetime(df['Date']).max().date()
            st.session_state.dr = [min_date, max_date]

        # Filter Reset Button
        if st.button("🔄 Reset All Filters"):
            st.session_state.sf = "All"
            st.session_state.zf = []
            st.session_state.pf = "All"
            st.session_state.rs = ""
            min_date = pd.to_datetime(df['Date']).min().date()
            max_date = pd.to_datetime(df['Date']).max().date()
            st.session_state.dr = [min_date, max_date]
            st.rerun()

        # Filter Controls
        c1, c2, c3 = st.columns(3)
        with c1:
            status_f = st.selectbox("📂 Status", ["All", "Current", "Future"], key="sf")
        with c2:
            size_options = sorted(df['Size (mm)'].dropna().unique())
            size_f = st.multiselect("📐 Size (mm)", options=size_options, key="zf")
        with c3:
            pending_f = st.selectbox("❗ Pending", ["All", "Yes", "No"], key="pf")

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

            if st.session_state.editing == match_idx:
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
with tabs[2]:
    import re
    st.subheader("💬 Rotor Chatbot lite")
    
    chat_query = st.text_input("Try: 'Buyer A', '100mm last 5', 'Buyer B pending', or 'MegaTech last 3 outgoing pending'")
    
    df = st.session_state.data.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df[df["Status"] != "Future"]  # ✅ Exclude Future entries
    # === CASE: 'pendings' or 'pending orders' — group by buyer + size
    if re.search(r"\b(pendings|pending orders?)\b", chat_query.lower()):
        pending_df = df[
            (df["Type"] == "Outgoing") &
            (df["Pending"] == True) &
            (df["Status"] == "Current")
        ].copy()
    
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
    
    # === Extract all possible filters ===
    last_n_match = re.search(r"last\s*(\d+)", chat_query.lower())
    size_match = re.search(r"(\d{2,6})", chat_query)
    type_match = re.search(r"\b(inward|outgoing)\b", chat_query.lower())
    is_pending = "pending" in chat_query.lower()
    
    entry_count = int(last_n_match.group(1)) if last_n_match else None
    rotor_size = int(size_match.group(1)) if size_match else None
    movement_type = type_match.group(1).capitalize() if type_match else None
    
    # Remove known keywords to isolate possible buyer name
    query_cleaned = re.sub(r"(last\s*\d+|inward|outgoing|pending|\d{2,4})", "", chat_query, flags=re.IGNORECASE).strip()
    buyer_name = query_cleaned if query_cleaned else None

    # === CASE: "250mm pendings"
    if rotor_size and is_pending:
        pending_for_size = df[
            (df["Size (mm)"] == rotor_size) &
            (df["Type"] == "Outgoing") &
            (df["Pending"] == True)
        ]
    
        if not pending_for_size.empty:
            st.success(f"📦 Pending Outgoing Orders for **{rotor_size}mm**")
            st.dataframe(pending_for_size[["Date", "Quantity", "Remarks"]].sort_values("Date"), use_container_width=True)
        else:
            st.info(f"No pending outgoing orders found for **{rotor_size}mm**.")
    
    # === CASE: "250mm stock"
    if rotor_size and "stock" in chat_query.lower():
        current_df = df[
            (df["Size (mm)"] == rotor_size) &
            (df["Status"] == "Current")
        ].copy()
    
        current_df["Net"] = current_df.apply(
            lambda x: x["Quantity"] if x["Type"] == "Inward" else -x["Quantity"] if not x["Pending"] else 0,
            axis=1
        )
    
        current_stock = current_df["Net"].sum()
    
        st.success(f"📦 Current stock for **{rotor_size}mm** rotor: `{int(current_stock)}` units")
    
        # Optional: Breakdown
        inward = current_df[current_df["Type"] == "Inward"]["Quantity"].sum()
        delivered = current_df[
            (current_df["Type"] == "Outgoing") &
            (~current_df["Pending"])
        ]["Quantity"].sum()
    
        pending_qty = current_df[
            (current_df["Type"] == "Outgoing") &
            (current_df["Pending"])
        ]["Quantity"].sum()
    
        st.markdown(f"""
    - 📥 **Total Inward**: `{int(inward)}`
    - 📤 **Delivered Outgoing**: `{int(delivered)}`
    - ❗ **Pending Outgoing**: `{int(pending_qty)}`
    - 📦 **Net Stock (Available)**: `{int(current_stock)}`
        """)
    
        # Optional: Trend chart
        history = current_df.groupby("Date")["Net"].sum().cumsum().reset_index()
        if not history.empty:
            st.markdown("#### 📈 Stock Movement Over Time")
            st.line_chart(history.set_index("Date"))
    # === CASE 1: "last N" entries (with optional rotor, type, buyer, pending)
    if entry_count:
        filtered = df.copy()
    
        if rotor_size:
            filtered = filtered[filtered["Size (mm)"] == rotor_size]
    
        if movement_type:
            filtered = filtered[filtered["Type"] == movement_type]
    
        if is_pending:
            filtered = filtered[filtered["Pending"] == True]
    
        if buyer_name:
            filtered = filtered[filtered["Remarks"].str.contains(buyer_name, case=False, na=False)]
    
        filtered = filtered.sort_values("Date", ascending=False).head(entry_count)
    
        if not filtered.empty:
            title = f"📋 Last {entry_count} entries"
            if rotor_size:
                title += f" for **{rotor_size}mm**"
            if movement_type:
                title += f" ({movement_type})"
            if is_pending:
                title += " [Pending]"
            if buyer_name:
                title += f" from **{buyer_name}**"
    
            st.success(title)
            st.dataframe(filtered[["Date", "Size (mm)", "Type", "Quantity", "Remarks", "Pending"]], use_container_width=True)
        else:
            st.info("No matching entries found.")
    
    # === CASE 2: Just rotor size
    elif rotor_size:
        size_df = df[df["Size (mm)"] == rotor_size]
        if not size_df.empty:
            st.success(f"📄 All entries for **{rotor_size}mm** rotor")
            st.dataframe(size_df[["Date", "Type", "Quantity", "Remarks", "Pending"]], use_container_width=True)
        else:
            st.info(f"No entries found for {rotor_size}mm.")
    
    # === CASE 3: Buyer with 'pending'
    elif is_pending and buyer_name:
        buyer_pending = df[
            (df["Type"] == "Outgoing") &
            (df["Pending"] == True) &
            (df["Remarks"].str.contains(buyer_name, case=False, na=False))
        ]
        if not buyer_pending.empty:
            st.success(f"📬 Pending orders for **{buyer_name}**")
            st.dataframe(buyer_pending[["Date", "Size (mm)", "Quantity", "Remarks"]], use_container_width=True)
        else:
            st.info(f"No pending orders found for {buyer_name}.")
    
    # === CASE 4: Buyer name only
    elif buyer_name:
        buyer_data = df[
            (df["Type"] == "Outgoing") &
            (df["Remarks"].str.contains(buyer_name, case=False, na=False))
        ]
        if not buyer_data.empty:
            st.success(f"📤 All orders for **{buyer_name}**")
            st.dataframe(buyer_data[["Date", "Size (mm)", "Quantity", "Remarks", "Pending"]], use_container_width=True)
        else:
            st.info(f"No entries found for buyer: **{buyer_name}**.")
    
    # === CASE 5: Nothing matched
    elif chat_query:
        st.info("❓ No match found. Try: 'Buyer A last 3', '300mm', or 'Buyer B pending'.")
    
import re
import pandas as pd

def chatbot_logic(query, df):
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df["Vendor"] = df["Remarks"].fillna("").str.strip()

    # Normalize query
    q = query.lower()

    # === Match Rotor Size (e.g., "250mm", "300mm")
    size_match = re.search(r"(\d{2,4})\s?mm", q)
    size = int(size_match.group(1)) if size_match else None

    # === Match Buyer Name
    buyer_match = re.search(r"buyer\s+(.+)", q)
    buyer = buyer_match.group(1).strip() if buyer_match else None

    # === Match "last N entries"
    last_n_match = re.search(r"last\s+(\d+)\s+entries", q)
    last_n = int(last_n_match.group(1)) if last_n_match else None

    # === 1: Stock of specific size
    if size and "stock" in q:
        current = df[(df["Status"] == "Current") & (~df["Pending"])].copy()
        current["Net"] = current.apply(lambda x: x["Quantity"] if x["Type"] == "Inward" else -x["Quantity"], axis=1)
        stock = current.groupby("Size (mm)")["Net"].sum()
        if size in stock:
            return f"📦 Current stock of *{size}mm*: {int(stock[size])} units"
        else:
            return f"❌ No stock info found for {size}mm."

    # === 2: Pendings by size
    if size and "pending" in q:
        pending = df[(df["Size (mm)"] == size) & (df["Pending"]) & (df["Status"] == "Current")]
        if not pending.empty:
            return pending[["Date", "Quantity", "Vendor", "Remarks"]].sort_values("Date")
        else:
            return f"✅ No pending orders found for {size}mm."

    # === 3: Pendings by buyer
    if "pending" in q and buyer:
        pending = df[(df["Vendor"].str.contains(buyer, case=False)) & (df["Pending"]) & (df["Status"] == "Current")]
        if not pending.empty:
            return pending[["Date", "Size (mm)", "Quantity", "Vendor"]].sort_values("Date")
        else:
            return f"✅ No pending entries found for buyer: *{buyer}*"

    # === 4: Last N entries for a size
    if size and last_n:
        entries = df[df["Size (mm)"] == size].sort_values("Date", ascending=False).head(last_n)
        return entries[["Date", "Type", "Quantity", "Vendor", "Pending"]]

    # === 5: All buyer pendings
    if "pending" in q and "buyer" in q:
        buyer_pendings = df[(df["Pending"]) & (df["Status"] == "Current")]
        grouped = buyer_pendings.groupby("Vendor")["Quantity"].sum().reset_index().sort_values("Quantity", ascending=False)
        return grouped.rename(columns={"Vendor": "Buyer", "Quantity": "Pending Qty"})

    # === 6: Show recent buyers
    if "buyers" in q or "vendors" in q:
        buyers = df["Vendor"].dropna().unique().tolist()
        return f"🧑‍💼 Known Buyers:\n" + ", ".join(sorted(set(buyers)))

    return None  # fallback to LLM
with tabs[3]:
    import re
    from openai import OpenAI

    st.subheader("🤖 Assistant Lite (qwen 2.5 instruct via OpenRouter)")

    df = st.session_state.data.copy()

    # OpenRouter client setup
    client = OpenAI(
        api_key=st.secrets["openrouter"]["api_key"],
        base_url="https://openrouter.ai/api/v1"
    )
    MODEL = "qwen/qwen2.5-coder-32b-instruct"

    # Context builder
    def get_rotor_summary(data):
        try:
            data["Net"] = data.apply(lambda x: x["Quantity"] if x["Type"] == "Inward" else -x["Quantity"], axis=1)
            stock = data[data["Status"] == "Current"].groupby("Size (mm)")["Net"].sum().reset_index()
            buyers = data[data["Type"] == "Outgoing"].groupby("Remarks")["Quantity"].sum().reset_index()

            context = "Rotor Stock Summary:\n" + stock.to_string(index=False) + "\n\nTop Buyers:\n" + buyers.to_string(index=False)
            return context
        except Exception as e:
            return f"Failed to create context: {e}"

    # Init session state
    if "chatbot_messages" not in st.session_state:
        st.session_state.chatbot_messages = [
            {"role": "system", "content": "You are an inventory assistant. Use rotor stock and buyer data to answer naturally.\n\n" + get_rotor_summary(df)}
        ]

    # Clear history button
    col_clear, _ = st.columns([1, 8])
    with col_clear:
        if st.button("🧹 Clear History"):
            context = get_rotor_summary(df)
            st.session_state.chatbot_messages = [
                {"role": "system", "content": "You are an inventory assistant. Use rotor stock and buyer data to answer naturally.\n\n" + context}
            ]
            st.rerun()

    # Display history
    for msg in st.session_state.chatbot_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # User input
    prompt = st.chat_input("Ask about rotor stock, buyers, pendings...")
    if prompt:
        st.session_state.chatbot_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("🤖 Thinking..."):
                result = chatbot_logic(prompt, df)
        
                if result is not None:
                    # Rule-based structured result
                    if isinstance(result, pd.DataFrame):
                        st.dataframe(result, use_container_width=True, hide_index=True)
                    else:
                        st.markdown(result)
                    st.session_state.chatbot_messages.append({
                        "role": "assistant",
                        "content": str(result)  # Save to history
                    })
                else:
                    # Fallback to LLM
                    try:
                        stream = client.chat.completions.create(
                            model=MODEL,
                            messages=st.session_state.chatbot_messages[-10:],
                            stream=True
                        )
        
                        def stream_generator():
                            full_reply = ""
                            for chunk in stream:
                                content = chunk.choices[0].delta.content if chunk.choices[0].delta else ""
                                full_reply += content
                                yield content
                            st.session_state.chatbot_messages.append({
                                "role": "assistant", "content": full_reply
                            })
        
                        st.write_stream(stream_generator())
        
                    except Exception as e:
                        st.error(f"❌ Chatbot error: {e}")

               
  
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

   
# ====== LAST SYNC STATUS ======
   # just do this directly

    
