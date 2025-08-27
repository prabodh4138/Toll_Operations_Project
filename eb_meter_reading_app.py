# eb_meter_reading_app.py — plaza/date OUTSIDE the form; instant auto-fetch; context-safe keys
import os
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd
from supabase import create_client
 
# ---------- Supabase ----------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ Missing SUPABASE_URL or SUPABASE_KEY"); st.stop()
 
@st.cache_resource
def supabase_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)
 
sb = supabase_client()
 
# ---------- Config ----------
TP_CONSUMER_MAP = {
    "TP01": "416000000110",
    "TP02": "812001020208",
    "TP03": "813000000281",
}
PLAZAS = list(TP_CONSUMER_MAP.keys())
 
# ---------- Helpers ----------
def to_float(s: str, field_name: str):
    s = (s or "").strip()
    if s == "":
        return 0.0, None
    try:
        return float(s), None
    except Exception:
        return None, f"❌ {field_name}: please enter a number."
 
def fetch_openings(plaza: str):
    r = sb.table("eb_live_status").select("opening_kwh, opening_kvah")\
        .eq("toll_plaza", plaza).single().execute()
    return {"data": r.data, "error": getattr(r, "error", None)}
 
def insert_reading(payload: dict):
    return sb.table("eb_meter_readings").insert(payload).execute()
 
def upsert_live(plaza: str, consumer: str, opening_kwh: float, opening_kvah: float):
    return sb.table("eb_live_status").upsert({
        "toll_plaza": plaza,
        "consumer_number": consumer,
        "opening_kwh": opening_kwh,
        "opening_kvah": opening_kvah
    }).execute()
 
def ctx_key(plaza: str, date_str: str, name: str):
    """Unique session_state key per (plaza, date, field)."""
    return f"eb::{plaza}::{date_str}::{name}"
 
# ---------- App ----------
def run():
    st.title("⚡ EB Meter Reading - Toll Operations")
 
    menu = ["User Block", "Last 10 Readings", "Admin Block", "Download CSV"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    # ============== USER BLOCK ==============
    if choice == "User Block":
        st.header("🛠️ User Block - Enter Readings")
 
        # ---- Put context selectors OUTSIDE the form so they rerun immediately ----
        colA, colB = st.columns([1,1])
        with colA:
            date_obj = st.date_input("Select Date", datetime.now(), key="eb_date_selector")
        with colB:
            toll_plaza = st.selectbox("Select Toll Plaza", PLAZAS, key="eb_plaza_selector")
 
        date_str = date_obj.strftime("%Y-%m-%d")
        st.info(f"Selected: **{toll_plaza}** | Date: **{date_obj.strftime('%d-%m-%Y')}**")
 
        consumer_number = TP_CONSUMER_MAP.get(toll_plaza, "N/A")
        st.info(f"Auto Fetched Consumer Number: **{consumer_number}**")
 
        # ---- Fresh opening fetch on every rerun (fast call) ----
        openings = fetch_openings(toll_plaza)
        if openings["error"]:
            st.error(f"Opening fetch error: {openings['error']}")
            open_kwh, open_kvah = 0.0, 0.0
        else:
            open_kwh  = float((openings["data"] or {}).get("opening_kwh", 0.0) or 0.0)
            open_kvah = float((openings["data"] or {}).get("opening_kvah", 0.0) or 0.0)
 
        st.info(f"Opening KWH: **{open_kwh:.2f}** | Opening KVAH: **{open_kvah:.2f}**")
 
        # ---- Context-scoped keys so switching plaza/date reseeds correctly ----
        ckwh_key  = ctx_key(toll_plaza, date_str, "closing_kwh_txt")
        ckvah_key = ctx_key(toll_plaza, date_str, "closing_kvah_txt")
        pf_key    = ctx_key(toll_plaza, date_str, "pf_txt")
        md_key    = ctx_key(toll_plaza, date_str, "md_txt")
        sol_key   = ctx_key(toll_plaza, date_str, "solar_txt")
 
        # Seed defaults ONCE per context
        if ckwh_key not in st.session_state:  st.session_state[ckwh_key]  = f"{open_kwh:.2f}"
        if ckvah_key not in st.session_state: st.session_state[ckvah_key] = f"{open_kvah:.2f}"
        if pf_key not in st.session_state:    st.session_state[pf_key]    = ""
        if md_key not in st.session_state:    st.session_state[md_key]    = ""
        if sol_key not in st.session_state:   st.session_state[sol_key]   = ""
 
        # ---- The form only contains the editable fields + submit button ----
        with st.form("eb_form", clear_on_submit=False):
            st.text_input("Closing KWH",  key=ckwh_key)
            st.text_input("Closing KVAH", key=ckvah_key)
            st.text_input("Power Factor (PF, 0.00–1.00)", key=pf_key)
            st.text_input("Maximum Demand (MD kVA)", key=md_key)
            st.text_input("Solar Unit Generated (kWh)  ➜ saved in 'remarks'", key=sol_key)
            submitted = st.form_submit_button("Submit Reading", type="primary")
 
        if submitted:
            # Read from session_state using the context keys
            closing_kwh,  e1 = to_float(st.session_state[ckwh_key],  "Closing KWH")
            closing_kvah, e2 = to_float(st.session_state[ckvah_key], "Closing KVAH")
            pf,           e3 = to_float(st.session_state[pf_key] or "0", "Power Factor")
            md,           e4 = to_float(st.session_state[md_key] or "0", "Maximum Demand")
            for err in (e1,e2,e3,e4):
                if err: st.error(err)
            if any([e1,e2,e3,e4]): st.stop()
 
            errors = []
            if not (0.0 <= pf <= 1.0): errors.append("PF must be between 0.00 and 1.00.")
            if closing_kwh  < open_kwh:  errors.append("Closing KWH must be ≥ Opening KWH.")
            if closing_kvah < open_kvah: errors.append("Closing KVAH must be ≥ Opening KVAH.")
            if errors:
                for m in errors: st.error("❌ " + m)
                st.stop()
 
            net_kwh  = closing_kwh  - open_kwh
            net_kvah = closing_kvah - open_kvah
 
            payload = {
                "date": date_str,
                "toll_plaza": toll_plaza,
                "consumer_number": consumer_number,
                "opening_kwh": open_kwh,
                "closing_kwh": closing_kwh,
                "net_kwh": net_kwh,
                "opening_kvah": open_kvah,
                "closing_kvah": closing_kvah,
                "net_kvah": net_kvah,
                "pf": pf,
                "md": md,
                # store Solar Unit Generated text into 'remarks'
                "remarks": (st.session_state[sol_key] or "").strip()
            }
 
            r1 = insert_reading(payload)
            if getattr(r1, "error", None):
                st.error(f"❌ Submission failed: {r1.error}"); st.stop()
 
            r2 = upsert_live(toll_plaza, consumer_number, closing_kwh, closing_kvah)
            if getattr(r2, "error", None):
                st.error(f"❌ Live-status update failed: {r2['error']}"); st.stop()
 
            # After submit, keep context but refresh defaults to latest closing values
            st.session_state[ckwh_key]  = f"{closing_kwh:.2f}"
            st.session_state[ckvah_key] = f"{closing_kvah:.2f}"
            st.session_state[pf_key]    = ""
            st.session_state[md_key]    = ""
            st.session_state[sol_key]   = ""
 
            st.success(f"✅ Reading submitted for {toll_plaza}. Net KWH: {net_kwh:.2f} | Net KVAH: {net_kvah:.2f}")
 
    # ============== LAST 10 ==============
    elif choice == "Last 10 Readings":
        st.header("📄 Last 10 Readings")
        plaza = st.selectbox("Filter by Toll Plaza", PLAZAS)
        resp = sb.table("eb_meter_readings").select("*")\
            .eq("toll_plaza", plaza).order("id", desc=True).limit(10).execute()
        if getattr(resp, "error", None):
            st.error(f"❌ Fetch error: {resp.error}")
        elif resp.data:
            st.dataframe(pd.DataFrame(resp.data), use_container_width=True)
        else:
            st.info("No data found.")
 
    # ============== ADMIN ==============
    elif choice == "Admin Block":
        st.header("🔐 Admin Block - Initialize Opening Values")
        pwd = st.text_input("Enter Admin Password", type="password")
        if pwd == "Sekura@2025":
            st.success("Access Granted.")
            plaza = st.selectbox("Select Toll Plaza for Initialization", PLAZAS)
            consumer = TP_CONSUMER_MAP.get(plaza, "N/A")
            st.info(f"Auto Fetched Consumer Number: {consumer}")
 
            # Admin fields (simple, state-bound)
            k1, k2 = f"admin_open_kwh_{plaza}", f"admin_open_kvah_{plaza}"
            if k1 not in st.session_state: st.session_state[k1] = "0"
            if k2 not in st.session_state: st.session_state[k2] = "0"
            st.text_input("Initialize Opening KWH",  key=k1)
            st.text_input("Initialize Opening KVAH", key=k2)
 
            if st.button("Save Initialization", type="primary"):
                open_kwh,  e1 = to_float(st.session_state[k1], "Opening KWH")
                open_kvah, e2 = to_float(st.session_state[k2], "Opening KVAH")
                for err in (e1,e2):
                    if err: st.error(err)
                if e1 or e2: st.stop()
 
                r = upsert_live(plaza, consumer, open_kwh, open_kvah)
                if getattr(r, "error", None):
                    st.error(f"❌ Initialization failed: {r.error}")
                else:
                    st.success("✅ Initialization saved and synced.")
        elif pwd != "":
            st.error("Incorrect password.")
 
    # ============== DOWNLOAD ==============
    elif choice == "Download CSV":
        st.header("📥 Download CSV Data")
        from_date = st.date_input("From Date", datetime.now() - timedelta(days=7))
        to_date   = st.date_input("To Date", datetime.now())
        if st.button("Download CSV"):
            resp = sb.table("eb_meter_readings").select("*")\
                .gte("date", from_date.strftime("%Y-%m-%d"))\
                .lte("date", to_date.strftime("%Y-%m-%d")).execute()
            if getattr(resp, "error", None):
                st.error(f"❌ Fetch error: {resp.error}")
            elif resp.data:
                df = pd.DataFrame(resp.data)
                st.download_button("📥 Click to Download CSV",
                    df.to_csv(index=False).encode("utf-8"),
                    "eb_meter_readings.csv", "text/csv")
            else:
                st.info("No data found in this range.")
 
# For Streamlit launcher
if __name__ == "__main__":
    run()
 
