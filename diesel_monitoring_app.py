# dg_module_app.py
 
import os
from datetime import datetime
import pandas as pd
import streamlit as st
from supabase import create_client
 
# --------------------- Supabase Connection ---------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
 
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ Missing SUPABASE_URL or SUPABASE_KEY in environment.")
    st.stop()
 
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
 
# --------------------- RH Utilities ---------------------
def parse_rh(rh_str: str):
    """
    Accept 'hh:mm' (or 'h:mm'). Return total minutes (int) or None if invalid.
    """
    try:
        if rh_str is None:
            return None
        s = str(rh_str).strip()
        parts = s.split(":")
        if len(parts) != 2:
            return None
        hours = int(parts[0])
        minutes = int(parts[1])
        if hours < 0 or minutes < 0 or minutes >= 60:
            return None
        return hours * 60 + minutes
    except Exception:
        return None
 
def minutes_to_rh(mins: int):
    hours = mins // 60
    minutes = mins % 60
    return f"{hours}:{minutes:02d}"
 
def calculate_net_rh(opening_rh: str, closing_rh: str):
    open_min = parse_rh(opening_rh)
    close_min = parse_rh(closing_rh)
    if open_min is None or close_min is None:
        return None, "❌ Invalid RH format. Use hh:mm (e.g., 4435:12)."
    if close_min < open_min:
        return None, "❌ Closing RH must be ≥ Opening RH."
    net_min = close_min - open_min
    return minutes_to_rh(net_min), None
 
# --------------------- Helpers ---------------------
PLAZAS = ["TP01", "TP02", "TP03"]
DGS = ["DG1", "DG2"]
 
def supabase_insert(table: str, data: dict):
    resp = supabase.table(table).insert(data).execute()
    if getattr(resp, "error", None):
        st.error(f"❌ Insert error on {table}: {resp.error}")
    return resp
 
def supabase_upsert(table: str, data: dict):
    resp = supabase.table(table).upsert(data).execute()
    if getattr(resp, "error", None):
        st.error(f"❌ Upsert error on {table}: {resp.error}")
    return resp
 
def get_single_row(table: str, **filters):
    q = supabase.table(table).select("*")
    for k, v in filters.items():
        q = q.eq(k, v)
    resp = q.limit(1).execute()
    if getattr(resp, "error", None):
        st.error(f"❌ Select error on {table}: {resp.error}")
        return None
    if not resp.data:
        return None
    return resp.data[0]
 
# --------------------- Main ---------------------
def run():
    st.title("⚡ DG Monitoring Module")
 
    menu = ["User Entry", "Admin Initialization", "Last 10 Transactions"]
    choice = st.sidebar.selectbox("Select Action", menu)
 
    # ============== Admin Initialization ==============
    if choice == "Admin Initialization":
        st.header("🛠️ Admin Initialization")
        toll_plaza = st.selectbox("Select Toll Plaza", PLAZAS, key="init_plaza")
        dg_name = st.selectbox("Select DG", DGS, key="init_dg")
 
        # Use number_input WITHOUT min_value to keep it editable during typing
        opening_diesel_stock = st.number_input("Opening Diesel Stock (L)", value=0.0, step=0.01, key="init_open_diesel")
        opening_kwh = st.number_input("Opening KWH", value=0.0, step=0.01, key="init_open_kwh")
        opening_rh = st.text_input("Opening RH (hh:mm)", value="", placeholder="e.g., 4435:12", key="init_open_rh")
 
        if st.button("Initialize", type="primary"):
            if parse_rh(opening_rh) is None:
                st.error("❌ Invalid RH format. Use hh:mm.")
            else:
                data = {
                    "toll_plaza": toll_plaza,
                    "dg_name": dg_name,
                    "opening_diesel_stock": float(opening_diesel_stock or 0),
                    "opening_kwh": float(opening_kwh or 0),
                    "opening_rh": opening_rh.strip() or "0:00",
                }
                resp = supabase_upsert("dg_opening_status", data)
                if resp and resp.data:
                    st.success("✅ Initialization saved.")
                    st.rerun()
 
    # ============== User Entry ==============
    elif choice == "User Entry":
        st.header("📝 User Entry")
 
        # Put inputs in a form so Streamlit doesn't rerun mid-typing
        with st.form("user_entry_form", clear_on_submit=False):
            date_str = st.date_input("Select Entry Date", value=datetime.now()).strftime("%Y-%m-%d")
 
            toll_plaza = st.selectbox("Select Toll Plaza", PLAZAS, key="entry_plaza")
            dg_name = st.selectbox("Select DG", DGS, key="entry_dg")
 
            # Fetch opening parameters
            open_row = get_single_row("dg_opening_status", toll_plaza=toll_plaza, dg_name=dg_name)
            if not open_row:
                st.error("❌ Opening data not initialized for this DG and Plaza.")
                submitted = st.form_submit_button("Submit Entry", disabled=True)
            else:
                opening_diesel_stock = float(open_row.get("opening_diesel_stock", 0.0) or 0.0)
                opening_kwh = float(open_row.get("opening_kwh", 0.0) or 0.0)
                opening_rh = str(open_row.get("opening_rh", "0:00") or "0:00")
 
                st.info(f"🔹 **Opening Diesel Stock:** {opening_diesel_stock:.2f} L")
                st.info(f"🔹 **Opening KWH:** {opening_kwh:.2f}")
                st.info(f"🔹 **Opening RH:** {opening_rh}")
 
                # Current plaza barrel stock from live status (optional)
                live_row = get_single_row("dg_live_status", toll_plaza=toll_plaza)
                current_barrel_stock = float((live_row or {}).get("updated_plaza_barrel_stock", 0.0) or 0.0)
                st.info(f"🛢️ **Current Plaza Barrel Stock:** {current_barrel_stock:.2f} L")
 
                # Editable entries (NO min_value to keep typing fluid)
                diesel_purchase = st.number_input("Diesel Purchase (L)", value=0.0, step=0.01, key="entry_purchase")
                diesel_topup = st.number_input("Diesel Topup to DG (L)", value=0.0, step=0.01, key="entry_topup")
 
                # Preview updated barrel stock (non-blocking)
                updated_barrel_stock_preview = current_barrel_stock + float(diesel_purchase or 0) - float(diesel_topup or 0)
                st.caption(f"🛢️ Updated Barrel Stock (preview): {updated_barrel_stock_preview:.2f} L")
 
                # Closing diesel stock
                closing_diesel_stock = st.number_input("Closing Diesel Stock (L)", value=0.0, step=0.01, key="entry_close_diesel")
 
                # Closing KWH
                closing_kwh = st.number_input("Closing KWH", value=opening_kwh, step=0.01, key="entry_close_kwh")
 
                # RH
                closing_rh = st.text_input("Closing RH (hh:mm)", value="", placeholder="e.g., 4436:30", key="entry_close_rh")
 
                # Preview nets (non-blocking)
                max_closing_stock = opening_diesel_stock + float(diesel_topup or 0)
                diesel_consumption_preview = max_closing_stock - float(closing_diesel_stock or 0)
                net_kwh_preview = float(closing_kwh or 0) - opening_kwh
                net_rh_preview, _ = calculate_net_rh(opening_rh, closing_rh) if closing_rh else (None, None)
 
                st.caption(f"🔻 Diesel Consumption (preview): {diesel_consumption_preview:.2f} L | ⚡ Net KWH (preview): {net_kwh_preview:.2f} | ⏱️ Net RH (preview): {net_rh_preview or '-'}")
 
                submitted = st.form_submit_button("Submit Entry", type="primary")
 
        # ---- Post-submit validation + write ----
        if choice == "User Entry" and 'submitted' in locals() and submitted and open_row:
            # Recompute with safety
            diesel_purchase = float(diesel_purchase or 0)
            diesel_topup = float(diesel_topup or 0)
            closing_diesel_stock = float(closing_diesel_stock or 0)
            closing_kwh = float(closing_kwh or 0)
            closing_rh = (closing_rh or "").strip()
 
            # Validations (AFTER typing, not during typing)
            errors = []
            # diesel stock
            max_closing_stock = opening_diesel_stock + diesel_topup
            if closing_diesel_stock > max_closing_stock + 1e-9:
                errors.append(f"Closing Diesel Stock cannot exceed Opening + Topup ({max_closing_stock:.2f} L).")
 
            # kwh
            if closing_kwh < opening_kwh:
                errors.append("Closing KWH must be ≥ Opening KWH.")
 
            # rh
            net_rh, rh_error = calculate_net_rh(opening_rh, closing_rh)
            if rh_error:
                errors.append(rh_error)
 
            if errors:
                for e in errors:
                    st.error("❌ " + e)
                st.stop()
 
            # Final computations
            diesel_consumption = max_closing_stock - closing_diesel_stock
            updated_barrel_stock = (get_single_row("dg_live_status", toll_plaza=toll_plaza) or {}).get("updated_plaza_barrel_stock", 0.0)
            updated_barrel_stock = float(updated_barrel_stock or 0.0) + diesel_purchase - diesel_topup
            net_kwh = closing_kwh - opening_kwh
 
            data = {
                "date": date_str,
                "toll_plaza": toll_plaza,
                "dg_name": dg_name,
                "diesel_purchase": diesel_purchase,
                "diesel_topup": diesel_topup,
                "updated_plaza_barrel_stock": updated_barrel_stock,
                "opening_diesel_stock": opening_diesel_stock,
                "closing_diesel_stock": closing_diesel_stock,
                "diesel_consumption": diesel_consumption,
                "opening_kwh": opening_kwh,
                "closing_kwh": closing_kwh,
                "net_kwh": net_kwh,
                "opening_rh": opening_rh,
                "closing_rh": closing_rh,
                "net_rh": net_rh,
                "maximum_demand": st.session_state.get("entry_md", 0.0),
                "remarks": st.session_state.get("entry_remarks", "")
            }
 
            # Save transaction
            resp = supabase_insert("dg_transactions", data)
            if resp and resp.data:
                # Update dg_live_status for barrel stock
                supabase_upsert("dg_live_status", {
                    "toll_plaza": toll_plaza,
                    "updated_plaza_barrel_stock": updated_barrel_stock
                })
 
                # Auto-update opening parameters to closing parameters for next cycle
                supabase_upsert("dg_opening_status", {
                    "toll_plaza": toll_plaza,
                    "dg_name": dg_name,
                    "opening_diesel_stock": closing_diesel_stock,
                    "opening_kwh": closing_kwh,
                    "opening_rh": closing_rh
                })
 
                st.success("✅ Entry submitted successfully, opening parameters updated for next cycle.")
                st.rerun()
            else:
                st.error("❌ Submission failed (see error above).")
 
    # ============== Last 10 Transactions ==============
    elif choice == "Last 10 Transactions":
        st.header("📜 Last 10 Transactions")
        toll_plaza = st.selectbox("Select Toll Plaza for Transactions", PLAZAS, key="tx_plaza")
  
 
