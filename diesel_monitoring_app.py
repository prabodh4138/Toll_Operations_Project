import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
 
# Direct Supabase credentials (EDIT HERE)
SUPABASE_URL = "https://maqujrsyrwrlirjodgoi.supabase.co""
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1hcXVqcnN5cndybGlyam9kZ29pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI1MDc4MTUsImV4cCI6MjA2ODA4MzgxNX0.LkQGWv21Nuh8GUO-nY6KUHTB3VULxvXnGcwK0E_PbTA"
 
# Initialize Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
 
# Parse RH "hh:mm" to minutes
def parse_rh(rh_str):
    try:
        h, m = rh_str.strip().split(":")
        h = int(h)
        m = int(m)
        if m >= 60 or h < 0 or m < 0:
            return None
        return h * 60 + m
    except:
        return None
 
# Calculate net RH
def calculate_net_rh(opening_rh, closing_rh):
    open_min = parse_rh(opening_rh)
    close_min = parse_rh(closing_rh)
    if open_min is None or close_min is None:
        return None, "❌ RH format must be hh:mm (e.g., 3210:45)"
    if close_min < open_min:
        return None, "❌ Closing RH must be greater than or equal to Opening RH."
    net_min = close_min - open_min
    return f"{net_min // 60}:{net_min % 60:02d}", None
 
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
                st.error("❌ Invalid RH format. Use hh:mm.")
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
 
                # Ensure dg_live_status entry
                live_resp = supabase.table("dg_live_status").select("*").eq("toll_plaza", toll_plaza).execute()
                if not live_resp.data:
                    supabase.table("dg_live_status").insert({
                        "toll_plaza": toll_plaza,
                        "updated_plaza_barrel_stock": 0
                    }).execute()
                st.rerun()
            else:
                st.error(f"❌ Initialization failed: {resp.error}")
 
    elif choice == "User Entry":
        st.header("📝 DG Daily Entry")
 
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        dg_name = st.selectbox("Select DG", ["DG1", "DG2"])
 
        diesel_purchase = st.number_input("Diesel Purchase (L)", min_value=0.0, value=0.0)
        diesel_topup = st.number_input("Diesel Topup (L)", min_value=0.0, value=0.0)
 
        # Fetch opening values
        resp = supabase.table("dg_opening_status").select("*").eq("toll_plaza", toll_plaza).eq("dg_name", dg_name).execute()
        if not resp.data:
            st.warning("⚠️ Please initialize first in Admin Initialization.")
            return
        data = resp.data[0]
        opening_diesel_stock = data.get("opening_diesel_stock", 0)
        opening_kwh = data.get("opening_kwh", 0)
        opening_rh = data.get("opening_rh", "0:00")
 
        st.success("🔹 Virtual Dynamic Opening Parameters:")
        st.info(f"Opening Diesel Stock: {opening_diesel_stock} L")
        st.info(f"Opening KWH: {opening_kwh}")
        st.info(f"Opening RH: {opening_rh}")
 
        closing_diesel_stock = st.number_input("Closing Diesel Stock (L)", min_value=0.0)
        if closing_diesel_stock > opening_diesel_stock + diesel_topup:
            st.error("❌ Closing Diesel Stock cannot exceed (Opening + Topup).")
            return
        diesel_consumption = opening_diesel_stock + diesel_topup - closing_diesel_stock
 
        closing_kwh = st.number_input("Closing KWH", min_value=0.0)
        if closing_kwh < opening_kwh:
            st.error("❌ Closing KWH cannot be less than Opening KWH.")
            return
        net_kwh = closing_kwh - opening_kwh
 
        closing_rh = st.text_input("Closing RH (hh:mm)")
        net_rh, rh_error = calculate_net_rh(opening_rh, closing_rh)
        if rh_error:
            st.error(rh_error)
            return
 
        maximum_demand = st.number_input("Maximum Demand (kVA)", min_value=0.0)
        remarks = st.text_area("Remarks (optional)")
        date = datetime.now().strftime("%Y-%m-%d")
 
        if st.button("Submit Entry"):
            # Update dg_live_status with diesel purchase
            live_resp = supabase.table("dg_live_status").select("*").eq("toll_plaza", toll_plaza).execute()
            current_barrel = live_resp.data[0]["updated_plaza_barrel_stock"] if live_resp.data else 0
            updated_barrel = current_barrel + diesel_purchase
 
            supabase.table("dg_live_status").upsert({
                "toll_plaza": toll_plaza,
                "updated_plaza_barrel_stock": updated_barrel
            }).execute()
 
            transaction = {
                "date": date,
                "toll_plaza": toll_plaza,
                "dg_name": dg_name,
                "diesel_purchase": diesel_purchase,
                "diesel_topup": diesel_topup,
                "updated_plaza_barrel_stock": updated_barrel,
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
            insert_resp = supabase.table("dg_transactions").insert(transaction).execute()
            if insert_resp.error is None:
                st.success("✅ Entry submitted successfully.")
                st.rerun()
            else:
                st.error(f"❌ Submission failed: {insert_resp.error}")
 
    elif choice == "Last 10 Transactions":
        st.header("📜 Last 10 Transactions")
        resp = supabase.table("dg_transactions").select("*").order("id", desc=True).limit(10).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            st.dataframe(df)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", data=csv, file_name="dg_last_10_transactions.csv", mime="text/csv")
        else:
            st.info("No transactions found.")
 
if __name__ == "__main__":
    run()
 
