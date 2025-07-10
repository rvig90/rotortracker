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
tabs = st.tabs(["📊 Stock Summary", "📋 Movement Log", "📈 Rotor Trend"])

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
# ====== LAST SYNC STATUS ======
if st.session_state.last_sync != "Never":
    st.caption(f"Last synced: {st.session_state.last_sync}")
