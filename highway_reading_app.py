import os
from datetime import datetime, date
import pandas as pd
import streamlit as st
from supabase import create_client
 
st.set_page_config(page_title="🛣️ Highway Energy Meter Reading", layout="wide")
 
# Supabase client
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
if not URL or not KEY:
    st.error("Set SUPABASE_URL and SUPABASE_KEY env vars.")
    st.stop()
sb = create_client(URL, KEY)
 
def ensure_consumer(toll_plaza, consumer_number, opening_kwh, opening_kvah, debug=False):
    # check exists
    resp = sb.table("highway_consumers").select("id").eq("toll_plaza", toll_plaza).eq("consumer_number", consumer_number).limit(1).execute()
    if debug: st.write("ensure_consumer - select:", resp)
    if resp.data:
        # update
        return sb.table("highway_consumers").update({"opening_kwh": opening_kwh, "opening_kvah": opening_kvah}).eq("toll_plaza", toll_plaza).eq("consumer_number", consumer_number).execute()
    else:
        # insert
        return sb.table("highway_consumers").insert({"toll_plaza": toll_plaza, "consumer_number": consumer_number, "opening_kwh": opening_kwh, "opening_kvah": opening_kvah}).execute()
 
def ensure_live_status(toll_plaza, consumer_number, opening_kwh, opening_kvah, debug=False):
    resp = sb.table("highway_live_status").select("id").eq("toll_plaza", toll_plaza).eq("consumer_number", consumer_number).limit(1).execute()
    if debug: st.write("ensure_live_status - select:", resp)
    if resp.data:
        return sb.table("highway_live_status").update({"opening_kwh": opening_kwh, "opening_kvah": opening_kvah}).eq("toll_plaza", toll_plaza).eq("consumer_number", consumer_number).execute()
    else:
        return sb.table("highway_live_status").insert({"toll_plaza": toll_plaza, "consumer_number": consumer_number, "opening_kwh": opening_kwh, "opening_kvah": opening_kvah}).execute()
 
def run():
    st.title("🛣️ Highway Energy Meter Reading")
    debug = st.sidebar.checkbox("Enable debug", value=False)
    choice = st.sidebar.selectbox("Select", ["User Block", "Last 10 Readings", "Admin Block", "Download CSV"])
 
    if choice == "User Block":
        st.header("Enter Readings")
        date_obj = st.date_input("Select Date", value=date.today())
        iso_date = date_obj.isoformat()
        toll = st.selectbox("Toll Plaza", ["TP01","TP02","TP03"])
        cons_resp = sb.table("highway_consumers").select("consumer_number").eq("toll_plaza", toll).order("consumer_number", desc=False).execute()
        if debug: st.write("cons_resp:", cons_resp)
        consumers = [r["consumer_number"] for r in cons_resp.data] if cons_resp.data else []
        if not consumers:
            st.warning("No consumers found for this Toll Plaza. Ask Admin to add.")
            return
        consumer = st.selectbox("Consumer Number", consumers)
 
        live = sb.table("highway_live_status").select("opening_kwh, opening_kvah").eq("toll_plaza", toll).eq("consumer_number", consumer).limit(1).execute()
        if debug: st.write("live fetch:", live)
        opening_kwh = float(live.data[0].get("opening_kwh",0)) if live.data else 0.0
        opening_kvah = float(live.data[0].get("opening_kvah",0)) if live.data else 0.0
 
        st.info(f"Opening KWH: {opening_kwh:.2f}")
        closing_kwh = st.number_input("Closing KWH", min_value=opening_kwh, value=opening_kwh, format="%.2f")
        net_kwh = closing_kwh - opening_kwh
        st.success(f"Net KWH: {net_kwh:.2f}")
 
        st.info(f"Opening KVAH: {opening_kvah:.2f}")
        closing_kvah = st.number_input("Closing KVAH", min_value=opening_kvah, value=opening_kvah, format="%.2f")
        net_kvah = closing_kvah - opening_kvah
        st.success(f"Net KVAH: {net_kvah:.2f}")
 
        pf = st.number_input("PF", min_value=0.0, max_value=1.0, value=1.0, step=0.01, format="%.2f")
        md = st.number_input("MD (kVA)", min_value=0.0, value=0.0, step=0.1, format="%.2f")
        remarks = st.text_area("Remarks")
 
        if st.button("Submit Reading"):
            try:
                data = {
                    "date": iso_date, "toll_plaza": toll, "consumer_number": consumer,
                    "opening_kwh": opening_kwh, "closing_kwh": float(closing_kwh), "net_kwh": float(net_kwh),
                    "opening_kvah": opening_kvah, "closing_kvah": float(closing_kvah), "net_kvah": float(net_kvah),
                    "pf": float(pf), "md": float(md), "remarks": remarks, "created_at": datetime.utcnow().isoformat()
                }
                ins = sb.table("highway_meter_readings").insert(data).execute()
                if debug: st.write("insert reading:", ins)
                # update live status by select -> update/insert (no ON CONFLICT)
                ensure_live_status(toll, consumer, float(closing_kwh), float(closing_kvah), debug=debug)
                st.success("Reading submitted. Closing saved as next opening.")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Submission failed: {e}")
 
    elif choice == "Last 10 Readings":
        st.header("Last 10")
        try:
            resp = sb.table("highway_meter_readings").select("*").order("id", desc=True).limit(10).execute()
            if debug: st.write(resp)
            if resp.data: st.dataframe(pd.DataFrame(resp.data))
            else: st.info("No readings found.")
        except Exception as e:
            st.error(e)
 
    elif choice == "Admin Block":
        st.header("Add Consumer")
        toll = st.selectbox("Toll Plaza", ["TP01","TP02","TP03"])
        consumer = st.text_input("Consumer Number")
        opening_kwh = st.number_input("Initial Opening KWH", min_value=0.0, value=0.0, format="%.2f")
        opening_kvah = st.number_input("Initial Opening KVAH", min_value=0.0, value=0.0, format="%.2f")
        if st.button("Add/Init Consumer"):
            try:
                ensure_consumer(toll, consumer, float(opening_kwh), float(opening_kvah), debug=debug)
                ensure_live_status(toll, consumer, float(opening_kwh), float(opening_kvah), debug=debug)
                st.success("Consumer added/initialized.")
                st.rerun()
            except Exception as e:
                st.error(f"Init failed: {e}")
 
    elif choice == "Download CSV":
        st.header("Download CSV")
        try:
            resp = sb.table("highway_meter_readings").select("*").execute()
            if resp.data:
                df = pd.DataFrame(resp.data)
                st.download_button("Download CSV", df.to_csv(index=False).encode(), file_name=f"highway_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv")
                st.dataframe(df.head(50))
            else:
                st.info("No data.")
        except Exception as e:
            st.error(e)
 
if __name__ == "__main__":
    run()

