import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import pandas as pd
import os
 
# --------------------- Supabase Connection ---------------------
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key)
 
# --------------------- Consumer Mapping ---------------------
TP_CONSUMER_MAP = {
    "TP01": "416000000110",
    "TP02": "812001020208",
    "TP03": "813000000281"
}
 
# --------------------- Main Function ---------------------
def run():
    st.title("⚡ EB Meter Reading - Toll Operations")
 
    menu = ["User Block", "Last 10 Readings", "Admin Block", "Download CSV"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    # --------------------- User Block ---------------------
    if choice == "User Block":
        st.header("🛠️ User Block - Enter Readings")
 
        date_obj = st.date_input("Select Date", datetime.now())
        date = date_obj.strftime("%Y-%m-%d")
        date_for_display = date_obj.strftime("%d-%m-%Y")
        st.info(f"Selected Date: {date_for_display}")
 
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        consumer_number = TP_CONSUMER_MAP.get(toll_plaza, "N/A")
        st.info(f"Auto Fetched Consumer Number: {consumer_number}")
 
        # Fetch virtual, dynamic opening values from eb_live_status
        opening_kwh = 0.0
        opening_kvah = 0.0
 
        try:
            live_resp = supabase.table("eb_live_status").select("opening_kwh, opening_kvah").eq("toll_plaza", toll_plaza).execute()
            if live_resp.data:
                opening_kwh = live_resp.data[0].get("opening_kwh", 0.0)
                opening_kvah = live_resp.data[0].get("opening_kvah", 0.0)
        except Exception as e:
            st.warning(f"Warning: {e}")
 
        st.info(f"Opening KWH (Auto Fetched): {opening_kwh}")
        closing_kwh = st.number_input("Closing KWH", min_value=opening_kwh, format="%.2f")
        net_kwh = closing_kwh - opening_kwh
        st.success(f"Net KWH: {net_kwh:.2f}")
 
        st.info(f"Opening KVAH (Auto Fetched): {opening_kvah}")
        closing_kvah = st.number_input("Closing KVAH", min_value=opening_kvah, format="%.2f")
        net_kvah = closing_kvah - opening_kvah
        st.success(f"Net KVAH: {net_kvah:.2f}")
 
        pf = st.number_input("Power Factor (PF)", min_value=0.0, max_value=1.0, format="%.2f")
        md = st.number_input("Maximum Demand (MD kVA)", min_value=0.0, format="%.2f")
        remarks = st.text_area("Remarks (optional)")
 
        if st.button("Submit Reading"):
            try:
                data = {
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
                }
                supabase.table("eb_meter_readings").insert(data).execute()
 
                # Update virtual opening values for next day (only if you want auto-forward)
                supabase.table("eb_live_status").upsert({
                    "toll_plaza": toll_plaza,
                    "consumer_number": consumer_number,
                    "opening_kwh": closing_kwh,
                    "opening_kvah": closing_kvah
                }).execute()
 
                st.success("✅ Reading submitted successfully.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Submission failed: {e}")
 
    # --------------------- Last 10 Readings ---------------------
    elif choice == "Last 10 Readings":
        st.header("📄 Last 10 Readings")
 
        toll_plaza = st.selectbox("Filter by Toll Plaza", ["TP01", "TP02", "TP03"])
        resp = supabase.table("eb_meter_readings").select("*").eq("toll_plaza", toll_plaza).order("id", desc=True).limit(10).execute()
        data = resp.data
        if data:
            df = pd.DataFrame(data)
            st.dataframe(df)
        else:
            st.info("No data found.")
 
    # --------------------- Admin Block ---------------------
    elif choice == "Admin Block":
        st.header("🔐 Admin Block - Initialize Opening Values")
        password = st.text_input("Enter Admin Password", type="password")
        if password == "Sekura@2025":
            st.success("Access Granted.")
            toll_plaza = st.selectbox("Select Toll Plaza for Initialization", ["TP01", "TP02", "TP03"])
            consumer_number = TP_CONSUMER_MAP.get(toll_plaza, "N/A")
            st.info(f"Auto Fetched Consumer Number: {consumer_number}")
 
            opening_kwh = st.number_input("Initialize Opening KWH", min_value=0.0, format="%.2f")
            opening_kvah = st.number_input("Initialize Opening KVAH", min_value=0.0, format="%.2f")
 
            if st.button("Save Initialization"):
                try:
                    supabase.table("eb_live_status").upsert({
                        "toll_plaza": toll_plaza,
                        "consumer_number": consumer_number,
                        "opening_kwh": opening_kwh,
                        "opening_kvah": opening_kvah
                    }).execute()
                    st.success("✅ Initialization saved and synced.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Initialization failed: {e}")
        else:
            if password != "":
                st.error("Incorrect password.")
 
    # --------------------- Download CSV ---------------------
    elif choice == "Download CSV":
        st.header("📥 Download CSV Data")
        from_date = st.date_input("From Date", datetime.now() - timedelta(days=7))
        to_date = st.date_input("To Date", datetime.now())
 
        if st.button("Download CSV"):
            resp = supabase.table("eb_meter_readings").select("*").gte("date", from_date.strftime("%Y-%m-%d")).lte("date", to_date.strftime("%Y-%m-%d")).execute()
            data = resp.data
            if data:
                df = pd.DataFrame(data)
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Click to Download CSV", csv, "eb_meter_readings.csv", "text/csv")
            else:
                st.info("No data found in this range.")
 

