import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import os
 
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
 
def run():
    st.title("🌉 Highway Energy Meter Reading")
 
    menu = ["User Block", "Last 10 Readings", "Download CSV", "Admin Block"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    if choice == "User Block":
        st.header("📝 Highway Energy Meter Reading Entry")
 
        date = st.date_input("Select Date", datetime.now()).strftime("%d-%m-%Y")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
 
        # Fetch consumer list for toll plaza
        resp = supabase.table("highway_consumers").select("consumer_no").eq("toll_plaza", toll_plaza).execute()
        consumers = [row["consumer_no"] for row in resp.data] if resp.data else []
        consumer_no = st.selectbox("Select Consumer Number", consumers) if consumers else st.warning("No consumer numbers found. Please initialize in Admin Block.")
 
        if consumers:
            # Fetch last readings
            resp = supabase.table("highway_meter_readings").select("*").eq("toll_plaza", toll_plaza).eq("consumer_no", consumer_no).order("id", desc=True).limit(1).execute()
            if resp.data:
                last_entry = resp.data[0]
                opening_kwh = last_entry["closing_kwh"]
                opening_kvah = last_entry["closing_kvah"]
            else:
                opening_kwh = 0.0
                opening_kvah = 0.0
 
            st.info(f"Opening KWH: {opening_kwh}")
            st.info(f"Opening KVAH: {opening_kvah}")
 
            closing_kwh = st.number_input("Closing KWH", min_value=opening_kwh)
            closing_kvah = st.number_input("Closing KVAH", min_value=opening_kvah)
            pf = st.number_input("Power Factor (0-1)", min_value=0.0, max_value=1.0)
            md = st.number_input("Maximum Demand (kVA)", min_value=0.0)
            remarks = st.text_area("Remarks (optional)")
 
            net_kwh = closing_kwh - opening_kwh
            net_kvah = closing_kvah - opening_kvah
 
            if st.button("Submit Entry"):
                try:
                    supabase.table("highway_meter_readings").insert({
                        "date": date,
                        "toll_plaza": toll_plaza,
                        "consumer_no": consumer_no,
                        "opening_kwh": opening_kwh,
                        "closing_kwh": closing_kwh,
                        "net_kwh": net_kwh,
                        "opening_kvah": opening_kvah,
                        "closing_kvah": closing_kvah,
                        "net_kvah": net_kvah,
                        "pf": pf,
                        "md": md,
                        "remarks": remarks,
                        "timestamp": datetime.now().isoformat()
                    }).execute()
                    st.success("✅ Entry submitted successfully.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {e}")
 
    elif choice == "Last 10 Readings":
        st.header("📊 Last 10 Highway Meter Readings")
        toll_plaza = st.selectbox("Filter by Toll Plaza", ["TP01", "TP02", "TP03"])
        resp = supabase.table("highway_meter_readings").select("*").eq("toll_plaza", toll_plaza).order("id", desc=True).limit(10).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            st.dataframe(df)
        else:
            st.info("No data available.")
 
    elif choice == "Download CSV":
        st.header("📥 Download Highway Meter CSV Records")
        toll_plaza = st.selectbox("Select Toll Plaza for Download", ["TP01", "TP02", "TP03"])
        resp = supabase.table("highway_meter_readings").select("*").eq("toll_plaza", toll_plaza).order("id", desc=True).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download CSV", csv, f"{toll_plaza}_highway_meter_readings.csv", "text/csv")
        else:
            st.info("No data available for download.")
 
    elif choice == "Admin Block":
        st.header("🔐 Admin Block")
        password = st.text_input("Enter Admin Password", type="password")
        if password == "Sekura@2025":
            st.success("Access Granted. Add Consumer Numbers for Highway Meter Reading.")
            toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
            consumer_no = st.text_input("Enter Consumer Number to Add")
            if st.button("Add Consumer Number"):
                try:
                    supabase.table("highway_consumers").insert({
                        "toll_plaza": toll_plaza,
                        "consumer_no": consumer_no
                    }).execute()
                    st.success("✅ Consumer Number Added.")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
        else:
            if password != "":
                st.error("Incorrect Password.")
 
