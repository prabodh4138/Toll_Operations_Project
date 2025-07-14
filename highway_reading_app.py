import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime, timedelta
import time
import os
 
# ---------------- Supabase Connection -----------------
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)
 
def run():
    st.title("🚦 Highway Meter Reading - Toll Operations")
 
    menu = ["User Block", "Last 10 Transactions", "Admin Block", "Download CSV"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    # ---------------- Helper: Fetch Consumers ----------------
    def fetch_consumers(toll_plaza):
        resp = supabase.table("highway_consumers").select("*").eq("toll_plaza", toll_plaza).execute()
        if resp.data:
            return [item["consumer_number"] for item in resp.data]
        else:
            return []
 
    # ---------------- Helper: Fetch Live Status ----------------
    def fetch_live_status(toll_plaza, consumer_number):
        resp = supabase.table("highway_live_status").select("*").eq("toll_plaza", toll_plaza).eq("consumer_no", consumer_no).execute()
        if resp.data:
            data = resp.data[0]
            return data["opening_kwh"], data["opening_kvah"]
        else:
            return 0.0, 0.0
 
    # ---------------- Helper: Update Live Status ----------------
    def update_live_status(toll_plaza, consumer_number, opening_kwh, opening_kvah):
        supabase.table("highway_live_status").upsert({
            "toll_plaza": toll_plaza,
            "consumer_number": consumer_number,
            "opening_kwh": opening_kwh,
            "opening_kvah": opening_kvah
        }).execute()
 
    # ---------------- User Block ----------------
    if choice == "User Block":
        st.header("📝 User Block - Data Entry")
 
        date = st.date_input("Select Date", datetime.now()).strftime("%d-%m-%Y")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        consumer_list = fetch_consumers(toll_plaza)
        if not consumer_list:
            st.warning("⚠️ No consumers available for this Toll Plaza. Please ask Admin to add consumers first.")
            return
 
        consumer_number = st.selectbox("Select Consumer Number", consumer_list)
        opening_kwh, opening_kvah = fetch_live_status(toll_plaza, consumer_number)
 
        st.info(f"**Opening KWH (Auto): {opening_kwh}**")
        st.info(f"**Opening KVAH (Auto): {opening_kvah}**")
 
        closing_kwh = st.number_input("Closing KWH (Must be >= Opening KWH)", min_value=opening_kwh)
        closing_kvah = st.number_input("Closing KVAH (Must be >= Opening KVAH)", min_value=opening_kvah)
        pf = st.number_input("Power Factor (0-1)", min_value=0.0, max_value=1.0)
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
                    "remarks": remarks,
                    "timestamp": datetime.now().isoformat()
                }).execute()
 
                update_live_status(toll_plaza, consumer_number, closing_kwh, closing_kvah)
                st.success("✅ Data submitted successfully and updated in database.")
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"❌ Submission failed: {e}")
 
    # ---------------- Last 10 Transactions ----------------
    elif choice == "Last 10 Transactions":
        st.header("📄 Last 10 Transactions")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        consumer_list = fetch_consumers(toll_plaza)
        if consumer_list:
            consumer_number = st.selectbox("Select Consumer Number", consumer_list)
            resp = supabase.table("highway_meter_readings").select("*").eq("toll_plaza", toll_plaza).eq("consumer_number", consumer_number).order("id", desc=True).limit(10).execute()
            if resp.data:
                df = pd.DataFrame(resp.data)
                st.dataframe(df)
            else:
                st.info("No records found.")
        else:
            st.warning("⚠️ No consumers available for this Toll Plaza.")
 
    # ---------------- Admin Block ----------------
    elif choice == "Admin Block":
        st.header("🔐 Admin Block")
        password = st.text_input("Enter Admin Password", type="password")
        if password == "Sekura@2025":
            st.success("Access Granted.")
 
            st.subheader("➕ Add Consumer")
            toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"], key="admin_tp")
            consumer_number = st.text_input("Enter Consumer Number")
            if st.button("Add Consumer"):
                try:
                    supabase.table("highway_consumers").insert({
                        "toll_plaza": toll_plaza,
                        "consumer_number": consumer_number
                    }).execute()
                    st.success("✅ Consumer added successfully.")
                except Exception as e:
                    st.error(f"❌ Failed to add consumer: {e}")
 
            st.subheader("🛠️ Initialize Opening Readings")
            consumer_list = fetch_consumers(toll_plaza)
            if consumer_list:
                consumer_number_init = st.selectbox("Select Consumer for Initialization", consumer_list, key="admin_consumer_init")
                init_kwh = st.number_input("Initialize Opening KWH", min_value=0.0)
                init_kvah = st.number_input("Initialize Opening KVAH", min_value=0.0)
                if st.button("Save Initialization"):
                    try:
                        update_live_status(toll_plaza, consumer_number_init, init_kwh, init_kvah)
                        st.success("✅ Initialization data saved and synced to user block.")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to initialize: {e}")
            else:
                st.info("ℹ️ Please add consumers first.")
 
        elif password != "":
            st.error("Incorrect password.")
 
    # ---------------- CSV Download ----------------
    elif choice == "Download CSV":
        st.header("📥 Download CSV Records")
        from_date = st.date_input("From Date", datetime.now() - timedelta(days=7))
        to_date = st.date_input("To Date", datetime.now())
        if st.button("Download CSV"):
            resp = supabase.table("highway_meter_readings").select("*").gte("date", from_date.strftime("%d-%m-%Y")).lte("date", to_date.strftime("%d-%m-%Y")).execute()
            if resp.data:
                df = pd.DataFrame(resp.data)
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Highway Meter Readings CSV", csv, "highway_meter_readings.csv", "text/csv")
            else:
                st.info("No records found for the selected period.")
 
