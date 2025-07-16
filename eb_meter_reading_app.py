import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime
import os
 
# ----------------- Supabase Connection -----------------
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)
 
# ----------------- Consumer Mapping -----------------
CONSUMER_MAP = {
    "TP01": "416000000110",
    "TP02": "812001020208",
    "TP03": "813000000281"
}
 
def run():
    st.title("⚡ EB Meter Reading Module")
 
    menu = ["User Block", "Last 10 Records", "Admin Block", "Download CSV"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    if choice == "User Block":
        st.subheader("📄 EB Meter Reading Entry")
 
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
 
        # Fetch live values
        live_resp = supabase.table("eb_live_status").select("*").eq("toll_plaza", toll_plaza).execute()
        if live_resp.data:
            consumer_number = live_resp.data[0]["consumer_number"]
            opening_kwh = live_resp.data[0]["opening_kwh"]
            opening_kvah = live_resp.data[0]["opening_kvah"]
        else:
            st.warning("Admin has not initialized data for this Toll Plaza yet.")
            st.stop()
 
        st.info(f"Consumer Number (Auto): {consumer_number}")
        st.info(f"Opening KWH: {opening_kwh}")
        st.info(f"Opening KVAH: {opening_kvah}")
 
        date = st.date_input("Select Date", datetime.now()).strftime("%d-%m-%Y")
 
        closing_kwh = st.number_input("Closing KWH", min_value=opening_kwh, format="%.2f")
        net_kwh = closing_kwh - opening_kwh
        st.success(f"Net KWH: {net_kwh:.2f}")
 
        closing_kvah = st.number_input("Closing KVAH", min_value=opening_kvah, format="%.2f")
        net_kvah = closing_kvah - opening_kvah
        st.success(f"Net KVAH: {net_kvah:.2f}")
 
        maximum_demand = st.number_input("Maximum Demand (kVA)", min_value=0.0, format="%.2f")
        remarks = st.text_area("Remarks (optional)")
 
        if st.button("Submit Reading"):
            try:
                # Insert into transactions
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
                    "maximum_demand": maximum_demand,
                    "remarks": remarks
                }).execute()
 
                # Update live_status
                supabase.table("eb_live_status").update({
                    "opening_kwh": closing_kwh,
                    "opening_kvah": closing_kvah
                }).eq("toll_plaza", toll_plaza).execute()
 
                st.success("✅ Data submitted and live values updated.")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"❌ Submission failed: {e}")
 
    elif choice == "Last 10 Records":
        st.subheader("📝 Last 10 EB Meter Records")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        resp = supabase.table("eb_meter_readings").select("*").eq("toll_plaza", toll_plaza).order("id", desc=True).limit(10).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            st.dataframe(df)
        else:
            st.info("No data found.")
 
    elif choice == "Admin Block":
        st.subheader("🔑 Admin Initialization")
 
        password = st.text_input("Enter Admin Password", type="password")
        if password != "Sekura@2025":
            st.warning("Please enter correct admin password to proceed.")
            st.stop()
 
        toll_plaza = st.selectbox("Select Toll Plaza to Initialize", ["TP01", "TP02", "TP03"])
        consumer_number = CONSUMER_MAP.get(toll_plaza, "NA")
        st.info(f"Consumer Number Auto-Set: {consumer_number}")
 
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
                st.success("✅ Initialization saved successfully.")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"❌ Initialization failed: {e}")
 
    elif choice == "Download CSV":
        st.subheader("📥 Download EB Meter Data CSV")
        resp = supabase.table("eb_meter_readings").select("*").execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "eb_meter_readings.csv", "text/csv")
        else:
            st.info("No data found to download.")
 
