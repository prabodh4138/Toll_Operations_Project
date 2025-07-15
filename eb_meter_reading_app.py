import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import os
 
# ---------------- Supabase Connection ----------------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
 
# ---------------- Main Function ----------------
def run():
    st.title("⚡ EB Meter Reading - Toll Operations")
 
    menu = ["User Block", "Last 10 Readings", "Download CSV", "Admin Block"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    if choice == "User Block":
        st.header("📝 EB Meter Reading Entry")
 
        date = st.date_input("Select Date", datetime.now()).strftime("%d-%m-%Y")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
 
        # Auto-fetch Consumer Number
        consumer_map = {
            "TP01": "416000000110",
            "TP02": "812001020208",
            "TP03": "813000000281"
        }
        consumer_no = consumer_map.get(toll_plaza, "")
        st.info(f"Consumer Number: {consumer_no}")
 
        # Fetch last opening values
        resp = supabase.table("eb_meter_readings").select("*").eq("toll_plaza", toll_plaza).order("id", desc=True).limit(1).execute()
        if resp.data:
            last_entry = resp.data[0]
            opening_kwh = last_entry["closing_kwh"]
            opening_kvah = last_entry["closing_kvah"]
        else:
            opening_kwh = 0.0
            opening_kvah = 0.0
 
        st.info(f"Opening KWH: {opening_kwh}")
        st.info(f"Opening KVAH: {opening_kvah}")
 
        closing_kwh = st.number_input("Closing KWH", min_value=opening_kwh, step=0.01,format="%.2f")
        closing_kvah = st.number_input("Closing KVAH", min_value=opening_kvah)
        pf = st.number_input("Power Factor (0-1)", min_value=0.0, max_value=1.0)
        md = st.number_input("Maximum Demand (kVA)", min_value=0.0)
        remarks = st.text_area("Remarks (optional)")
 
        net_kwh = closing_kwh - opening_kwh
        net_kvah = closing_kvah - opening_kvah
 
        if st.button("Submit Entry"):
            try:
                supabase.table("eb_meter_readings").insert({
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
        st.header("📊 Last 10 EB Meter Readings")
        toll_plaza = st.selectbox("Filter by Toll Plaza", ["TP01", "TP02", "TP03"])
        resp = supabase.table("eb_meter_readings").select("*").eq("toll_plaza", toll_plaza).order("id", desc=True).limit(10).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            st.dataframe(df)
        else:
            st.info("No data available.")
 
    elif choice == "Download CSV":
        st.header("📥 Download EB Meter CSV Records")
        toll_plaza = st.selectbox("Select Toll Plaza for Download", ["TP01", "TP02", "TP03"])
        resp = supabase.table("eb_meter_readings").select("*").eq("toll_plaza", toll_plaza).order("id", desc=True).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download CSV", csv, f"{toll_plaza}_eb_meter_readings.csv", "text/csv")
        else:
            st.info("No data available for download.")
 
    elif choice == "Admin Block":
        st.header("🔐 Admin Block")
        password = st.text_input("Enter Admin Password", type="password")
        if password == "Sekura@2025":
            st.success("Access Granted. No initialization required for EB Meter as it auto-syncs.")
        else:
            if password != "":
                st.error("Incorrect Password.")
 
