# rotor_tracker.py — Fixed & Improved Version

# ══════════════════════════════════════════════
# 1. IMPORTS  (consolidated — no duplicates)
# ══════════════════════════════════════════════
import os
import re
import json
from uuid import uuid4
from datetime import datetime, timedelta

import requests
import pandas as pd
import altair as alt
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image
import io

# ══════════════════════════════════════════════
# 2. PAGE CONFIG  (must be the very first st call)
# ══════════════════════════════════════════════
st.set_page_config(
    page_title="Rotor + Stator Tracker",
    page_icon="🔁",
    layout="wide",
)

# ══════════════════════════════════════════════
# 3. CONSTANTS
# ══════════════════════════════════════════════
ROTOR_WEIGHTS = {
    80: 0.5,   100: 1.0,  110: 1.01, 120: 1.02, 125: 1.058,
    130: 1.1,  140: 1.15, 150: 1.3,  160: 1.4,  170: 1.422,
    180: 1.5,  200: 1.7,  225: 1.9,  260: 2.15,
    1803: 1.0, 2003: 1.1, 2403: 1.46,
}

CLITTING_USAGE = {
    100: 0.04, 120: 0.05, 125: 0.05, 130: 0.05, 140: 0.06,
    150: 0.06, 160: 0.07, 170: 0.08, 180: 0.09, 190: 0.10,
    200: 0.11, 225: 0.12, 260: 0.13, 300: 0.14,
}

AI_PROVIDERS = {
    "Sarvam AI": {
        "base_url": "https://api.sarvam.ai/v1/chat/completions",
        "models": ["sarvam-m", "sarvam-2b"],
        "default_model": "sarvam-m",
        "headers": lambda k: {"api-subscription-key": k, "Content-Type": "application/json"},
        "api_key_in_url": False,
        "format": "openai",
    },
    "Gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/models/",
        "models": ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
        "default_model": "gemini-2.0-flash",
        "headers": lambda k: {"Content-Type": "application/json"},
        "api_key_in_url": True,
        "format": "gemini",
    },
    "OpenRouter": {
        "base_url": "https://openrouter.ai/api/v1/chat/completions",
        "models": ["deepseek/deepseek-chat", "mistralai/mistral-7b-instruct", "google/gemma-7b-it"],
        "default_model": "deepseek/deepseek-chat",
        "headers": lambda k: {"Authorization": f"Bearer {k}", "Content-Type": "application/json"},
        "api_key_in_url": False,
        "format": "openai",
    },
}

# ══════════════════════════════════════════════
# 4. SESSION STATE INITIALISATION
# ══════════════════════════════════════════════
def _init_session():
    defaults = {
        "data": pd.DataFrame(columns=[
            "Date", "Size (mm)", "Type", "Quantity",
            "Remarks", "Status", "Pending", "ID"
        ]),
        "last_sync": "Never",
        "editing": None,
        "clitting_data": pd.DataFrame(columns=[
            "Date", "Size (mm)", "Bags", "Weight per Bag (kg)", "Remarks", "ID"
        ]),
        "lamination_v3": pd.DataFrame(columns=["Date", "Quantity", "Remarks", "ID"]),
        "lamination_v4": pd.DataFrame(columns=["Date", "Quantity", "Remarks", "ID"]),
        "stator_data": pd.DataFrame(columns=[
            "Date", "Size (mm)", "Quantity", "Remarks",
            "Estimated Clitting (kg)", "Laminations Used", "Lamination Type", "ID"
        ]),
        "fixed_prices": {1803: 460, 2003: 511, 35: 210, 40: 265, 50: 293, 70: 398},
        "base_rate_per_mm": 4.15,
        # AI assistant
        "ai_chat_messages": [
            {"role": "assistant",
             "content": "👋 Hi! I'm your AI inventory assistant. Ask me anything about your stock!"}
        ],
        "ai_conversation_history": [],
        "ai_config": {
            "provider": "Sarvam AI",
            "model": "sarvam-m",
            "api_key": "",
            "initialized": False,
        },
        # Rotor entry flow
        "new_entry": None,
        "conflict_resolved": False,
        "action_required": False,
        "selected_idx": None,
        "future_matches": None,
        "last_snapshot": None,
        "last_action_note": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # Auto-load Sarvam key from secrets if present
    if not st.session_state.ai_config["api_key"]:
        try:
            key = st.secrets.get("SARVAM_API_KEY", "")
            if key:
                st.session_state.ai_config.update({"api_key": key, "initialized": True})
        except Exception:
            pass

_init_session()

# ══════════════════════════════════════════════
# 5. UTILITY FUNCTIONS
# ══════════════════════════════════════════════
def normalize_pending(df: pd.DataFrame) -> pd.DataFrame:
    df["Pending"] = df["Pending"].apply(
        lambda x: str(x).strip().lower() == "true" if isinstance(x, str) else bool(x)
    )
    return df

def get_price(size_mm) -> float:
    s = int(size_mm)
    if s in st.session_state.fixed_prices:
        return float(st.session_state.fixed_prices[s])
    return st.session_state.base_rate_per_mm * s

def calc_value(size_mm, qty) -> float:
    if pd.isna(size_mm) or pd.isna(qty):
        return 0.0
    return get_price(size_mm) * float(qty)

# ══════════════════════════════════════════════
# 6. GOOGLE SHEETS FUNCTIONS
# ══════════════════════════════════════════════
def _creds():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    raw = st.secrets["gcp_service_account"]
    d = json.loads(raw) if isinstance(raw, str) else dict(raw)
    d["private_key"] = d["private_key"].replace("\\n", "\n")
    return ServiceAccountCredentials.from_json_keyfile_dict(d, scope)

def _spreadsheet():
    return gspread.authorize(_creds()).open("Rotor Log")

def load_from_gsheet():
    try:
        sheet = _spreadsheet().sheet1
        records = sheet.get_all_records()
        if records:
            df = pd.DataFrame(records)
            for col, default in [("Status", "Current"), ("Pending", False)]:
                if col not in df.columns:
                    df[col] = default
            df = normalize_pending(df)
            if "ID" not in df.columns:
                df["ID"] = [str(uuid4()) for _ in range(len(df))]
            st.session_state.data = df
        st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"Error loading data: {e}")

def auto_save_to_gsheet():
    try:
        ss = _spreadsheet()
        sheet = ss.sheet1
        sheet.clear()
        if not st.session_state.data.empty:
            df = st.session_state.data.copy()
            df["Pending"] = df["Pending"].apply(lambda x: "TRUE" if x else "FALSE")
            cols = ["Date", "Size (mm)", "Type", "Quantity", "Remarks", "Status", "Pending", "ID"]
            for c in cols:
                if c not in df.columns:
                    df[c] = ""
            df = df[cols]
            sheet.update([df.columns.tolist()] + df.values.tolist())
            # Backup sheet
            try:
                try:
                    bk = ss.worksheet("Backup")
                except gspread.WorksheetNotFound:
                    bk = ss.add_worksheet("Backup", rows="1000", cols=str(len(df.columns)))
                bk.clear()
                bk.update([df.columns.tolist()] + df.values.tolist())
            except Exception:
                pass
        st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.error(f"Auto-save failed: {e}")

def _save_ws(df: pd.DataFrame, title: str):
    try:
        ss = _spreadsheet()
        try:
            ws = ss.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = ss.add_worksheet(title=title, rows="1000", cols="20")
        ws.clear()
        if not df.empty:
            ws.update([df.columns.tolist()] + df.values.tolist())
    except Exception as e:
        st.error(f"Error saving {title}: {e}")

def _load_ws(title: str, default_cols) -> pd.DataFrame:
    try:
        ws = _spreadsheet().worksheet(title)
        records = ws.get_all_records()
        if records:
            return pd.DataFrame(records)
    except gspread.WorksheetNotFound:
        pass
    except Exception as e:
        st.error(f"Error loading {title}: {e}")
    return pd.DataFrame(columns=default_cols)

save_clitting = lambda: _save_ws(st.session_state.clitting_data,  "Clitting")
save_v3_lam   = lambda: _save_ws(st.session_state.lamination_v3,  "V3 Laminations")
save_v4_lam   = lambda: _save_ws(st.session_state.lamination_v4,  "V4 Laminations")
save_stator   = lambda: _save_ws(st.session_state.stator_data,    "Stator Usage")
save_lam      = lambda t: save_v3_lam() if t == "V3" else save_v4_lam()

# ══════════════════════════════════════════════
# 7. AI ASSISTANT  (consolidated & improved)
# ══════════════════════════════════════════════

def build_inventory_context() -> dict:
    """Build a rich snapshot of inventory for the AI."""
    if st.session_state.data.empty:
        return {"error": "No inventory data loaded."}

    df = st.session_state.data.copy()
    df["Date"]     = pd.to_datetime(df["Date"], errors="coerce")
    df["Size (mm)"] = pd.to_numeric(df["Size (mm)"], errors="coerce")
    df["Quantity"]  = pd.to_numeric(df["Quantity"],  errors="coerce")
    df = normalize_pending(df)

    stock_rows = []
    for size in sorted(df["Size (mm)"].dropna().unique()):
        sdf     = df[df["Size (mm)"] == size]
        inward  = int(sdf[sdf["Type"] == "Inward"]["Quantity"].sum())
        sold    = int(sdf[(sdf["Type"] == "Outgoing") & (~sdf["Pending"])]["Quantity"].sum())
        pending = int(sdf[(sdf["Type"] == "Outgoing") & (sdf["Pending"] == True)]["Quantity"].sum())
        future  = int(sdf[(sdf["Type"] == "Inward")  & (sdf["Status"] == "Future")]["Quantity"].sum())
        stock   = inward - sold
        stock_rows.append({
            "size": int(size), "stock": stock,
            "pending_out": pending, "future_in": future,
            "price_per_unit": round(get_price(size), 2),
            "stock_value": round(calc_value(size, stock), 2),
        })

    # Pending by buyer
    pend_df = df[(df["Type"] == "Outgoing") & (df["Pending"] == True)]
    pending_by_buyer = {}
    for buyer in pend_df["Remarks"].dropna().unique():
        bdf = pend_df[pend_df["Remarks"] == buyer]
        pending_by_buyer[str(buyer)] = [
            {
                "size": int(r["Size (mm)"]), "qty": int(r["Quantity"]),
                "date": r["Date"].strftime("%Y-%m-%d") if pd.notna(r["Date"]) else "?",
                "value": round(calc_value(r["Size (mm)"], r["Quantity"]), 2),
            }
            for _, r in bdf.iterrows()
        ]

    # Future incoming
    fut_df = df[(df["Type"] == "Inward") & (df["Status"] == "Future")].sort_values("Date")
    future_incoming = [
        {
            "size": int(r["Size (mm)"]), "qty": int(r["Quantity"]),
            "date": r["Date"].strftime("%Y-%m-%d") if pd.notna(r["Date"]) else "?",
            "supplier": str(r["Remarks"]),
            "value": round(calc_value(r["Size (mm)"], r["Quantity"]), 2),
        }
        for _, r in fut_df.iterrows() if pd.notna(r["Size (mm)"])
    ]

    # Recent 30 days
    cutoff = datetime.now() - timedelta(days=30)
    recent = df[df["Date"] >= cutoff].sort_values("Date", ascending=False)
    recent_txns = [
        {
            "date": r["Date"].strftime("%Y-%m-%d"),
            "type": r["Type"], "size": int(r["Size (mm)"]),
            "qty": int(r["Quantity"]), "party": str(r["Remarks"]),
            "status": r["Status"], "pending": bool(r["Pending"]),
        }
        for _, r in recent.iterrows() if pd.notna(r["Size (mm)"])
    ]

    # All-time transaction history (last 100 for context)
    all_txns = df.sort_values("Date", ascending=False).head(100)
    all_txns_list = [
        {
            "date": r["Date"].strftime("%Y-%m-%d") if pd.notna(r["Date"]) else "?",
            "type": r["Type"], "size": int(r["Size (mm)"]) if pd.notna(r["Size (mm)"]) else 0,
            "qty": int(r["Quantity"]) if pd.notna(r["Quantity"]) else 0,
            "party": str(r["Remarks"]), "status": r["Status"],
            "pending": bool(r["Pending"]),
        }
        for _, r in all_txns.iterrows()
    ]

    buyers = sorted(df[df["Type"] == "Outgoing"]["Remarks"].dropna().astype(str).unique().tolist())

    return {
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "stock": stock_rows,
        "pending_by_buyer": pending_by_buyer,
        "future_incoming": future_incoming,
        "recent_30d": recent_txns,
        "all_transactions_last100": all_txns_list,
        "buyers": buyers,
        "fixed_prices": {str(k): v for k, v in st.session_state.fixed_prices.items()},
        "base_rate_per_mm": st.session_state.base_rate_per_mm,
        "total_transactions": len(df),
    }


def _build_system_prompt(ctx: dict) -> str:
    return f"""You are an expert AI inventory assistant for a rotor manufacturing/trading company.
You have complete, real-time access to the inventory data below.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INVENTORY SNAPSHOT  ({ctx.get('as_of','')})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CURRENT STOCK (by size):
{json.dumps(ctx.get('stock', []), indent=2)}

PENDING ORDERS (by buyer):
{json.dumps(ctx.get('pending_by_buyer', {}), indent=2)}

FUTURE INCOMING ROTORS:
{json.dumps(ctx.get('future_incoming', []), indent=2)}

RECENT TRANSACTIONS (last 30 days):
{json.dumps(ctx.get('recent_30d', []), indent=2)}

LAST 100 TRANSACTIONS (newest first):
{json.dumps(ctx.get('all_transactions_last100', []), indent=2)}

ALL BUYERS: {ctx.get('buyers', [])}
TOTAL TRANSACTIONS IN SYSTEM: {ctx.get('total_transactions', 0)}

PRICING:
  Fixed prices (₹/rotor): {ctx.get('fixed_prices', {})}
  Base rate for other sizes: ₹{ctx.get('base_rate_per_mm', 4.15)}/mm × size

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INSTRUCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Base every answer strictly on the data above.
2. When asked about a buyer, search both 'pending_by_buyer' and transaction history.
3. Always show ₹ values when relevant.  Use commas for thousands: ₹1,23,000
4. For stock alerts, flag sizes where stock < 50 AND future_in == 0.
5. For pending orders, show buyer name, size, qty, and value.
6. Show calculations when they add clarity.
7. Keep answers concise but complete.  Use bullet points for lists.
8. Remember the full conversation history — refer back when relevant.
9. If something is not in the data, say "I don't have that information."
10. Never make up numbers or guess — use only the provided data.
"""


def _call_ai_api(user_input: str, system: str) -> str:
    cfg  = st.session_state.ai_config
    prov = AI_PROVIDERS[cfg["provider"]]
    key  = cfg["api_key"]
    model = cfg["model"]

    if prov["format"] == "gemini":
        url = f"{prov['base_url']}{model}:generateContent?key={key}"
        payload = {
            "contents": [{"parts": [{"text": f"{system}\n\n{user_input}"}]}],
            "generationConfig": {"temperature": 0.15, "maxOutputTokens": 1024},
        }
        r = requests.post(url, headers=prov["headers"](key), json=payload, timeout=25)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    else:  # OpenAI-compatible
        messages = [{"role": "system", "content": system}]
        for m in st.session_state.ai_conversation_history[-12:]:
            messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": user_input})
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.15,
            "max_tokens": 1024,
        }
        r = requests.post(prov["base_url"], headers=prov["headers"](key), json=payload, timeout=25)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def _fallback_response(text: str, ctx: dict) -> str:
    """Rule-based response when no AI provider is connected."""
    t      = text.lower()
    stock  = ctx.get("stock", [])
    pend   = ctx.get("pending_by_buyer", {})
    future = ctx.get("future_incoming", [])
    buyers = ctx.get("buyers", [])
    recent = ctx.get("recent_30d", [])

    # ── Stock alerts ──────────────────────────────
    if "alert" in t or ("low" in t and "stock" in t):
        alerts = [r for r in stock if r["stock"] < 50 and r["future_in"] == 0]
        if not alerts:
            return "✅ All sizes have healthy stock levels (none below 50 with no incoming)."
        lines = ["**🚨 Low Stock Alerts (< 50 units, no incoming scheduled):**\n"]
        for r in alerts:
            lines.append(f"- **{r['size']}mm** — {r['stock']} units remaining (₹{r['stock_value']:,.0f})")
        return "\n".join(lines)

    # ── Stock query ───────────────────────────────
    if "stock" in t:
        m = re.search(r'\b(\d{2,4})\b', t)
        if m:
            sz  = int(m.group(1))
            row = next((r for r in stock if r["size"] == sz), None)
            if row:
                avail = row["stock"] - row["pending_out"]
                return (f"**{sz}mm Stock:**\n"
                        f"- Current stock: **{row['stock']}** units\n"
                        f"- Pending outgoing: {row['pending_out']} units\n"
                        f"- Future incoming: {row['future_in']} units\n"
                        f"- Available after pending: **{avail}** units\n"
                        f"- Stock value: ₹{row['stock_value']:,.0f}  (₹{row['price_per_unit']:.0f}/unit)")
            return f"No stock data found for {sz}mm."
        if not stock:
            return "No stock data available."
        lines = ["**📦 Current Stock Levels:**\n"]
        total = 0
        for r in sorted(stock, key=lambda x: -x["stock"]):
            if r["stock"] > 0:
                tag = f" ⏳ {r['pending_out']} pending" if r["pending_out"] else ""
                lines.append(f"- **{r['size']}mm**: {r['stock']} units (₹{r['stock_value']:,.0f}){tag}")
                total += r["stock"]
        lines.append(f"\n**Total: {total} units**")
        return "\n".join(lines)

    # ── Pending ───────────────────────────────────
    if "pending" in t:
        if not pend:
            return "✅ No pending orders at the moment."
        for buyer in buyers:
            if buyer.lower() in t:
                orders = pend.get(buyer, [])
                if not orders:
                    return f"No pending orders for {buyer}."
                total = sum(o["qty"] for o in orders)
                total_val = sum(o.get("value", 0) for o in orders)
                lines = [f"**⏳ Pending for {buyer}:**\n"]
                for o in orders:
                    lines.append(f"- {o['size']}mm × {o['qty']} units = ₹{o.get('value',0):,.0f} (date: {o['date']})")
                lines.append(f"\n**Total: {total} units | ₹{total_val:,.0f}**")
                return "\n".join(lines)
        # All pending
        lines = ["**⏳ All Pending Orders:**\n"]
        grand_qty = 0; grand_val = 0
        for buyer, orders in pend.items():
            qty = sum(o["qty"] for o in orders)
            val = sum(o.get("value", 0) for o in orders)
            grand_qty += qty; grand_val += val
            lines.append(f"**{buyer}** — {qty} units (₹{val:,.0f})")
            for o in orders:
                lines.append(f"  • {o['size']}mm × {o['qty']} units")
        lines.append(f"\n**Grand Total: {grand_qty} units | ₹{grand_val:,.0f}**")
        return "\n".join(lines)

    # ── Future / coming ───────────────────────────
    if any(w in t for w in ["coming", "future", "incoming", "expected", "arriving"]):
        if not future:
            return "No future incoming rotors currently scheduled."
        lines = ["**📅 Future Incoming Rotors:**\n"]
        total_qty = 0; total_val = 0
        for r in future:
            lines.append(f"- **{r['date']}** — {r['size']}mm × {r['qty']} units"
                         f" from {r['supplier']} (₹{r.get('value',0):,.0f})")
            total_qty += r["qty"]; total_val += r.get("value", 0)
        lines.append(f"\n**Total: {total_qty} units | ₹{total_val:,.0f}**")
        return "\n".join(lines)

    # ── Recent transactions ───────────────────────
    if any(w in t for w in ["recent", "latest", "last"]):
        if not recent:
            return "No transactions in the last 30 days."
        incoming = [r for r in recent if r["type"] == "Inward"]
        outgoing = [r for r in recent if r["type"] == "Outgoing"]
        lines = ["**📊 Recent Transactions (last 30 days):**\n"]
        if incoming:
            lines.append(f"**📥 Incoming ({len(incoming)} entries):**")
            for r in incoming[:10]:
                lines.append(f"  • {r['date']}: {r['size']}mm × {r['qty']} from {r['party']}")
        if outgoing:
            lines.append(f"\n**📤 Outgoing ({len(outgoing)} entries):**")
            for r in outgoing[:10]:
                pend_tag = " ⏳" if r["pending"] else ""
                lines.append(f"  • {r['date']}: {r['size']}mm × {r['qty']} to {r['party']}{pend_tag}")
        return "\n".join(lines)

    # ── Buyers ────────────────────────────────────
    if any(w in t for w in ["buyer", "customer", "client", "who"]):
        if not buyers:
            return "No buyer data found."
        return "**👥 All Buyers:**\n" + "\n".join(f"- {b}" for b in buyers)

    # ── Summary / overview ────────────────────────
    if any(w in t for w in ["summary", "overview", "total"]):
        total_stock = sum(r["stock"] for r in stock)
        total_val   = sum(r["stock_value"] for r in stock)
        total_pend  = sum(sum(o["qty"] for o in orders) for orders in pend.values())
        total_fut   = sum(r["qty"] for r in future)
        return (f"**📊 Inventory Overview:**\n\n"
                f"- **Total stock**: {total_stock} units  (₹{total_val:,.0f})\n"
                f"- **Pending orders**: {total_pend} units across {len(pend)} buyers\n"
                f"- **Future incoming**: {total_fut} units in {len(future)} shipments\n"
                f"- **Sizes tracked**: {len(stock)}\n"
                f"- **Total buyers**: {len(buyers)}\n"
                f"- **Total transactions**: {ctx.get('total_transactions', 0)}")

    # ── Specific size (catch-all) ─────────────────
    m = re.search(r'\b(\d{2,4})\b', t)
    if m:
        sz  = int(m.group(1))
        row = next((r for r in stock if r["size"] == sz), None)
        if row:
            return (f"**{sz}mm:**\n"
                    f"- Stock: {row['stock']} units (₹{row['stock_value']:,.0f})\n"
                    f"- Pending: {row['pending_out']} | Incoming: {row['future_in']}\n"
                    f"- Price: ₹{row['price_per_unit']:.0f}/unit")

    # ── Help ──────────────────────────────────────
    return (
        "**🤖 What I can help with:**\n\n"
        "- `stock` — all current stock levels\n"
        "- `stock 1803` — stock for a specific size\n"
        "- `pending` — all pending orders\n"
        "- `pending [buyer name]` — buyer-specific pending\n"
        "- `coming` / `future` — upcoming shipments\n"
        "- `recent` — last 30 days of activity\n"
        "- `low stock` — at-risk sizes\n"
        "- `buyers` — list all buyers\n"
        "- `summary` — overall overview\n\n"
        "💡 Connect an AI provider in the settings above for full natural language queries!"
    )


def get_ai_response(user_input: str) -> str:
    """Main entry point: returns AI or fallback response."""
    ctx = build_inventory_context()

    if st.session_state.ai_config.get("initialized"):
        try:
            system   = _build_system_prompt(ctx)
            response = _call_ai_api(user_input, system)
            # Update conversation history
            st.session_state.ai_conversation_history.append(
                {"role": "user", "content": user_input}
            )
            st.session_state.ai_conversation_history.append(
                {"role": "assistant", "content": response}
            )
            # Cap history at 60 turns
            if len(st.session_state.ai_conversation_history) > 120:
                st.session_state.ai_conversation_history = \
                    st.session_state.ai_conversation_history[-120:]
            return response
        except Exception as e:
            err_msg = str(e)
            fallback = _fallback_response(user_input, ctx)
            return f"⚠️ AI error: {err_msg}\n\nFallback answer:\n\n{fallback}"

    return _fallback_response(user_input, ctx)


# ══════════════════════════════════════════════
# 8. LOGO
# ══════════════════════════════════════════════
def display_logo():
    try:
        url = "https://ik.imagekit.io/zmv7kjha8x/D936A070-DB06-4439-B642-854E6510A701.PNG?updatedAt=1752629786861"
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        st.image(Image.open(io.BytesIO(r.content)), width=200)
    except Exception:
        st.title("Rotor Tracker")

display_logo()

# ══════════════════════════════════════════════
# 9. SYNC CONTROLS
# ══════════════════════════════════════════════
if st.session_state.last_sync == "Never":
    load_from_gsheet()

col_sync, col_status = st.columns([2, 8])
with col_sync:
    if st.button("🔄 Sync Now"):
        load_from_gsheet()
with col_status:
    st.caption(f"Last sync: {st.session_state.last_sync}")

# ══════════════════════════════════════════════
# 10. SIDEBAR NAVIGATION
# ══════════════════════════════════════════════
tab_choice = st.sidebar.radio(
    "📊 Choose Tab",
    ["🔁 Rotor Tracker", "🧰 Clitting + Laminations + Stators", "📄 Invoices"],
)

# ══════════════════════════════════════════════
# 11. ROTOR TRACKER TAB
# ══════════════════════════════════════════════
if tab_choice == "🔁 Rotor Tracker":
    st.title("🔁 Rotor Tracker")

    # ── Helper ────────────────────────────────
    def add_rotor_entry(data_dict: dict):
        data_dict["ID"] = str(uuid4())
        new = pd.DataFrame([data_dict])
        st.session_state.data = pd.concat(
            [st.session_state.data, new], ignore_index=True
        )
        auto_save_to_gsheet()
        st.rerun()

    # ── Entry forms ───────────────────────────
    form_tabs = st.tabs(["📥 Current Movement", "📅 Coming Rotors", "⏳ Pending Rotors"])

    with form_tabs[0]:
        st.subheader("📥 Add Rotor Movement")
        with st.form("current_form"):
            c1, c2 = st.columns(2)
            with c1:
                date        = st.date_input("📅 Date", value=datetime.today())
                rotor_size  = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1)
            with c2:
                entry_type  = st.selectbox("🔄 Type", ["Inward", "Outgoing"])
                quantity    = st.number_input("🔢 Quantity", min_value=1, step=1)
            remarks = st.text_input("📝 Remarks")
            submit_form = st.form_submit_button("📋 Preview Entry")

        if submit_form:
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
            st.session_state.new_entry = new_entry
            st.session_state.conflict_resolved = True
            st.session_state.action_required   = False

            # Check for future matches on blank-remarks Inward
            if entry_type == "Inward" and remarks.strip() == "":
                matches = df[
                    (df["Type"] == "Inward") &
                    (df["Size (mm)"] == int(rotor_size)) &
                    (df["Remarks"].astype(str).str.strip() == "") &
                    (df["Status"].str.lower() == "future")
                ].sort_values("Date")
                if not matches.empty:
                    st.warning("⚠ Matching future rotor(s) found.")
                    st.session_state.conflict_resolved = False
                    st.session_state.action_required   = True
                    st.session_state.future_matches    = matches

        # Conflict resolution UI
        if st.session_state.action_required and not st.session_state.conflict_resolved:
            matches = st.session_state.future_matches
            if matches is not None and not matches.empty:
                st.dataframe(matches[["Date", "Quantity", "Status"]], use_container_width=True)
                selected = st.selectbox(
                    "Select a future entry to act on:",
                    options=matches.index,
                    format_func=lambda i: f"{matches.at[i,'Date']} → Qty: {matches.at[i,'Quantity']}",
                )
                st.session_state.selected_idx = selected
                c1, c2, c3 = st.columns(3)
                if c1.button("🗑 Delete Selected"):
                    st.session_state.data = st.session_state.data.drop(selected)
                    st.session_state.conflict_resolved = True
                    st.session_state.action_required   = False
                    st.success("Deleted. Please Save!")
                if c2.button("➖ Deduct from Selected"):
                    qty_new = st.session_state.new_entry["Quantity"]
                    qty_fut = int(st.session_state.data.at[selected, "Quantity"])
                    if qty_new >= qty_fut:
                        st.session_state.data = st.session_state.data.drop(selected)
                    else:
                        st.session_state.data.at[selected, "Quantity"] = qty_fut - qty_new
                    st.session_state.conflict_resolved = True
                    st.session_state.action_required   = False
                    st.success("Deducted. Please Save!")
                if c3.button("Do Nothing"):
                    st.session_state.conflict_resolved = True
                    st.session_state.action_required   = False
                    st.success("No changes made. Please Save!")

        # Save button
        if (st.session_state.conflict_resolved
                and st.session_state.new_entry is not None):
            if st.button("💾 Save Entry"):
                with st.spinner("Saving…"):
                    df        = st.session_state.data.copy()
                    new_entry = st.session_state.new_entry

                    # Deduct pending if Outgoing with buyer name
                    if new_entry["Type"] == "Outgoing" and new_entry["Remarks"]:
                        buyer_kw = new_entry["Remarks"].lower()
                        size     = new_entry["Size (mm)"]
                        qty_left = new_entry["Quantity"]
                        pend_rows = df[
                            (df["Size (mm)"] == size) &
                            (df["Remarks"].str.lower().str.contains(buyer_kw, na=False)) &
                            (df["Pending"] == True) &
                            (df["Status"] == "Current")
                        ].sort_values("Date")
                        for idx, row in pend_rows.iterrows():
                            if qty_left <= 0:
                                break
                            p_qty = int(row["Quantity"])
                            if qty_left >= p_qty:
                                df.at[idx, "Quantity"] = 0
                                df.at[idx, "Pending"]  = False
                                qty_left -= p_qty
                            else:
                                df.at[idx, "Quantity"] = p_qty - qty_left
                                qty_left = 0
                        df = df[df["Quantity"] > 0]

                    df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
                    df["Date"] = df["Date"].astype(str)
                    st.session_state.data = df.reset_index(drop=True)
                    auto_save_to_gsheet()
                    st.success("✅ Entry saved.")
                    # Reset flow
                    for k in ("new_entry", "future_matches", "selected_idx"):
                        st.session_state[k] = None
                    st.session_state.conflict_resolved = False
                    st.session_state.action_required   = False
                    st.rerun()

    with form_tabs[1]:
        with st.form("future_form"):
            c1, c2 = st.columns(2)
            with c1:
                future_date = st.date_input(
                    "📅 Expected Date",
                    min_value=datetime.today() + timedelta(days=1),
                )
                future_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, key="f_size")
            with c2:
                future_qty     = st.number_input("🔢 Quantity", min_value=1, step=1, key="f_qty")
                future_remarks = st.text_input("📝 Remarks", key="f_rem")
            if st.form_submit_button("➕ Add Coming Rotors"):
                add_rotor_entry({
                    "Date": future_date.strftime("%Y-%m-%d"),
                    "Size (mm)": int(future_size),
                    "Type": "Inward",
                    "Quantity": int(future_qty),
                    "Remarks": future_remarks,
                    "Status": "Future",
                    "Pending": False,
                })

    with form_tabs[2]:
        with st.form("pending_form"):
            c1, c2 = st.columns(2)
            with c1:
                pend_date = st.date_input("📅 Date", value=datetime.today(), key="p_date")
                pend_size = st.number_input("📐 Rotor Size (mm)", min_value=1, step=1, key="p_size")
            with c2:
                pend_qty     = st.number_input("🔢 Quantity", min_value=1, step=1, key="p_qty")
                pend_remarks = st.text_input("📝 Remarks", key="p_rem")
            if st.form_submit_button("➕ Add Pending Rotors"):
                add_rotor_entry({
                    "Date": pend_date.strftime("%Y-%m-%d"),
                    "Size (mm)": int(pend_size),
                    "Type": "Outgoing",
                    "Quantity": int(pend_qty),
                    "Remarks": pend_remarks,
                    "Status": "Current",
                    "Pending": True,
                })

    # ── Main tabs ─────────────────────────────
    main_tabs = st.tabs(["📊 Stock Summary", "📋 Movement Log", "🤖 AI Assistant"])

    # ── TAB 0: Stock Summary ──────────────────
    with main_tabs[0]:
        st.subheader("📊 Current Stock Summary")
        if not st.session_state.data.empty:
            try:
                df = normalize_pending(st.session_state.data.copy())
                current = df[(df["Status"] == "Current") & (~df["Pending"])].copy()
                current["Net"] = current.apply(
                    lambda r: r["Quantity"] if r["Type"] == "Inward" else -r["Quantity"], axis=1
                )
                stock_sum = current.groupby("Size (mm)")["Net"].sum().reset_index()
                stock_sum = stock_sum[stock_sum["Net"] != 0]

                future_df  = df[df["Status"] == "Future"]
                coming     = future_df.groupby("Size (mm)")["Quantity"].sum().reset_index()
                pend_df    = df[(df["Status"] == "Current") & df["Pending"]]
                pend_sum   = pend_df.groupby("Size (mm)")["Quantity"].sum().reset_index()

                combined = (stock_sum
                    .merge(coming,   on="Size (mm)", how="outer")
                    .merge(pend_sum, on="Size (mm)", how="outer", suffixes=("", "_pending"))
                    .fillna(0))
                combined.columns = ["Size (mm)", "Current Stock", "Coming Rotors", "Pending Rotors"]
                st.dataframe(combined, use_container_width=True, hide_index=True)

            except Exception as e:
                st.error(f"Error generating summary: {e}")
        else:
            st.info("No data yet.")

        # Stock alerts
        st.subheader("🚨 Stock Risk Alerts")
        if not st.session_state.data.empty:
            df = normalize_pending(st.session_state.data.copy())
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

            cur = df[(df["Status"] == "Current") & (~df["Pending"])].copy()
            cur["Net"] = cur.apply(
                lambda r: r["Quantity"] if r["Type"] == "Inward" else -r["Quantity"], axis=1
            )
            stk = cur.groupby("Size (mm)")["Net"].sum().reset_index().rename(columns={"Net": "Stock"})
            pnd = (df[(df["Pending"] == True) & (df["Status"] == "Current")]
                   .groupby("Size (mm)")["Quantity"].sum().reset_index()
                   .rename(columns={"Quantity": "Pending Out"}))
            fut = (df[(df["Status"] == "Future") & (df["Type"] == "Inward")]
                   .groupby("Size (mm)")["Quantity"].sum().reset_index()
                   .rename(columns={"Quantity": "Coming In"}))

            merged = (stk.merge(pnd, on="Size (mm)", how="outer")
                         .merge(fut, on="Size (mm)", how="outer")
                         .fillna(0))
            for c in ["Stock", "Pending Out", "Coming In"]:
                merged[c] = merged[c].astype(int)

            low  = merged[(merged["Stock"] < 100) & (merged["Coming In"] == 0)]
            risky = merged[merged["Pending Out"] > (merged["Stock"] + merged["Coming In"])]

            if not low.empty:
                st.warning("🟠 Low stock (< 100) with no incoming:")
                st.dataframe(low[["Size (mm)", "Stock"]], use_container_width=True, hide_index=True)
            else:
                st.success("✅ No low stock issues.")

            if not risky.empty:
                st.error("🔴 Pending exceeds available + incoming:")
                st.dataframe(risky[["Size (mm)", "Stock", "Coming In", "Pending Out"]],
                             use_container_width=True, hide_index=True)
            else:
                st.success("✅ All pending can be fulfilled.")

    # ── TAB 1: Movement Log ───────────────────
    with main_tabs[1]:
        st.subheader("📋 Movement Log")
        if st.session_state.data.empty:
            st.info("No entries yet.")
        else:
            df = st.session_state.data.copy()
            st.markdown("### 🔍 Filters")

            for k, v in [("sf","All"),("zf",[]),("pf","All"),("tf","All"),("rs","")]:
                if k not in st.session_state:
                    st.session_state[k] = v
            if "dr" not in st.session_state:
                max_d = pd.to_datetime(df["Date"]).max().date()
                min_d = pd.to_datetime(df["Date"]).min().date()
                st.session_state.dr = [min_d, max_d]

            if st.button("🔄 Reset Filters"):
                st.session_state.sf = "All"
                st.session_state.zf = []
                st.session_state.pf = "All"
                st.session_state.tf = "All"
                st.session_state.rs = ""
                max_d = pd.to_datetime(df["Date"]).max().date()
                min_d = pd.to_datetime(df["Date"]).min().date()
                st.session_state.dr = [min_d, max_d]
                st.rerun()

            c1, c2, c3, c4 = st.columns(4)
            with c1: status_f  = st.selectbox("Status",  ["All","Current","Future"], key="sf")
            with c2: size_f    = st.multiselect("Size (mm)", sorted(df["Size (mm)"].dropna().unique()), key="zf")
            with c3: pending_f = st.selectbox("Pending", ["All","Yes","No"], key="pf")
            with c4: type_f    = st.selectbox("Type",    ["All","Inward","Outgoing"], key="tf")
            remark_s   = st.text_input("Search Remarks", key="rs")
            date_range = st.date_input("Date Range", key="dr")

            try:
                fdf = df.copy()
                if status_f  != "All":     fdf = fdf[fdf["Status"] == status_f]
                if pending_f == "Yes":     fdf = fdf[fdf["Pending"] == True]
                elif pending_f == "No":    fdf = fdf[fdf["Pending"] == False]
                if size_f:                 fdf = fdf[fdf["Size (mm)"].isin(size_f)]
                if remark_s:               fdf = fdf[fdf["Remarks"].astype(str).str.contains(remark_s, case=False, na=False)]
                if type_f   != "All":      fdf = fdf[fdf["Type"] == type_f]
                if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
                    s, e = date_range
                    fdf = fdf[
                        (pd.to_datetime(fdf["Date"]) >= pd.to_datetime(s)) &
                        (pd.to_datetime(fdf["Date"]) <= pd.to_datetime(e))
                    ]
            except Exception as ex:
                st.error(f"Filter error: {ex}")
                fdf = st.session_state.data.copy()

            fdf = fdf.reset_index(drop=True)
            st.markdown(f"**{len(fdf)} entries**")

            for _, row in fdf.iterrows():
                entry_id = row["ID"]
                match    = st.session_state.data[st.session_state.data["ID"] == entry_id]
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
                        st.session_state.data = st.session_state.data[
                            st.session_state.data["ID"] != entry_id
                        ]
                        auto_save_to_gsheet()
                        st.rerun()

                if st.session_state.editing == match_idx:
                    er = st.session_state.data.loc[match_idx]
                    with st.form(f"edit_form_{entry_id}"):
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            e_date = st.date_input("Date", pd.to_datetime(er["Date"]), key=f"ed_{entry_id}")
                            e_size = st.number_input("Size (mm)", min_value=1, value=int(er["Size (mm)"]), key=f"es_{entry_id}")
                        with ec2:
                            e_type = st.selectbox("Type", ["Inward","Outgoing"],
                                                  index=0 if er["Type"]=="Inward" else 1, key=f"et_{entry_id}")
                            e_qty  = st.number_input("Quantity", min_value=1, value=int(er["Quantity"]), key=f"eq_{entry_id}")
                        e_rem     = st.text_input("Remarks", value=er["Remarks"], key=f"er_{entry_id}")
                        e_status  = st.selectbox("Status", ["Current","Future"],
                                                 index=0 if er["Status"]=="Current" else 1, key=f"est_{entry_id}")
                        e_pending = st.checkbox("Pending", value=er["Pending"], key=f"ep_{entry_id}")
                        sc, cc    = st.columns(2)
                        with sc: submitted = st.form_submit_button("💾 Save", type="primary")
                        with cc: cancelled = st.form_submit_button("❌ Cancel")
                        if submitted:
                            for col, val in [
                                ("Date", e_date.strftime("%Y-%m-%d")),
                                ("Size (mm)", e_size), ("Type", e_type), ("Quantity", e_qty),
                                ("Remarks", e_rem), ("Status", e_status), ("Pending", e_pending),
                            ]:
                                st.session_state.data.at[match_idx, col] = val
                            st.session_state.editing = None
                            auto_save_to_gsheet()
                            st.rerun()
                        if cancelled:
                            st.session_state.editing = None
                            st.rerun()

    # ── TAB 2: AI Assistant ───────────────────
    with main_tabs[2]:
        st.subheader("🤖 AI Inventory Assistant")

        # Connection settings
        cfg = st.session_state.ai_config
        connected = cfg.get("initialized", False)
        provider_name = cfg.get("provider", "Sarvam AI")
        model_name    = cfg.get("model", "sarvam-m")

        if connected:
            st.success(f"✅ Connected — {provider_name} / {model_name}")
        else:
            st.warning("⚠️ No AI provider connected — using smart fallback mode.")

        with st.expander("🔌 AI Provider Settings", expanded=not connected):
            prov_sel  = st.selectbox("Provider", list(AI_PROVIDERS.keys()),
                                     index=list(AI_PROVIDERS.keys()).index(provider_name)
                                     if provider_name in AI_PROVIDERS else 0,
                                     key="ai_prov_sel")
            model_sel = st.selectbox("Model", AI_PROVIDERS[prov_sel]["models"],
                                     key="ai_model_sel")
            key_input = st.text_input("API Key", type="password",
                                      value=cfg.get("api_key",""), key="ai_key_in")
            ca, cb = st.columns(2)
            with ca:
                if st.button("🔄 Connect / Update"):
                    if key_input:
                        st.session_state.ai_config.update({
                            "provider": prov_sel, "model": model_sel,
                            "api_key": key_input, "initialized": True,
                        })
                        st.success("✅ Connected!")
                        st.rerun()
                    else:
                        st.warning("Please enter an API key.")
            with cb:
                if st.button("❌ Disconnect"):
                    st.session_state.ai_config["initialized"] = False
                    st.info("Disconnected.")
                    st.rerun()

        st.divider()

        # Quick action buttons
        qa_cols = st.columns(6)
        quick_actions = [
            ("📦 Stock",    "Show current stock levels for all sizes"),
            ("⏳ Pending",  "Show all pending orders with buyer details"),
            ("📅 Coming",   "Show all future incoming rotors"),
            ("📉 Alerts",   "Show low stock alerts"),
            ("📤 Recent",   "Show latest transactions from last 30 days"),
            ("📊 Summary",  "Give me a full inventory overview"),
        ]
        for col, (label, query) in zip(qa_cols, quick_actions):
            if col.button(label, use_container_width=True):
                st.session_state.ai_chat_messages.append({"role":"user","content":query})
                with st.spinner("Thinking…"):
                    resp = get_ai_response(query)
                st.session_state.ai_chat_messages.append({"role":"assistant","content":resp})
                st.rerun()

        # Chat history display
        chat_container = st.container(height=420, border=True)
        with chat_container:
            for msg in st.session_state.ai_chat_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        # Chat input
        user_input = st.chat_input("Ask anything about your inventory…")
        if user_input:
            st.session_state.ai_chat_messages.append({"role":"user","content":user_input})
            with st.spinner("Thinking…"):
                resp = get_ai_response(user_input)
            st.session_state.ai_chat_messages.append({"role":"assistant","content":resp})
            st.rerun()

        # Clear chat
        if st.button("🗑️ Clear Chat"):
            st.session_state.ai_chat_messages = [
                {"role":"assistant","content":"Chat cleared! I still know everything about your inventory. Ask away!"}
            ]
            st.session_state.ai_conversation_history = []
            st.rerun()

# ══════════════════════════════════════════════
# 12. CLITTING + LAMINATIONS + STATORS TAB
# ══════════════════════════════════════════════
elif tab_choice == "🧰 Clitting + Laminations + Stators":
    st.title("🧰 Clitting + Laminations + Stator Outgoings")

    # Load from sheets on first visit
    if st.session_state.clitting_data.empty:
        st.session_state.clitting_data = _load_ws("Clitting", st.session_state.clitting_data.columns)
    if st.session_state.lamination_v3.empty:
        st.session_state.lamination_v3 = _load_ws("V3 Laminations", st.session_state.lamination_v3.columns)
    if st.session_state.lamination_v4.empty:
        st.session_state.lamination_v4 = _load_ws("V4 Laminations", st.session_state.lamination_v4.columns)
    if st.session_state.stator_data.empty:
        st.session_state.stator_data = _load_ws("Stator Usage", st.session_state.stator_data.columns)

    cls_tab1, cls_tab2, cls_tab3, cls_tab4 = st.tabs(
        ["📥 Clitting", "🧩 Laminations", "📤 Stator Outgoings", "📊 Summary"]
    )

    # ── Clitting ──────────────────────────────
    with cls_tab1:
        st.subheader("📥 Clitting Inward")
        with st.form("clitting_form"):
            c_date    = st.date_input("📅 Date", datetime.today())
            c_size    = st.number_input("📏 Stator Size (mm)", min_value=1, step=1)
            c_bags    = st.number_input("🧮 Bags", min_value=1, step=1)
            c_weight  = st.number_input("⚖ Weight per Bag (kg)", value=25.0, step=0.5)
            c_remarks = st.text_input("📝 Remarks")
            if st.form_submit_button("➕ Add Clitting"):
                entry = {
                    "Date": c_date.strftime("%Y-%m-%d"), "Size (mm)": int(c_size),
                    "Bags": int(c_bags), "Weight per Bag (kg)": float(c_weight),
                    "Remarks": c_remarks.strip(), "ID": str(uuid4()),
                }
                st.session_state.clitting_data = pd.concat(
                    [st.session_state.clitting_data, pd.DataFrame([entry])], ignore_index=True
                )
                save_clitting()
                st.success("✅ Clitting entry added.")

        st.subheader("📄 Clitting Log")
        for idx, row in st.session_state.clitting_data.iterrows():
            with st.expander(f"{row['Date']} | {row['Size (mm)']}mm | {row['Bags']} bags"):
                c1, c2 = st.columns([1, 2])
                with c1:
                    if st.button("🗑 Delete", key=f"del_clit_{row['ID']}"):
                        st.session_state.clitting_data = (
                            st.session_state.clitting_data[
                                st.session_state.clitting_data["ID"] != row["ID"]
                            ].reset_index(drop=True)
                        )
                        save_clitting()
                        st.rerun()
                with c2:
                    nb = st.number_input("Bags",         value=int(row["Bags"]),                key=f"eb_{row['ID']}")
                    nw = st.number_input("Weight/Bag",   value=float(row["Weight per Bag (kg)"]), key=f"ew_{row['ID']}")
                    nr = st.text_input("Remarks",        value=row["Remarks"],                  key=f"er_{row['ID']}")
                    if st.button("💾 Save", key=f"sc_{row['ID']}"):
                        st.session_state.clitting_data.at[idx, "Bags"]              = nb
                        st.session_state.clitting_data.at[idx, "Weight per Bag (kg)"] = nw
                        st.session_state.clitting_data.at[idx, "Remarks"]           = nr
                        save_clitting()
                        st.success("✅ Updated.")

    # ── Laminations ───────────────────────────
    with cls_tab2:
        st.subheader("📥 Laminations Inward (V3 / V4)")
        with st.form("lamination_form"):
            l_date = st.date_input("📅 Date", datetime.today(), key="ld")
            l_type = st.selectbox("🔀 Type", ["V3", "V4"])
            l_qty  = st.number_input("🔢 Quantity", min_value=1, step=1)
            l_rem  = st.text_input("📝 Remarks", key="lr")
            if st.form_submit_button("➕ Add Laminations"):
                entry   = {"Date": l_date.strftime("%Y-%m-%d"), "Quantity": int(l_qty),
                           "Remarks": l_rem.strip(), "ID": str(uuid4())}
                lam_key = "lamination_v3" if l_type == "V3" else "lamination_v4"
                st.session_state[lam_key] = pd.concat(
                    [st.session_state[lam_key], pd.DataFrame([entry])], ignore_index=True
                )
                save_lam(l_type)
                st.success(f"✅ {l_type} Lamination added.")

        for lam_type in ["V3", "V4"]:
            lam_key = "lamination_v3" if lam_type == "V3" else "lamination_v4"
            ldf     = st.session_state[lam_key].copy()
            st.markdown(f"### 📄 {lam_type} Log")
            for idx, row in ldf.iterrows():
                with st.expander(f"{row['Date']} | Qty: {row['Quantity']}"):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        if st.button("🗑", key=f"dl_{lam_type}_{row['ID']}"):
                            st.session_state[lam_key] = (
                                ldf[ldf["ID"] != row["ID"]].reset_index(drop=True)
                            )
                            save_lam(lam_type)
                            st.rerun()
                    with c2:
                        nq = st.number_input("Qty",     value=int(row["Quantity"]), key=f"lq_{row['ID']}")
                        nm = st.text_input("Remarks",   value=row["Remarks"],       key=f"lm_{row['ID']}")
                        if st.button("💾 Save", key=f"sl_{row['ID']}"):
                            st.session_state[lam_key].at[idx, "Quantity"] = nq
                            st.session_state[lam_key].at[idx, "Remarks"]  = nm
                            save_lam(lam_type)
                            st.success("✅ Updated.")

    # ── Stator Outgoings ──────────────────────
    with cls_tab3:
        st.subheader("📤 Stator Outgoings")
        with st.form("stator_form"):
            s_date = st.date_input("📅 Date", datetime.today(), key="sd")
            s_size = st.number_input("📏 Stator Size (mm)", min_value=1, step=1, key="ss")
            s_qty  = st.number_input("🔢 Quantity", min_value=1, step=1, key="sq")
            s_type = st.selectbox("🔀 Lamination Type", ["V3", "V4"], key="st_type")
            s_rem  = st.text_input("📝 Remarks", key="sr")

            if st.form_submit_button("📋 Log Stator Outgoing"):
                size_key       = int(s_size)
                clitting_used  = CLITTING_USAGE.get(size_key, 0) * int(s_qty)
                laminations_used = int(s_qty) * 2

                # Check clitting stock
                clit_stock = 0
                for _, r in st.session_state.clitting_data.iterrows():
                    if int(r["Size (mm)"]) == size_key:
                        clit_stock += int(r["Bags"]) * float(r["Weight per Bag (kg)"])
                for _, r in st.session_state.stator_data.iterrows():
                    if int(r["Size (mm)"]) == size_key:
                        clit_stock -= float(r.get("Estimated Clitting (kg)", 0) or 0)
                if clit_stock < clitting_used:
                    st.warning(
                        f"⚠ Clitting shortage for {size_key}mm: "
                        f"stock {clit_stock:.2f} kg, need {clitting_used:.2f} kg"
                    )

                # Check lamination stock
                lam_key  = "lamination_v3" if s_type == "V3" else "lamination_v4"
                lam_stk  = pd.to_numeric(st.session_state[lam_key]["Quantity"], errors="coerce").sum()
                if lam_stk < laminations_used:
                    st.warning(
                        f"⚠ {s_type} lamination shortage: stock {lam_stk}, need {laminations_used}"
                    )

                # Save stator entry regardless
                new_s = {
                    "Date": s_date.strftime("%Y-%m-%d"), "Size (mm)": size_key,
                    "Quantity": int(s_qty), "Remarks": s_rem.strip(),
                    "Estimated Clitting (kg)": round(clitting_used, 2),
                    "Laminations Used": laminations_used,
                    "Lamination Type": s_type, "ID": str(uuid4()),
                }
                st.session_state.stator_data = pd.concat(
                    [st.session_state.stator_data, pd.DataFrame([new_s])], ignore_index=True
                )
                save_stator()

                # Deduct laminations (FIFO)
                ldf = st.session_state[lam_key].copy()
                need = laminations_used
                for i, r in ldf.iterrows():
                    if need <= 0:
                        break
                    avail = int(r["Quantity"])
                    if need >= avail:
                        need -= avail
                        ldf.at[i, "Quantity"] = 0
                    else:
                        ldf.at[i, "Quantity"] = avail - need
                        need = 0
                st.session_state[lam_key] = ldf[ldf["Quantity"] > 0].reset_index(drop=True)
                save_lam(s_type)
                st.success(
                    f"✅ Stator logged | Clitting: {clitting_used:.2f} kg | "
                    f"Laminations: {laminations_used}"
                )
                st.rerun()

        st.subheader("📄 Stator Usage Log")
        for idx, row in st.session_state.stator_data.iterrows():
            with st.expander(f"{row['Date']} | {row['Size (mm)']}mm | Qty: {row['Quantity']}"):
                c1, c2 = st.columns([1, 2])
                with c1:
                    if st.button("🗑 Delete", key=f"ds_{row['ID']}"):
                        st.session_state.stator_data = (
                            st.session_state.stator_data[
                                st.session_state.stator_data["ID"] != row["ID"]
                            ].reset_index(drop=True)
                        )
                        save_stator()
                        st.rerun()
                with c2:
                    nq = st.number_input("Qty",     value=int(row["Quantity"]), key=f"sq_{row['ID']}")
                    nm = st.text_input("Remarks",   value=row["Remarks"],       key=f"sm_{row['ID']}")
                    if st.button("💾 Save", key=f"ss_{row['ID']}"):
                        st.session_state.stator_data.at[idx, "Quantity"] = nq
                        st.session_state.stator_data.at[idx, "Remarks"]  = nm
                        save_stator()
                        st.success("✅ Updated.")

    # ── Summary ───────────────────────────────
    with cls_tab4:
        st.subheader("📊 Clitting & Lamination Summary")

        # Clitting summary
        st.markdown("#### ⚙️ Clitting Stock by Size")
        if not st.session_state.clitting_data.empty:
            cdf = st.session_state.clitting_data.copy()
            cdf["Total kg"] = pd.to_numeric(cdf["Bags"], errors="coerce") * \
                              pd.to_numeric(cdf["Weight per Bag (kg)"], errors="coerce")
            sdf = st.session_state.stator_data.copy()
            sdf["Estimated Clitting (kg)"] = pd.to_numeric(
                sdf["Estimated Clitting (kg)"], errors="coerce"
            ).fillna(0)
            inward  = cdf.groupby("Size (mm)")["Total kg"].sum().reset_index().rename(columns={"Total kg": "Inward kg"})
            used    = sdf.groupby("Size (mm)")["Estimated Clitting (kg)"].sum().reset_index().rename(
                columns={"Estimated Clitting (kg)": "Used kg"}
            )
            clit_summary = inward.merge(used, on="Size (mm)", how="outer").fillna(0)
            clit_summary["Remaining kg"] = clit_summary["Inward kg"] - clit_summary["Used kg"]
            st.dataframe(clit_summary, use_container_width=True, hide_index=True)
        else:
            st.info("No clitting data.")

        # Lamination totals
        st.markdown("#### 🧩 Lamination Stock")
        v3_qty = pd.to_numeric(st.session_state.lamination_v3["Quantity"], errors="coerce").sum()
        v4_qty = pd.to_numeric(st.session_state.lamination_v4["Quantity"], errors="coerce").sum()
        lam_col1, lam_col2 = st.columns(2)
        lam_col1.metric("V3 Laminations Remaining", int(v3_qty))
        lam_col2.metric("V4 Laminations Remaining", int(v4_qty))

        # Stator summary
        st.markdown("#### 📤 Stator Outgoings by Size")
        if not st.session_state.stator_data.empty:
            sdf = st.session_state.stator_data.copy()
            sdf["Quantity"] = pd.to_numeric(sdf["Quantity"], errors="coerce")
            stat_sum = sdf.groupby("Size (mm)")["Quantity"].sum().reset_index()
            st.dataframe(stat_sum, use_container_width=True, hide_index=True)
        else:
            st.info("No stator data.")

# ══════════════════════════════════════════════
# 13. INVOICES TAB  (placeholder)
# ══════════════════════════════════════════════
elif tab_choice == "📄 Invoices":
    st.title("📄 Invoices")
    st.info("Invoice feature coming soon. This tab will support generating and managing invoices for buyers.")
