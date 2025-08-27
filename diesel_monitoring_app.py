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
 
# ---------- numeric parsing so typing never blocks ----------
def to_float(txt, field_name):
    s = (txt or "").strip()
    if s == "":
        return 0.0, None
    try:
        return float(s), None
    except Exception:
        return None, f"❌ {field_name}: please enter a number."
 
# --------------------- Helpers ---------------------
PLAZAS = ["TP01", "TP02", "TP03"]
DGS = ["DG1", "DG2"]
 
def supabase_insert(table: str, data: dict):
    resp = supabase.table(table).insert(data).execute()
    return resp
 
def supabase_upsert(table: str, data: dict):
    resp = supabase.table(table).upsert(data).execute()
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
 
        # Use free-typing inputs (converted later)
        open_diesel_txt = st.text_input("Opening Diesel Stock (L)", value="0")
        open_kwh_txt    = st.text_input("Opening KWH", value="0")
        opening_rh      = st.text_input("Opening RH (hh:mm)", value="", placeholder="e.g., 4435:12")
 
        if st.button("Initialize", type="primary"):
            opening_diesel_stock, e1 = to_float(open_diesel_txt, "Opening Diesel Stock")
            opening_kwh, e2 = to_float(open_kwh_txt, "Opening KWH")
            if e1: st.error(e1)
            if e2: st.error(e2)
            if e1 or e2:
                st.stop()
 
            if parse_rh(opening_rh) is None:
                st.error("❌ Invalid RH format. Use hh:mm.")
            else:
                data = {
                    "toll_plaza": toll_plaza,
                    "dg_name": dg_name,
                    "opening_diesel_stock": opening_diesel_stock,
                    "opening_kwh": opening_kwh,
                    "opening_rh": opening_rh.strip() or "0:00",
                }
                resp = supabase_upsert("dg_opening_status", data)
                if getattr(resp, "error", None):
                    st.error(f"❌ Initialization failed: {resp.error}")
                elif resp.data is not None:
                    st.success("✅ Initialization saved.")
                    st.rerun()
                else:
                    st.error("❌ Initialization failed (no data returned).")
 
    # ============== User Entry ==============
    elif choice == "User Entry":
        st.header("📝 User Entry")
 
        with st.form("user_entry_form", clear_on_submit=False):
            date_str   = st.date_input("Select Entry Date", value=datetime.now()).strftime("%Y-%m-%d")
            toll_plaza = st.selectbox("Select Toll Plaza", PLAZAS, key="entry_plaza")
            dg_name    = st.selectbox("Select DG", DGS, key="entry_dg")
 
            open_row = get_single_row("dg_opening_status", toll_plaza=toll_plaza, dg_name=dg_name)
            if not open_row:
                st.error("❌ Opening data not initialized for this DG and Plaza.")
                submitted = st.form_submit_button("Submit Entry", disabled=True)
            else:
                opening_diesel_stock = float(open_row.get("opening_diesel_stock", 0.0) or 0.0)
                opening_kwh          = float(open_row.get("opening_kwh", 0.0) or 0.0)
                opening_rh           = str(open_row.get("opening_rh", "0:00") or "0:00")
 
                st.info(f"🔹 **Opening Diesel Stock:** {opening_diesel_stock:.2f} L")
                st.info(f"🔹 **Opening KWH:** {opening_kwh:.2f}")
                st.info(f"🔹 **Opening RH:** {opening_rh}")
 
                live_row = get_single_row("dg_live_status", toll_plaza=toll_plaza)
                current_barrel_stock = float((live_row or {}).get("updated_plaza_barrel_stock", 0.0) or 0.0)
                st.info(f"🛢️ **Current Plaza Barrel Stock:** {current_barrel_stock:.2f} L")
 
                # ---- Free-typing inputs (never block typing) ----
                diesel_purchase_txt       = st.text_input("Diesel Purchase (L)", value="0")
                diesel_topup_txt          = st.text_input("Diesel Topup to DG (L)", value="0")
                closing_diesel_stock_txt  = st.text_input("Closing Diesel Stock (L)", value="0")
                closing_kwh_txt           = st.text_input("Closing KWH", value=f"{opening_kwh:.2f}")
                closing_rh                = st.text_input("Closing RH (hh:mm)", value="", placeholder="e.g., 4436:30")
                maximum_demand_txt        = st.text_input("Maximum Demand (kVA)", value="0")
                remarks                   = st.text_area("Remarks (optional)", value="")
 
                submitted = st.form_submit_button("Submit Entry", type="primary")
 
        # ---- Post-submit validation + write ----
        if choice == "User Entry" and 'submitted' in locals() and submitted and open_row:
            # Convert numbers
            diesel_purchase, e1 = to_float(diesel_purchase_txt, "Diesel Purchase")
            diesel_topup,    e2 = to_float(diesel_topup_txt, "Diesel Topup")
            closing_diesel_stock, e3 = to_float(closing_diesel_stock_txt, "Closing Diesel Stock")
            closing_kwh,      e4 = to_float(closing_kwh_txt, "Closing KWH")
            maximum_demand,   e5 = to_float(maximum_demand_txt, "Maximum Demand")
 
            for err in [e1, e2, e3, e4, e5]:
                if err: st.error(err)
            if any([e1, e2, e3, e4, e5]):
                st.stop()
 
            # Validations
            errors = []
            max_closing_stock = opening_diesel_stock + diesel_topup
            if closing_diesel_stock > max_closing_stock + 1e-9:
                errors.append(f"Closing Diesel Stock cannot exceed Opening + Topup ({max_closing_stock:.2f} L).")
 
            if closing_kwh < opening_kwh:
                errors.append("Closing KWH must be ≥ Opening KWH.")
 
            net_rh, rh_error = calculate_net_rh(opening_rh, closing_rh)
            if rh_error:
                errors.append(rh_error)
 
            if errors:
                for e in errors: st.error("❌ " + e)
                st.stop()
 
            # Final computations
            diesel_consumption   = max_closing_stock - closing_diesel_stock
            updated_barrel_stock = current_barrel_stock + diesel_purchase - diesel_topup
            net_kwh              = closing_kwh - opening_kwh
 
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
                "maximum_demand": maximum_demand,
                "remarks": remarks
            }
 
            # Save transaction
            resp = supabase_insert("dg_transactions", data)
            if getattr(resp, "error", None):
                st.error(f"❌ Submission failed: {resp.error}")
                st.stop()
            if resp.data is None:
                st.error("❌ Submission failed (no data returned).")
                st.stop()
 
            # Update dg_live_status for barrel stock
            resp2 = supabase_upsert("dg_live_status", {
                "toll_plaza": toll_plaza,
                "updated_plaza_barrel_stock": updated_barrel_stock
            })
            if getattr(resp2, "error", None):
                st.error(f"❌ Live status update failed: {resp2.error}")
                st.stop()
 
            # Auto-update opening parameters to closing parameters for next cycle
            resp3 = supabase_upsert("dg_opening_status", {
                "toll_plaza": toll_plaza,
                "dg_name": dg_name,
                "opening_diesel_stock": closing_diesel_stock,
                "opening_kwh": closing_kwh,
                "opening_rh": closing_rh
            })
            if getattr(resp3, "error", None):
                st.error(f"❌ Opening status update failed: {resp3.error}")
                st.stop()
 
            st.success("✅ Entry submitted successfully, opening parameters updated for next cycle.")
            st.rerun()
 
    # ============== Last 10 Transactions ==============
    elif choice == "Last 10 Transactions":
        st.header("📜 Last 10 Transactions")
        toll_plaza = st.selectbox("Select Toll Plaza for Transactions", ["TP01", "TP02", "TP03"], key="tx_plaza")
        resp = supabase.table("dg_transactions").select("*").eq("toll_plaza", toll_plaza).order("id", desc=True).limit(10).execute()
        if getattr(resp, "error", None):
            st.error(f"❌ Fetch error: {resp.error}")
        elif resp.data:
            df = pd.DataFrame(resp.data)
            st.dataframe(df, use_container_width=True)
     
 
