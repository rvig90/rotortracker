# ============================================================
# ROTOR TRACKER — Upgraded & Cleaned Version
# ============================================================

import os
import json
import re
import time
import requests
import io
from uuid import uuid4
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import altair as alt
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ── Page config (must be first Streamlit call) ───────────────
st.set_page_config(
    page_title="Rotor + Stator Tracker",
    page_icon="🔁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Global CSS — upgraded dark industrial theme ───────────────
st.markdown("""
<style>
/* ── Base ── */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #0f1117;
    color: #e8e8e8;
}
[data-testid="stSidebar"] {
    background-color: #161b27;
    border-right: 1px solid #2a2f3e;
}

/* ── Metric cards ── */
[data-testid="metric-container"] {
    background: #1a1f2e;
    border: 1px solid #2a3048;
    border-radius: 10px;
    padding: 14px 18px;
}
[data-testid="stMetricValue"] { color: #e8e8e8; font-size: 1.6rem !important; }
[data-testid="stMetricLabel"] { color: #8892a4; font-size: 0.78rem !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: #161b27;
    border-radius: 10px;
    gap: 4px;
    padding: 4px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: #8892a4;
    border-radius: 8px;
    font-size: 0.85rem;
    padding: 8px 18px;
}
.stTabs [aria-selected="true"] {
    background: #e23c3c !important;
    color: white !important;
    font-weight: 600;
}

/* ── Buttons ── */
.stButton > button {
    border-radius: 8px;
    font-weight: 500;
    transition: all 0.2s;
}
.stButton > button:hover { transform: translateY(-1px); }
button[kind="primary"] {
    background: #e23c3c !important;
    border-color: #e23c3c !important;
    color: white !important;
}

/* ── Forms ── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div,
.stTextArea > div > div > textarea {
    background: #1a1f2e !important;
    border: 1px solid #2a3048 !important;
    color: #e8e8e8 !important;
    border-radius: 8px !important;
}

/* ── DataFrames ── */
[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #2a3048;
}

/* ── Section headers ── */
.section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 0 8px;
    border-bottom: 2px solid #e23c3c;
    margin-bottom: 16px;
}
.section-header h3 { margin: 0; font-size: 1.05rem; font-weight: 600; }

/* ── Alert pills ── */
.pill-green  { background:#1a3a2a; color:#4ade80; padding:3px 12px; border-radius:20px; font-size:0.78rem; }
.pill-red    { background:#3a1a1a; color:#f87171; padding:3px 12px; border-radius:20px; font-size:0.78rem; }
.pill-amber  { background:#3a2a0a; color:#fbbf24; padding:3px 12px; border-radius:20px; font-size:0.78rem; }

/* ── Expanders ── */
.streamlit-expanderHeader {
    background: #1a1f2e !important;
    border-radius: 8px !important;
    color: #e8e8e8 !important;
}

/* ── Floating AI button ── */
div[data-testid="stButton"]:has(button[key="open_assistant"]) button {
    background: #e23c3c;
    color: white;
    border: none;
    border-radius: 50px;
    padding: 10px 22px;
    font-weight: bold;
    box-shadow: 0 4px 14px rgba(226,60,60,0.4);
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0f1117; }
::-webkit-scrollbar-thumb { background: #2a3048; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# CONSTANTS
# ============================================================
ROTOR_WEIGHTS = {
    80: 0.5, 100: 1, 110: 1.01, 120: 1.02, 125: 1.058,
    130: 1.1, 140: 1.15, 150: 1.3, 160: 1.4, 170: 1.422,
    180: 1.5, 200: 1.7, 225: 1.9, 260: 2.15,
    2403: 1.46, 1803: 1, 2003: 1.1
}

CLITTING_USAGE = {
    100: 0.04, 120: 0.05, 125: 0.05, 130: 0.05,
    140: 0.06, 150: 0.06, 160: 0.07, 170: 0.08,
    180: 0.09, 190: 0.10, 200: 0.11, 225: 0.12,
    260: 0.13, 300: 0.14,
}

AI_PROVIDERS = {
    "Sarvam AI": {
        "base_url": "https://api.sarvam.ai/v1/chat/completions",
        "models": ["sarvam-m", "sarvam-2b", "sarvam-7b"],
        "default_model": "sarvam-m",
        "headers": lambda k: {"api-subscription-key": k, "Content-Type": "application/json"},
        "api_key_in_url": False,
    },
    "Gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1/models/",
        "models": ["gemini-2.5-flash-lite", "gemini-2.5-flash"],
        "default_model": "gemini-2.5-flash-lite",
        "headers": lambda k: {"Content-Type": "application/json"},
        "api_key_in_url": True,
    },
    "OpenRouter": {
        "base_url": "https://openrouter.ai/api/v1/chat/completions",
        "models": ["deepseek/deepseek-chat", "openrouter/free"],
        "default_model": "deepseek/deepseek-chat",
        "headers": lambda k: {"Authorization": f"Bearer {k}", "Content-Type": "application/json"},
        "api_key_in_url": False,
    },
}


# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================
def init_session():
    defaults = {
        "data": pd.DataFrame(columns=["Date","Size (mm)","Type","Quantity","Remarks","Status","Pending","ID"]),
        "last_sync": "Never",
        "editing": None,
        "filter_reset": False,
        "new_entry": None,
        "conflict_resolved": False,
        "action_required": False,
        "future_matches": pd.DataFrame(),
        "selected_idx": None,
        "last_snapshot": None,
        "last_action_note": "",
        "clitting_data": pd.DataFrame(columns=["Date","Size (mm)","Bags","Weight per Bag (kg)","Remarks","ID"]),
        "lamination_v3": pd.DataFrame(columns=["Date","Quantity","Remarks","ID"]),
        "lamination_v4": pd.DataFrame(columns=["Date","Quantity","Remarks","ID"]),
        "stator_data": pd.DataFrame(columns=["Date","Size (mm)","Quantity","Remarks","Estimated Clitting (kg)","Laminations Used","Lamination Type","ID"]),
        "show_assistant": False,
        "chat_messages": [{"role": "assistant", "content": "👋 Hi! I'm your AI inventory assistant. Ask me anything about your stock!"}],
        "conversation_history": [],
        "ai_config": {
            "provider": "Sarvam AI",
            "model": "sarvam-m",
            "api_key": st.secrets.get("SARVAM_API_KEY", "") if hasattr(st, "secrets") else "",
            "initialized": False,
        },
        "fixed_prices": {1803: 460, 2003: 511, 35: 210, 40: 265, 50: 293, 70: 398},
        "base_rate_per_mm": 4.15,
        # filter keys
        "sf": "All", "zf": [], "pf": "All", "tf": "All", "rs": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()


# ============================================================
# HELPERS
# ============================================================
def normalize_pending(df):
    df["Pending"] = df["Pending"].apply(
        lambda x: str(x).lower() == "true" if isinstance(x, str) else bool(x)
    )
    return df

def get_price(size_mm):
    s = int(size_mm)
    fp = st.session_state.fixed_prices
    return fp[s] if s in fp else st.session_state.base_rate_per_mm * s

def calc_value(size_mm, qty):
    if pd.isna(size_mm) or pd.isna(qty):
        return 0
    return get_price(size_mm) * qty

def section(icon, title):
    st.markdown(f'<div class="section-header"><h3>{icon} {title}</h3></div>', unsafe_allow_html=True)


# ============================================================
# GOOGLE SHEETS
# ============================================================
def gsheet_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    raw = st.secrets.get("gcp_service_account", "{}")
    creds_dict = json.loads(raw) if isinstance(raw, str) else dict(raw)
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds).open("Rotor Log")

def get_main_sheet():
    return gsheet_client().sheet1

def save_to_named_sheet(df, title):
    try:
        ss = gsheet_client()
        try:
            ws = ss.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = ss.add_worksheet(title=title, rows="1000", cols="20")
        ws.clear()
        if not df.empty:
            ws.update([df.columns.tolist()] + df.values.tolist())
    except Exception as e:
        st.error(f"❌ Error saving to '{title}': {e}")

def load_named_sheet(title, default_cols):
    try:
        ss = gsheet_client()
        ws = ss.worksheet(title)
        records = ws.get_all_records()
        if records:
            return pd.DataFrame(records)
    except gspread.WorksheetNotFound:
        pass
    except Exception as e:
        st.error(f"❌ Error loading '{title}': {e}")
    return pd.DataFrame(columns=default_cols)

def auto_save():
    try:
        sheet = get_main_sheet()
        sheet.clear()
        if not st.session_state.data.empty:
            df = st.session_state.data.copy()
            df["Pending"] = df["Pending"].apply(lambda x: "TRUE" if x else "FALSE")
            expected = ["Date","Size (mm)","Type","Quantity","Remarks","Status","Pending","ID"]
            for c in expected:
                if c not in df.columns:
                    df[c] = ""
            df = df[expected]
            sheet.update([df.columns.tolist()] + df.values.tolist())
            # Backup
            try:
                ss = gsheet_client()
                try:
                    bk = ss.worksheet("Backup")
                except gspread.WorksheetNotFound:
                    bk = ss.add_worksheet(title="Backup", rows="1000", cols=str(len(df.columns)))
                bk.clear()
                bk.update([df.columns.tolist()] + df.values.tolist())
            except Exception:
                pass
        st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"Auto-save failed: {e}")

def load_from_gsheet():
    try:
        sheet = get_main_sheet()
        records = sheet.get_all_records()
        if records:
            df = pd.DataFrame(records)
            for col, default in [("Status","Current"), ("Pending", False)]:
                if col not in df.columns:
                    df[col] = default
            df = normalize_pending(df)
            if "ID" not in df.columns:
                df["ID"] = [str(uuid4()) for _ in range(len(df))]
            st.session_state.data = df
        st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.success("✅ Synced from Google Sheets")
    except Exception as e:
        st.error(f"Load failed: {e}")

def add_entry(data_dict):
    data_dict["ID"] = str(uuid4())
    new = pd.DataFrame([data_dict])
    st.session_state.data = pd.concat([st.session_state.data, new], ignore_index=True)
    auto_save()
    st.rerun()

def save_sub_sheets():
    save_to_named_sheet(st.session_state.clitting_data, "Clitting")
    save_to_named_sheet(st.session_state.lamination_v3, "V3 Laminations")
    save_to_named_sheet(st.session_state.lamination_v4, "V4 Laminations")
    save_to_named_sheet(st.session_state.stator_data, "Stator Usage")


# ============================================================
# LOGO
# ============================================================
def display_logo():
    try:
        url = "https://ik.imagekit.io/zmv7kjha8x/D936A070-DB06-4439-B642-854E6510A701.PNG?updatedAt=1752629786861"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        st.image(img, width=160)
    except Exception:
        st.markdown("## 🔁 Rotor Tracker")


# ============================================================
# AI FUNCTIONS
# ============================================================
def get_inventory_context():
    if "data" not in st.session_state or st.session_state.data.empty:
        return {}
    df = st.session_state.data.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Size (mm)"] = pd.to_numeric(df["Size (mm)"], errors="coerce")
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")

    stock_summary = []
    for size in sorted(df["Size (mm)"].dropna().unique()):
        sdf = df[df["Size (mm)"] == size]
        tin  = sdf[sdf["Type"] == "Inward"]["Quantity"].sum()
        tout = sdf[(sdf["Type"] == "Outgoing") & (~sdf["Pending"])]["Quantity"].sum()
        pend = sdf[(sdf["Type"] == "Outgoing") & (sdf["Pending"] == True)]["Quantity"].sum()
        fut  = sdf[(sdf["Type"] == "Inward") & (sdf["Status"] == "Future")]["Quantity"].sum()
        cur  = tin - tout
        if cur > 0 or pend > 0 or fut > 0:
            stock_summary.append({"size": int(size), "current": int(cur), "pending": int(pend), "future": int(fut)})

    pending_by_buyer = {}
    pdf = df[(df["Type"] == "Outgoing") & (df["Pending"] == True)]
    for buyer in pdf["Remarks"].dropna().unique():
        bdf = pdf[pdf["Remarks"] == buyer]
        pending_by_buyer[str(buyer)] = {
            "total": int(bdf["Quantity"].sum()),
            "orders": [{"size": int(r["Size (mm)"]), "qty": int(r["Quantity"])} for _, r in bdf.iterrows()]
        }

    buyers = df[df["Type"] == "Outgoing"]["Remarks"].dropna().unique().tolist()
    return {
        "stock": stock_summary,
        "pending": pending_by_buyer,
        "buyers": [str(b) for b in buyers],
        "total_tx": len(df),
        "last_sync": st.session_state.last_sync,
    }

def get_ai_response(user_input):
    ctx = get_inventory_context()
    cfg = st.session_state.ai_config

    if cfg["initialized"]:
        try:
            prov = AI_PROVIDERS[cfg["provider"]]
            sys_prompt = f"""You are an AI inventory assistant with full knowledge of this rotor inventory.
STOCK: {json.dumps(ctx.get('stock', []))}
PENDING BY BUYER: {json.dumps(ctx.get('pending', {}))}
BUYERS: {ctx.get('buyers', [])}
TOTAL TRANSACTIONS: {ctx.get('total_tx', 0)}
LAST SYNC: {ctx.get('last_sync', 'Unknown')}
CONVERSATION HISTORY: {json.dumps(st.session_state.conversation_history[-20:])}
Answer concisely and naturally. Hide your reasoning, show only the final answer."""

            if prov.get("api_key_in_url"):
                url = f"{prov['base_url']}{cfg['model']}:generateContent?key={cfg['api_key']}"
                data = {"contents": [{"parts": [{"text": sys_prompt + "\nUser: " + user_input}]}],
                        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 800}}
            else:
                url = prov["base_url"]
                messages = [{"role": "system", "content": sys_prompt}]
                for m in st.session_state.conversation_history[-10:]:
                    messages.append(m)
                messages.append({"role": "user", "content": user_input})
                data = {"model": cfg["model"], "messages": messages, "temperature": 0.2, "max_tokens": 800}

            resp = requests.post(url, headers=prov["headers"](cfg["api_key"]), json=data, timeout=15)
            if resp.status_code == 200:
                result = resp.json()
                if "gemini" in cfg["provider"].lower():
                    answer = result["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    answer = result["choices"][0]["message"]["content"]
                st.session_state.conversation_history.append({"role": "user", "content": user_input})
                st.session_state.conversation_history.append({"role": "assistant", "content": answer})
                if len(st.session_state.conversation_history) > 100:
                    st.session_state.conversation_history = st.session_state.conversation_history[-100:]
                return answer
            return f"⚠️ API error {resp.status_code}. Using fallback."
        except Exception as e:
            return f"⚠️ Connection error: {str(e)[:60]}. Using fallback."

    # Fallback
    text = user_input.lower()
    if "stock" in text:
        lines = ["📦 **Current Stock:**\n"]
        for item in ctx.get("stock", []):
            lines.append(f"• {item['size']}mm: **{item['current']}** units (pending: {item['pending']}, coming: {item['future']})")
        return "\n".join(lines) or "No stock data."
    if "pending" in text:
        lines = ["⏳ **Pending Orders:**\n"]
        for buyer, info in ctx.get("pending", {}).items():
            lines.append(f"• **{buyer}**: {info['total']} units")
        return "\n".join(lines) or "No pending orders."
    return "Ask me about stock, pending orders, or buyers. Connect an AI provider for smarter answers."


# ============================================================
# STOCK SUMMARY CALC
# ============================================================
def calc_stock_summary():
    df = st.session_state.data
    if df.empty:
        return pd.DataFrame(columns=["Size (mm)","Current Stock","Coming Rotors","Pending Rotors"])
    df = normalize_pending(df.copy())
    cur = df[(df["Status"] == "Current") & (~df["Pending"])].copy()
    cur["Net"] = cur.apply(lambda x: x["Quantity"] if x["Type"] == "Inward" else -x["Quantity"], axis=1)
    stock = cur.groupby("Size (mm)")["Net"].sum().reset_index().rename(columns={"Net": "Current Stock"})
    fut   = df[df["Status"] == "Future"].groupby("Size (mm)")["Quantity"].sum().reset_index().rename(columns={"Quantity": "Coming Rotors"})
    pend  = df[(df["Status"] == "Current") & (df["Pending"])].groupby("Size (mm)")["Quantity"].sum().reset_index().rename(columns={"Quantity": "Pending Rotors"})
    out   = stock.merge(fut, on="Size (mm)", how="outer").merge(pend, on="Size (mm)", how="outer").fillna(0)
    out["Current Stock"]  = out["Current Stock"].astype(int)
    out["Coming Rotors"]  = out["Coming Rotors"].astype(int)
    out["Pending Rotors"] = out["Pending Rotors"].astype(int)
    return out[out["Current Stock"] != 0]


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    display_logo()
    st.markdown("---")
    tab_choice = st.radio("📊 Choose Tab", ["🔁 Rotor Tracker", "🧰 Clitting + Laminations + Stators"])
    st.markdown("---")
    st.caption(f"Last sync: {st.session_state.last_sync}")
    if st.button("🔄 Sync Now", use_container_width=True):
        load_from_gsheet()
        st.rerun()

# Initial load
if st.session_state.last_sync == "Never":
    load_from_gsheet()


# ============================================================
# ── TAB 1: ROTOR TRACKER ────────────────────────────────────
# ============================================================
if tab_choice == "🔁 Rotor Tracker":
    st.title("🔁 Rotor Tracker")

    # ── Top metrics ─────────────────────────────────────────
    summary = calc_stock_summary()
    total_stock   = int(summary["Current Stock"].sum())
    total_coming  = int(summary["Coming Rotors"].sum())
    total_pending = int(summary["Pending Rotors"].sum())
    sizes_tracked = len(summary)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Total Stock",    f"{total_stock:,}")
    c2.metric("📥 Incoming",       f"{total_coming:,}")
    c3.metric("⏳ Pending Out",    f"{total_pending:,}")
    c4.metric("📐 Sizes Tracked",  sizes_tracked)

    st.markdown("---")

    # ── Entry forms ─────────────────────────────────────────
    form_tabs = st.tabs(["📥 Current Movement", "📅 Coming Rotors", "⏳ Pending Rotors"])

    # ── FORM TAB 0: Current Movement ──
    with form_tabs[0]:
        section("📥", "Add Rotor Movement")
        with st.form("current_form"):
            col1, col2 = st.columns(2)
            with col1:
                date        = st.date_input("📅 Date", value=datetime.today())
                rotor_size  = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
            with col2:
                entry_type  = st.selectbox("🔄 Type", ["Inward", "Outgoing"])
                quantity    = st.number_input("🔢 Quantity", min_value=1, step=1)
            remarks = st.text_input("📝 Remarks")
            submitted = st.form_submit_button("📋 Submit Entry Info", type="primary")

        if submitted:
            df = st.session_state.data.copy()
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
            new_entry = {
                "Date": date.strftime("%Y-%m-%d"),
                "Size (mm)": int(rotor_size),
                "Type": entry_type,
                "Quantity": int(quantity),
                "Remarks": remarks.strip(),
                "Status": "Current",
                "Pending": False,
                "ID": str(uuid4()),
            }
            st.session_state["new_entry"] = new_entry
            st.session_state["conflict_resolved"] = True
            st.session_state["action_required"] = False

            if entry_type == "Inward" and remarks.strip() == "":
                matches = df[
                    (df["Type"] == "Inward") &
                    (df["Size (mm)"] == int(rotor_size)) &
                    (df["Remarks"].astype(str).str.strip() == "") &
                    (df["Status"].str.lower() == "future")
                ].sort_values("Date")
                if not matches.empty:
                    st.warning("⚠️ Matching future rotor entries found. Please resolve below.")
                    st.session_state["conflict_resolved"] = False
                    st.session_state["action_required"] = True
                    st.session_state["future_matches"] = matches
                    st.session_state["selected_idx"] = matches.index[0]

        # Conflict resolution
        if st.session_state.get("action_required") and not st.session_state.get("conflict_resolved"):
            matches = st.session_state["future_matches"]
            st.dataframe(matches[["Date","Quantity","Status"]], use_container_width=True)
            selected = st.selectbox(
                "Select a future entry to act on:",
                options=matches.index,
                format_func=lambda i: f"{matches.at[i,'Date']} → Qty: {matches.at[i,'Quantity']}"
            )
            st.session_state["selected_idx"] = selected
            col1, col2, col3 = st.columns(3)
            if col1.button("🗑 Delete Selected"):
                st.session_state.data = st.session_state.data.drop(selected)
                st.session_state["conflict_resolved"] = True
                st.session_state["action_required"] = False
                st.success("✅ Deleted. Click Save Entry to continue.")
            if col2.button("➖ Deduct from Selected"):
                qty = st.session_state["new_entry"]["Quantity"]
                fqty = int(st.session_state.data.at[selected, "Quantity"])
                if qty >= fqty:
                    st.session_state.data = st.session_state.data.drop(selected)
                else:
                    st.session_state.data.at[selected, "Quantity"] = fqty - qty
                st.session_state["conflict_resolved"] = True
                st.session_state["action_required"] = False
                st.success("✅ Deducted. Click Save Entry to continue.")
            if col3.button("Skip / Do Nothing"):
                st.session_state["conflict_resolved"] = True
                st.session_state["action_required"] = False

        # Save button
        if st.session_state.get("conflict_resolved") and st.session_state.get("new_entry"):
            if st.button("💾 Save Entry", type="primary"):
                with st.spinner("Saving..."):
                    df = st.session_state.data.copy()
                    ne = st.session_state["new_entry"]

                    # Auto-deduct pending for outgoing
                    if ne["Type"] == "Outgoing" and ne["Remarks"]:
                        buyer = ne["Remarks"].lower()
                        size  = ne["Size (mm)"]
                        qty   = ne["Quantity"]
                        pend_rows = df[
                            (df["Size (mm)"] == size) &
                            (df["Remarks"].str.lower().str.contains(buyer)) &
                            (df["Pending"] == True) &
                            (df["Status"] == "Current")
                        ].sort_values("Date")
                        for idx, row in pend_rows.iterrows():
                            if qty <= 0:
                                break
                            pq = int(row["Quantity"])
                            if qty >= pq:
                                df.at[idx, "Quantity"] = 0
                                df.at[idx, "Pending"] = False
                                qty -= pq
                            else:
                                df.at[idx, "Quantity"] = pq - qty
                                qty = 0
                        df = df[df["Quantity"] > 0]

                    df = pd.concat([df, pd.DataFrame([ne])], ignore_index=True)
                    df["Date"] = df["Date"].astype(str)
                    st.session_state.data = df.reset_index(drop=True)
                    auto_save()
                    st.success("✅ Entry saved!")
                    for k in ["new_entry","future_matches","selected_idx"]:
                        st.session_state[k] = None
                    st.session_state["conflict_resolved"] = False
                    st.session_state["action_required"] = False
                    st.rerun()

        # Undo
        if st.session_state.get("last_snapshot") is not None:
            if st.button("↩ Undo Last Action"):
                st.session_state.data = st.session_state.last_snapshot.copy()
                st.success(f"Undone: {st.session_state.last_action_note}")
                auto_save()

    # ── FORM TAB 1: Coming Rotors ──
    with form_tabs[1]:
        section("📅", "Add Coming Rotors")
        with st.form("future_form"):
            col1, col2 = st.columns(2)
            with col1:
                future_date    = st.date_input("📅 Expected Date", min_value=datetime.today() + timedelta(days=1))
                future_size    = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
            with col2:
                future_qty     = st.number_input("🔢 Quantity", min_value=1, step=1)
                future_remarks = st.text_input("📝 Remarks")
            if st.form_submit_button("➕ Add Coming Rotors", type="primary"):
                add_entry({
                    "Date": future_date.strftime("%Y-%m-%d"),
                    "Size (mm)": future_size,
                    "Type": "Inward",
                    "Quantity": future_qty,
                    "Remarks": future_remarks,
                    "Status": "Future",
                    "Pending": False,
                })
                st.success("✅ Entry added!")

    # ── FORM TAB 2: Pending Rotors ──
    with form_tabs[2]:
        section("⏳", "Add Pending Order")
        with st.form("pending_form"):
            col1, col2 = st.columns(2)
            with col1:
                pending_date    = st.date_input("📅 Date", value=datetime.today())
                pending_size    = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
            with col2:
                pending_qty     = st.number_input("🔢 Quantity", min_value=1, step=1)
                pending_remarks = st.text_input("📝 Remarks")
            if st.form_submit_button("➕ Add Pending", type="primary"):
                add_entry({
                    "Date": pending_date.strftime("%Y-%m-%d"),
                    "Size (mm)": pending_size,
                    "Type": "Outgoing",
                    "Quantity": pending_qty,
                    "Remarks": pending_remarks,
                    "Status": "Current",
                    "Pending": True,
                })
                st.success("✅ Entry added!")

    st.markdown("---")

    # ── Bottom tabs ─────────────────────────────────────────
    tabs = st.tabs(["📊 Stock Summary", "📋 Movement Log", "💬 Chatbot Lite", "🤖 AI Assistant"])

    # ══ TAB: Stock Summary ══
    with tabs[0]:
        section("📊", "Current Stock Summary")
        summary = calc_stock_summary()
        if not summary.empty:
            st.dataframe(summary, use_container_width=True, hide_index=True)
            # Value column
            summary["Value (₹)"] = summary.apply(lambda r: f"₹{calc_value(r['Size (mm)'], r['Current Stock']):,.0f}", axis=1)
        else:
            st.info("No stock data yet.")

        # Risk alerts
        section("🚨", "Stock Risk Alerts")
        df_a = st.session_state.data.copy()
        if not df_a.empty:
            df_a["Date"] = pd.to_datetime(df_a["Date"], errors="coerce")
            df_a = normalize_pending(df_a)
            cur_a = df_a[(df_a["Status"] == "Current") & (~df_a["Pending"])].copy()
            cur_a["Net"] = cur_a.apply(lambda x: x["Quantity"] if x["Type"] == "Inward" else -x["Quantity"], axis=1)
            stk = cur_a.groupby("Size (mm)")["Net"].sum().reset_index().rename(columns={"Net": "Stock"})
            po  = df_a[(df_a["Pending"] == True) & (df_a["Status"] == "Current")].groupby("Size (mm)")["Quantity"].sum().reset_index().rename(columns={"Quantity": "Pending Out"})
            ci  = df_a[(df_a["Status"] == "Future") & (df_a["Type"] == "Inward")].groupby("Size (mm)")["Quantity"].sum().reset_index().rename(columns={"Quantity": "Coming In"})
            merged = stk.merge(po, on="Size (mm)", how="outer").merge(ci, on="Size (mm)", how="outer").fillna(0)
            for c in ["Stock","Pending Out","Coming In"]:
                merged[c] = merged[c].astype(int)
            low   = merged[(merged["Stock"] < 100) & (merged["Coming In"] == 0)]
            risky = merged[merged["Pending Out"] > (merged["Stock"] + merged["Coming In"])]
            if not low.empty:
                st.warning("🟠 Low stock (< 100) with no incoming:")
                st.dataframe(low[["Size (mm)","Stock"]], use_container_width=True, hide_index=True)
            else:
                st.success("✅ No low-stock issues.")
            if not risky.empty:
                st.error("🔴 Pending exceeds available supply:")
                st.dataframe(risky[["Size (mm)","Stock","Coming In","Pending Out"]], use_container_width=True, hide_index=True)
            else:
                st.success("✅ All pending orders can be fulfilled.")

    # ══ TAB: Movement Log ══
    with tabs[1]:
        section("📋", "Movement Log")
        df_log = st.session_state.data.copy()
        if df_log.empty:
            st.info("No entries yet.")
        else:
            # Filters
            with st.expander("🔍 Filters", expanded=True):
                fc1, fc2, fc3, fc4 = st.columns(4)
                with fc1:
                    status_f = st.selectbox("Status", ["All","Current","Future"], key="sf")
                with fc2:
                    size_opts = sorted(df_log["Size (mm)"].dropna().unique())
                    size_f    = st.multiselect("Size (mm)", size_opts, key="zf")
                with fc3:
                    pending_f = st.selectbox("Pending", ["All","Yes","No"], key="pf")
                with fc4:
                    type_f    = st.selectbox("Type", ["All","Inward","Outgoing"], key="tf")
                remark_s   = st.text_input("Search Remarks", key="rs")
                col_dr1, col_dr2 = st.columns(2)
                with col_dr1:
                    date_from = st.date_input("From", value=pd.to_datetime(df_log["Date"]).min().date() if not df_log.empty else datetime.today().date())
                with col_dr2:
                    date_to   = st.date_input("To", value=pd.to_datetime(df_log["Date"]).max().date() if not df_log.empty else datetime.today().date())
                if st.button("🔄 Reset Filters"):
                    for k in ["sf","zf","pf","tf","rs"]:
                        st.session_state[k] = "All" if k in ["sf","pf","tf"] else ([] if k == "zf" else "")
                    st.rerun()

            # Apply filters
            try:
                df_log["Date"] = pd.to_datetime(df_log["Date"], errors="coerce")
                if status_f  != "All": df_log = df_log[df_log["Status"] == status_f]
                if pending_f == "Yes": df_log = df_log[df_log["Pending"] == True]
                elif pending_f == "No": df_log = df_log[df_log["Pending"] == False]
                if size_f:  df_log = df_log[df_log["Size (mm)"].isin(size_f)]
                if remark_s: df_log = df_log[df_log["Remarks"].astype(str).str.contains(remark_s, case=False, na=False)]
                if type_f  != "All": df_log = df_log[df_log["Type"] == type_f]
                df_log = df_log[(df_log["Date"] >= pd.to_datetime(date_from)) & (df_log["Date"] <= pd.to_datetime(date_to))]
            except Exception as e:
                st.error(f"Filter error: {e}")
                df_log = st.session_state.data.copy()

            df_log = df_log.reset_index(drop=True)
            st.caption(f"{len(df_log)} entries")

            for idx, row in df_log.iterrows():
                entry_id  = row["ID"]
                match     = st.session_state.data[st.session_state.data["ID"] == entry_id]
                if match.empty:
                    continue
                match_idx = match.index[0]
                cols = st.columns([10, 1, 1])
                with cols[0]:
                    disp = row.drop(labels="ID").to_dict()
                    disp["Pending"] = "Yes" if row["Pending"] else "No"
                    st.dataframe(pd.DataFrame([disp]), hide_index=True, use_container_width=True)
                with cols[1]:
                    if st.button("✏️", key=f"edit_{entry_id}"):
                        st.session_state.editing = match_idx
                with cols[2]:
                    if st.button("❌", key=f"del_{entry_id}"):
                        st.session_state.data = st.session_state.data[st.session_state.data["ID"] != entry_id]
                        auto_save()
                        st.rerun()

                if st.session_state.get("editing") == match_idx:
                    er = st.session_state.data.loc[match_idx]
                    with st.form(f"edit_{entry_id}"):
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            e_date = st.date_input("Date", value=pd.to_datetime(er["Date"]), key=f"ed_{entry_id}")
                            e_size = st.number_input("Size (mm)", min_value=1, value=int(er["Size (mm)"]), key=f"es_{entry_id}")
                        with ec2:
                            e_type = st.selectbox("Type", ["Inward","Outgoing"], index=0 if er["Type"]=="Inward" else 1, key=f"et_{entry_id}")
                            e_qty  = st.number_input("Quantity", min_value=1, value=int(er["Quantity"]), key=f"eq_{entry_id}")
                        e_rem     = st.text_input("Remarks", value=er["Remarks"], key=f"er_{entry_id}")
                        e_status  = st.selectbox("Status", ["Current","Future"], index=0 if er["Status"]=="Current" else 1, key=f"ess_{entry_id}")
                        e_pending = st.checkbox("Pending", value=er["Pending"], key=f"ep_{entry_id}")
                        s_col, c_col = st.columns(2)
                        with s_col:
                            save_edit = st.form_submit_button("💾 Save", type="primary")
                        with c_col:
                            cancel_edit = st.form_submit_button("❌ Cancel")
                        if save_edit:
                            for col, val in [("Date", e_date.strftime("%Y-%m-%d")),("Size (mm)",e_size),("Type",e_type),("Quantity",e_qty),("Remarks",e_rem),("Status",e_status),("Pending",e_pending)]:
                                st.session_state.data.at[match_idx, col] = val
                            st.session_state.editing = None
                            auto_save()
                            st.rerun()
                        if cancel_edit:
                            st.session_state.editing = None
                            st.rerun()

    # ══ TAB: Chatbot Lite ══
    with tabs[2]:
        section("💬", "Rotor Chatbot Lite")

        # Fixed prices editor
        with st.expander("⚙️ Edit Fixed Rates", expanded=False):
            rates_df = pd.DataFrame([{"Size (mm)": k, "Price (₹)": v} for k, v in sorted(st.session_state.fixed_prices.items())])
            edited   = st.data_editor(rates_df, num_rows="dynamic", hide_index=True, use_container_width=True)
            new_base = st.number_input("Base Rate (₹/mm)", value=float(st.session_state.base_rate_per_mm), step=0.2, format="%.2f")
            col_u, col_r = st.columns(2)
            with col_u:
                if st.button("💾 Update Rates", type="primary"):
                    new_fp = {}
                    for _, r in edited.iterrows():
                        try:
                            if not pd.isna(r["Size (mm)"]) and not pd.isna(r["Price (₹)"]):
                                new_fp[int(r["Size (mm)"])] = int(r["Price (₹)"])
                        except Exception:
                            pass
                    st.session_state.fixed_prices = new_fp
                    st.session_state.base_rate_per_mm = new_base
                    st.success("✅ Updated!")
                    st.rerun()
            with col_r:
                if st.button("🔄 Reset Defaults"):
                    st.session_state.fixed_prices = {1803:460,2003:511,35:210,40:265,50:293,70:398}
                    st.session_state.base_rate_per_mm = 4.15
                    st.rerun()

        with st.expander("💰 Current Pricing", expanded=False):
            for s, p in sorted(st.session_state.fixed_prices.items()):
                st.write(f"• {s}mm: ₹{p} per rotor")
            st.write(f"• Other sizes: ₹{st.session_state.base_rate_per_mm:.2f}/mm × size")

        chat_query = st.text_input("💬 Ask about rotors:", placeholder="e.g., history 1803 | pending ajji | coming rotors | buyers list | march 2025")
        _chatbot_done = False  # flag to skip later blocks without st.stop()

        if not chat_query:
            st.info("👆 Enter a query above to get started. Try: size number, buyer name, 'pending', 'coming', 'all buyers'")
            _chatbot_done = True

        if not _chatbot_done:
            df_cb = st.session_state.data.copy()
            df_cb["Date"]     = pd.to_datetime(df_cb["Date"], errors="coerce")
            df_cb["Remarks"]  = df_cb["Remarks"].astype(str).str.strip()
            df_cb["Size (mm)"]= pd.to_numeric(df_cb["Size (mm)"], errors="coerce")
            df_cb["Quantity"] = pd.to_numeric(df_cb["Quantity"],   errors="coerce")
            if "Pending" not in df_cb.columns:
                df_cb["Pending"] = False
            df_cb = normalize_pending(df_cb)
            df_cb = df_cb.dropna(subset=["Date"])

            query = chat_query.lower().strip()

            # ── Detect size ──
            target_size = None
            for s in re.findall(r"\b(\d+)\b", query):
                n = int(s)
                if n in st.session_state.fixed_prices or n > 20:
                    target_size = n
                    break

            # ── Detect month / year ──
            month_mapping = {
                "january":1,"jan":1,"february":2,"feb":2,"march":3,"mar":3,
                "april":4,"apr":4,"may":5,"june":6,"jun":6,"july":7,"jul":7,
                "august":8,"aug":8,"september":9,"sep":9,"october":10,"oct":10,
                "november":11,"nov":11,"december":12,"dec":12
            }
            month_num = None; month_name = None; year_num = datetime.now().year
            for ms, mv in month_mapping.items():
                if ms in query:
                    month_name = ms.capitalize(); month_num = mv; break
            yr = re.search(r"\b(20\d{2})\b", query)
            if yr:
                year_num = int(yr.group(1))

            # ── Detect buyer ──
            buyers_list = sorted([b for b in df_cb["Remarks"].unique() if b and b.lower() not in ["","nan","none"]])
            buyer_cb = None
            for b in buyers_list:
                if b.lower() in query:
                    buyer_cb = b; break
            if not buyer_cb:
                for w in query.split():
                    if len(w) > 2:
                        for b in buyers_list:
                            if w in b.lower():
                                buyer_cb = b; break
                    if buyer_cb:
                        break
            if buyer_cb:
                st.info(f"🔍 Detected buyer: **{buyer_cb}**")

            # ── Detect movement ──
            movement = None
            if "pending"  in query:                          movement = "pending"
            elif "incoming" in query or "inward" in query:   movement = "incoming"
            elif "outgoing" in query or "outward" in query:  movement = "outgoing"
            elif "coming"   in query or "future"  in query:  movement = "coming"
            elif "summary"  in query:                        movement = "summary"
            elif "all buyers" in query or "buyers list" in query or "buyers" in query:
                movement = "buyers"

            # ══════════════════════════════════════════════════
            # CASE 1 — SIZE HISTORY (most detailed view)
            # ══════════════════════════════════════════════════
            if target_size and not _chatbot_done:
                price_per = get_price(target_size)
                hist = df_cb[df_cb["Size (mm)"] == target_size].sort_values("Date", ascending=False)

                if hist.empty:
                    st.warning(f"No transactions found for {target_size}mm")
                    _chatbot_done = True
                else:
                    st.subheader(f"📜 Transaction History — {target_size}mm")
                    ti = int(hist[hist["Type"]=="Inward"]["Quantity"].sum())
                    to = int(hist[hist["Type"]=="Outgoing"]["Quantity"].sum())
                    c1,c2,c3,c4 = st.columns(4)
                    c1.metric("Total Inward",   ti)
                    c2.metric("Total Outgoing", to)
                    c3.metric("Net Change",     ti - to)
                    c4.metric("Transactions",   len(hist))
                    st.info(f"Price: ₹{price_per:,.0f} per rotor")

                    # Type / status / pending filters for this size
                    flt1, flt2, flt3 = st.columns(3)
                    with flt1:
                        sh_type = st.selectbox("Filter Type",   ["All","Inward","Outgoing"], key="cb_htype")
                    with flt2:
                        sh_stat = st.selectbox("Filter Status", ["All","Current","Future"],  key="cb_hstat")
                    with flt3:
                        sh_pend = st.selectbox("Filter Pending",["All","Pending Only","Non-Pending"], key="cb_hpend")

                    fhist = hist.copy()
                    if sh_type != "All": fhist = fhist[fhist["Type"] == sh_type]
                    if sh_stat != "All": fhist = fhist[fhist["Status"] == sh_stat]
                    if sh_pend == "Pending Only":   fhist = fhist[fhist["Pending"] == True]
                    elif sh_pend == "Non-Pending":  fhist = fhist[fhist["Pending"] == False]

                    fhist["Value (₹)"] = fhist.apply(lambda r: f"₹{calc_value(r['Size (mm)'],r['Quantity']):,.0f}", axis=1)
                    disp = fhist.copy()
                    disp["Date"]    = disp["Date"].dt.strftime("%Y-%m-%d")
                    disp["Pending"] = disp["Pending"].apply(lambda x: "Yes" if x else "No")
                    st.subheader(f"📋 Transaction Details ({len(fhist)} records)")
                    st.dataframe(
                        disp[["Date","Type","Quantity","Remarks","Status","Pending","Value (₹)"]].rename(columns={"Remarks":"Buyer/Supplier"}),
                        use_container_width=True, hide_index=True
                    )

                    # Monthly summary
                    st.subheader("📅 Monthly Summary")
                    hist2 = hist.copy()
                    hist2["MonthYear"] = hist2["Date"].dt.strftime("%b %Y")
                    mpivot = hist2.pivot_table(index="MonthYear", columns="Type", values="Quantity", aggfunc="sum", fill_value=0).reset_index()
                    if "Inward"   not in mpivot.columns: mpivot["Inward"]   = 0
                    if "Outgoing" not in mpivot.columns: mpivot["Outgoing"] = 0
                    mpivot["Net"]           = mpivot["Inward"] - mpivot["Outgoing"]
                    mpivot["Inward Value"]  = (mpivot["Inward"]   * price_per).apply(lambda x: f"₹{x:,.0f}")
                    mpivot["Outgoing Value"]= (mpivot["Outgoing"] * price_per).apply(lambda x: f"₹{x:,.0f}")
                    st.dataframe(mpivot.sort_values("MonthYear", ascending=False), use_container_width=True, hide_index=True)

                    # Top buyers for this size
                    st.subheader("👥 Top Buyers")
                    buyers_sz = hist[hist["Type"]=="Outgoing"].groupby("Remarks").agg({"Quantity":"sum","Date":["min","max"]}).reset_index()
                    buyers_sz.columns = ["Buyer","Total Qty","First Purchase","Last Purchase"]
                    buyers_sz["Total Value"] = (buyers_sz["Total Qty"] * price_per).apply(lambda x: f"₹{x:,.0f}")
                    buyers_sz["First Purchase"] = pd.to_datetime(buyers_sz["First Purchase"]).dt.strftime("%Y-%m-%d")
                    buyers_sz["Last Purchase"]  = pd.to_datetime(buyers_sz["Last Purchase"]).dt.strftime("%Y-%m-%d")
                    st.dataframe(buyers_sz.sort_values("Total Qty", ascending=False), use_container_width=True, hide_index=True)

                    # Stock timeline
                    st.subheader("📈 Stock Timeline")
                    tl = hist.sort_values("Date").copy()
                    tl["Net Qty"] = tl.apply(lambda x: x["Quantity"] if x["Type"]=="Inward" else -x["Quantity"], axis=1)
                    tl["Cumulative"] = tl["Net Qty"].cumsum()
                    tl_m = tl.set_index("Date").resample("ME")["Cumulative"].last().reset_index()
                    if not tl_m.empty:
                        chart = alt.Chart(tl_m).mark_line(point=True, color="#e23c3c").encode(
                            x=alt.X("Date:T", title="Date"),
                            y=alt.Y("Cumulative:Q", title="Stock Level"),
                            tooltip=["Date","Cumulative"]
                        ).properties(height=280, title=f"Stock Level Over Time — {target_size}mm")
                        st.altair_chart(chart, use_container_width=True)

                    _chatbot_done = True

            # ══════════════════════════════════════════════════
            # CASE 2 — BUYER QUERY (detailed per buyer)
            # ══════════════════════════════════════════════════
            if buyer_cb and not _chatbot_done:
                bdf = df_cb[df_cb["Remarks"].str.lower() == buyer_cb.lower()].copy()

                if movement == "pending":
                    bdf = bdf[(bdf["Type"]=="Outgoing") & (bdf["Pending"]==True)]
                    st.subheader(f"⏳ Pending Orders — {buyer_cb}")
                elif movement == "incoming":
                    bdf = bdf[bdf["Type"]=="Inward"]
                    st.subheader(f"📥 Incoming — {buyer_cb}")
                elif movement == "outgoing":
                    bdf = bdf[bdf["Type"]=="Outgoing"]
                    st.subheader(f"📤 Outgoing — {buyer_cb}")
                else:
                    st.subheader(f"📊 All Transactions — {buyer_cb}")

                if month_num:
                    start_dt = datetime(year_num, month_num, 1)
                    end_dt   = (datetime(year_num, month_num+1, 1) - timedelta(days=1)) if month_num < 12 else datetime(year_num,12,31)
                    bdf = bdf[(bdf["Date"] >= start_dt) & (bdf["Date"] <= end_dt)]

                bdf = bdf.dropna(subset=["Size (mm)","Quantity"])

                if bdf.empty:
                    st.warning(f"No records found for {buyer_cb}" + (f" in {month_name} {year_num}" if month_num else ""))
                else:
                    bdf["Value (₹)"] = bdf.apply(lambda r: calc_value(r["Size (mm)"], r["Quantity"]), axis=1)
                    total_b = int(bdf["Quantity"].sum())
                    total_v = bdf["Value (₹)"].sum()
                    c1,c2,c3 = st.columns(3)
                    c1.metric("Total Rotors", f"{total_b:,}")
                    c2.metric("Total Value",  f"₹{total_v:,.0f}")
                    c3.metric("Transactions", len(bdf))

                    # Detailed transactions
                    disp_b = bdf.copy()
                    disp_b["Date"]    = disp_b["Date"].dt.strftime("%Y-%m-%d")
                    disp_b["Value (₹)"] = disp_b["Value (₹)"].apply(lambda x: f"₹{x:,.0f}")
                    disp_b["Pending"] = disp_b["Pending"].apply(lambda x: "Yes" if x else "No")
                    st.subheader("📋 Detailed Transactions")
                    st.dataframe(
                        disp_b[["Date","Type","Size (mm)","Quantity","Status","Pending","Value (₹)"]].rename(columns={"Size (mm)":"Size"}),
                        use_container_width=True, hide_index=True
                    )

                    # Size-wise breakdown
                    st.subheader("📊 Size-wise Summary")
                    sz_grp = bdf.groupby("Size (mm)").agg({"Quantity":"sum","Value (₹)":"sum"}).reset_index()
                    sz_grp["Price/Rotor"] = sz_grp["Size (mm)"].apply(lambda s: f"₹{get_price(s):,.0f}")
                    sz_grp["Value (₹)"]  = sz_grp["Value (₹)"].apply(lambda x: f"₹{x:,.0f}")
                    st.dataframe(sz_grp.rename(columns={"Size (mm)":"Size","Quantity":"Total Qty"}), use_container_width=True, hide_index=True)

                    # Monthly summary for buyer
                    st.subheader("📅 Monthly Summary")
                    bdf2 = bdf.copy()
                    bdf2["MonthYear"] = bdf2["Date"].dt.strftime("%b %Y") if not bdf2["Date"].dtype == object else pd.to_datetime(bdf2["Date"]).dt.strftime("%b %Y")
                    bm = bdf2.groupby("MonthYear").agg({"Quantity":"sum","Value (₹)":"sum"}).reset_index()
                    bm["Value (₹)"] = bm["Value (₹)"].apply(lambda x: f"₹{x:,.0f}")
                    st.dataframe(bm.sort_values("MonthYear", ascending=False), use_container_width=True, hide_index=True)

                _chatbot_done = True

            # ══════════════════════════════════════════════════
            # CASE 3 — ALL BUYERS LIST
            # ══════════════════════════════════════════════════
            if movement == "buyers" and not _chatbot_done:
                st.subheader("👥 All Buyers")
                bout = df_cb[df_cb["Type"]=="Outgoing"].groupby("Remarks").agg(
                    {"Quantity":"sum","Date":["min","max","count"]}
                ).reset_index()
                bout.columns = ["Buyer","Total Qty","First","Last","Transactions"]
                bout["Total Value"] = bout.apply(lambda r: f"₹{r['Total Qty'] * get_price(0):,.0f}", axis=1)
                bout = bout.sort_values("Total Qty", ascending=False)
                bout["First"] = pd.to_datetime(bout["First"]).dt.strftime("%Y-%m-%d")
                bout["Last"]  = pd.to_datetime(bout["Last"]).dt.strftime("%Y-%m-%d")

                c1,c2,c3 = st.columns(3)
                c1.metric("Total Buyers",       len(bout))
                c2.metric("Total Rotors Sold",  f"{int(bout['Total Qty'].sum()):,}")
                c3.metric("Transactions",        int(bout["Transactions"].sum()))
                st.dataframe(bout, use_container_width=True, hide_index=True)
                _chatbot_done = True

            # ══════════════════════════════════════════════════
            # CASE 4 — COMING ROTORS
            # ══════════════════════════════════════════════════
            if movement == "coming" and not _chatbot_done:
                st.subheader("📅 Coming Rotors")
                com = df_cb[(df_cb["Status"]=="Future") & (df_cb["Type"]=="Inward")].sort_values("Date")
                if com.empty:
                    st.info("No future rotors scheduled.")
                else:
                    com["Value (₹)"] = com.apply(lambda r: calc_value(r["Size (mm)"], r["Quantity"]), axis=1)
                    total_com = int(com["Quantity"].sum())
                    total_comv = com["Value (₹)"].sum()
                    c1,c2,c3,c4 = st.columns(4)
                    c1.metric("Total Coming",    f"{total_com:,}")
                    c2.metric("Total Value",     f"₹{total_comv:,.0f}")
                    c3.metric("Different Sizes", com["Size (mm)"].nunique())
                    c4.metric("Suppliers",       com["Remarks"].nunique())

                    # Date-wise schedule
                    st.subheader("📆 Date-wise Schedule")
                    dsum = com.groupby("Date").agg({
                        "Size (mm)": lambda x: ", ".join(map(str, sorted(set(x)))),
                        "Quantity":  "sum",
                        "Value (₹)": "sum",
                        "Remarks":   lambda x: ", ".join(sorted(set(x.astype(str))))
                    }).reset_index()
                    dsum["Date"]     = dsum["Date"].dt.strftime("%Y-%m-%d")
                    dsum["Value (₹)"]= dsum["Value (₹)"].apply(lambda x: f"₹{x:,.0f}")
                    st.dataframe(dsum.rename(columns={"Date":"Arrival Date","Size (mm)":"Sizes","Quantity":"Total Qty","Remarks":"Suppliers"}), use_container_width=True, hide_index=True)

                    # Size-wise breakdown
                    st.subheader("📊 Size-wise Breakdown")
                    scom = com.groupby("Size (mm)").agg({"Quantity":"sum","Value (₹)":"sum"}).reset_index()
                    scom["Price/Rotor"] = scom["Size (mm)"].apply(lambda s: f"₹{get_price(s):,.0f}")
                    scom["Value (₹)"]   = scom["Value (₹)"].apply(lambda x: f"₹{x:,.0f}")
                    st.dataframe(scom.rename(columns={"Size (mm)":"Size","Quantity":"Total Qty"}), use_container_width=True, hide_index=True)

                    # Full transaction list
                    with st.expander("📋 All Scheduled Transactions"):
                        dc = com.copy()
                        dc["Date"]     = dc["Date"].dt.strftime("%Y-%m-%d")
                        dc["Value (₹)"]= dc["Value (₹)"].apply(lambda x: f"₹{x:,.0f}")
                        st.dataframe(dc[["Date","Size (mm)","Quantity","Remarks","Value (₹)"]].rename(columns={"Size (mm)":"Size","Remarks":"Supplier"}), use_container_width=True, hide_index=True)

                _chatbot_done = True

            # ══════════════════════════════════════════════════
            # CASE 5 — PENDING ORDERS (no buyer filter)
            # ══════════════════════════════════════════════════
            if movement == "pending" and not buyer_cb and not _chatbot_done:
                st.subheader("⏳ All Pending Orders")
                pend_df = df_cb[(df_cb["Type"]=="Outgoing") & (df_cb["Pending"]==True)].copy()
                if pend_df.empty:
                    st.info("No pending orders.")
                else:
                    pend_df["Value (₹)"] = pend_df.apply(lambda r: calc_value(r["Size (mm)"], r["Quantity"]), axis=1)
                    c1,c2,c3 = st.columns(3)
                    c1.metric("Total Pending", int(pend_df["Quantity"].sum()))
                    c2.metric("Total Value",   f"₹{pend_df['Value (₹)'].sum():,.0f}")
                    c3.metric("Buyers",        pend_df["Remarks"].nunique())

                    # Per buyer
                    for buyer_p in sorted(pend_df["Remarks"].unique()):
                        bpdf = pend_df[pend_df["Remarks"]==buyer_p]
                        with st.expander(f"👤 {buyer_p} — {int(bpdf['Quantity'].sum())} rotors"):
                            disp_p = bpdf.copy()
                            disp_p["Date"]     = disp_p["Date"].dt.strftime("%Y-%m-%d")
                            disp_p["Value (₹)"]= disp_p["Value (₹)"].apply(lambda x: f"₹{x:,.0f}")
                            st.dataframe(disp_p[["Date","Size (mm)","Quantity","Value (₹)"]].rename(columns={"Size (mm)":"Size"}), use_container_width=True, hide_index=True)

                    # Size summary
                    st.subheader("📊 Pending by Size")
                    psz = pend_df.groupby("Size (mm)").agg({"Quantity":"sum","Value (₹)":"sum"}).reset_index()
                    psz["Value (₹)"] = psz["Value (₹)"].apply(lambda x: f"₹{x:,.0f}")
                    st.dataframe(psz.rename(columns={"Size (mm)":"Size","Quantity":"Total Qty"}), use_container_width=True, hide_index=True)

                _chatbot_done = True

            # ══════════════════════════════════════════════════
            # CASE 6 — MONTH/YEAR QUERY (general)
            # ══════════════════════════════════════════════════
            if month_num and not _chatbot_done:
                start_dt = datetime(year_num, month_num, 1)
                end_dt   = (datetime(year_num, month_num+1, 1) - timedelta(days=1)) if month_num < 12 else datetime(year_num, 12, 31)
                mdf = df_cb[(df_cb["Date"] >= start_dt) & (df_cb["Date"] <= end_dt)].copy()
                mdf = mdf.dropna(subset=["Size (mm)","Quantity"])
                st.subheader(f"📅 {month_name} {year_num} — All Transactions")
                if mdf.empty:
                    st.info(f"No transactions in {month_name} {year_num}.")
                else:
                    mdf["Value (₹)"] = mdf.apply(lambda r: calc_value(r["Size (mm)"], r["Quantity"]), axis=1)
                    c1,c2,c3 = st.columns(3)
                    c1.metric("Total Rotors",   int(mdf["Quantity"].sum()))
                    c2.metric("Total Value",    f"₹{mdf['Value (₹)'].sum():,.0f}")
                    c3.metric("Transactions",   len(mdf))
                    disp_m = mdf.copy()
                    disp_m["Date"]     = disp_m["Date"].dt.strftime("%Y-%m-%d")
                    disp_m["Value (₹)"]= disp_m["Value (₹)"].apply(lambda x: f"₹{x:,.0f}")
                    disp_m["Pending"]  = disp_m["Pending"].apply(lambda x: "Yes" if x else "No")
                    st.dataframe(
                        disp_m[["Date","Type","Size (mm)","Quantity","Remarks","Status","Pending","Value (₹)"]].rename(columns={"Size (mm)":"Size","Remarks":"Buyer/Supplier"}),
                        use_container_width=True, hide_index=True
                    )
                    # Buyer breakdown
                    st.subheader("👥 Buyer Breakdown")
                    bg = mdf.groupby("Remarks").agg({"Quantity":"sum","Value (₹)":"sum"}).reset_index()
                    bg["Value (₹)"] = bg["Value (₹)"].apply(lambda x: f"₹{x:,.0f}")
                    st.dataframe(bg.rename(columns={"Remarks":"Buyer","Quantity":"Total Qty"}), use_container_width=True, hide_index=True)
                _chatbot_done = True

            # ══════════════════════════════════════════════════
            # CASE 7 — INCOMING / OUTGOING (no other filters)
            # ══════════════════════════════════════════════════
            if movement in ("incoming","outgoing") and not buyer_cb and not _chatbot_done:
                fdf = df_cb[df_cb["Type"] == ("Inward" if movement=="incoming" else "Outgoing")].copy()
                fdf = fdf.dropna(subset=["Size (mm)","Quantity"])
                label = "📥 Latest Incoming" if movement=="incoming" else "📤 Latest Outgoing"
                st.subheader(label)
                if fdf.empty:
                    st.info("No records.")
                else:
                    fdf["Value (₹)"] = fdf.apply(lambda r: calc_value(r["Size (mm)"], r["Quantity"]), axis=1)
                    c1,c2 = st.columns(2)
                    c1.metric("Total Qty",   int(fdf["Quantity"].sum()))
                    c2.metric("Total Value", f"₹{fdf['Value (₹)'].sum():,.0f}")
                    disp_f = fdf.sort_values("Date", ascending=False).copy()
                    disp_f["Date"]     = disp_f["Date"].dt.strftime("%Y-%m-%d")
                    disp_f["Value (₹)"]= disp_f["Value (₹)"].apply(lambda x: f"₹{x:,.0f}")
                    disp_f["Pending"]  = disp_f["Pending"].apply(lambda x: "Yes" if x else "No")
                    st.dataframe(
                        disp_f[["Date","Size (mm)","Quantity","Remarks","Status","Pending","Value (₹)"]].rename(columns={"Size (mm)":"Size","Remarks":"Buyer/Supplier"}),
                        use_container_width=True, hide_index=True
                    )
                    # Size summary
                    st.subheader("📊 By Size")
                    sg = fdf.groupby("Size (mm)").agg({"Quantity":"sum","Value (₹)":"sum"}).reset_index()
                    sg["Value (₹)"] = sg["Value (₹)"].apply(lambda x: f"₹{x:,.0f}")
                    st.dataframe(sg.rename(columns={"Size (mm)":"Size","Quantity":"Total Qty"}), use_container_width=True, hide_index=True)
                _chatbot_done = True

            # ══════════════════════════════════════════════════
            # CASE 8 — FALLBACK: show all matching
            # ══════════════════════════════════════════════════
            if not _chatbot_done:
                st.warning(f"No specific match for '{chat_query}'. Showing all records.")
                all_df = df_cb.dropna(subset=["Size (mm)","Quantity"]).copy()
                all_df["Value (₹)"] = all_df.apply(lambda r: calc_value(r["Size (mm)"], r["Quantity"]), axis=1)
                all_df["Date"]      = all_df["Date"].dt.strftime("%Y-%m-%d")
                all_df["Pending"]   = all_df["Pending"].apply(lambda x: "Yes" if x else "No")
                all_df["Value (₹)"] = all_df["Value (₹)"].apply(lambda x: f"₹{x:,.0f}")
                st.dataframe(
                    all_df[["Date","Type","Size (mm)","Quantity","Remarks","Status","Pending","Value (₹)"]].rename(columns={"Size (mm)":"Size","Remarks":"Buyer/Supplier"}),
                    use_container_width=True, hide_index=True
                )

    # ══ TAB: AI Assistant ══
    with tabs[3]:
        section("🤖", "AI Assistant")

        connected = st.session_state.ai_config["initialized"]
        if connected:
            st.success(f"✅ Connected to {st.session_state.ai_config['provider']} ({st.session_state.ai_config['model']})")
        else:
            st.warning("⚠️ Not connected — using basic fallback mode")

        with st.expander("🔌 AI Connection Settings", expanded=not connected):
            prov  = st.selectbox("Provider", list(AI_PROVIDERS.keys()), index=list(AI_PROVIDERS.keys()).index(st.session_state.ai_config["provider"]))
            model = st.selectbox("Model", AI_PROVIDERS[prov]["models"])
            akey  = st.text_input("API Key", type="password", value=st.session_state.ai_config.get("api_key",""))
            colA, colB = st.columns(2)
            with colA:
                if st.button("🔄 Connect", use_container_width=True, type="primary"):
                    if akey:
                        st.session_state.ai_config.update({"provider":prov,"model":model,"api_key":akey,"initialized":True})
                        st.success("✅ Connected!")
                        st.rerun()
            with colB:
                if st.button("❌ Disconnect", use_container_width=True):
                    st.session_state.ai_config["initialized"] = False
                    st.rerun()

        # Chat display
        for msg in st.session_state.chat_messages[-10:]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # Quick buttons
        qcols = st.columns(6)
        quick = [("📦 Stock","Show current stock levels"),("⏳ Pending","Show all pending orders"),("📥 Incoming","Latest incoming transactions"),("📤 Outgoing","Latest outgoing transactions"),("📅 Coming","Future incoming rotors"),("❓ Help","What can you help me with?")]
        for i, (label, prompt) in enumerate(quick):
            with qcols[i]:
                if st.button(label, key=f"qb_{i}", use_container_width=True):
                    resp = get_ai_response(prompt)
                    st.session_state.chat_messages.append({"role":"user","content":prompt})
                    st.session_state.chat_messages.append({"role":"assistant","content":resp})
                    st.rerun()

        # Chat input
        with st.form("ai_chat_form", clear_on_submit=True):
            user_inp = st.text_input("Ask me anything about your inventory...", placeholder="e.g., stock of 1803mm, pending for Ajji")
            c1, c2 = st.columns([4,1])
            with c1:
                send = st.form_submit_button("📤 Send", type="primary", use_container_width=True)
            with c2:
                clear = st.form_submit_button("🗑 Clear", use_container_width=True)
        if send and user_inp:
            resp = get_ai_response(user_inp)
            st.session_state.chat_messages.append({"role":"user","content":user_inp})
            st.session_state.chat_messages.append({"role":"assistant","content":resp})
            st.rerun()
        if clear:
            st.session_state.chat_messages = [{"role":"assistant","content":"👋 Chat cleared. Ask me anything!"}]
            st.rerun()


# ============================================================
# ── TAB 2: CLITTING + LAMINATIONS + STATORS ─────────────────
# ============================================================
elif tab_choice == "🧰 Clitting + Laminations + Stators":

    # Load sub-sheets if empty
    if st.session_state.clitting_data.empty:
        st.session_state.clitting_data = load_named_sheet("Clitting", st.session_state.clitting_data.columns)
    if st.session_state.lamination_v3.empty:
        st.session_state.lamination_v3 = load_named_sheet("V3 Laminations", st.session_state.lamination_v3.columns)
    if st.session_state.lamination_v4.empty:
        st.session_state.lamination_v4 = load_named_sheet("V4 Laminations", st.session_state.lamination_v4.columns)
    if st.session_state.stator_data.empty:
        st.session_state.stator_data = load_named_sheet("Stator Usage", st.session_state.stator_data.columns)

    st.title("🧰 Clitting + Laminations + Stator Outgoings")
    tab1, tab2, tab3, tab4 = st.tabs(["📥 Clitting", "🧩 Laminations", "📤 Stator Outgoings", "📊 Summary"])

    # ── TAB 1: Clitting ──
    with tab1:
        section("📥", "Clitting Inward")
        with st.form("clitting_form"):
            c_date   = st.date_input("📅 Date", value=datetime.today())
            c_size   = st.number_input("📏 Stator Size (mm)", min_value=1, step=1)
            c_bags   = st.number_input("🧮 Bags", min_value=1, step=1)
            c_weight = st.number_input("⚖️ Weight per Bag (kg)", value=25.0, step=0.5)
            c_rem    = st.text_input("📝 Remarks")
            if st.form_submit_button("➕ Add Clitting", type="primary"):
                entry = {"Date":c_date.strftime("%Y-%m-%d"),"Size (mm)":int(c_size),"Bags":int(c_bags),"Weight per Bag (kg)":float(c_weight),"Remarks":c_rem.strip(),"ID":str(uuid4())}
                st.session_state.clitting_data = pd.concat([st.session_state.clitting_data, pd.DataFrame([entry])], ignore_index=True)
                save_to_named_sheet(st.session_state.clitting_data, "Clitting")
                st.success("✅ Clitting entry added.")
                st.rerun()

        section("📄", "Clitting Log")
        for idx, row in st.session_state.clitting_data.iterrows():
            with st.expander(f"{row['Date']} | {row['Size (mm)']}mm | {row['Bags']} bags"):
                col1, col2 = st.columns([1,2])
                with col1:
                    if st.button("🗑 Delete", key=f"del_clit_{row['ID']}"):
                        st.session_state.clitting_data = st.session_state.clitting_data[st.session_state.clitting_data["ID"] != row["ID"]].reset_index(drop=True)
                        save_to_named_sheet(st.session_state.clitting_data, "Clitting")
                        st.rerun()
                with col2:
                    nb = st.number_input("Bags", value=int(row["Bags"]), key=f"cb_{row['ID']}")
                    nw = st.number_input("Weight/Bag", value=float(row["Weight per Bag (kg)"]), key=f"cw_{row['ID']}")
                    nr = st.text_input("Remarks", value=row["Remarks"], key=f"cr_{row['ID']}")
                    if st.button("💾 Save", key=f"cs_{row['ID']}", type="primary"):
                        st.session_state.clitting_data.at[idx,"Bags"] = nb
                        st.session_state.clitting_data.at[idx,"Weight per Bag (kg)"] = nw
                        st.session_state.clitting_data.at[idx,"Remarks"] = nr
                        save_to_named_sheet(st.session_state.clitting_data, "Clitting")
                        st.success("✅ Updated.")

    # ── TAB 2: Laminations ──
    with tab2:
        section("📥", "Laminations Inward (V3 / V4)")
        with st.form("lamination_form"):
            l_date = st.date_input("📅 Date", value=datetime.today(), key="lam_date")
            l_type = st.selectbox("🔀 Type", ["V3","V4"])
            l_qty  = st.number_input("🔢 Quantity", min_value=1, step=1)
            l_rem  = st.text_input("📝 Remarks", key="lam_rem")
            if st.form_submit_button("➕ Add Laminations", type="primary"):
                entry = {"Date":l_date.strftime("%Y-%m-%d"),"Quantity":int(l_qty),"Remarks":l_rem.strip(),"ID":str(uuid4())}
                lk = "lamination_v3" if l_type=="V3" else "lamination_v4"
                st.session_state[lk] = pd.concat([st.session_state[lk], pd.DataFrame([entry])], ignore_index=True)
                save_to_named_sheet(st.session_state[lk], f"{'V3' if l_type=='V3' else 'V4'} Laminations")
                st.success(f"✅ {l_type} Lamination added.")
                st.rerun()

        for lt in ["V3","V4"]:
            lk = "lamination_v3" if lt=="V3" else "lamination_v4"
            section("📄", f"{lt} Lamination Log")
            ldf = st.session_state[lk].copy()
            total_lam = pd.to_numeric(ldf["Quantity"], errors="coerce").sum() if not ldf.empty else 0
            st.metric(f"{lt} Stock", int(total_lam))
            for idx, row in ldf.iterrows():
                with st.expander(f"{row['Date']} | Qty: {row['Quantity']}"):
                    col1, col2 = st.columns([1,2])
                    with col1:
                        if st.button("🗑", key=f"dl_{lt}_{row['ID']}"):
                            st.session_state[lk] = ldf[ldf["ID"] != row["ID"]].reset_index(drop=True)
                            save_to_named_sheet(st.session_state[lk], f"{lt} Laminations")
                            st.rerun()
                    with col2:
                        nq = st.number_input("Qty", value=int(row["Quantity"]), key=f"lq_{row['ID']}")
                        nr = st.text_input("Remarks", value=row["Remarks"], key=f"lr_{row['ID']}")
                        if st.button("💾 Save", key=f"ls_{row['ID']}", type="primary"):
                            st.session_state[lk].at[idx,"Quantity"] = nq
                            st.session_state[lk].at[idx,"Remarks"]  = nr
                            save_to_named_sheet(st.session_state[lk], f"{lt} Laminations")
                            st.success("✅ Updated.")

    # ── TAB 3: Stator Outgoings ──
    with tab3:
        section("📤", "Stator Outgoings")
        with st.form("stator_form"):
            s_date = st.date_input("📅 Date", value=datetime.today(), key="sd")
            s_size = st.number_input("📏 Stator Size (mm)", min_value=1, step=1, key="ss")
            s_qty  = st.number_input("🔢 Quantity", min_value=1, step=1, key="sq")
            s_type = st.selectbox("🔀 Lamination Type", ["V3","V4"], key="st")
            s_rem  = st.text_input("📝 Remarks", key="sr")
            if st.form_submit_button("📋 Log Stator Outgoing", type="primary"):
                sk       = int(s_size)
                c_used   = CLITTING_USAGE.get(sk, 0) * int(s_qty)
                lam_used = int(s_qty) * 2
                lk       = "lamination_v3" if s_type=="V3" else "lamination_v4"

                # Stock check
                clit_stock = 0
                for _, cr in st.session_state.clitting_data.iterrows():
                    if int(cr["Size (mm)"]) == sk:
                        clit_stock += int(cr["Bags"]) * float(cr["Weight per Bag (kg)"])
                for _, sr in st.session_state.stator_data.iterrows():
                    if int(sr["Size (mm)"]) == sk:
                        clit_stock -= float(sr.get("Estimated Clitting (kg)",0) or 0)
                if clit_stock < c_used:
                    st.warning(f"⚠️ Clitting low: have {clit_stock:.2f}kg, need {c_used:.2f}kg")
                lam_stock = pd.to_numeric(st.session_state[lk]["Quantity"], errors="coerce").sum()
                if lam_stock < lam_used:
                    st.warning(f"⚠️ {s_type} laminations low: have {lam_stock}, need {lam_used}")

                new_s = {"Date":s_date.strftime("%Y-%m-%d"),"Size (mm)":sk,"Quantity":int(s_qty),"Remarks":s_rem.strip(),"Estimated Clitting (kg)":round(c_used,2),"Laminations Used":lam_used,"Lamination Type":s_type,"ID":str(uuid4())}
                st.session_state.stator_data = pd.concat([st.session_state.stator_data, pd.DataFrame([new_s])], ignore_index=True)
                save_to_named_sheet(st.session_state.stator_data, "Stator Usage")

                # Deduct laminations
                ldf = st.session_state[lk].copy()
                need = lam_used
                for i2, r2 in ldf.iterrows():
                    if need <= 0: break
                    avail = int(r2["Quantity"])
                    if need >= avail:
                        need -= avail
                        ldf.at[i2,"Quantity"] = 0
                    else:
                        ldf.at[i2,"Quantity"] = avail - need
                        need = 0
                ldf = ldf[ldf["Quantity"] > 0].reset_index(drop=True)
                st.session_state[lk] = ldf
                save_to_named_sheet(st.session_state[lk], f"{'V3' if s_type=='V3' else 'V4'} Laminations")
                st.success(f"✅ Logged. Clitting used: {c_used:.2f}kg | Laminations: {lam_used}")
                st.rerun()

        section("📄", "Stator Usage Log")
        for idx, row in st.session_state.stator_data.iterrows():
            with st.expander(f"{row['Date']} | {row['Size (mm)']}mm | Qty: {row['Quantity']}"):
                col1, col2 = st.columns([1,2])
                with col1:
                    if st.button("🗑 Delete", key=f"ds_{row['ID']}"):
                        st.session_state.stator_data = st.session_state.stator_data[st.session_state.stator_data["ID"] != row["ID"]].reset_index(drop=True)
                        save_to_named_sheet(st.session_state.stator_data, "Stator Usage")
                        st.rerun()
                with col2:
                    nq = st.number_input("Qty", value=int(row["Quantity"]), key=f"sq2_{row['ID']}")
                    nr = st.text_input("Remarks", value=row["Remarks"], key=f"sr2_{row['ID']}")
                    if st.button("💾 Save", key=f"ss2_{row['ID']}", type="primary"):
                        st.session_state.stator_data.at[idx,"Quantity"] = nq
                        st.session_state.stator_data.at[idx,"Remarks"]  = nr
                        save_to_named_sheet(st.session_state.stator_data, "Stator Usage")
                        st.success("✅ Updated.")

    # ── TAB 4: Summary ──
    with tab4:
        section("📊", "Production Summary")

        # Clitting stock by size
        cdf = st.session_state.clitting_data.copy()
        sdf = st.session_state.stator_data.copy()
        cdf["Size (mm)"] = pd.to_numeric(cdf["Size (mm)"], errors="coerce")
        cdf["Bags"]      = pd.to_numeric(cdf["Bags"], errors="coerce")
        cdf["Weight per Bag (kg)"] = pd.to_numeric(cdf["Weight per Bag (kg)"], errors="coerce")
        cdf["Total kg"]  = cdf["Bags"] * cdf["Weight per Bag (kg)"]
        sdf["Size (mm)"] = pd.to_numeric(sdf["Size (mm)"], errors="coerce")
        sdf["Estimated Clitting (kg)"] = pd.to_numeric(sdf["Estimated Clitting (kg)"], errors="coerce")

        if not cdf.empty:
            cin  = cdf.groupby("Size (mm)")["Total kg"].sum().reset_index().rename(columns={"Total kg":"Clitting In (kg)"})
            cout = sdf.groupby("Size (mm)")["Estimated Clitting (kg)"].sum().reset_index().rename(columns={"Estimated Clitting (kg)":"Clitting Used (kg)"}) if not sdf.empty else pd.DataFrame(columns=["Size (mm)","Clitting Used (kg)"])
            cm   = cin.merge(cout, on="Size (mm)", how="outer").fillna(0)
            cm["Clitting Balance (kg)"] = cm["Clitting In (kg)"] - cm["Clitting Used (kg)"]
            st.subheader("📦 Clitting Stock")
            st.dataframe(cm.round(2), use_container_width=True, hide_index=True)

        # Lamination stock
        v3_stock = pd.to_numeric(st.session_state.lamination_v3["Quantity"], errors="coerce").sum() if not st.session_state.lamination_v3.empty else 0
        v4_stock = pd.to_numeric(st.session_state.lamination_v4["Quantity"], errors="coerce").sum() if not st.session_state.lamination_v4.empty else 0
        st.subheader("🧩 Lamination Stock")
        c1, c2 = st.columns(2)
        c1.metric("V3 Laminations", int(v3_stock))
        c2.metric("V4 Laminations", int(v4_stock))

        # Stator log
        if not sdf.empty:
            st.subheader("📤 Stator Outgoings Summary")
            stator_grp = sdf.groupby("Size (mm)").agg({"Quantity":"sum","Estimated Clitting (kg)":"sum","Laminations Used":"sum"}).reset_index()
            st.dataframe(stator_grp.round(2), use_container_width=True, hide_index=True)
