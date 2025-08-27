# eb_meter_reading_app.py  -- compact, fixed indentation
import os
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
from supabase import create_client
 
URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_KEY")
if not URL or not KEY:
    st.error("Missing SUPABASE_URL/SUPABASE_KEY")
    st.stop()
 
@st.cache_resource
def sb():
    return create_client(URL, KEY)
 
db = sb()
 
PLAZA_CONSUMER = {
    "TP01": "416000000110",
    "TP02": "812001020208",
    "TP03": "813000000281",
}
PLAZAS = list(PLAZA_CONSUMER.keys())
 
def f2(text, name):
    text = (text or "").strip()
    if text == "":
        return 0.0, None
    try:
        return float(text), None
    except Exception:
        return None, f"❌ {name}: enter a number."
 
def fetch_open(plaza):
    r = db.table("eb_live_status").select("opening_kwh, opening_kvah") \
        .eq("toll_plaza", plaza).single().execute()
    return {"data": r.data, "error": getattr(r, "error", None)}
 
def insert_reading(payload):
    return db.table("eb_meter_readings").insert(payload).execute()
 
def upsert_live(plaza, consumer, okwh, okvah):
    return db.table("eb_live_status").upsert({
        "toll_plaza": plaza,
        "consumer_number": consumer,
        "opening_kwh": okwh,
        "opening_kvah": okvah
    }).execute()
 
def kctx(plaza, date_str, name):
    return f"eb::{plaza}::{date_str}::{name}"
 
def reset_ctx(plaza, date_str):
    prefix = f"eb::{plaza}::{date_str}::"
    for k in list(st.session_state.keys()):
        if k.startswith(prefix):
            st.session_state.pop(k, None)
 
def run():
    st.title("EB Meter Reading")
 
    col_fc, _, _ = st.columns([1, 1, 1])
    with col_fc:
        if st.button("🧹 Force Clear Cache", use_container_width=True):
            try:
                st.cache_data.clear()
                st.cache_resource.clear()
            except Exception:
                pass
            st.rerun()
 
    page = st.sidebar.selectbox("Menu", ["User Entry", "Admin Init", "Last 10", "Download CSV"])
 
    if page == "User Entry":
        c1, c2 = st.columns(2)
        with c1:
            date = st.date_input("Date", datetime.now())
        with c2:
            plaza = st.selectbox("Toll Plaza", PLAZAS)
 
        date_str = date.strftime("%Y-%m-%d")
        consumer = PLAZA_CONSUMER.get(plaza, "N/A")
st.info(f"Plaza: {plaza} | Date: {date.strftime('%d-%m-%Y')}")
st.info(f"Consumer: {consumer}")
 
        op = fetch_open(plaza)
        if op["error"]:
            st.error(f"Opening fetch error: {op['error']}")
            okwh, okvah = 0.0, 0.0
        else:
            okwh = float((op["data"] or {}).get("opening_kwh", 0.0) or 0.0)
            okvah = float((op["data"] or {}).get("opening_kvah", 0.0) or 0.0)
st.info(f"Opening KWH: {okwh:.2f} | Opening KVAH: {okvah:.2f}")
 
        r1, r2 = st.columns([1, 2])
        with r1:
            if st.button("🔄 Refresh Opening", use_container_width=True):
                reset_ctx(plaza, date_str)
                st.rerun()
        with r2:
            with st.expander("🧰 Quick Init/Update Opening"):
                t_okwh = st.text_input("Opening KWH", f"{okwh:.2f}", key=f"init_okwh_{plaza}")
                t_okvh = st.text_input("Opening KVAH", f"{okvah:.2f}", key=f"init_okvh_{plaza}")
                if st.button("Save Opening", key=f"save_open_{plaza}"):
                    nv1, e1 = f2(t_okwh, "Opening KWH")
                    nv2, e2 = f2(t_okvh, "Opening KVAH")
                    for e in (e1, e2):
                        if e:
                            st.error(e)
                    if not (e1 or e2):
                        res = upsert_live(plaza, consumer, nv1, nv2)
                        if getattr(res, "error", None):
                            st.error(f"❌ {res.error}")
                        else:
                            reset_ctx(plaza, date_str)
                            st.success("Opening saved.")
                            st.rerun()
 
        k_ckwh = kctx(plaza, date_str, "ckwh")
        k_ckvh = kctx(plaza, date_str, "ckvah")
        k_pf = kctx(plaza, date_str, "pf")
        k_md = kctx(plaza, date_str, "md")
        k_sol = kctx(plaza, date_str, "solar")
 
        if k_ckwh not in st.session_state:
            st.session_state[k_ckwh] = f"{okwh:.2f}"
        if k_ckvh not in st.session_state:
            st.session_state[k_ckvh] = f"{okvah:.2f}"
        if k_pf not in st.session_state:
            st.session_state[k_pf] = ""
        if k_md not in st.session_state:
            st.session_state[k_md] = ""
        if k_sol not in st.session_state:
            st.session_state[k_sol] = ""
 
        with st.form("eb_form", clear_on_submit=False):
            st.text_input("Closing KWH", key=k_ckwh)
            st.text_input("Closing KVAH", key=k_ckvh)
            st.text_input("Power Factor (PF, 0.00-1.00)", key=k_pf)
            st.text_input("Maximum Demand (MD kVA)", key=k_md)
            st.text_input("Solar Unit Generated (kWh) -> saved in 'remarks'", key=k_sol)
            sub = st.form_submit_button("Submit Reading", type="primary")
 
        if sub:
            ckwh, e1 = f2(st.session_state[k_ckwh], "Closing KWH")
            ckvh, e2 = f2(st.session_state[k_ckvh], "Closing KVAH")
            pf, e3 = f2(st.session_state[k_pf] or "0", "Power Factor")
            md, e4 = f2(st.session_state[k_md] or "0", "Maximum Demand")
 
            for e in (e1, e2, e3, e4):
                if e:
                    st.error(e)
            if any([e1, e2, e3, e4]):
                st.stop()
 
            errs = []
            if not (0 <= pf <= 1):
                errs.append("PF must be 0.00-1.00.")
            if ckwh < okwh:
                errs.append("Closing KWH must be >= Opening KWH.")
            if ckvh < okvah:
                errs.append("Closing KVAH must be >= Opening KVAH.")
            if errs:
                for x in errs:
                    st.error("❌ " + x)
                st.stop()
 
            net_kwh = ckwh - okwh
            net_kvah = ckvh - okvah
            payload = {
                "date": date_str,
                "toll_plaza": plaza,
                "consumer_number": consumer,
                "opening_kwh": okwh,
                "closing_kwh": ckwh,
                "net_kwh": net_kwh,
                "opening_kvah": okvah,
                "closing_kvah": ckvh,
                "net_kvah": net_kvah,
                "pf": pf,
                "md": md,
                "remarks": (st.session_state[k_sol] or "").strip()
            }
            r1 = insert_reading(payload)
            if getattr(r1, "error", None):
                st.error(f"❌ Submit failed: {r1.error}")
                st.stop()
            r2 = upsert_live(plaza, consumer, ckwh, ckvh)
            if getattr(r2, "error", None):
                st.error(f"❌ Live update failed: {r2.error}")
                st.stop()
 
            st.success(f"Saved. Net KWH: {net_kwh:.2f} | Net KVAH: {net_kvah:.2f}")
            # keep context but reset optional fields
            st.session_state[k_ckwh] = f"{ckwh:.2f}"
            st.session_state[k_ckvh] = f"{ckvh:.2f}"
            st.session_state[k_pf] = ""
            st.session_state[k_md] = ""
            st.session_state[k_sol] = ""
 
    elif page == "Admin Init":
        st.header("Admin Init")
        plaza = st.selectbox("Plaza", PLAZAS)
        consumer = PLAZA_CONSUMER.get(plaza, "N/A")
st.info(f"Consumer: {consumer}")
        t1 = st.text_input("Opening KWH", "0")
        t2 = st.text_input("Opening KVAH", "0")
        if st.button("Save Opening", type="primary"):
            v1, e1 = f2(t1, "Opening KWH")
            v2, e2 = f2(t2, "Opening KVAH")
            for e in (e1, e2):
                if e:
                    st.error(e)
            if not (e1 or e2):
                r = upsert_live(plaza, consumer, v1, v2)
                if getattr(r, "error", None):
                    st.error(f"❌ {r.error}")
                else:
                    st.success("Saved.")
 
    elif page == "Last 10":
        st.header("Last 10 Readings")
        plaza = st.selectbox("Plaza", PLAZAS)
        r = db.table("eb_meter_readings").select("*") \
            .eq("toll_plaza", plaza).order("id", desc=True).limit(10).execute()
        if getattr(r, "error", None):
            st.error(f"❌ Fetch error: {r.error}")
        elif r.data:
            st.dataframe(pd.DataFrame(r.data), use_container_width=True)
        else:
st.info("No data found.")
 
    elif page == "Download CSV":
        st.header("Download CSV")
        f = st.date_input("From", datetime.now() - timedelta(days=7))
        t = st.date_input("To", datetime.now())
        if st.button("Download"):
            r = db.table("eb_meter_readings").select("*") \
                .gte("date", f.strftime("%Y-%m-%d")) \
                .lte("date", t.strftime("%Y-%m-%d")).execute()
            if getattr(r, "error", None):
                st.error(f"❌ Fetch error: {r.error}")
            elif r.data:
                df = pd.DataFrame(r.data)
                st.download_button(
                    "Save CSV",
                    df.to_csv(index=False).encode(),
                    "eb_meter_readings.csv",
                    "text/csv"
                )
            else:
st.info("No data in range.")
 
if __name__ == "__main__":
    run()
