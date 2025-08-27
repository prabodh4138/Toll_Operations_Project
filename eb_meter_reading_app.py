# eb_meter_reading_app.py — editable fields (state-safe), same logic
import os
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd
from supabase import create_client
 
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ Missing SUPABASE_URL or SUPABASE_KEY"); st.stop()
 
@st.cache_resource
def get_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)
supabase = get_client()
 
TP_CONSUMER_MAP = {"TP01":"416000000110","TP02":"812001020208","TP03":"813000000281"}
 
def to_float(s, name):
    s = (s or "").strip()
    if s == "": return 0.0, None
    try: return float(s), None
    except: return None, f"❌ {name}: please enter a number."
 
def fetch_openings(plaza: str):
    r = supabase.table("eb_live_status").select("opening_kwh, opening_kvah").eq("toll_plaza", plaza).single().execute()
    return {"data": r.data, "error": getattr(r, "error", None)}
 
def insert_reading(payload: dict):
    return supabase.table("eb_meter_readings").insert(payload).execute()
 
def upsert_live(plaza: str, consumer: str, opening_kwh: float, opening_kvah: float):
    return supabase.table("eb_live_status").upsert({
        "toll_plaza": plaza, "consumer_number": consumer,
        "opening_kwh": opening_kwh, "opening_kvah": opening_kvah
    }).execute()
 
def set_default(key, value):
    if key not in st.session_state:
        st.session_state[key] = value
 
def run():
    st.title("⚡ EB Meter Reading - Toll Operations")
    choice = st.sidebar.selectbox("Select Block", ["User Block","Last 10 Readings","Admin Block","Download CSV"])
 
    # ============== USER BLOCK ==============
    if choice == "User Block":
        st.header("🛠️ User Block - Enter Readings")
        with st.form("eb_form", clear_on_submit=False):
            date_obj = st.date_input("Select Date", datetime.now())
            date = date_obj.strftime("%Y-%m-%d")
            st.info(f"Selected Date: {date_obj.strftime('%d-%m-%Y')}")
 
            toll_plaza = st.selectbox("Select Toll Plaza", ["TP01","TP02","TP03"], key="eb_plaza")
            consumer_number = TP_CONSUMER_MAP.get(toll_plaza, "N/A")
            st.info(f"Auto Fetched Consumer Number: {consumer_number}")
 
            openings = fetch_openings(toll_plaza)
            if openings["error"]:
                st.error(f"Opening fetch error: {openings['error']}")
                submitted = st.form_submit_button("Submit Reading", disabled=True)
 
            else:
                open_kwh  = float((openings["data"] or {}).get("opening_kwh", 0.0) or 0.0)
                open_kvah = float((openings["data"] or {}).get("opening_kvah", 0.0) or 0.0)
                st.info(f"Opening KWH: {open_kwh:.2f} | Opening KVAH: {open_kvah:.2f}")
 
                # ---- Bind to session_state so values don't reset while typing ----
                set_default("closing_kwh_txt",  f"{open_kwh:.2f}")
                set_default("closing_kvah_txt", f"{open_kvah:.2f}")
                set_default("pf_txt",           "")
                set_default("md_txt",           "")
                set_default("solar_txt",        "")
 
                st.text_input("Closing KWH",  key="closing_kwh_txt")
                st.text_input("Closing KVAH", key="closing_kvah_txt")
                st.text_input("Power Factor (PF, 0.00-1.00)", key="pf_txt")
                st.text_input("Maximum Demand (MD kVA)", key="md_txt")
                st.text_input("Solar Unit Generated (kWh)  ➜ saved in 'remarks'", key="solar_txt")
 
                submitted = st.form_submit_button("Submit Reading", type="primary")
 
        if choice == "User Block" and 'submitted' in locals() and submitted and not openings["error"]:
            closing_kwh,  e1 = to_float(st.session_state.closing_kwh_txt, "Closing KWH")
            closing_kvah, e2 = to_float(st.session_state.closing_kvah_txt, "Closing KVAH")
            pf,           e3 = to_float(st.session_state.pf_txt or "0", "PF")
            md,           e4 = to_float(st.session_state.md_txt or "0", "MD")
            for err in (e1,e2,e3,e4):
                if err: st.error(err)
            if any([e1,e2,e3,e4]): st.stop()
 
            # validations
            errors=[]
            open_kwh  = float((openings["data"] or {}).get("opening_kwh", 0.0) or 0.0)
            open_kvah = float((openings["data"] or {}).get("opening_kvah", 0.0) or 0.0)
            if pf < 0 or pf > 1: errors.append("PF must be between 0.00 and 1.00.")
            if closing_kwh  < open_kwh:  errors.append("Closing KWH must be ≥ Opening KWH.")
            if closing_kvah < open_kvah: errors.append("Closing KVAH must be ≥ Opening KVAH.")
            if errors:
                for m in errors: st.error("❌ " + m); st.stop()
 
            net_kwh  = closing_kwh  - open_kwh
            net_kvah = closing_kvah - open_kvah
 
            payload = {
                "date": date, "toll_plaza": toll_plaza, "consumer_number": consumer_number,
                "opening_kwh": open_kwh, "closing_kwh": closing_kwh, "net_kwh": net_kwh,
                "opening_kvah": open_kvah, "closing_kvah": closing_kvah, "net_kvah": net_kvah,
                "pf": pf, "md": md,
                "remarks": (st.session_state.solar_txt or "").strip(),  # stores solar units text
            }
            r1 = insert_reading(payload)
            if getattr(r1, "error", None): st.error(f"❌ Submission failed: {r1.error}"); st.stop()
 
            r2 = upsert_live(toll_plaza, consumer_number, closing_kwh, closing_kvah)
            if getattr(r2, "error", None): st.error(f"❌ Live update failed: {r2.error}"); st.stop()
 
            # Clear just the input fields for next entry
            for k in ["closing_kwh_txt","closing_kvah_txt","pf_txt","md_txt","solar_txt"]:
                if k in st.session_state: del st.session_state[k]
 
            st.success(f"✅ Reading submitted. Net KWH: {net_kwh:.2f} | Net KVAH: {net_kvah:.2f}")
            st.rerun()
 
    # ============== LAST 10 ==============
    elif choice == "Last 10 Readings":
        st.header("📄 Last 10 Readings")
        toll_plaza = st.selectbox("Filter by Toll Plaza", ["TP01","TP02","TP03"])
        resp = supabase.table("eb_meter_readings").select("*").eq("toll_plaza", toll_plaza)\
                .order("id", desc=True).limit(10).execute()
        if getattr(resp, "error", None): st.error(f"❌ Fetch error: {resp.error}")
        elif resp.data:
            df = pd.DataFrame(resp.data); st.dataframe(df, use_container_width=True)
        else: st.info("No data found.")
 
    # ============== ADMIN ==============
    elif choice == "Admin Block":
        st.header("🔐 Admin Block - Initialize Opening Values")
        pwd = st.text_input("Enter Admin Password", type="password")
        if pwd == "Sekura@2025":
            st.success("Access Granted.")
            toll_plaza = st.selectbox("Select Toll Plaza", ["TP01","TP02","TP03"])
            consumer_number = TP_CONSUMER_MAP.get(toll_plaza, "N/A")
            st.info(f"Auto Fetched Consumer Number: {consumer_number}")
 
            set_default("init_open_kwh_txt","0"); set_default("init_open_kvah_txt","0")
            st.text_input("Initialize Opening KWH",  key="init_open_kwh_txt")
            st.text_input("Initialize Opening KVAH", key="init_open_kvah_txt")
 
            if st.button("Save Initialization", type="primary"):
                open_kwh,  e1 = to_float(st.session_state.init_open_kwh_txt, "Opening KWH")
                open_kvah, e2 = to_float(st.session_state.init_open_kvah_txt, "Opening KVAH")
                for err in (e1,e2):
                    if err: st.error(err)
                if e1 or e2: st.stop()
                r = upsert_live(toll_plaza, consumer_number, open_kwh, open_kvah)
                if getattr(r, "error", None): st.error(f"❌ Initialization failed: {r.error}")
                else:
                    st.success("✅ Initialization saved and synced."); st.rerun()
        elif pwd != "": st.error("Incorrect password.")
 
    # ============== DOWNLOAD ==============
    elif choice == "Download CSV":
        st.header("📥 Download CSV Data")
        from_date = st.date_input("From Date", datetime.now() - timedelta(days=7))
        to_date   = st.date_input("To Date", datetime.now())
        if st.button("Download CSV"):
            resp = supabase.table("eb_meter_readings").select("*")\
                    .gte("date", from_date.strftime("%Y-%m-%d"))\
                    .lte("date", to_date.strftime("%Y-%m-%d")).execute()
            if getattr(resp, "error", None): st.error(f"❌ Fetch error: {resp.error}")
            elif resp.data:
                df = pd.DataFrame(resp.data)
                st.download_button("📥 Click to Download CSV",
                    df.to_csv(index=False).encode("utf-8"),
                    "eb_meter_readings.csv", "text/csv")
            else: st.info("No data found in this range.")
 
if __name__ == "__main__":
    run()
 
