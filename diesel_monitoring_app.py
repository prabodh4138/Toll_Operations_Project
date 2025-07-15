import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import pandas as pd
import time
import os
 
# ------------------- Supabase Connection -------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
 
# ------------------- Helper Functions -------------------
def calculate_net_rh(opening_rh, closing_rh):
    fmt = "%H:%M"
    tdelta = datetime.strptime(closing_rh, fmt) - datetime.strptime(opening_rh, fmt)
    if tdelta.total_seconds() < 0:
        tdelta += timedelta(days=1)
    hours, remainder = divmod(tdelta.seconds, 3600)
    minutes = remainder // 60
    return f"{hours:02}:{minutes:02}"
 
def get_live_values(toll_plaza):
    resp = supabase.table("dg_live_status").select("*").eq("toll_plaza", toll_plaza).execute()
    if resp.data:
        row = resp.data[0]
        return (
            row["updated_plaza_barrel_stock"] or 0.0,
            row["updated_diesel_stock"] or 0.0,
            row["updated_opening_kwh"] or 0.0,
            row["updated_opening_rh"] or "00:00"
        )
    else:
        return (0.0, 0.0, 0.0, "00:00")
 
def update_live_status(toll_plaza, updated_barrel_stock, closing_diesel_stock, closing_kwh, closing_rh):
    resp = supabase.table("dg_live_status").upsert({
        "toll_plaza": toll_plaza,
        "updated_plaza_barrel_stock": updated_barrel_stock,
        "updated_diesel_stock": closing_diesel_stock,
        "updated_opening_kwh": closing_kwh,
        "updated_opening_rh": closing_rh
    }).execute()
 
# ------------------- Main App -------------------
def run():
    st.title("🚩 DG Monitoring - Toll Operations")
 
    menu = ["User Block", "Last 10 Transactions", "Admin Block", "Download CSV"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    if choice == "User Block":
        st.subheader("🛠️ User Block - Data Entry")
        date = st.date_input("Select Date", datetime.now()).strftime("%d-%m-%Y")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        dg_name = st.selectbox("Select DG Name", ["DG1", "DG2"])
 
        barrel_stock, diesel_stock, opening_kwh, opening_rh = get_live_values(toll_plaza)
 
        st.info(f"**Plaza Barrel Stock (Virtual): {barrel_stock} L**")
        st.info(f"**Opening Diesel Stock at DG (Virtual): {diesel_stock} L**")
        st.info(f"**Opening KWH (Virtual): {opening_kwh}**")
        st.info(f"**Opening RH (Virtual): {opening_rh}**")
 
        diesel_purchase = st.number_input("Diesel Purchase (L)", min_value=0.0, value=0.0)
        diesel_topup = st.number_input("Diesel Top Up (L)", min_value=0.0, value=0.0)
        updated_barrel_stock = barrel_stock + diesel_purchase - diesel_topup
        st.success(f"Updated Plaza Barrel Stock: {updated_barrel_stock} L")
 
        closing_diesel_stock = st.number_input("Closing Diesel Stock at DG (L)", min_value=0.0)
        diesel_consumption = max(0, (diesel_stock + diesel_topup - closing_diesel_stock))
        st.success(f"Diesel Consumption: {diesel_consumption} L")
 
        closing_kwh = st.number_input("Closing KWH (Must be >= Opening KWH)", min_value=float(opening_kwh))
        net_kwh = closing_kwh - opening_kwh
        st.success(f"Net KWH: {net_kwh}")
 
        closing_rh = st.text_input("Closing RH (HH:MM)", "00:00")
        if closing_rh:
            try:
                net_rh = calculate_net_rh(opening_rh, closing_rh)
                st.success(f"Net RH: {net_rh}")
            except:
                st.warning("Invalid RH format. Use HH:MM")
                net_rh = "00:00"
        else:
            net_rh = "00:00"
 
        maximum_demand = st.number_input("Maximum Demand (kVA)", min_value=0.0)
        remarks = st.text_area("Remarks (optional)")
 
        if st.button("Submit Entry"):
            try:
                supabase.table("diesel_transactions").insert({
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
 
                update_live_status(toll_plaza, updated_barrel_stock, closing_diesel_stock, closing_kwh, closing_rh)
 
                st.success("✅ Data submitted successfully and synced to Supabase.")
                time.sleep(1)
                st.experimental_rerun()
            except Exception as e:
                st.error(f"❌ Submission failed: {e}")
 
    elif choice == "Last 10 Transactions":
        st.subheader("📄 Last 10 Transactions")
        toll_plaza = st.selectbox("Filter Toll Plaza", ["TP01", "TP02", "TP03"])
        dg_name = st.selectbox("Filter DG Name", ["DG1", "DG2"])
 
        resp = supabase.table("diesel_transactions").select("*").eq("toll_plaza", toll_plaza).eq("dg_name", dg_name).order("id", desc=True).limit(10).execute()
        df = pd.DataFrame(resp.data)
        st.dataframe(df)
 
    elif choice == "Admin Block":
        st.subheader("🔐 Admin Block - Initialization")
        password = st.text_input("Enter Admin Password", type="password")
 
        if password == "Sekura@2025":
            st.success("Access Granted.")
            toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
            init_barrel_stock = st.number_input("Initialize Plaza Barrel Stock (L)", min_value=0.0)
            init_diesel_stock = st.number_input("Initialize Opening Diesel Stock at DG (L)", min_value=0.0)
            init_opening_kwh = st.number_input("Initialize Opening KWH", min_value=0.0)
            init_opening_rh = st.text_input("Initialize Opening RH (HH:MM)", "00:00")
 
            if st.button("Initialize"):
                try:
                    update_live_status(toll_plaza, init_barrel_stock, init_diesel_stock, init_opening_kwh, init_opening_rh)
                    st.success("✅ Initialization completed and synced.")
                    time.sleep(1)
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"❌ Initialization failed: {e}")
        else:
            if password != "":
                st.error("Incorrect Password.")
 
    elif choice == "Download CSV":
        st.subheader("📥 Download Diesel Transactions CSV")
        resp = supabase.table("diesel_transactions").select("*").order("id", desc=True).limit(1000).execute()
        df = pd.DataFrame(resp.data)
 
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv, "diesel_transactions.csv", "text/csv")
 
