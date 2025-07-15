import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timedelta
import pandas as pd
import time
import os
 
# ---------------- Supabase Connection -------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
 
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
 
# ---------------- Helper Functions -------------------
def calculate_net_rh(opening_rh, closing_rh):
    fmt = "%H:%M"
    try:
        tdelta = datetime.strptime(closing_rh, fmt) - datetime.strptime(opening_rh, fmt)
        if tdelta.total_seconds() < 0:
            tdelta += timedelta(days=1)
        hours, remainder = divmod(tdelta.seconds, 3600)
        minutes = remainder // 60
        return f"{hours:02}:{minutes:02}"
    except:
        return "00:00"
 
def get_live_values(toll_plaza, dg_name):
    response = supabase.table("dg_live_status").select("*").eq("toll_plaza", toll_plaza).eq("dg_name", dg_name).execute()
    if response.data:
        row = response.data[0]
        return (
            row.get("updated_plaza_barrel_stock", 0.0),
            row.get("updated_diesel_stock", 0.0),
            row.get("updated_opening_kwh", 0.0),
            row.get("updated_opening_rh", "00:00")
        )
    else:
        return (0.0, 0.0, 0.0, "00:00")
 
def update_live_status(toll_plaza, dg_name, barrel_stock, diesel_stock, opening_kwh, opening_rh):
    supabase.table("dg_live_status").upsert({
        "toll_plaza": toll_plaza,
        "dg_name": dg_name,
        "updated_plaza_barrel_stock": barrel_stock,
        "updated_diesel_stock": diesel_stock,
        "updated_opening_kwh": opening_kwh,
        "updated_opening_rh": opening_rh
    }).execute()
 
# ---------------- UI -------------------
 
def run():
    st.title("🚩 Diesel Monitoring App - Toll Operations (Supabase)")
 
    menu = ["User Block", "Last 10 Transactions", "Admin Block", "Download CSV"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    if choice == "User Block":
        st.header("🛠️ User Block - Data Entry")
        date = st.date_input("Select Date", datetime.now()).strftime("%d-%m-%Y")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        dg_name = st.selectbox("Select DG Name", ["DG1", "DG2"])
 
        barrel_stock, diesel_stock, opening_kwh, opening_rh = get_live_values(toll_plaza, dg_name)
 
        st.info(f"**Plaza Barrel Stock: {barrel_stock} L**")
        st.info(f"**Opening Diesel Stock at DG: {diesel_stock} L**")
        st.info(f"**Opening KWH: {opening_kwh}**")
        st.info(f"**Opening RH: {opening_rh}**")
 
        diesel_purchase = st.number_input("Diesel Purchase (L)", min_value=0.0, value=0.0)
        diesel_topup = st.number_input("Diesel Top Up (L)", min_value=0.0, value=0.0)
        updated_barrel_stock = barrel_stock + diesel_purchase - diesel_topup
        st.success(f"Updated Plaza Barrel Stock: {updated_barrel_stock} L")
 
        closing_diesel_stock = st.number_input("Closing Diesel Stock at DG (L)", min_value=0.0)
        diesel_consumption = max(0, (diesel_stock + diesel_topup - closing_diesel_stock))
        st.success(f"Diesel Consumption: {diesel_consumption} L")
 
        closing_kwh = st.number_input("Closing KWH", min_value=opening_kwh)
        net_kwh = closing_kwh - opening_kwh
        st.success(f"Net KWH: {net_kwh}")
 
        closing_rh = st.text_input("Closing RH (HH:MM)", "00:00")
        if closing_rh != "00:00":
            net_rh = calculate_net_rh(opening_rh, closing_rh)
            st.success(f"Net RH: {net_rh}")
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
 
                update_live_status(toll_plaza, dg_name, updated_barrel_stock, closing_diesel_stock, closing_kwh, closing_rh)
 
                st.success("✅ Data submitted successfully and updated.")
                time.sleep(1.5)
                st.rerun()
 
            except Exception as e:
                st.error(f"❌ Error: {e}")
 
    elif choice == "Last 10 Transactions":
        st.header("📄 Last 10 Transactions")
        toll_plaza = st.selectbox("Filter by Toll Plaza", ["TP01", "TP02", "TP03"])
        dg_name = st.selectbox("Filter by DG Name", ["DG1", "DG2"])
 
        data = supabase.table("dg_meter_readings").select("*").eq("toll_plaza", toll_plaza).eq("dg_name", dg_name).order("id", desc=True).limit(10).execute()
        df = pd.DataFrame(data.data)
        st.dataframe(df)
 
    elif choice == "Admin Block":
        st.header("🔐 Admin Block - Initialization")
        password = st.text_input("Enter Admin Password", type="password")
        if password == "Sekura@2025":
            st.success("Access Granted. Initialize data below.")
            toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"], key="admin_tp")
            dg_name = st.selectbox("Select DG Name", ["DG1", "DG2"], key="admin_dg")
 
            init_barrel_stock = st.number_input("Initialize Plaza Barrel Stock (L)", min_value=0.0)
            init_diesel_stock = st.number_input("Initialize Opening Diesel Stock at DG (L)", min_value=0.0)
            init_opening_kwh = st.number_input("Initialize Opening KWH", min_value=0.0)
            init_opening_rh = st.text_input("Initialize Opening RH (HH:MM)", "00:00")
 
            if st.button("Save Initialization"):
                try:
                    update_live_status(toll_plaza, dg_name, init_barrel_stock, init_diesel_stock, init_opening_kwh, init_opening_rh)
                    st.success("✅ Initialization data saved.")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {e}")
        else:
            if password != "":
                st.error("Incorrect password. Please try again.")
 
    elif choice == "Download CSV":
        st.header("📥 Download CSV")
        from_date = st.date_input("From Date", datetime.now() - timedelta(days=7))
        to_date = st.date_input("To Date", datetime.now())
 
        if st.button("Download CSV"):
            data = supabase.table("transactions").select("*").execute()
            df = pd.DataFrame(data.data)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download CSV", csv, "diesel_monitoring_data.csv", "text/csv")
 
