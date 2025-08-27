# eb_meter_reading_app.py  — editable inputs + safe validation
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
def get_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)
 
supabase = get_client()
 
# ---------- Helpers ----------
TP_CONSUMER_MAP = {
    "TP01": "416000000110",
    "TP02": "812001020208",
    "TP03": "813000000281",
}
 
def to_float(s, field_name):
    s = (s or "").strip()
    if s == "":
        return 0.0, None
    try:
        return float(s), None
    except Exception:
        return None, f"❌ {field_name}: please enter a number."
 
def fetch_openings(plaza: str):
    """Read opening_kwh/opening_kvah from eb_live_status for the plaza."""
    r = supabase.table("eb_live_status").select("opening_kwh, opening_kvah").eq("toll_plaza", plaza).single().execute()
    return {"data": r.data, "error": getattr(r, "error", None)}
 
def insert_reading(payload: dict):
    return supabase.table("eb_meter_readings").insert(payload).execute()
 
def upsert_live(plaza: str, consumer: str, opening_kwh: float, opening_kvah: float):
    return supabase.table("eb_live_status").upsert({
        "toll_plaza": plaza,
        "consumer_number": consumer,
        "opening_kwh": opening_kwh,
        "opening_kvah": opening_kvah
    }).execute()
 
# ---------- App ----------
def run():
    st.title("⚡ EB Meter Reading - Toll Operations")
 
    menu = ["User Block", "Last 10 Readings", "Admin Block", "Download CSV"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    # ========== USER BLOCK ==========
    if choice == "User Block":
        st.header("🛠️ User Block - Enter Readings")
 
        with st.form("eb_form", clear_on_submit=False):
            date_obj = st.date_input("Select Date", datetime.now())
            date = date_obj.strftime("%Y-%m-%d")
            date_for_display = date_obj.strftime("%d-%m-%Y")
            st.info(f"Selected Date: {date_for_display}")
 
            toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
            consumer_number = TP_CONSUMER_MAP.get(toll_plaza, "N/A")
            st.info(f"Auto Fetched Consumer Number: {consumer_number}")
 
            openings = fetch_openings(toll_plaza)
            if openings["error"]:
                st.error(f"Opening fetch error: {openings['error']}")
                submitted = st.form_submit_button("Submit Reading", disabled=True)
            else:
                open_kwh  = float((openings["data"] or {}).get("opening_kwh", 0.0) or 0.0)
                open_kvah = float((openings["data"] or {}).get("opening_kvah", 0.0) or 0.0)
 
                st.info(f"Opening KWH (Auto Fetched): {open_kwh:.2f}")
                st.info(f"Opening KVAH (Auto Fetched): {open_kvah:.2f}")
 
                # --- Always-editable inputs (free typing) ---
                closing_kwh_txt  = st.text_input("Closing KWH",  value=f"{open_kwh:.2f}")
                closing_kvah_txt = st.text_input("Closing KVAH", value=f"{open_kvah:.2f}")
                pf_txt           = st.text_input("Power Factor (PF, 0.00-1.00)", value="")
                md_txt           = st.text_input("Maximum Demand (MD kVA)", value="")
                solar_txt        = st.text_input("Solar Unit Generated (kWh)  ➜  (saved in 'remarks')", value="")
 
                submitted = st.form_submit_button("Submit Reading", type="primary")
 
        if choice == "User Block" and 'submitted' in locals() and submitted and not openings["error"]:
            # Parse numbers
            closing_kwh, e1  = to_float(closing_kwh_txt, "Closing KWH")
            closing_kvah, e2 = to_float(closing_kvah_txt, "Closing KVAH")
            pf, e3           = to_float(pf_txt or "0", "Power Factor")
            md, e4           = to_float(md_txt or "0", "Maximum Demand")
            # solar can be blank; store as text in remarks
            for err in (e1, e2, e3, e4):
                if err: st.error(err)
            if any([e1, e2, e3, e4]):
                st.stop()
 
            # Validate ranges
            errors = []
            if pf < 0 or pf > 1:
                errors.append("PF must be between 0.00 and 1.00.")
            if closing_kwh < open_kwh:
                errors.append("Closing KWH must be ≥ Opening KWH.")
            if closing_kvah < open_kvah:
                errors.append("Closing KVAH must be ≥ Opening KVAH.")
            if errors:
                for msg in errors: st.error("❌ " + msg)
                st.stop()
 
            # Compute nets
            net_kwh  = closing_kwh  - open_kwh
            net_kvah = closing_kvah - open_kvah
 
            data = {
                "date": date,
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
                # Save the solar units into the existing 'remarks' column
                "remarks": (solar_txt or "").strip()
            }
 
            r1 = insert_reading(data)
            if getattr(r1, "error", None):
                st.error(f"❌ Submission failed: {r1.error}")
                st.stop()
 
            r2 = upsert_live(toll_plaza, consumer_number, closing_kwh, closing_kvah)
            if getattr(r2, "error", None):
                st.error(f"❌ Live-status update failed: {r2.error}")
                st.stop()
 
            st.success(f"✅ Reading submitted. Net KWH: {net_kwh:.2f} | Net KVAH: {net_kvah:.2f}")
            st.rerun()
 
    # ========== LAST 10 ==========
    elif choice == "Last 10 Readings":
        st.header("📄 Last 10 Readings")
        toll_plaza = st.selectbox("Filter by Toll Plaza", ["TP01", "TP02", "TP03"])
        resp = supabase.table("eb_meter_readings").select("*").eq("toll_plaza", toll_plaza)\
            .order("id", desc=True).limit(10).execute()
        if getattr(resp, "error", None):
            st.error(f"❌ Fetch error: {resp.error}")
        elif resp.data:
            df = pd.DataFrame(resp.data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No data found.")
 
    # ========== ADMIN ==========
    elif choice == "Admin Block":
        st.header("🔐 Admin Block - Initialize Opening Values")
        pwd = st.text_input("Enter Admin Password", type="password")
        if pwd == "Sekura@2025":
            st.success("Access Granted.")
            toll_plaza = st.selectbox("Select Toll Plaza for Initialization", ["TP01", "TP02", "TP03"])
            consumer_number = TP_CONSUMER_MAP.get(toll_plaza, "N/A")
            st.info(f"Auto Fetched Consumer Number: {consumer_number}")
 
            # free typing + validate later
            open_kwh_txt  = st.text_input("Initialize Opening KWH",  value="0")
            open_kvah_txt = st.text_input("Initialize Opening KVAH", value="0")
 
            if st.button("Save Initialization", type="primary"):
                open_kwh, e1  = to_float(open_kwh_txt, "Opening KWH")
                open_kvah, e2 = to_float(open_kvah_txt, "Opening KVAH")
                for err in (e1, e2):
                    if err: st.error(err)
                if e1 or e2: st.stop()
 
                r = upsert_live(toll_plaza, consumer_number, open_kwh, open_kvah)
                if getattr(r, "error", None):
                    st.error(f"❌ Initialization failed: {r.error}")
                else:
                    st.success("✅ Initialization saved and synced.")
                    st.rerun()
        elif pwd != "":
            st.error("Incorrect password.")
 
    # ========== DOWNLOAD ==========
    elif choice == "Download CSV":
        st.header("📥 Download CSV Data")
        from_date = st.date_input("From Date", datetime.now() - timedelta(days=7))
        to_date   = st.date_input("To Date", datetime.now())
        if st.button("Download CSV"):
            resp = supabase.table("eb_meter_readings").select("*")\
                .gte("date", from_date.strftime("%Y-%m-%d"))\
                .lte("date", to_date.strftime("%Y-%m-%d")).execute()
            if getattr(resp, "error", None):
                st.error(f"❌ Fetch error: {resp.error}")
            elif resp.data:
                df = pd.DataFrame(resp.data)
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Click to Download CSV", csv, "eb_meter_readings.csv", "text/csv")
            else:
                st.info("No data found in this range.")
 
# For Streamlit launcher
if __name__ == "__main__":
    run()
 
