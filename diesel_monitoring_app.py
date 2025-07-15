import streamlit as st
from supabase import create_client
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import pandas as pd
import time
 
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)
 
def run():
    st.title("⛽ DG Monitoring - Toll Operations")
 
    menu = ["User Block", "Last 10 Transactions", "Admin Block", "Download CSV"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    if choice == "User Block":
        st.header("🛠️ User Block - Data Entry")
        date = st.date_input("Select Date", datetime.now()).strftime("%d-%m-%Y")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        dg_name = st.selectbox("Select DG Name", ["DG1", "DG2"])
 
        # Fetch barrel stock (plaza level)
        barrel_resp = supabase.table("plaza_barrel_status").select("*").eq("toll_plaza", toll_plaza).execute()
        if barrel_resp.data:
            barrel_stock = barrel_resp.data[0]["updated_plaza_barrel_stock"]
        else:
            barrel_stock = 0.0
 
        # Fetch DG-specific live values
        live_resp = supabase.table("dg_live_status").select("*").eq("toll_plaza", toll_plaza).eq("dg_name", dg_name).execute()
        if live_resp.data:
            dg_data = live_resp.data[0]
            diesel_stock = dg_data["updated_diesel_stock"]
            opening_kwh = dg_data["opening_kwh"]
            opening_rh = dg_data["opening_rh"]
        else:
            diesel_stock = 0.0
            opening_kwh = 0.0
            opening_rh = "00:00"
 
        st.info(f"🚩 Plaza Barrel Stock (Virtual): {barrel_stock} L")
        st.info(f"🛢️ Opening Diesel Stock at DG (Virtual): {diesel_stock} L")
        st.info(f"🔌 Opening KWH (Virtual): {opening_kwh}")
        st.info(f"⏱️ Opening RH (Virtual): {opening_rh}")
 
        diesel_purchase = st.number_input("Diesel Purchase (L)", min_value=0.0, value=0.0)
        diesel_topup = st.number_input("Diesel Top Up (L)", min_value=0.0, value=0.0)
        updated_barrel_stock = barrel_stock + diesel_purchase - diesel_topup
        st.success(f"Updated Plaza Barrel Stock: {updated_barrel_stock} L")
 
        closing_diesel_stock = st.number_input("Closing Diesel Stock at DG (L) (Mandatory)", min_value=0.0)
        diesel_consumption = max(0, (diesel_stock + diesel_topup - closing_diesel_stock))
        st.success(f"Diesel Consumption: {diesel_consumption} L")
 
        closing_kwh = st.number_input("Closing KWH (Must be >= Opening KWH)", min_value=opening_kwh)
        net_kwh = closing_kwh - opening_kwh
        st.success(f"Net KWH: {net_kwh}")
 
        closing_rh = st.text_input("Closing RH (HH:MM, Must be >= Opening RH)", "00:00")
        def calculate_net_rh(opening_rh, closing_rh):
            fmt = "%H:%M"
            tdelta = datetime.strptime(closing_rh, fmt) - datetime.strptime(opening_rh, fmt)
            if tdelta.total_seconds() < 0:
                tdelta += timedelta(days=1)
            hours, remainder = divmod(tdelta.seconds, 3600)
            minutes = remainder // 60
            return f"{hours:02}:{minutes:02}"
 
        if closing_rh != "00:00":
            try:
                net_rh = calculate_net_rh(opening_rh, closing_rh)
                st.success(f"Net RH: {net_rh}")
            except Exception:
                st.warning("Incorrect RH format. Please use HH:MM.")
                net_rh = "00:00"
        else:
            net_rh = "00:00"
 
        maximum_demand = st.number_input("Maximum Demand (kVA)", min_value=0.0)
        remarks = st.text_area("Remarks (optional)")
 
        if st.button("Submit Entry"):
            try:
                supabase.table("dg_meter_readings").insert({
                    "date": date,
                    "toll_plaza": toll_plaza,
                    "dg_name": dg_name,
                    "plaza_barrel_stock": barrel_stock,
                    "diesel_purchase": diesel_purchase,
                    "diesel_topup": diesel_topup,
                    "updated_plaza_barrel_stock": updated_barrel_stock,
                    "opening_diesel_stock": diesel_stock,
                    "closing_diesel_stock": closing_diesel_stock,
                    "diesel_consumption": diesel_consumption,
                    "opening_kwh": opening_kwh,
                    "closing_kwh": closing_kwh,
                    "net_kwh": net_kwh,
                    "opening_rh": opening_rh,
                    "closing_rh": closing_rh,
                    "net_rh": net_rh,
                    "maximum_demand": maximum_demand,
                    "remarks": remarks
                }).execute()
 
                # Update plaza barrel status
                supabase.table("plaza_barrel_status").upsert({
                    "toll_plaza": toll_plaza,
                    "updated_plaza_barrel_stock": updated_barrel_stock
                }).execute()
 
                # Update DG live status
                supabase.table("dg_live_status").upsert({
                    "toll_plaza": toll_plaza,
                    "dg_name": dg_name,
                    "updated_diesel_stock": closing_diesel_stock,
                    "opening_kwh": closing_kwh,
                    "opening_rh": closing_rh
                }).execute()
 
                st.success("✅ Data submitted successfully and updated in database.")
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"❌ Submission failed: {e}")
 
    elif choice == "Last 10 Transactions":
        st.header("📄 Last 10 Transactions")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        dg_name = st.selectbox("Select DG Name", ["DG1", "DG2"])
        resp = supabase.table("dg_meter_readings").select("*").eq("toll_plaza", toll_plaza).eq("dg_name", dg_name).order("id", desc=True).limit(10).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            st.dataframe(df)
        else:
            st.info("No transactions found.")
 
    elif choice == "Admin Block":
        st.header("🔐 Admin Block - Initialization")
        password = st.text_input("Enter Admin Password", type="password")
        if password == "Sekura@2025":
            st.success("Access Granted. You can initialize Plaza Barrel and DG Parameters.")
            toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"], key="admin_tp")
            dg_name = st.selectbox("Select DG Name", ["DG1", "DG2"], key="admin_dg")
            init_barrel_stock = st.number_input("Initialize Plaza Barrel Stock (L)", min_value=0.0)
            init_diesel_stock = st.number_input("Initialize Opening Diesel Stock at DG (L)", min_value=0.0)
            init_opening_kwh = st.number_input("Initialize Opening KWH", min_value=0.0)
            init_opening_rh = st.text_input("Initialize Opening RH (HH:MM)", "00:00")
            if st.button("Save Initialization"):
                try:
                    supabase.table("plaza_barrel_status").upsert({
                        "toll_plaza": toll_plaza,
                        "updated_plaza_barrel_stock": init_barrel_stock
                    }).execute()
 
                    supabase.table("dg_live_status").upsert({
                        "toll_plaza": toll_plaza,
                        "dg_name": dg_name,
                        "updated_diesel_stock": init_diesel_stock,
                        "opening_kwh": init_opening_kwh,
                        "opening_rh": init_opening_rh
                    }).execute()
 
                    st.success("✅ Initialization data saved successfully.")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Initialization failed: {e}")
        else:
            if password != "":
                st.error("Incorrect password. Please try again.")
 
    elif choice == "Download CSV":
        st.header("📥 Download CSV Records")
        from_date = st.date_input("From Date", datetime.now() - timedelta(days=7))
        to_date = st.date_input("To Date", datetime.now())
        if st.button("Download CSV"):
            resp = supabase.table("dg_meter_readings").select("*").execute()
            if resp.data:
                df = pd.DataFrame(resp.data)
                df_filtered = df[
                    (pd.to_datetime(df["date"], format="%d-%m-%Y") >= from_date) &
                    (pd.to_datetime(df["date"], format="%d-%m-%Y") <= to_date)
                ]
                csv = df_filtered.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Click to Download CSV", csv, "dg_meter_readings.csv", "text/csv")
            else:
                st.info("No records found for download.")
 
