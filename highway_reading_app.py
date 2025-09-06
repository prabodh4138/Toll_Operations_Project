import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import os
 
# ------------------ Supabase Connection ------------------
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key)
 
# ------------------ Main Function ------------------
def run():
    st.title("🛣️ Highway Energy Meter Reading")
 
    # Debug toggle in sidebar
    debug = st.sidebar.checkbox("Enable debug (show raw API responses)", value=False)
 
    menu = ["User Block", "Last 10 Readings", "Admin Block", "Download CSV"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    # ------------------ User Block ------------------
    if choice == "User Block":
        st.header("🛠️ User Block - Enter Highway Readings")
        date_obj = st.date_input("Select Date", datetime.now())
        display_date = date_obj.strftime("%d-%m-%Y")
        iso_date = date_obj.strftime("%Y-%m-%d")
        st.info(f"Selected Date: {display_date}")
 
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
 
        # Fetch consumers under this plaza
        consumer_resp = supabase.table("highway_consumers").select("consumer_number").eq("toll_plaza", toll_plaza).execute()
        if debug: st.write("DEBUG: consumer_resp:", consumer_resp)
        consumer_list = [c["consumer_number"] for c in consumer_resp.data] if consumer_resp.data else []
        if not consumer_list:
            st.warning("No consumers found for this Toll Plaza. Please ask Admin to initialize.")
            return
 
        consumer_number = st.selectbox("Select Consumer Number", consumer_list)
 
        # Fetch live opening values
        opening_kwh, opening_kvah = 0.0, 0.0
        try:
            live_resp = (
                supabase.table("highway_live_status")
                .select("opening_kwh, opening_kvah")
                .eq("toll_plaza", toll_plaza)
                .eq("consumer_number", consumer_number)
                .execute()
            )
            if debug: st.write("DEBUG: live_resp (fetch opening):", live_resp)
            if live_resp.data:
                opening_kwh = float(live_resp.data[0].get("opening_kwh", 0.0) or 0.0)
                opening_kvah = float(live_resp.data[0].get("opening_kvah", 0.0) or 0.0)
        except Exception as e:
            st.warning(f"Error fetching live data: {e}")
 
        st.info(f"Opening KWH: {opening_kwh:.2f}")
        closing_kwh = st.number_input("Closing KWH", min_value=opening_kwh, format="%.2f")
        net_kwh = float(closing_kwh) - float(opening_kwh)
        st.success(f"Net KWH: {net_kwh:.2f}")
 
        st.info(f"Opening KVAH: {opening_kvah:.2f}")
        closing_kvah = st.number_input("Closing KVAH", min_value=opening_kvah, format="%.2f")
        net_kvah = float(closing_kvah) - float(opening_kvah)
        st.success(f"Net KVAH: {net_kvah:.2f}")
 
        pf = st.number_input("Power Factor (PF)", min_value=0.0, max_value=1.0, step=0.01, format="%.2f")
        md = st.number_input("Maximum Demand (MD in kVA)", min_value=0.0, step=0.1, format="%.2f")
        remarks = st.text_area("Remarks (optional)")
 
        if st.button("Submit Reading"):
            try:
                # prepare data
                data = {
                    "date": iso_date,
                    "toll_plaza": toll_plaza,
                    "consumer_number": consumer_number,
                    "opening_kwh": float(opening_kwh),
                    "closing_kwh": float(closing_kwh),
                    "net_kwh": float(net_kwh),
                    "opening_kvah": float(opening_kvah),
                    "closing_kvah": float(closing_kvah),
                    "net_kvah": float(net_kvah),
                    "pf": float(pf),
                    "md": float(md),
                    "remarks": remarks,
                }
 
                # insert reading
                insert_resp = supabase.table("highway_meter_readings").insert(data).execute()
                if debug: st.write("DEBUG: insert_resp:", insert_resp)
 
                # Update live status for the next cycle using upsert with on_conflict so it updates, not inserts duplicates
                live_payload = {
                    "toll_plaza": toll_plaza,
                    "consumer_number": consumer_number,
                    "opening_kwh": float(closing_kwh),
                    "opening_kvah": float(closing_kvah),
                }
                upsert_resp = supabase.table("highway_live_status").upsert(live_payload, on_conflict="toll_plaza,consumer_number").execute()
                if debug: st.write("DEBUG: upsert_resp:", upsert_resp)
 
                st.success("✅ Reading submitted successfully.")
 
                # Verification: read back the live_status row and display
                verify = supabase.table("highway_live_status").select("*").eq("toll_plaza", toll_plaza).eq("consumer_number", consumer_number).execute()
                if debug: st.write("DEBUG: verify_resp:", verify)
                if verify.data:
                    v = verify.data[0]
                   st.info(f"Verified live status — opening_kwh: {v.get('opening_kwh')}, opening_kvah: {v.get('opening_kvah')}")
                else:
                    st.warning("Verification: no live_status row found after upsert.")
 
                st.rerun()
            except Exception as e:
                st.error(f"❌ Submission failed: {e}")
 
    # ------------------ Last 10 Readings ------------------
    elif choice == "Last 10 Readings":
        st.header("📊 Last 10 Highway Meter Readings")
        try:
            readings_resp = supabase.table("highway_meter_readings").select("*").order("id", desc=True).limit(10).execute()
            if debug: st.write("DEBUG: readings_resp:", readings_resp)
            if readings_resp.data:
                df = pd.DataFrame(readings_resp.data)
                st.dataframe(df)
            else:
               st.info("No readings found.")
        except Exception as e:
            st.error(f"Error fetching data: {e}")
 
    # ------------------ Admin Block ------------------
    elif choice == "Admin Block":
        st.header("🛠️ Admin Block - Add Consumer")
        toll_plaza = st.selectbox("Select Toll Plaza to Add Consumer", ["TP01", "TP02", "TP03"])
        consumer_number = st.text_input("Enter Consumer Number")
        opening_kwh = st.number_input("Initial Opening KWH", min_value=0.0, format="%.2f")
        opening_kvah = st.number_input("Initial Opening KVAH", min_value=0.0, format="%.2f")
 
        if st.button("Add Consumer"):
            try:
                # prevent empty consumer_number
                if not consumer_number.strip():
                    st.error("Consumer number cannot be empty.")
                else:
                    # upsert consumer to consumers table (avoid duplicate)
                    consumer_payload = {
                        "toll_plaza": toll_plaza,
                        "consumer_number": consumer_number,
                        "opening_kwh": float(opening_kwh),
                        "opening_kvah": float(opening_kvah),
                    }
                    upsert_cons_resp = supabase.table("highway_consumers").upsert(consumer_payload, on_conflict="toll_plaza,consumer_number").execute()
                    if debug: st.write("DEBUG: upsert_cons_resp:", upsert_cons_resp)
 
                    # Initialize live status (use on_conflict so it updates if exists)
                    upsert_live_resp = supabase.table("highway_live_status").upsert(consumer_payload, on_conflict="toll_plaza,consumer_number").execute()
                    if debug: st.write("DEBUG: upsert_live_resp:", upsert_live_resp)
 
                    st.success("✅ Consumer added and initialized successfully.")
 
                    # Verification: read back live status and show
                    verify = supabase.table("highway_live_status").select("*").eq("toll_plaza", toll_plaza).eq("consumer_number", consumer_number).execute()
                    if debug: st.write("DEBUG: verify_resp_admin:", verify)
                    if verify.data:
                        v = verify.data[0]
                       st.info(f"Verified initialization — opening_kwh: {v.get('opening_kwh')}, opening_kvah: {v.get('opening_kvah')}")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Initialization failed: {e}")
 
    # ------------------ Download CSV ------------------
    elif choice == "Download CSV":
        st.header("⬇️ Download Highway Meter Readings")
        try:
            data_resp = supabase.table("highway_meter_readings").select("*").execute()
            if debug: st.write("DEBUG: data_resp (download):", data_resp)
            if data_resp.data:
                df = pd.DataFrame(data_resp.data)
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f'highway_meter_readings_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
                    mime='text/csv',
                )
            else:
              st.info("No data available for download.")
        except Exception as e:
            st.error(f"Error downloading data: {e}")
 
 
if __name__ == "__main__":
    run()

