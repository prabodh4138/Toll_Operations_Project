import streamlit as st
from datetime import datetime, timedelta
from supabase import create_client
import pandas as pd
from io import StringIO
import os
 
# -------------------- Supabase Connection --------------------
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)
 
# -------------------- Helper Functions --------------------
 
def get_live_plaza_stock(toll_plaza):
    resp = supabase.table("dg_live_status").select("updated_plaza_barrel_stock").eq("toll_plaza", toll_plaza).execute()
    if resp.data and resp.data[0]["updated_plaza_barrel_stock"] is not None:
        return resp.data[0]["updated_plaza_barrel_stock"]
    return 0.0
 
def get_opening_status(toll_plaza, dg_name):
    resp = supabase.table("dg_opening_status").select("*").eq("toll_plaza", toll_plaza).eq("dg_name", dg_name).execute()
    if resp.data:
        row = resp.data[0]
        return (
            row.get("opening_diesel_stock", 0.0),
            row.get("opening_kwh", 0.0),
            row.get("opening_rh", "00:00")
        )
    return (0.0, 0.0, "00:00")
 
def update_live_plaza_stock(toll_plaza, updated_plaza_barrel_stock):
    supabase.table("dg_live_status").upsert({
        "toll_plaza": toll_plaza,
        "updated_plaza_barrel_stock": updated_plaza_barrel_stock,
        "last_updated": datetime.utcnow().isoformat()
    }).execute()
 
def update_opening_status(toll_plaza, dg_name, opening_diesel_stock, opening_kwh, opening_rh):
    supabase.table("dg_opening_status").upsert({
        "toll_plaza": toll_plaza,
        "dg_name": dg_name,
        "opening_diesel_stock": opening_diesel_stock,
        "opening_kwh": opening_kwh,
        "opening_rh": opening_rh,
        "last_updated": datetime.utcnow().isoformat()
    }).execute()
 
def calculate_net_rh(opening_rh, closing_rh):
    fmt = "%H:%M"
    tdelta = datetime.strptime(closing_rh, fmt) - datetime.strptime(opening_rh, fmt)
    if tdelta.total_seconds() < 0:
        tdelta += timedelta(days=1)
    hours, remainder = divmod(tdelta.seconds, 3600)
    minutes = remainder // 60
    return f"{hours:02}:{minutes:02}"
 
# -------------------- Main App --------------------
def run():
    st.title("🛢️ DG Monitoring Module")
 
    menu = ["User Block", "Last 10 Transactions", "Admin Block", "Download CSV"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    if choice == "User Block":
        st.subheader("🛠️ User Block - Data Entry")
        date = st.date_input("Date", datetime.now()).strftime("%Y-%m-%d")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        dg_name = st.selectbox("Select DG Name", ["DG1", "DG2"])
 
        plaza_barrel_stock = get_live_plaza_stock(toll_plaza)
        st.info(f"Plaza Barrel Stock (Virtual): {plaza_barrel_stock} L")
 
        opening_diesel_stock, opening_kwh, opening_rh = get_opening_status(toll_plaza, dg_name)
        st.info(f"Opening Diesel Stock at DG: {opening_diesel_stock} L")
        st.info(f"Opening KWH: {opening_kwh}")
        st.info(f"Opening RH: {opening_rh}")
 
        diesel_purchase = st.number_input("Diesel Purchase (L)", min_value=0.0)
        diesel_topup = st.number_input("Diesel Top Up to DG (L)", min_value=0.0)
        updated_plaza_barrel_stock = plaza_barrel_stock + diesel_purchase - diesel_topup
        st.success(f"Updated Plaza Barrel Stock: {updated_plaza_barrel_stock} L")
 
        closing_diesel_stock = st.number_input("Closing Diesel Stock at DG (L)", min_value=0.0)
        diesel_consumption = opening_diesel_stock + diesel_topup - closing_diesel_stock
        st.success(f"Diesel Consumption: {diesel_consumption} L")
 
        closing_kwh = st.number_input("Closing KWH", min_value=opening_kwh)
        net_kwh = closing_kwh - opening_kwh
        st.success(f"Net KWH: {net_kwh}")
 
        closing_rh = st.text_input("Closing RH (HH:MM)", "00:00")
        if closing_rh != "00:00":
            try:
                net_rh = calculate_net_rh(opening_rh, closing_rh)
                st.success(f"Net RH: {net_rh}")
            except:
                st.error("Incorrect RH format, use HH:MM.")
                return
        else:
            net_rh = "00:00"
 
        maximum_demand = st.number_input("Maximum Demand (kVA)", min_value=0.0)
        remarks = st.text_area("Remarks")
 
        if st.button("Submit Entry"):
            try:
                supabase.table("dg_transactions").insert({
                    "date": date,
                    "toll_plaza": toll_plaza,
                    "dg_name": dg_name,
                    "diesel_purchase": diesel_purchase,
                    "diesel_topup": diesel_topup,
                    "updated_plaza_barrel_stock": updated_plaza_barrel_stock,
                    "opening_diesel_stock": opening_diesel_stock,
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
 
                update_live_plaza_stock(toll_plaza, updated_plaza_barrel_stock)
                update_opening_status(toll_plaza, dg_name, closing_diesel_stock, closing_kwh, closing_rh)
 
                st.success("✅ Data submitted successfully.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Submission failed: {e}")
 
    elif choice == "Last 10 Transactions":
        st.subheader("📄 Last 10 DG Transactions")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"], key="last_tp")
        dg_name = st.selectbox("Select DG Name", ["DG1", "DG2"], key="last_dg")
        resp = supabase.table("dg_transactions").select("*").eq("toll_plaza", toll_plaza).eq("dg_name", dg_name).order("id", desc=True).limit(10).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            st.dataframe(df)
        else:
            st.info("No transactions found.")
 
    elif choice == "Admin Block":
        st.subheader("🔐 Admin Initialization Block")
        password = st.text_input("Enter Admin Password", type="password")
        if password == "Sekura@2025":
            st.success("Access Granted")
            toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"], key="admin_tp")
            dg_name = st.selectbox("Select DG Name", ["DG1", "DG2"], key="admin_dg")
 
            init_barrel_stock = st.number_input("Initialize Plaza Barrel Stock", min_value=0.0)
            init_diesel_stock = st.number_input("Initialize Opening Diesel Stock at DG", min_value=0.0)
            init_opening_kwh = st.number_input("Initialize Opening KWH", min_value=0.0)
            init_opening_rh = st.text_input("Initialize Opening RH (HH:MM)", "00:00")
 
            if st.button("Save Initialization"):
                try:
                    update_live_plaza_stock(toll_plaza, init_barrel_stock)
                    update_opening_status(toll_plaza, dg_name, init_diesel_stock, init_opening_kwh, init_opening_rh)
                    st.success("✅ Initialization data saved successfully.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Initialization failed: {e}")
        else:
            if password != "":
                st.error("Incorrect password. Try again.")
 
    elif choice == "Download CSV":
        st.subheader("📥 Download DG Transactions as CSV")
        from_date = st.date_input("From Date", datetime.now() - timedelta(days=7))
        to_date = st.date_input("To Date", datetime.now())
        if st.button("Download CSV"):
            resp = supabase.table("dg_transactions").select("*").gte("date", str(from_date)).lte("date", str(to_date)).execute()
            if resp.data:
                df = pd.DataFrame(resp.data)
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download CSV", csv, "dg_transactions.csv", "text/csv")
            else:
                st.info("No data found for the selected period.")
