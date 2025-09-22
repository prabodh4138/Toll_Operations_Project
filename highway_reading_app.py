import os
from datetime import datetime, date
import pandas as pd
import streamlit as st
from supabase import create_client
 
st.set_page_config(page_title="🛣️ Highway Energy Meter Reading", layout="wide")
 
# --- Supabase Connection ---
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
if not url or not key:
    st.error("Set SUPABASE_URL and SUPABASE_KEY as environment variables.")
    st.stop()
supabase = create_client(url, key)
 
def run():
    st.title("🛣️ Highway Energy Meter Reading")
    debug = st.sidebar.checkbox("Enable debug", value=False)
    menu = ["User Block", "Last 10 Readings", "Admin Block", "Download CSV"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    # --- User Block ---
    if choice == "User Block":
        st.header("🛠️ User Block - Enter Highway Readings")
        date_obj = st.date_input("Select Date", value=date.today())
        iso_date = date_obj.isoformat()
        st.info(f"Selected Date: {date_obj.strftime('%d-%m-%Y')}")
 
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        resp = supabase.table("highway_consumers").select("consumer_number").eq("toll_plaza", toll_plaza).execute()
        if debug: st.write(resp)
        consumers = [r["consumer_number"] for r in resp.data] if resp.data else []
        if not consumers:
            st.warning("No consumers found for this Toll Plaza.")
            return
        consumer_number = st.selectbox("Select Consumer Number", consumers)
 
        live = supabase.table("highway_live_status").select("opening_kwh, opening_kvah") \
            .eq("toll_plaza", toll_plaza).eq("consumer_number", consumer_number).execute()
        if debug: st.write(live)
        opening_kwh = float(live.data[0].get("opening_kwh", 0)) if live.data else 0.0
        opening_kvah = float(live.data[0].get("opening_kvah", 0)) if live.data else 0.0
 
        st.info(f"Opening KWH: {opening_kwh:.2f}")
        closing_kwh = st.number_input("Closing KWH", min_value=opening_kwh, value=opening_kwh, format="%.2f")
        net_kwh = closing_kwh - opening_kwh
        st.success(f"Net KWH: {net_kwh:.2f}")
 
        st.info(f"Opening KVAH: {opening_kvah:.2f}")
        closing_kvah = st.number_input("Closing KVAH", min_value=opening_kvah, value=opening_kvah, format="%.2f")
        net_kvah = closing_kvah - opening_kvah
        st.success(f"Net KVAH: {net_kvah:.2f}")
 
        pf = st.number_input("Power Factor (PF)", min_value=0.0, max_value=1.0, step=0.01, value=1.0, format="%.2f")
        md = st.number_input("Maximum Demand (MD in kVA)", min_value=0.0, step=0.1, value=0.0, format="%.2f")
        remarks = st.text_area("Remarks (optional)")
 
        if st.button("Submit Reading"):
            try:
                data = {
                    "date": iso_date, "toll_plaza": toll_plaza, "consumer_number": consumer_number,
                    "opening_kwh": opening_kwh, "closing_kwh": closing_kwh, "net_kwh": net_kwh,
                    "opening_kvah": opening_kvah, "closing_kvah": closing_kvah, "net_kvah": net_kvah,
                    "pf": pf, "md": md, "remarks": remarks, "created_at": datetime.utcnow().isoformat()
                }
                ins = supabase.table("highway_meter_readings").insert(data).execute()
                if debug: st.write(ins)
                live_payload = {"toll_plaza": toll_plaza, "consumer_number": consumer_number,
                                "opening_kwh": closing_kwh, "opening_kvah": closing_kvah}
                up = supabase.table("highway_live_status").upsert(live_payload, on_conflict="toll_plaza,consumer_number").execute()
                if debug: st.write(up)
                st.success("✅ Reading submitted successfully.")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"❌ Submission failed: {e}")
 
    # --- Last 10 Readings ---
    elif choice == "Last 10 Readings":
        st.header("📊 Last 10 Highway Meter Readings")
        try:
            resp = supabase.table("highway_meter_readings").select("*").order("id", desc=True).limit(10).execute()
            if debug: st.write(resp)
            if resp.data: st.dataframe(pd.DataFrame(resp.data))
            else: st.info("No readings found.")
        except Exception as e: st.error(e)
 
    # --- Admin Block ---
    elif choice == "Admin Block":
        st.header("🛠️ Admin Block - Add Consumer")
        toll_plaza = st.selectbox("Toll Plaza", ["TP01", "TP02", "TP03"])
        consumer_number = st.text_input("Consumer Number")
        opening_kwh = st.number_input("Initial Opening KWH", min_value=0.0, value=0.0, format="%.2f")
        opening_kvah = st.number_input("Initial Opening KVAH", min_value=0.0, value=0.0, format="%.2f")
        if st.button("Add Consumer"):
            try:
                payload = {"toll_plaza": toll_plaza, "consumer_number": consumer_number,
                           "opening_kwh": opening_kwh, "opening_kvah": opening_kvah}
                supabase.table("highway_consumers").upsert(payload, on_conflict="toll_plaza,consumer_number").execute()
                supabase.table("highway_live_status").upsert(payload, on_conflict="toll_plaza,consumer_number").execute()
                st.success("✅ Consumer added and initialized successfully.")
                st.experimental_rerun()
            except Exception as e: st.error(f"❌ Initialization failed: {e}")
 
    # --- Download CSV ---
    elif choice == "Download CSV":
        st.header("⬇️ Download Highway Meter Readings")
        try:
            resp = supabase.table("highway_meter_readings").select("*").execute()
            if debug: st.write(resp)
            if resp.data:
                df = pd.DataFrame(resp.data)
                st.download_button("Download CSV", df.to_csv(index=False).encode(),
                                   file_name=f"highway_readings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                   mime="text/csv")
                st.dataframe(df.head(50))
            else: st.info("No data available.")
        except Exception as e: st.error(e)
 
if __name__ == "__main__":
    run()
 
