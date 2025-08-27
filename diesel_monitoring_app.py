# dg_module_app.py  — NO @st.cache_data anywhere (fixes UnserializableReturnValueError)
import os, streamlit as st
from datetime import datetime
import pandas as pd
from supabase import create_client
 
# ---------- Environment ----------
URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_KEY")
if not URL or not KEY:
    st.error("Missing SUPABASE_URL or SUPABASE_KEY"); st.stop()
 
# ---------- Supabase client (resource cache OK) ----------
@st.cache_resource
def get_client():
    return create_client(URL, KEY)
sb = get_client()
 
# ---------- Helpers ----------
PLAZAS = ["TP01","TP02","TP03"]; DGS = ["DG1","DG2"]
 
def to_float(s, name):
    s = (s or "").strip()
    if s == "": return 0.0, None
    try: return float(s), None
    except: return None, f"❌ {name}: enter a number"
 
def parse_rh(s):
    try:
        h,m = str(s).strip().split(":"); h=int(h); m=int(m)
        if h<0 or m<0 or m>=60: return None
        return h*60+m
    except: return None
 
def rh_delta(open_rh, close_rh):
    a,b = parse_rh(open_rh), parse_rh(close_rh)
    if a is None or b is None: return None,"❌ RH must be hh:mm"
    if b<a: return None,"❌ Closing RH ≥ Opening RH"
    d=b-a; return f"{d//60}:{d%60:02d}", None
 
# ---------- Fetchers (return PLAIN DICTS, never Supabase objects) ----------
def fetch_opening(plaza, dg):
    r = sb.table("dg_opening_status").select(
        "toll_plaza,dg_name,opening_diesel_stock,opening_kwh,opening_rh"
    ).eq("toll_plaza", plaza).eq("dg_name", dg).single().execute()
    return {"data": r.data, "error": str(getattr(r, "error", "")) or None}
 
def fetch_live(plaza):
    r = sb.table("dg_live_status").select(
        "toll_plaza,updated_plaza_barrel_stock"
    ).eq("toll_plaza", plaza).single().execute()
    return {"data": r.data, "error": str(getattr(r, "error", "")) or None}
 
def insert(table, data):  return sb.table(table).insert(data).execute()
def upsert(table, data):  return sb.table(table).upsert(data).execute()
 
# ---------- UI ----------
def run():
    st.title("⚡ DG Monitoring (no data caching)")
 
    # Safety: clear any previous cache from older runs that used @st.cache_data
    colA, colB = st.columns([1,1])
    with colA:
        if st.button("🧹 Force Clear Cache"):
            try:
                st.cache_data.clear()     # no-op if not used, safe to call
                st.cache_resource.clear() # clears old clients if needed
            except Exception:
                pass
            st.success("Cleared Streamlit caches. Reloading…")
            st.rerun()
    with colB:
        page = st.selectbox("Menu", ["User Entry","Admin Init","Last 10"])
 
    # ---------- Admin Init ----------
    if page=="Admin Init":
        pl = st.selectbox("Toll Plaza", PLAZAS); dg = st.selectbox("DG", DGS)
        open_diesel = st.text_input("Opening Diesel Stock (L)","0")
        open_kwh    = st.text_input("Opening KWH","0")
        open_rh     = st.text_input("Opening RH (hh:mm)","",placeholder="4435:12")
        if st.button("Initialize", type="primary"):
            v1,e1 = to_float(open_diesel,"Opening Diesel"); v2,e2 = to_float(open_kwh,"Opening KWH")
            if e1 or e2:
                if e1: st.error(e1)
                if e2: st.error(e2)
                st.stop()
            if parse_rh(open_rh) is None: st.error("❌ RH must be hh:mm"); st.stop()
            r = upsert("dg_opening_status",{
                "toll_plaza":pl,"dg_name":dg,
                "opening_diesel_stock":v1,"opening_kwh":v2,"opening_rh":open_rh or "0:00"
            })
            if getattr(r,"error",None): st.error(r.error)
            else: st.success("✅ Saved")
 
    # ---------- User Entry ----------
    if page=="User Entry":
        with st.form("f", clear_on_submit=False):
            date_str = st.date_input("Entry Date", datetime.now()).strftime("%Y-%m-%d")
            c1,c2,c3 = st.columns([1,1,1])
            with c1: pl = st.selectbox("Toll Plaza", PLAZAS, key="pl")
            with c2: dg = st.selectbox("DG", DGS, key="dg")
            with c3:
                refresh = st.form_submit_button("🔄 Refresh Opening", use_container_width=True)
 
            # Always fetch fresh (no cache) and only return JSON-able dict
            op = fetch_opening(pl,dg)
            if op["error"]:
                st.error(f"Open fetch: {op['error']}")
                sub = st.form_submit_button("Submit", disabled=True)
            elif not op["data"]:
                st.error("❌ Opening not initialized")
                sub = st.form_submit_button("Submit", disabled=True)
            else:
                o = op["data"]
                o_diesel = float(o.get("opening_diesel_stock",0) or 0)
                o_kwh    = float(o.get("opening_kwh",0) or 0)
                o_rh     = str(o.get("opening_rh","0:00") or "0:00")
                st.info(f"Opening Diesel: {o_diesel:.2f} L | Opening KWH: {o_kwh:.2f} | Opening RH: {o_rh}")
 
                lv = fetch_live(pl)
                curr_barrel = float((lv["data"] or {}).get("updated_plaza_barrel_stock",0) or 0)
                st.info(f"Plaza Barrel Stock: {curr_barrel:.2f} L")
 
                # Free-typing inputs (always editable)
                dp  = st.text_input("Diesel Purchase (L)","0")
                dt  = st.text_input("Diesel Topup to DG (L)","0")
                cds = st.text_input("Closing Diesel Stock (L)","0")
                ckwh= st.text_input("Closing KWH", f"{o_kwh:.2f}")
                crh = st.text_input("Closing RH (hh:mm)","",placeholder="4436:30")
                md  = st.text_input("Maximum Demand (kVA)","0")
                rm  = st.text_area("Remarks","")
                sub = st.form_submit_button("Submit", type="primary")
 
        if 'sub' in locals() and sub and op["data"]:
            dp, e1 = to_float(dp,"Diesel Purchase")
            dt, e2 = to_float(dt,"Diesel Topup")
            cds,e3 = to_float(cds,"Closing Diesel Stock")
            ckwh,e4= to_float(ckwh,"Closing KWH")
            md, e5 = to_float(md,"Maximum Demand")
            for e in [e1,e2,e3,e4,e5]:
                if e: st.error(e)
            if any([e1,e2,e3,e4,e5]): st.stop()
 
            errs=[]
            max_close = o_diesel + dt
            if cds > max_close + 1e-9: errs.append(f"Closing Diesel > Opening+Topup ({max_close:.2f} L)")
            if ckwh < o_kwh: errs.append("Closing KWH must be ≥ Opening KWH")
            net_rh, rh_err = rh_delta(o_rh, crh)
            if rh_err: errs.append(rh_err)
            if errs:
                for x in errs: st.error("❌ "+x); st.stop()
 
            diesel_cons = max_close - cds
            upd_barrel  = curr_barrel + dp - dt
            net_kwh     = ckwh - o_kwh
 
            tx = {"date":date_str,"toll_plaza":pl,"dg_name":dg,
                  "diesel_purchase":dp,"diesel_topup":dt,"updated_plaza_barrel_stock":upd_barrel,
                  "opening_diesel_stock":o_diesel,"closing_diesel_stock":cds,"diesel_consumption":diesel_cons,
                  "opening_kwh":o_kwh,"closing_kwh":ckwh,"net_kwh":net_kwh,
                  "opening_rh":o_rh,"closing_rh":crh,"net_rh":net_rh,
                  "maximum_demand":md,"remarks":rm}
 
            r1 = insert("dg_transactions", tx)
            if getattr(r1,"error",None): st.error(f"Submit failed: {r1.error}"); st.stop()
            r2 = upsert("dg_live_status", {"toll_plaza":pl,"updated_plaza_barrel_stock":upd_barrel})
            if getattr(r2,"error",None): st.error(f"Live update failed: {r2.error}"); st.stop()
            r3 = upsert("dg_opening_status", {"toll_plaza":pl,"dg_name":dg,
                                              "opening_diesel_stock":cds,"opening_kwh":ckwh,"opening_rh":crh})
            if getattr(r3,"error",None): st.error(f"Opening update failed: {r3.error}"); st.stop()
 
            st.success("✅ Saved & Opening updated"); st.rerun()
 
    # ---------- Last 10 ----------
    if page=="Last 10":
        pl = st.selectbox("Toll Plaza", PLAZAS, key="tx_plaza")
        r = sb.table("dg_transactions").select("*").eq("toll_plaza",pl).order("id",desc=True).limit(10).execute()
        if getattr(r,"error",None): st.error(f"Fetch error: {r.error}")
        elif r.data:
            df = pd.DataFrame(r.data); st.dataframe(df, use_container_width=True)
            st.download_button("📥 Download CSV", df.to_csv(index=False).encode(), f"{pl}_dg_last10.csv","text/csv")
        else:
            st.info("No transactions found.")
 
if __name__ == "__main__":
    run()
 
