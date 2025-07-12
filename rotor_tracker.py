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
def display_logo():
    try:
        logo_url = "https://via.placeholder.com/200x100?text=Rotor+Tracker"
        logo = Image.open(io.BytesIO(requests.get(logo_url).content))
        st.image(logo, width=200)
    except:
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
tabs = st.tabs(["📊 Stock Summary", "📋 Movement Log", "📈 Rotor Trend", "Rotor Chatbot", "Rotor Assistant lite", "Planning Dashboard"])

# === TAB 1: Stock Summary ===
with tabs[0]:
    st.subheader("🔔 Stock Alerts")

    current = st.session_state.data[
        (st.session_state.data['Status'] == 'Current') &
        (~st.session_state.data['Pending'])
    ].copy()
    current['Net'] = current.apply(
        lambda x: x['Quantity'] if x['Type'] == 'Inward' else -x['Quantity'], axis=1
    )
    stock = current.groupby('Size (mm)')['Net'].sum().reset_index()
    stock.columns = ['Size (mm)', 'Current Stock']

    # Alert: Low stock
    low_stock = stock[stock['Current Stock'] < 100]
    if not low_stock.empty:
        st.warning("⚠️ Low Stock Rotor Sizes (Below 100 units):")
        st.dataframe(low_stock, use_container_width=True, hide_index=True)

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

    # Top Moved Rotor Sizes
    st.subheader("🏆 Top Moved Rotor Sizes")
    df = st.session_state.data.copy()
    top_moved = df.groupby(['Size (mm)', 'Type'])['Quantity'].sum().reset_index()

    chart = alt.Chart(top_moved).mark_bar().encode(
        x=alt.X('Quantity:Q', title="Total Quantity"),
        y=alt.Y('Size (mm):N', sort='-x', title="Rotor Size"),
        color=alt.Color('Type:N'),
        tooltip=['Size (mm)', 'Type', 'Quantity']
    ).properties(
        width="container",
        height=400,
        title="Most Moved Rotor Sizes (Inward & Outgoing)"
    )
    st.altair_chart(chart, use_container_width=True)

    # Forecast
    st.subheader("📅 Seasonal Forecast by Month")

    df = st.session_state.data.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    
    # Use only outgoing, non-pending data
    outgoing = df[
        (df["Status"] == "Current") &
        (~df["Pending"]) &
        (df["Type"] == "Outgoing")
    ].copy()
    
    # Extract month name for seasonality
    outgoing["Month"] = outgoing["Date"].dt.month
    outgoing["Month Name"] = outgoing["Date"].dt.strftime('%b')
    
    # Group by rotor size and month
    seasonal = outgoing.groupby(["Size (mm)", "Month", "Month Name"])["Quantity"].mean().reset_index()
    seasonal = seasonal.sort_values(["Size (mm)", "Month"])
    
    # Show seasonal trend per rotor size
    if seasonal.empty:
        st.info("Not enough outgoing data for seasonal analysis.")
    else:
        st.dataframe(seasonal[["Size (mm)", "Month Name", "Quantity"]].rename(columns={
            "Quantity": "Average Outgoing Quantity"
        }), use_container_width=True, hide_index=True)
    
        # Optional: Chart of seasonal trend
       
        seasonal["Month Name"] = pd.Categorical(seasonal["Month Name"],
                                                categories=["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                                            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                                                ordered=True)
    
        chart = alt.Chart(seasonal).mark_line(point=True).encode(
            x=alt.X("Month Name:N", title="Month"),
            y=alt.Y("Quantity:Q", title="Avg Outgoing Quantity"),
            color=alt.Color("Size (mm):N", title="Rotor Size"),
            tooltip=["Size (mm)", "Month Name", "Quantity"]
        ).properties(
            width="container",
            height=400,
            title="Seasonal Rotor Demand (Monthly Average)"
        )
    
        st.altair_chart(chart, use_container_width=True)
        
    st.subheader("🔮 Forecast for Next Month Based on Seasonality")
    
    # Get next month number
    today = datetime.today()
    next_month_num = (today.month % 12) + 1  # handles Dec → Jan
    
    # Filter seasonal averages for next month
    next_month_forecast = seasonal[seasonal["Month"] == next_month_num].copy()
    
    # Clean display
    next_month_forecast = next_month_forecast[["Size (mm)", "Quantity"]]
    next_month_forecast.columns = ["Size (mm)", f"Forecast for {datetime(1900, next_month_num, 1).strftime('%B')}"]
    
    if next_month_forecast.empty:
        st.info("No seasonal data available to forecast next month.")
    else:
        st.dataframe(next_month_forecast, use_container_width=True, hide_index=True)
    # Stock Summary
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
    try:
        df = st.session_state.data.copy()
        df["Date"] = pd.to_datetime(df["Date"])

        trend_df = df[(df["Status"] == "Current") & (~df["Pending"])].copy()
        trend_df["Net"] = trend_df.apply(
            lambda x: x["Quantity"] if x["Type"] == "Inward" else -x["Quantity"], axis=1
        )

        min_date = trend_df["Date"].min()
        max_date = trend_df["Date"].max()

        st.subheader("📅 Select Date Range & Rotor Sizes")
        col1, col2 = st.columns(2)
        with col1:
            trend_range = st.date_input(
                "Filter by Date",
                value=[min_date, max_date],
                min_value=min_date,
                max_value=max_date,
                key="trend_date_range"
            )
        with col2:
            size_options = sorted(trend_df["Size (mm)"].unique())
            selected_sizes = st.multiselect(
                "Filter by Rotor Size", options=size_options, default=size_options, key="trend_sizes"
            )

        filtered = trend_df[
            (trend_df["Date"] >= pd.to_datetime(trend_range[0])) &
            (trend_df["Date"] <= pd.to_datetime(trend_range[1])) &
            (trend_df["Size (mm)"].isin(selected_sizes))
        ]

        if filtered.empty:
            st.warning("No data available for selected filters.")
        else:
            grouped = (
                filtered.groupby(["Date", "Size (mm)"])["Net"]
                .sum()
                .reset_index()
                .sort_values("Date")
            )
            grouped["Cumulative Stock"] = grouped.groupby("Size (mm)")["Net"].cumsum()

            import altair as alt
            chart = alt.Chart(grouped).mark_line(point=True).encode(
                x=alt.X("Date:T", title="Date"),
                y=alt.Y("Cumulative Stock:Q", title="Net Stock Level"),
                color=alt.Color("Size (mm):N", title="Rotor Size"),
                tooltip=[
                    alt.Tooltip("Date:T"),
                    alt.Tooltip("Size (mm):N"),
                    alt.Tooltip("Cumulative Stock:Q")
                ]
            ).properties(
                width="container",
                height=400,
                title="Rotor Stock Trend Over Time"
            ).interactive()

            st.altair_chart(chart, use_container_width=True)

    except Exception as e:
        st.error(f"Failed to generate rotor trend chart: {e}")
        
st.subheader("📉 Actual vs Forecasted Rotor Demand with Confidence Band")

df = st.session_state.data.copy()
df["Date"] = pd.to_datetime(df["Date"])

# Filter for valid entries
df = df[
    (df["Type"] == "Outgoing") &
    (df["Status"] == "Current") &
    (~df["Pending"])
]

if df.empty:
    st.info("Not enough data to forecast.")
else:
    # === SIZE FILTER ===
    available_sizes = sorted(df["Size (mm)"].unique())
    selected_sizes = st.multiselect(
        "📐 Select Rotor Sizes to Forecast",
        options=available_sizes,
        default=available_sizes
    )

    if not selected_sizes:
        st.warning("Please select at least one rotor size.")
    else:
        combined_data = []
        confidence_data = []

        for size in selected_sizes:
            df_size = df[df["Size (mm)"] == size]
            actual = df_size.groupby("Date")["Quantity"].sum().reset_index()
            actual.columns = ["Date", "Quantity"]
            actual["Size (mm)"] = size
            actual["Type"] = "Actual"

            if len(actual) < 3:
                continue

            try:
                prophet_df = actual[["Date", "Quantity"]].copy()
                prophet_df.columns = ["ds", "y"]

                model = Prophet()
                model.fit(prophet_df)

                future = model.make_future_dataframe(periods=30)
                forecast = model.predict(future)

                # Forecast points
                forecast_df = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
                forecast_df.columns = ["Date", "Quantity", "Lower", "Upper"]
                forecast_df["Size (mm)"] = size
                forecast_df["Type"] = "Forecast"

                combined = pd.concat([
                    actual,
                    forecast_df[["Date", "Quantity", "Size (mm)", "Type"]]
                ])
                combined_data.append(combined)
                confidence_data.append(forecast_df)

            except Exception as e:
                st.warning(f"Forecast failed for size {size}: {e}")

        if combined_data:
            full_df = pd.concat(combined_data)
            full_df["Quantity"] = full_df["Quantity"].round(2)

            band_df = pd.concat(confidence_data)

            line_chart = alt.Chart(full_df).mark_line(point=True).encode(
                x="Date:T",
                y="Quantity:Q",
                color="Size (mm):N",
                strokeDash="Type:N",
                tooltip=["Date", "Size (mm)", "Quantity", "Type"]
            )

            band_chart = alt.Chart(band_df).mark_area(opacity=0.2).encode(
                x="Date:T",
                y="Lower:Q",
                y2="Upper:Q",
                color=alt.Color("Size (mm):N", legend=None)
            )

            st.altair_chart((band_chart + line_chart).properties(height=400), use_container_width=True)

            st.markdown("### 📄 Combined Forecast Data")
            st.dataframe(full_df.sort_values(["Size (mm)", "Date"]), use_container_width=True, hide_index=True)
        else:
            st.info("No sizes had enough data to forecast.")

st.subheader("📦 XGBoost Forecast")

for size in sorted(df["Size (mm)"].unique()):
    df_size = df[df["Size (mm)"] == size]
    df_outgoing = df_size[
        (df_size["Type"] == "Outgoing") &
        (df_size["Status"] == "Current") &
        (~df_size["Pending"])
    ][["Date", "Quantity"]].copy()

    if len(df_outgoing) < 10:
     st.info(f"📉 Not enough data to forecast {size}mm (only {len(df_outgoing)} rows)")
     continue

    try:
        forecast_df = forecast_with_xgboost(df_outgoing, forecast_days=7)

        forecast_df["Size (mm)"] = size
        st.markdown(f"#### 📦 Forecast for {size}mm Rotor")
        st.line_chart(forecast_df.set_index("Date")["Forecast Qty"])
        st.dataframe(forecast_df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.warning(f"XGBoost forecast failed for {size}: {e}")
with tabs[3]:
    # Sample dataframe (you can use st.session_state.data instead)
    df = st.session_state.data.copy()
    
    st.subheader("🧠 Ask Your Rotor Assistant")
    
    if "openai" not in st.secrets:
        st.error("❌ OpenAI key missing from secrets.toml")
    else:
        try:
            # ✅ Build LLM with explicit key
            llm = OpenAI(
                temperature=0,
                openai_api_key=st.secrets["openai"]["api_key"]
            )
    
            # ✅ Create agent
            agent = create_pandas_dataframe_agent(
                llm,
                df,
                verbose=False,
                allow_dangerous_code=True
            )
    
            # ✅ User input
            user_q = st.text_input("Ask about rotor data:")
            if user_q:
                with st.spinner("Thinking..."):
                    try:
                        response = agent.run(user_q)
                        st.success(response)
                    except Exception as e:
                        st.error(f"Chatbot error: {e}")
    
        except Exception as e:
            st.error(f"Failed to initialize chatbot: {e}")
  
with tabs[4]:
    
    st.subheader("🧠 Rotor Assistant (Smart Buttons)")
    query = st.selectbox("📌 Ask a rotor question:", [
        "Most used rotor size",
        "Sizes running low",
        "Pending outgoing rotors",
        "Incoming future rotors",
        "Average daily outgoing usage",
        "Pending rotors by vendor"
    ])
    
    df = st.session_state.data.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    
    if query == "Most used rotor size":
        result = (
            df[df["Type"] == "Outgoing"]
            .groupby("Size (mm)")["Quantity"]
            .sum()
            .sort_values(ascending=False)
            .reset_index()
        )
        st.write("📦 Most used rotor sizes:")
        st.dataframe(result)
    
    elif query == "Sizes running low":
        current = df[
            (df["Status"] == "Current") & (~df["Pending"])
        ].copy()
        current["Net"] = current.apply(lambda x: x["Quantity"] if x["Type"] == "Inward" else -x["Quantity"], axis=1)
        stock = current.groupby("Size (mm)")["Net"].sum().reset_index()
        low = stock[stock["Net"] < 100]
        st.warning("🚨 Low stock rotors (below 100 units):")
        st.dataframe(low)
    
    elif query == "Pending outgoing rotors":
        pending = df[
            (df["Pending"]) & (df["Status"] == "Current") & (df["Type"] == "Outgoing")
        ]
        st.info("📤 Pending outgoing rotors:")
        st.dataframe(pending)
    
    elif query == "Incoming future rotors":
        future = df[
            (df["Status"] == "Future") & (df["Type"] == "Inward")
        ]
        st.success("📥 Incoming future rotors:")
        st.dataframe(future)
    
    elif query == "Average daily outgoing usage":
        last_60 = df[
            (df["Type"] == "Outgoing") &
            (df["Status"] == "Current") &
            (~df["Pending"]) &
            (df["Date"] >= pd.Timestamp.today() - pd.Timedelta(days=60))
        ]
        usage = last_60.groupby(["Date", "Size (mm)"])["Quantity"].sum().groupby("Size (mm)").mean().reset_index()
        usage.columns = ["Size (mm)", "Avg Daily Outgoing"]
        usage["Avg Daily Outgoing"] = usage["Avg Daily Outgoing"].round(0).astype(int)
        st.dataframe(usage)
    
    
    elif query == "Pending rotors by vendor":
        pending = df[
            (df["Pending"]) & 
            (df["Status"] == "Current")
        ].copy()
    
        # Auto-extract vendors from Remarks
        vendors = pending["Remarks"].dropna().unique().tolist()
        vendors.sort()
    
        if not vendors:
            st.info("No vendor names found in remarks.")
        else:
            selected_vendor = st.selectbox("Choose a vendor:", vendors)
            filtered = pending[
                pending["Remarks"].str.contains(selected_vendor, case=False, na=False)
            ]
    
            if filtered.empty:
                st.success(f"No pending rotors for vendor: {selected_vendor}")
            else:
                summary = (
                    filtered.groupby("Size (mm)")["Quantity"]
                    .sum().reset_index().sort_values("Size (mm)")
                )
                st.success(f"📦 Pending Rotors from **{selected_vendor}**")
                st.dataframe(summary, use_container_width=True)

st.subheader("💬 Ask about a rotor size or vendor")

chat_query = st.text_input("Try: 'Vendor A', 'Pending from XYZ', or 'Tell me about 250mm'")

df = st.session_state.data.copy()
df["Date"] = pd.to_datetime(df["Date"])

pending_df = df[(df["Pending"]) & (df["Status"] == "Current")].copy()
pending_df["Vendor Name"] = pending_df["Remarks"].fillna("").str.strip()

# === Rotor size match
size_match = re.search(r"(\d{2,4})", chat_query)
matched_size = int(size_match.group(1)) if size_match else None

# === Vendor match check
matched_vendors = pending_df[
    pending_df["Vendor Name"].str.contains(chat_query.strip(), case=False, na=False)
]

if matched_vendors.shape[0] > 0:
    vendor_name_guess = matched_vendors["Vendor Name"].iloc[0]
    st.success(f"📬 Pending orders for vendor: **{vendor_name_guess}**")

    result = matched_vendors[["Date", "Size (mm)", "Quantity", "Remarks"]].copy()
    result["Days Pending"] = (pd.Timestamp.today() - result["Date"]).dt.days
    st.dataframe(result.sort_values("Date"), use_container_width=True)

    # === 🔁 Edit a specific entry
    edit_query = st.text_input("✏️ To edit, type: 'Edit entry 2'")
    edit_match = re.search(r"edit entry\s*(\d+)", edit_query.lower()) if edit_query else None
    if edit_match:
        entry_num = int(edit_match.group(1)) - 1
        if matched_vendors.shape[0] > entry_num:
            entry_to_edit = matched_vendors.iloc[entry_num]
            row_index = entry_to_edit.name
            st.markdown(f"### ✏️ Editing Entry #{entry_num + 1} for **{vendor_name_guess}**")

            with st.form("edit_vendor_entry"):
                c1, c2 = st.columns(2)
                with c1:
                    e_date = st.date_input("📅 Date", pd.to_datetime(entry_to_edit["Date"]))
                    e_size = st.number_input("📐 Size (mm)", value=int(entry_to_edit["Size (mm)"]), min_value=1)
                    e_qty = st.number_input("🔢 Quantity", value=int(entry_to_edit["Quantity"]), min_value=1)
                with c2:
                    e_type = st.selectbox("🔁 Type", ["Inward", "Outgoing"], index=0 if entry_to_edit["Type"] == "Inward" else 1)
                    e_status = st.selectbox("📂 Status", ["Current", "Future"], index=0 if entry_to_edit["Status"] == "Current" else 1)
                    e_pending = st.checkbox("❗ Pending", value=bool(entry_to_edit["Pending"]))
                e_remarks = st.text_input("📝 Remarks", value=entry_to_edit["Remarks"])

                if st.form_submit_button("💾 Save Changes"):
                    st.session_state.data.at[row_index, "Date"] = e_date.strftime("%Y-%m-%d")
                    st.session_state.data.at[row_index, "Size (mm)"] = e_size
                    st.session_state.data.at[row_index, "Quantity"] = e_qty
                    st.session_state.data.at[row_index, "Type"] = e_type
                    st.session_state.data.at[row_index, "Status"] = e_status
                    st.session_state.data.at[row_index, "Pending"] = e_pending
                    st.session_state.data.at[row_index, "Remarks"] = e_remarks

                    if "auto_save_to_gsheet" in globals():
                        auto_save_to_gsheet()
                    st.success("✅ Entry updated.")
                    st.rerun()

    # === 📤 Recent outgoings
    recent_out = df[
        (df["Type"] == "Outgoing") &
        (~df["Pending"]) &
        (df["Remarks"].str.contains(vendor_name_guess, case=False, na=False))
    ].copy()

    if not recent_out.empty:
        st.markdown(f"### 📤 Recent Outgoings for **{vendor_name_guess}**")

        st.dataframe(
            recent_out.sort_values("Date", ascending=False).head(5)[
                ["Date", "Size (mm)", "Quantity", "Remarks"]
            ],
            use_container_width=True
        )

        # === Grouped summary by rotor size
        grouped = recent_out.groupby("Size (mm)")["Quantity"].sum().reset_index()
        grouped.columns = ["Rotor Size (mm)", "Total Outgoing"]
        st.markdown("#### 📊 Total Outgoing Quantity by Rotor Size")
        st.dataframe(grouped, use_container_width=True, hide_index=True)

        # === Outgoing quantity trend
        st.markdown("#### 📈 Outgoing Trend (Last 60 Days)")
        trend = recent_out[recent_out["Date"] >= pd.Timestamp.today() - pd.Timedelta(days=60)]
        if not trend.empty:
            trend_data = trend.groupby("Date")["Quantity"].sum().reset_index()
            st.line_chart(trend_data.set_index("Date"))
    else:
        st.info(f"No recent outgoings recorded for **{vendor_name_guess}**.")

# === Rotor size biodata block
elif matched_size:
    data = df[df["Size (mm)"] == matched_size]
    inward = data[data["Type"] == "Inward"]["Quantity"].sum()
    outgoing = data[data["Type"] == "Outgoing"]["Quantity"].sum()
    current_stock = inward - outgoing

    usage_window = pd.Timestamp.today() - pd.Timedelta(days=60)
    recent_out = data[
        (data["Type"] == "Outgoing") &
        (data["Date"] >= usage_window) &
        (~data["Pending"])
    ]
    avg_daily_usage = recent_out.groupby("Date")["Quantity"].sum().mean()
    days_left = (current_stock / avg_daily_usage) if avg_daily_usage else None

    pending_qty = data[data["Pending"]]["Quantity"].sum()
    future_qty = data[
        (data["Status"] == "Future") & (data["Type"] == "Inward")
    ]["Quantity"].sum()

    vendors = data["Remarks"].dropna().unique().tolist()
    recent_vendors = sorted(set(v for v in vendors if len(v) > 2))
    last_out = data[data["Type"] == "Outgoing"]["Date"].max()

    st.success(f"📋 Biodata for Rotor Size **{matched_size} mm**:")
    st.markdown(f"""
- 📥 **Total Inward**: {int(inward)}
- 📤 **Total Outgoing**: {int(outgoing)}
- 📦 **Current Stock**: {int(current_stock)}
- ❗ **Pending Orders**: {int(pending_qty)}
- 📥 **Future Inward**: {int(future_qty)}
- 📆 **Last Outgoing**: {last_out.date() if pd.notnull(last_out) else "N/A"}
- 📈 **Avg Daily Usage**: {round(avg_daily_usage,2) if avg_daily_usage else 'N/A'}
- ⏳ **Days of Stock Left**: {int(days_left) if days_left else 'N/A'}
- 🧑‍💼 **Vendors (from Remarks)**: {', '.join(recent_vendors) if recent_vendors else 'N/A'}
""")

    chart_data = recent_out.groupby("Date")["Quantity"].sum().reset_index()
    if not chart_data.empty:
        st.markdown("#### 📊 Usage Trend (Last 60 Days)")
        st.line_chart(chart_data.set_index("Date"))

# === Fallback
elif chat_query:
    st.info("❓ No rotor or vendor match found. Try a rotor size like '250', or a vendor name from your remarks.")

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

    
