import os
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd
from supabase import create_client
 
# ---------- Supabase ----------
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
if not URL or not KEY:
    st.error("❌ Missing SUPABASE_URL or SUPABASE_KEY"); st.stop()
 
@st.cache_resource
def supabase_client():
    return create_client(URL, KEY)
sb = supabase_client()
 
# ---------- Helpers ----------
TP_CONSUMER_MAP = {"TP01":"416000000110","TP02":"812001020208","TP03":"813000000281"}
 
def to_float(s, name):
    s = (s or "").strip()
    if s == "": return 0.0, None
    try: return float(s), None
    except: return None, f"❌ {name}: please enter a number."
 
def fetch_openings(plaza: str):
    r = sb.table("eb_live_status").select("opening_kwh, opening_kvah").eq("toll_plaza", plaza).single().execute()
    return {"data": r.data, "error": getattr(r, "error", None)}
 
def insert_reading(payload: dict):
    return sb.table("eb_meter_readings").insert(payload).execute()
 
def upsert_live(plaza: str, consumer: str, opening_kwh: float, opening_kvah: float):
    return sb.table("eb_live_status").upsert({
        "toll_plaza": plaza, "consumer_number": consumer,
        "opening_kwh": opening_kwh, "opening_kvah": opening_kvah
    }).execute()
 
def ensure_ctx_seed(ctx_key, *, open_kwh, open_kvah):
    """Seed inputs once per (plaza:date) context so typing never gets overwritten."""
    if st.session_state.get("eb_ctx") != ctx_key:
        st.session_state["eb_ctx"] = ctx_key
        st.session_state["closing_kwh_txt"]  = f"{open_kwh:.2f}"
        st.session_state["closing_kvah_txt"] = f"{open_kvah:.2f}"
        st.session_state["pf_txt"]           = ""
        st.session_state["md_txt"]           = ""
        st.session_state["solar_txt"]        = ""
 
def run():
    st.title("⚡ EB Meter Reading - Toll Operations")
    choice = st.sidebar.selectbox("Select Block", ["User Block","Last 10 Readings","Admin Block","Download CSV"])
 
    # ============== USER BLOCK ==============
    if choice == "User Block":
        st.header("🛠️ User Block - Enter Readings")
 
        with st.form("eb_form", clear_on_submit=False):
            date_obj = st.date_input("Select Date", datetime.now())
            date     = date_obj.strftime("%Y-%m-%d")
            st.info(f"Selected Date: {date_obj.strftime('%d-%m-%Y')}")
 
            toll_plaza = st.selectbox("Select Toll Plaza", ["TP01","TP02","TP03"], key="eb_plaza")
            consumer   = TP_CONSUMER_MAP.get(toll_plaza, "N/A")
            st.info(f"Auto Fetched Consumer Number: {consumer}")
 
            openings = fetch_openings(toll_plaza)
            if openings["error"]:
                st.error(f"Opening fetch error: {openings['error']}")
                # still render inputs so user can type; just seed with zeros
                open_kwh  = 0.0
                open_kvah = 0.0
            else:
                open_kwh  = float((openings["data"] or {}).get("opening_kwh", 0.0) or 0.0)
                open_kvah = float((openings["data"] or {}).get("opening_kvah", 0.0) or 0.0)
 
            st.info(f"Opening KWH: {open_kwh:.2f} | Opening KVAH: {open_kvah:.2f}")
 
            # ---- Context-aware seeding ----
            ctx = f"{toll_plaza}:{date}"
            ensure_ctx_seed(ctx, open_kwh=open_kwh, open_kvah=open_kvah)
 
            # ---- Editable inputs bound to session_state ----
            st.text_input("Closing KWH",  key="closing_kwh_txt")
            st.text_input("Closing KVAH", key="closing_kvah_txt")
            st.text_input("Power Factor (PF, 0.00-1.00)", key="pf_txt")
            st.text_input("Maximum Demand (MD kVA)", key="md_txt")
            st.text_input("Solar Unit Generated (kWh)  ➜ saved in 'remarks'", key="solar_txt")
 
            submitted = st.form_submit_button("Submit Reading", type="primary")
 
        if submitted:
            # Parse and validate
            closing_kwh,  e1 = to_float(st.session_state.closing_kwh_txt, "Closing KWH")
            closing_kvah, e2 = to_float(st.session_state.closing_kvah_txt, "Closing KVAH")
            pf,           e3 = to_float(st.session_state.pf_txt or "0", "PF")
            md,           e4 = to_float(st.session_state.md_txt or "0", "MD")
            for err in (e1,e2,e3,e4):
                if err: st.error(err)
            if any([e1,e2,e3,e4]): st.stop()
 
            errs=[]
            if not (0 <= pf <= 1): errs.append("PF must be between 0.00 and 1.00.")
            if closing_kwh  < open_kwh:  errs.append("Closing KWH must be ≥ Opening KWH.")
            if closing_kvah < open_kvah: errs.append("Closing KVAH must be ≥ Opening KVAH.")
            if errs:
                for m in errs: st.error("❌ " + m)
                st.stop()
 
            net_kwh  = closing_kwh  - open_kwh
            net_kvah = closing_kvah - open_kvah
 
            payload = {
                "date": date, "toll_plaza": toll_plaza, "consumer_number": consumer,
                "opening_kwh": open_kwh, "closing_kwh": closing_kwh, "net_kwh": net_kwh,
                "opening_kvah": open_kvah, "closing_kvah": closing_kvah, "net_kvah": net_kvah,
                "pf": pf, "md": md,
                "remarks": (st.session_state.solar_txt or "").strip()  # solar units stored in remarks
            }
 
            r1 = insert_reading(payload)
            if getattr(r1, "error", None):
                st.error(f"❌ Submission failed: {r1.error}"); st.stop()
 
            r2 = upsert_live(toll_plaza, consumer, closing_kwh, closing_kvah)
            if getattr(r2, "error", None):
                st.error(f"❌ Live update failed: {r2.error}"); st.stop()
 
            # Reset inputs for same context (keep ctx so they don't instantly reseed)
            st.session_state["closing_kwh_txt"]  = f"{closing_kwh:.2f}"
            st.session_state["closing_kvah_txt"] = f"{closing_kvah:.2f}"
            st.session_state["pf_txt"]           = ""
            st.session_state["md_txt"]           = ""
            st.session_state["solar_txt"]        = ""
 
            st.success(f"✅ Reading submitted. Net KWH: {net_kwh:.2f} | Net KVAH: {net_kvah:.2f}")
 
    # ============== LAST 10 ==============
    elif choice == "Last 10 Readings":
        st.header("📄 Last 10 Readings")
        plaza = st.selectbox("Filter by Toll Plaza", ["TP01","TP02","TP03"])
        resp = sb.table("eb_meter_readings").select("*").eq("toll_plaza", plaza).order("id", desc=True).limit(10).execute()
        if getattr(resp, "error", None): st.error(f"❌ Fetch error: {resp.error}")
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
            plaza = st.selectbox("Select Toll Plaza for Initialization", ["TP01","TP02","TP03"])
            consumer = TP_CONSUMER_MAP.get(plaza, "N/A")
            st.info(f"Auto Fetched Consumer Number: {consumer}")
 
            # Admin inputs (state-bound)
            if "admin_open_kwh" not in st.session_state: st.session_state["admin_open_kwh"] = "0"
            if "admin_open_kvah" not in st.session_state: st.session_state["admin_open_kvah"] = "0"
            st.text_input("Initialize Opening KWH",  key="admin_open_kwh")
            st.text_input("Initialize Opening KVAH", key="admin_open_kvah")
 
            if st.button("Save Initialization", type="primary"):
                open_kwh,  e1 = to_float(st.session_state.admin_open_kwh, "Opening KWH")
                open_kvah, e2 = to_float(st.session_state.admin_open_kvah, "Opening KVAH")
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
                st.download_button("📥 Click to Download CSV", df.to_csv(index=False).encode("utf-8"),
                                   "eb_meter_readings.csv", "text/csv")
            else:
                st.info("No data found in this range.")
 
if __name__ == "__main__":
    run()
 
