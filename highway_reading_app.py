import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import os
 
# Supabase setup
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key)
 
def run():
    st.title("🚦 Highway Energy Meter Reading")
 
    menu = ["User Block", "Admin Block", "Last 10 Transactions", "Download CSV"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    if choice == "User Block":
        st.header("📥 User Block - Enter Readings")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        
        # Fetch consumer numbers for the selected plaza
        consumers = supabase.table("highway_consumers").select("*").eq("toll_plaza", toll_plaza).execute().data
        if consumers:
            consumer_numbers = [c["consumer_number"] for c in consumers]
            consumer_number = st.selectbox("Select Consumer Number", consumer_numbers)
 
            # Fetch live opening values
            live = supabase.table("highway_live_status").select("*").eq("toll_plaza", toll_plaza).eq("consumer_number", consumer_number).execute().data
            if live:
                opening_kwh = live[0]["opening_kwh"]
                opening_kvah = live[0]["opening_kvah"]
            else:
                opening_kwh = 0.0
                opening_kvah = 0.0
 
            st.info(f"Opening KWH: {opening_kwh}")
            st.info(f"Opening KVAH: {opening_kvah}")
 
            date = st.date_input("Select Date", datetime.now()).strftime("%d-%m-%Y")
            closing_kwh = st.number_input("Closing KWH", min_value=opening_kwh, value=opening_kwh)
            closing_kvah = st.number_input("Closing KVAH", min_value=opening_kvah, value=opening_kvah)
            pf = st.number_input("Power Factor (0-1)", min_value=0.0, max_value=1.0, step=0.01)
            md = st.number_input("Maximum Demand (kVA)", min_value=0.0)
            remarks = st.text_area("Remarks (optional)")
 
            net_kwh = closing_kwh - opening_kwh
            net_kvah = closing_kvah - opening_kvah
            st.success(f"Net KWH: {net_kwh}")
            st.success(f"Net KVAH: {net_kvah}")
 
            if st.button("Submit Entry"):
                try:
                    supabase.table("highway_meter_readings").insert({
                        "date": date,
                        "toll_plaza": toll_plaza,
                        "consumer_number": consumer_number,
                        "opening_kwh": opening_kwh,
                        "closing_kwh": closing_kwh,
                        "net_kwh": net_kwh,
                        "opening_kvah": opening_kvah,
                        "closing_kvah": closing_kvah,
                        "net_kvah": net_kvah,
                        "pf": pf,
                        "md": md,
                        "remarks": remarks
                    }).execute()
 
                    # Update live status
                    supabase.table("highway_live_status").upsert({
                        "toll_plaza": toll_plaza,
                        "consumer_number": consumer_number,
                        "opening_kwh": closing_kwh,
                        "opening_kvah": closing_kvah
                    }).execute()
 
                    st.success("✅ Data submitted and live values updated.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Submission failed: {e}")
 
        else:
            st.warning("No consumer numbers initialized for this Toll Plaza. Contact admin.")
 
    elif choice == "Admin Block":
        st.header("🔐 Admin Block - Initialize Consumer & Values")
        password = st.text_input("Enter Admin Password", type="password")
        if password == "Sekura@2025":
            st.success("Access Granted.")
            toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
            consumer_number = st.text_input("Enter Consumer Number")
 
            init_kwh = st.number_input("Initialize Opening KWH", min_value=0.0)
            init_kvah = st.number_input("Initialize Opening KVAH", min_value=0.0)
 
            if st.button("Save Initialization"):
                try:
                    # Add consumer if not exists
                    supabase.table("highway_consumers").upsert({
                        "toll_plaza": toll_plaza,
                        "consumer_number": consumer_number
                    }).execute()
 
                    # Initialize live status
                    supabase.table("highway_live_status").upsert({
                        "toll_plaza": toll_plaza,
                        "consumer_number": consumer_number,
                        "opening_kwh": init_kwh,
                        "opening_kvah": init_kvah
                    }).execute()
 
                    st.success("✅ Initialization saved.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to initialize: {e}")
        else:
            if password != "":
                st.error("Incorrect password.")
 
    elif choice == "Last 10 Transactions":
        st.header("📄 Last 10 Transactions")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        consumer_number = st.text_input("Enter Consumer Number to Filter (Optional)", "")
        query = supabase.table("highway_meter_readings").select("*").eq("toll_plaza", toll_plaza)
        if consumer_number:
            query = query.eq("consumer_number", consumer_number)
        data = query.order("id", desc=True).limit(10).execute().data
        df = pd.DataFrame(data)
        st.dataframe(df)
 
    elif choice == "Download CSV":
        st.header("📥 Download CSV Records")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        from_date = st.date_input("From Date")
        to_date = st.date_input("To Date")
        if st.button("Download CSV"):
            data = supabase.table("highway_meter_readings").select("*").eq("toll_plaza", toll_plaza).execute().data
            df = pd.DataFrame(data)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", csv, "highway_meter_readings.csv", "text/csv")
 
