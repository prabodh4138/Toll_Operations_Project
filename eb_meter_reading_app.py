import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime
 
# --- Supabase connection ---
import os
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
 
def run():
    st.title("💡 EB Meter Reading - Toll Operations")
 
    menu = ["User Block", "Last 10 Records", "Admin Block", "Download CSV"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    # Predefined mapping
    plaza_consumer_map = {
        "TP01": "416000000110",
        "TP02": "812001020208",
        "TP03": "813000000281"
    }
 
    if choice == "User Block":
        st.subheader("📥 User Entry")
 
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        consumer_number = plaza_consumer_map.get(toll_plaza, "")
 
        st.info(f"Auto-fetched Consumer Number: **{consumer_number}**")
 
        date = st.date_input("Select Date", datetime.now()).strftime("%d-%m-%Y")
        opening_kwh = st.number_input("Opening KWH", min_value=0.0, format="%.2f")
        closing_kwh = st.number_input("Closing KWH", min_value=opening_kwh, format="%.2f")
        net_kwh = closing_kwh - opening_kwh
        st.success(f"Net KWH: {net_kwh:.2f}")
 
        opening_kvah = st.number_input("Opening KVAH", min_value=0.0, format="%.2f")
        closing_kvah = st.number_input("Closing KVAH", min_value=opening_kvah, format="%.2f")
        net_kvah = closing_kvah - opening_kvah
        st.success(f"Net KVAH: {net_kvah:.2f}")
 
        maximum_demand = st.number_input("Maximum Demand (kVA)", min_value=0.0, format="%.2f")
        remarks = st.text_area("Remarks (Optional)")
 
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
                    "maximum_demand": maximum_demand,
                    "remarks": remarks
                }
                supabase.table("eb_meter_readings").insert(data).execute()
                st.success("✅ Reading submitted successfully.")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"❌ Submission failed: {e}")
 
    elif choice == "Last 10 Records":
        st.subheader("🗂️ Last 10 EB Meter Readings")
        toll_plaza = st.selectbox("Filter by Toll Plaza", ["TP01", "TP02", "TP03"])
        consumer_number = plaza_consumer_map.get(toll_plaza, "")
        try:
            resp = supabase.table("eb_meter_readings").select("*").eq("toll_plaza", toll_plaza).eq("consumer_number", consumer_number).order("id", desc=True).limit(10).execute()
            df = pd.DataFrame(resp.data)
            if not df.empty:
                st.dataframe(df)
            else:
                st.info("No data found for this Toll Plaza.")
        except Exception as e:
            st.error(f"❌ Fetching data failed: {e}")
 
    elif choice == "Admin Block":
        st.subheader("🔐 Admin Initialization Block")
        password = st.text_input("Enter Admin Password", type="password")
        if password == "Sekura@2025":
            st.success("Access Granted.")
 
            toll_plaza = st.selectbox("Select Toll Plaza for Initialization", ["TP01", "TP02", "TP03"])
            consumer_number = plaza_consumer_map.get(toll_plaza, "")
            st.info(f"Auto-fetched Consumer Number: **{consumer_number}**")
 
            init_opening_kwh = st.number_input("Initialize Opening KWH", min_value=0.0, format="%.2f")
            init_opening_kvah = st.number_input("Initialize Opening KVAH", min_value=0.0, format="%.2f")
 
            if st.button("Save Initialization"):
                try:
                    # Upsert to eb_live_status table
                    data = {
                        "toll_plaza": toll_plaza,
                        "consumer_number": consumer_number,
                        "opening_kwh": init_opening_kwh,
                        "opening_kvah": init_opening_kvah
                    }
                    supabase.table("eb_live_status").upsert(data, on_conflict=["toll_plaza"]).execute()
                    st.success("✅ Initialization saved successfully.")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"❌ Initialization failed: {e}")
        elif password != "":
            st.error("❌ Incorrect password.")
 
    elif choice == "Download CSV":
        st.subheader("📥 Download EB Meter Reading Data")
        try:
            resp = supabase.table("eb_meter_readings").select("*").execute()
            df = pd.DataFrame(resp.data)
            if not df.empty:
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("Download CSV", csv, "eb_meter_readings.csv", "text/csv")
            else:
                st.info("No data available to download.")
        except Exception as e:
            st.error(f"❌ Download failed: {e}")
 
