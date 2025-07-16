import streamlit as st
from datetime import datetime
from supabase import create_client
import pandas as pd
import re
import os
 
# Initialize Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)
 
def calculate_net_rh(opening_rh, closing_rh):
    fmt = "%H:%M"
    tdelta = datetime.strptime(closing_rh, fmt) - datetime.strptime(opening_rh, fmt)
    total_minutes = tdelta.total_seconds() // 60
    hours = int(total_minutes // 60)
    minutes = int(total_minutes % 60)
    return f"{hours:02d}:{minutes:02d}"
 
def run():
    st.title("🔋 DG Monitoring")
 
    tabs = st.tabs(["Admin: Initialize Data", "User: Submit Readings", "View Transactions", "Download CSV"])
 
    # ----------------------- ADMIN BLOCK -----------------------
    with tabs[0]:
        st.subheader("🛠️ Admin: Initialize DG Data")
 
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        dg_name = st.text_input("Enter DG Name", placeholder="e.g., DG01")
 
        opening_diesel_stock = st.number_input("Opening Diesel Stock (L)", min_value=0.0, format="%.2f")
        opening_kwh = st.number_input("Opening KWH", min_value=0.0, format="%.2f")
        opening_rh = st.text_input("Opening RH (HH:MM)", placeholder="e.g., 07:30")
 
        if st.button("Initialize / Update"):
            # Validate RH Format
            rh_pattern = re.compile(r"^\d{2}:\d{2}$")
            if not rh_pattern.match(opening_rh):
                st.error("Invalid RH format. Please enter in HH:MM (e.g., 07:30).")
            else:
                # Upsert into dg_opening_status
                data = {
                    "toll_plaza": toll_plaza,
                    "dg_name": dg_name,
                    "opening_diesel_stock": opening_diesel_stock,
                    "opening_kwh": opening_kwh,
                    "opening_rh": opening_rh,
                }
                resp = supabase.table("dg_opening_status").upsert(data).execute()
                if resp.status_code in [200, 201]:
                    st.success("Initialization successful.")
                else:
                    st.error(f"Initialization failed: {resp.data}")
 
    # ----------------------- USER BLOCK -----------------------
    with tabs[1]:
        st.subheader("📝 User: Submit DG Meter Reading")
 
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"], key="user_tp")
        dg_name = st.text_input("Enter DG Name", placeholder="e.g., DG01", key="user_dg")
        date = st.date_input("Date", datetime.now()).strftime("%Y-%m-%d")
 
        # Fetch opening parameters dynamically
        opening_data = supabase.table("dg_opening_status").select("*").eq("toll_plaza", toll_plaza).eq("dg_name", dg_name).execute()
        if opening_data.data:
            opening_kwh_val = opening_data.data[0]["opening_kwh"] or 0.0
            opening_rh_val = opening_data.data[0]["opening_rh"] or "00:00"
            opening_diesel_stock_val = opening_data.data[0]["opening_diesel_stock"] or 0.0
        else:
            opening_kwh_val = 0.0
            opening_rh_val = "00:00"
            opening_diesel_stock_val = 0.0
 
        st.info(f"Opening KWH: {opening_kwh_val} | Opening RH: {opening_rh_val} | Opening Diesel: {opening_diesel_stock_val} L")
 
        closing_kwh = st.number_input("Closing KWH", min_value=0.0, format="%.2f")
        closing_rh = st.text_input("Closing RH (HH:MM)", placeholder="e.g., 08:45")
        diesel_purchase = st.number_input("Diesel Purchase (L)", min_value=0.0, format="%.2f")
        diesel_topup = st.number_input("Diesel Top-up from Barrel (L)", min_value=0.0, format="%.2f")
        closing_diesel_stock = st.number_input("Closing Diesel Stock in DG (L)", min_value=0.0, format="%.2f")
        maximum_demand = st.number_input("Maximum Demand (kVA)", min_value=0.0, format="%.2f")
        remarks = st.text_area("Remarks (optional)")
 
        if st.button("Submit Reading"):
            rh_pattern = re.compile(r"^\d{2}:\d{2}$")
            if not rh_pattern.match(closing_rh) or not rh_pattern.match(opening_rh_val):
                st.error("Incorrect RH format. Please use HH:MM format.")
            else:
                try:
                    net_rh = calculate_net_rh(opening_rh_val, closing_rh)
                except Exception as e:
                    st.error(f"Error calculating Net RH: {e}")
                    net_rh = "00:00"
 
                net_kwh = closing_kwh - opening_kwh_val
                diesel_consumption = opening_diesel_stock_val + diesel_topup - closing_diesel_stock
 
                # Update dg_live_status
                barrel_stock_resp = supabase.table("dg_live_status").upsert({
                    "toll_plaza": toll_plaza,
                    "updated_plaza_barrel_stock": diesel_purchase
                }).execute()
 
                # Insert into dg_transactions
                insert_data = {
                    "date": date,
                    "toll_plaza": toll_plaza,
                    "dg_name": dg_name,
                    "diesel_purchase": diesel_purchase,
                    "diesel_topup": diesel_topup,
                    "updated_plaza_barrel_stock": diesel_purchase,
                    "opening_diesel_stock": opening_diesel_stock_val,
                    "closing_diesel_stock": closing_diesel_stock,
                    "diesel_consumption": diesel_consumption,
                    "opening_kwh": opening_kwh_val,
                    "closing_kwh": closing_kwh,
                    "net_kwh": net_kwh,
                    "opening_rh": opening_rh_val,
                    "closing_rh": closing_rh,
                    "net_rh": net_rh,
                    "maximum_demand": maximum_demand,
                    "remarks": remarks
                }
                insert_resp = supabase.table("dg_transactions").insert(insert_data).execute()
                if insert_resp.status_code in [200, 201]:
                    st.success("Reading submitted successfully.")
                    st.experimental_rerun()
                else:
                    st.error(f"Submission failed: {insert_resp.data}")
 
    # ----------------------- VIEW TRANSACTIONS -----------------------
    with tabs[2]:
        st.subheader("📊 View DG Transactions")
        data_resp = supabase.table("dg_transactions").select("*").order("id", desc=True).limit(100).execute()
        if data_resp.data:
            df = pd.DataFrame(data_resp.data)
            st.dataframe(df)
        else:
            st.info("No transactions found.")
 
    # ----------------------- DOWNLOAD CSV -----------------------
    with tabs[3]:
        st.subheader("⬇️ Download DG Data as CSV")
        data_resp = supabase.table("dg_transactions").select("*").order("id", desc=True).execute()
        if data_resp.data:
            df = pd.DataFrame(data_resp.data)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "dg_transactions.csv", "text/csv")
        else:
            st.info("No data available for download.")
 
