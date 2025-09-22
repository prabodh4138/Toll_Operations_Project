import os
from datetime import datetime, date
import pandas as pd
import streamlit as st
from supabase import create_client
 
st.set_page_config(page_title="🛣️ Highway Energy Meter Reading", layout="wide")
 
# Supabase connection
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
if not URL or not KEY:
    st.error("Set SUPABASE_URL and SUPABASE_KEY as environment variables.")
    st.stop()
sb = create_client(URL, KEY)
 
def run():
    st.title("🛣️ Highway Energy Meter Reading")
    debug = st.sidebar.checkbox("Enable debug", value=False)
    menu = ["User Block", "Last 10 Readings", "Admin Block", "Download CSV"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    # --- User Block ---
    if choice == "User Block":
        st.header("Enter Readings")
        d = st.date_input("Select Date", value=date.today())
        toll = st.selectbox("Toll Plaza", ["TP01","TP02","TP03"])
 
        # fetch consumers
        resp = sb.table("highway_consumers").select("consumer_number").eq("toll_plaza", toll).execute()
        consumers = [r["consumer_number"] for r in resp.data] if resp.data else []
        if not consumers:
            st.warning("No consumers for this Toll Plaza. Add via Admin Block.")
            return
        cons = st.selectbox("Consumer Number", consumers)
 
        # fetch live openings
        live = sb.table("highway_live_status").select("opening_kwh, opening_kvah") \
            .eq("toll_plaza", toll).eq("consumer_number", cons).limit(1).execute()
        opening_kwh = float(live.data[0].get("opening_kwh",0)) if live.data else 0.0
        opening_kvah = float(live.data[0].get("opening_kvah",0)) if live.data else 0.0
 
        st.info(f"Opening KWH: {opening_kwh:.2f}")
        ckwh = st.number_input("Closing KWH", min_value=opening_kwh, value=opening_kwh, format="%.2f")
        st.success(f"Net KWH: {ckwh-opening_kwh:.2f}")
 
        st.info(f"Opening KVAH: {opening_kvah:.2f}")
        ckvah = st.number_input("Closing KVAH", min_value=opening_kvah, value=opening_kvah, format="%.2f")
        st.success(f"Net KVAH: {ckvah-opening_kvah:.2f}")
 
        pf = st.number_input("PF", min_value=0.0, max_value=1.0, value=1.0, step=0.01)
        md = st.number_input("MD (kVA)", min_value=0.0, value=0.0, step=0.1)
        remarks = st.text_area("Remarks")
 
        if st.button("Submit Reading"):
            try:
                data = {
                    "date": d.isoformat(), "toll_plaza": toll, "consumer_number": cons,
                    "opening_kwh": opening_kwh, "closing_kwh": ckwh, "net_kwh": ckwh-opening_kwh,
                    "opening_kvah": opening_kvah, "closing_kvah": ckvah, "net_kvah": ckvah-opening_kvah,
                    "pf": pf, "md": md, "remarks": remarks, "created_at": datetime.utcnow().isoformat()
                }
                sb.table("highway_meter_readings").insert(data).execute()
                sb.table("highway_live_status").upsert(
                    {"toll_plaza": toll, "consumer_number": cons, "opening_kwh": ckwh, "opening_kvah": ckvah},
                    on_conflict="toll_plaza,consumer_number"
                ).execute()
                st.success("✅ Reading submitted. Closing saved as next opening.")
                st.rerun()   # <-- new API
            except Exception as e:
                st.error(f"Submission failed: {e}")
 
    # --- Last 10 Readings ---
    elif choice == "Last 10 Readings":
        st.header("Last 10 Readings")
        resp = sb.table("highway_meter_readings").select("*").order("id", desc=True).limit(10).execute()
        if resp.data: st.dataframe(pd.DataFrame(resp.data))
        else: st.info("No readings found.")
 
    # --- Admin Block ---
    elif choice == "Admin Block":
        st.header("Add Consumer")
        toll = st.selectbox("Toll Plaza", ["TP01","TP02","TP03"])
        cons = st.text_input("Consumer Number")
        okwh = st.number_input("Initial Opening KWH", min_value=0.0, value=0.0)
        okvah = st.number_input("Initial Opening KVAH", min_value=0.0, value=0.0)
        if st.button("Add/Init Consumer"):
            try:
                payload = {"toll_plaza": toll, "consumer_number": cons, "opening_kwh": okwh, "opening_kvah": okvah}
                sb.table("highway_consumers").upsert(payload, on_conflict="toll_plaza,consumer_number").execute()
                sb.table("highway_live_status").upsert(payload, on_conflict="toll_plaza,consumer_number").execute()
                st.success("✅ Consumer added/initialized.")
                st.rerun()
            except Exception as e:
                st.error(f"Init failed: {e}")
 
    # --- Download CSV ---
    elif choice == "Download CSV":
        st.header("Download All")
        resp = sb.table("highway_meter_readings").select("*").execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            st.download_button("⬇️ Download CSV", df.to_csv(index=False).encode(),
                               file_name=f"highway_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                               mime="text/csv")
            st.dataframe(df.head(50))
        else: st.info("No data available.")
 
if __name__ == "__main__":
    run()
