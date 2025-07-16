import streamlit as st
from datetime import datetime, timedelta
from supabase import create_client
import pandas as pd
 
# -------------------- Supabase Connection --------------------
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)
 
# -------------------- Helper Functions --------------------
 
def get_live_values(toll_plaza, consumer_number):
    resp = supabase.table("eb_live_status").select("*").eq("toll_plaza", toll_plaza).eq("consumer_number", consumer_number).execute()
    if resp.data:
        row = resp.data[0]
        return (
            row.get("opening_kwh", 0.0),
            row.get("opening_kvah", 0.0)
        )
    return (0.0, 0.0)
 
def update_live_values(toll_plaza, consumer_number, opening_kwh, opening_kvah):
    supabase.table("eb_live_status").upsert({
        "toll_plaza": toll_plaza,
        "consumer_number": consumer_number,
        "opening_kwh": opening_kwh,
        "opening_kvah": opening_kvah,
        "last_updated": datetime.utcnow().isoformat()
    }).execute()
 
# -------------------- Main App --------------------
 
def run():
    st.title("⚡ EB Meter Reading Module")
 
    menu = ["User Block", "Last 10 Readings", "Admin Block", "Download CSV"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    if choice == "User Block":
        st.subheader("📥 User Block - EB Reading Entry")
        date = st.date_input("Date", datetime.now()).strftime("%Y-%m-%d")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        consumer_number = st.text_input("Enter Consumer Number")
 
        if consumer_number:
            opening_kwh, opening_kvah = get_live_values(toll_plaza, consumer_number)
            st.info(f"Opening KWH: {opening_kwh}")
            st.info(f"Opening KVAH: {opening_kvah}")
 
            closing_kwh = st.number_input("Closing KWH", min_value=opening_kwh)
            net_kwh = closing_kwh - opening_kwh
            st.success(f"Net KWH: {net_kwh}")
 
            closing_kvah = st.number_input("Closing KVAH", min_value=opening_kvah)
            net_kvah = closing_kvah - opening_kvah
            st.success(f"Net KVAH: {net_kvah}")
 
            maximum_demand = st.number_input("Maximum Demand (kVA)", min_value=0.0)
            power_factor = st.number_input("Power Factor", min_value=0.0, max_value=1.0, step=0.01)
            remarks = st.text_area("Remarks")
 
            if st.button("Submit Reading"):
                try:
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
                        "power_factor": power_factor,
                        "remarks": remarks
                    }).execute()
 
                    update_live_values(toll_plaza, consumer_number, closing_kwh, closing_kvah)
                    st.success("✅ Reading submitted successfully.")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"❌ Submission failed: {e}")
 
    elif choice == "Last 10 Readings":
        st.subheader("📄 Last 10 EB Meter Readings")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"], key="last_tp")
        consumer_number = st.text_input("Enter Consumer Number for Filter", key="last_consumer")
        if consumer_number:
            resp = supabase.table("eb_meter_readings").select("*").eq("toll_plaza", toll_plaza).eq("consumer_number", consumer_number).order("id", desc=True).limit(10).execute()
        else:
            resp = supabase.table("eb_meter_readings").select("*").eq("toll_plaza", toll_plaza).order("id", desc=True).limit(10).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            st.dataframe(df)
        else:
            st.info("No readings found.")
 
    elif choice == "Admin Block":
        st.subheader("🔐 Admin Initialization Block")
        password = st.text_input("Enter Admin Password", type="password")
        if password == "Sekura@2025":
            st.success("Access Granted")
            toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"], key="admin_tp")
            consumer_number = st.text_input("Enter Consumer Number", key="admin_consumer")
            opening_kwh = st.number_input("Initialize Opening KWH", min_value=0.0)
            opening_kvah = st.number_input("Initialize Opening KVAH", min_value=0.0)
            if st.button("Save Initialization"):
                try:
                    update_live_values(toll_plaza, consumer_number, opening_kwh, opening_kvah)
                    st.success("✅ Initialization data saved successfully.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Initialization failed: {e}")
        else:
            if password != "":
                st.error("Incorrect password. Try again.")
 
    elif choice == "Download CSV":
        st.subheader("📥 Download EB Meter Readings as CSV")
        from_date = st.date_input("From Date", datetime.now() - timedelta(days=7))
        to_date = st.date_input("To Date", datetime.now())
        if st.button("Download CSV"):
            resp = supabase.table("eb_meter_readings").select("*").gte("date", str(from_date)).lte("date", str(to_date)).execute()
            if resp.data:
                df = pd.DataFrame(resp.data)
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download CSV", csv, "eb_meter_readings.csv", "text/csv")
            else:
                st.info("No data found for the selected period.")
 
