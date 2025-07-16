import streamlit as st
from supabase import create_client
from datetime import datetime
from dotenv import load_dotenv
import os
import pandas as pd
 
# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
 
# Parse RH string to minutes
def parse_rh(rh_str):
    try:
        parts = rh_str.strip().split(":")
        if len(parts) != 2:
            return None
        hours = int(parts[0])
        minutes = int(parts[1])
        if minutes >= 60 or hours < 0 or minutes < 0:
            return None
        return hours * 60 + minutes
    except:
        return None
 
# Calculate Net RH
def calculate_net_rh(opening_rh, closing_rh):
    open_min = parse_rh(opening_rh)
    close_min = parse_rh(closing_rh)
    if open_min is None or close_min is None:
        return None, "❌ RH format must be hh:mm with valid numbers."
    if close_min < open_min:
        return None, "❌ Closing RH must be greater than or equal to Opening RH."
    net_min = close_min - open_min
    net_hours = net_min // 60
    net_minutes = net_min % 60
    return f"{net_hours}:{net_minutes:02d}", None
 
def run():
    st.title("⚡ DG Monitoring Module")
 
    menu = ["User Entry", "Admin Initialization", "Last 10 Transactions"]
    choice = st.sidebar.selectbox("Select Action", menu)
 
    if choice == "Admin Initialization":
        st.header("🛠️ Admin Initialization")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        dg_name = st.selectbox("Select DG", ["DG1", "DG2"])
        opening_diesel_stock = st.number_input("Opening Diesel Stock (L)", min_value=0.0)
        opening_kwh = st.number_input("Opening KWH", min_value=0.0)
        opening_rh = st.text_input("Opening RH (hh:mm)")
 
        if st.button("Initialize"):
            if parse_rh(opening_rh) is None:
                st.error("❌ Invalid RH format. Enter in hh:mm.")
                return
 
            data = {
                "toll_plaza": toll_plaza,
                "dg_name": dg_name,
                "opening_diesel_stock": opening_diesel_stock,
                "opening_kwh": opening_kwh,
                "opening_rh": opening_rh
            }
 
            resp = supabase.table("dg_opening_status").upsert(data).execute()
            if resp.error is None:
                st.success("✅ Initialization saved successfully.")
 
                # Initialize dg_live_status for plaza if not exists
                live_resp = supabase.table("dg_live_status").select("*").eq("toll_plaza", toll_plaza).execute()
                if not live_resp.data:
                    supabase.table("dg_live_status").insert({
                        "toll_plaza": toll_plaza,
                        "updated_plaza_barrel_stock": 0
                    }).execute()
 
            else:
                st.error(f"❌ Initialization failed: {resp.error}")
 
    elif choice == "User Entry":
        st.header("📝 User Entry")
 
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        dg_name = st.selectbox("Select DG", ["DG1", "DG2"])
        diesel_purchase = st.number_input("Diesel Purchase (L)", min_value=0.0, value=0.0)
        diesel_topup = st.number_input("Diesel Topup (L)", min_value=0.0, value=0.0)
 
        # Fetch opening values
        resp = supabase.table("dg_opening_status").select("*").eq("toll_plaza", toll_plaza).eq("dg_name", dg_name).execute()
        if resp.error or not resp.data:
            st.error("❌ Initialization missing for this Plaza/DG. Please contact admin.")
            return
 
        open_data = resp.data[0]
        opening_diesel_stock = open_data.get("opening_diesel_stock", 0)
        opening_kwh = open_data.get("opening_kwh", 0)
        opening_rh = open_data.get("opening_rh", "0:00")
 
        st.info(f"🔹 Opening Diesel Stock: {opening_diesel_stock} L")
        st.info(f"🔹 Opening KWH: {opening_kwh}")
        st.info(f"🔹 Opening RH: {opening_rh}")
 
        closing_diesel_stock = st.number_input("Closing Diesel Stock (L)", min_value=0.0)
        max_closing = opening_diesel_stock + diesel_topup
        if closing_diesel_stock > max_closing:
            st.error(f"❌ Closing Diesel Stock cannot exceed {max_closing} L (Opening + Topup).")
            return
 
        diesel_consumption = opening_diesel_stock + diesel_topup - closing_diesel_stock
 
        closing_kwh = st.number_input("Closing KWH", min_value=0.0)
        if closing_kwh < opening_kwh:
            st.error("❌ Closing KWH must be greater than or equal to Opening KWH.")
            return
        net_kwh = closing_kwh - opening_kwh
 
        closing_rh = st.text_input("Closing RH (hh:mm)")
        net_rh, rh_error = calculate_net_rh(opening_rh, closing_rh)
        if rh_error:
            st.error(rh_error)
            return
 
        maximum_demand = st.number_input("Maximum Demand (kVA)", min_value=0.0)
        remarks = st.text_area("Remarks (Optional)")
 
        if st.button("Submit Entry"):
            date = datetime.now().strftime("%Y-%m-%d")
            # Update dg_live_status barrel stock for plaza
            live_resp = supabase.table("dg_live_status").select("*").eq("toll_plaza", toll_plaza).execute()
            if live_resp.error is None and live_resp.data:
                prev_stock = live_resp.data[0].get("updated_plaza_barrel_stock", 0)
            else:
                prev_stock = 0
 
            updated_plaza_barrel_stock = prev_stock + diesel_purchase
 
            # Upsert updated barrel stock
            supabase.table("dg_live_status").upsert({
                "toll_plaza": toll_plaza,
                "updated_plaza_barrel_stock": updated_plaza_barrel_stock
            }).execute()
 
            # Insert transaction
            data = {
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
            }
 
            resp = supabase.table("dg_transactions").insert(data).execute()
            if resp.error is None:
                st.success("✅ Entry submitted successfully.")
                st.rerun()
            else:
                st.error(f"❌ Submission failed: {resp.error}")
 
    elif choice == "Last 10 Transactions":
        st.header("📜 Last 10 DG Transactions")
        resp = supabase.table("dg_transactions").select("*").order("id", desc=True).limit(10).execute()
        if resp.error is None and resp.data:
            df = pd.DataFrame(resp.data)
            st.dataframe(df)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download CSV", data=csv, file_name="dg_last_10_transactions.csv", mime="text/csv")
        else:
            st.info("No transactions found.")
 
if __name__ == "__main__":
    run()
 
