import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import pandas as pd
import time
import os
 
# ----------------- Supabase Initialization -----------------
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key)
 
# ----------------- App Core -----------------
def run():
    st.title("⚡ EB Meter Reading - Toll Operations")
 
    menu = ["User Block", "Last 10 Transactions", "Admin Block", "Download CSV"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    if choice == "User Block":
        st.header("🛠️ User Block - Data Entry")
 
        date = st.date_input("Select Date", datetime.now()).strftime("%d-%m-%Y")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
 
        # Fetch consumer number for this toll plaza
        consumer_data = supabase.table("eb_consumers").select("*").eq("toll_plaza", toll_plaza).execute()
        consumer_numbers = [item["consumer_number"] for item in consumer_data.data]
        consumer_number = st.selectbox("Select Consumer Number", consumer_numbers)
 
        # Fetch live opening values
        resp = supabase.table("eb_live_status").select("*").eq("toll_plaza", toll_plaza).eq("consumer_number", consumer_number).execute()
        if resp.data:
            opening_kwh = resp.data[0]["opening_kwh"]
            opening_kvah = resp.data[0]["opening_kvah"]
        else:
            opening_kwh = 0.0
            opening_kvah = 0.0
 
        st.info(f"**Opening KWH (Virtual): {opening_kwh}**")
        st.info(f"**Opening KVAH (Virtual): {opening_kvah}**")
 
        closing_kwh = st.number_input("Closing KWH", min_value=opening_kwh, step=0.01, format="%.2f")
        net_kwh = closing_kwh - opening_kwh
        st.success(f"Net KWH: {net_kwh}")
 
        closing_kvah = st.number_input("Closing KVAH", min_value=opening_kvah, step=0.01, format="%.2f")
        net_kvah = closing_kvah - opening_kvah
        st.success(f"Net KVAH: {net_kvah}")
 
        pf = st.number_input("Power Factor (0-1)", min_value=0.0, max_value=1.0, step=0.01, format="%.2f")
        md = st.number_input("Maximum Demand (kVA)", min_value=0.0, step=0.01, format="%.2f")
        remarks = st.text_area("Remarks (Optional)")
 
        if st.button("Submit Entry"):
            try:
                # Insert data
                supabase.table("eb_meter_readings").insert({
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
                    "remarks": remarks,
                    "timestamp": datetime.now().isoformat()
                }).execute()
 
                # Update live status for next opening
                supabase.table("eb_live_status").upsert({
                    "toll_plaza": toll_plaza,
                    "consumer_number": consumer_number,
                    "opening_kwh": closing_kwh,
                    "opening_kvah": closing_kvah
                }).execute()
 
                st.success("✅ Data submitted and updated successfully.")
                time.sleep(1)
                st.rerun()
 
            except Exception as e:
                st.error(f"❌ Submission failed: {e}")
 
    elif choice == "Last 10 Transactions":
        st.header("📄 Last 10 Transactions")
        toll_plaza = st.selectbox("Filter by Toll Plaza", ["TP01", "TP02", "TP03"])
        consumer_number = st.text_input("Consumer Number (optional)", "")
 
        query = supabase.table("eb_meter_readings").select("*").eq("toll_plaza", toll_plaza)
        if consumer_number.strip() != "":
            query = query.eq("consumer_number", consumer_number.strip())
        query = query.order("id", desc=True).limit(10)
        data = query.execute().data
 
        if data:
            df = pd.DataFrame(data)
            st.dataframe(df)
        else:
            st.info("No transactions found.")
 
    elif choice == "Admin Block":
        st.header("🔐 Admin Block - Initialization")
        password = st.text_input("Enter Admin Password", type="password")
 
        if password == "Sekura@2025":
            st.success("Access Granted. Initialize Data Below:")
 
            toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
            consumer_number = st.text_input("Consumer Number")
 
            init_opening_kwh = st.number_input("Initialize Opening KWH", min_value=0.0, step=0.01, format="%.2f")
            init_opening_kvah = st.number_input("Initialize Opening KVAH", min_value=0.0, step=0.01, format="%.2f")
 
            if st.button("Save Initialization"):
                try:
                    supabase.table("eb_live_status").upsert({
                        "toll_plaza": toll_plaza,
                        "consumer_number": consumer_number,
                        "opening_kwh": init_opening_kwh,
                        "opening_kvah": init_opening_kvah
                    }).execute()
                    st.success("✅ Initialization saved successfully.")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to initialize: {e}")
        else:
            if password != "":
                st.error("Incorrect password.")
 
    elif choice == "Download CSV":
        st.header("📥 Download EB Meter Readings as CSV")
 
        from_date = st.date_input("From Date", datetime.now() - timedelta(days=7))
        to_date = st.date_input("To Date", datetime.now())
 
        if st.button("Download CSV"):
            try:
                data = supabase.table("eb_meter_readings").select("*").gte("date", from_date.strftime("%d-%m-%Y")).lte("date", to_date.strftime("%d-%m-%Y")).execute().data
                if data:
                    df = pd.DataFrame(data)
                    csv = df.to_csv(index=False).encode("utf-8")
                    st.download_button("📥 Click to Download CSV", csv, "eb_meter_readings.csv", "text/csv")
                else:
                    st.info("No data available for selected date range.")
            except Exception as e:
                st.error(f"❌ Failed to download CSV: {e}")
 
