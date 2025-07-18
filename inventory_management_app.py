import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import os
 
# Initialize Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
 
def run():
    st.title("🏗️ Inventory Management Module")
 
    menu = ["User Block", "Admin Block", "Last 10 Transactions", "Download CSV"]
    choice = st.sidebar.selectbox("Select Action", menu)
 
    if choice == "Admin Block":
        st.header("🛠️ Admin Block (Upload Initial Stock Data)")
        password = st.text_input("Enter Admin Password", type="password")
        if password != "Sekura@2025":
            st.warning("🔒 Enter correct admin password to proceed.")
            return
 
        uploaded_file = st.file_uploader("Upload CSV file (toll_plaza, material_code, material_name, available_stock)", type=["csv"])
        if uploaded_file is not None:
            df = pd.read_csv(uploaded_file)
            records = df.to_dict(orient='records')
            for record in records:
                supabase.table("material_stock").upsert(record).execute()
            st.success("✅ Stock data uploaded/updated successfully.")
            st.dataframe(df)
 
        elif choice == "User Block":
        st.header("📝 User Entry")
 
date = st.date_input("Select Date", value=datetime.today())
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
 
        search_mode = st.radio("Search Material By", ["Material Code", "Material Name"])
 
        material_code = ""
        material_name = ""
        available_stock = 0
 
        if search_mode == "Material Code":
            material_code_input = st.text_input("Enter Material Code (numeric)")
            if material_code_input:
                resp = supabase.table("material_stock").select("*").eq("toll_plaza", toll_plaza).eq("material_code", material_code_input).execute()
                if resp.data:
                    data = resp.data[0]
                    material_code = data["material_code"]
                    material_name = data["material_name"]
                    available_stock = data["available_stock"]
                else:
                    st.warning("⚠️ Material code not found for selected plaza.")
        else:
            material_name_input = st.text_input("Enter Material Name Keyword")
            if material_name_input:
                resp = supabase.table("material_stock").select("*").eq("toll_plaza", toll_plaza).ilike("material_name", f"%{material_name_input}%").execute()
                if resp.data:
                    data = resp.data[0]
                    material_code = data["material_code"]
                    material_name = data["material_name"]
                    available_stock = data["available_stock"]
                else:
                    st.warning("⚠️ Material name keyword not found for selected plaza.")
 
        if material_code:
st.info(f"🔹 Material Code: {material_code}")
st.info(f"🔹 Material Name: {material_name}")
st.info(f"📦 Available Stock: {available_stock} units")
 
            transaction_type = st.selectbox("Transaction Type", ["Stock In", "Stock Out"])
            quantity = st.number_input("Quantity", min_value=0.0, step=1.0)
 
            if transaction_type == "Stock In":
                source_type = st.text_input("Source Type (e.g., Vendor, Transfer)")
                material_consumption = ""
            else:
                material_consumption = st.text_input("Material Consumption (e.g., Repair, Project)")
                source_type = ""
 
            remarks = st.text_area("Remarks (optional)")
 
            if st.button("Submit"):
                if quantity <= 0:
                    st.error("❌ Quantity must be greater than zero.")
                    return
 
                if transaction_type == "Stock In":
                    updated_stock = available_stock + quantity
                else:
                    if quantity > available_stock:
                        st.error(f"❌ Quantity exceeds available stock ({available_stock}).")
                        return
                    updated_stock = available_stock - quantity
 
                # Insert into inventory_transactions
                transaction_data = {
                    "date": str(date),
                    "material_code": material_code,
                    "material_name": material_name,
                    "transaction_type": transaction_type,
                    "quantity": quantity,
                    "source_type": source_type,
                    "material_consumption": material_consumption,
                    "updated_available_stock": updated_stock,
                    "remarks": remarks,
                    "created_at": datetime.now().isoformat()
                }
                supabase.table("inventory_transactions").insert(transaction_data).execute()
 
                # Update material_stock table
                supabase.table("material_stock").upsert({
                    "toll_plaza": toll_plaza,
                    "material_code": material_code,
                    "material_name": material_name,
                    "available_stock": updated_stock
                }).execute()
 
                st.success("✅ Transaction recorded and stock updated successfully.")
                st.rerun()
 
    elif choice == "Last 10 Transactions":
        st.header("📜 Last 10 Transactions Per TP")
        toll_plaza = st.selectbox("Select Toll Plaza for Viewing Transactions", ["TP01", "TP02", "TP03"])
        resp = supabase.table("inventory_transactions").select("*").eq("toll_plaza", toll_plaza).order("created_at", desc=True).limit(10).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            st.dataframe(df)
        else:
st.info("No transactions found for this plaza.")
 
    elif choice == "Download CSV":
        st.header("📥 Download All Transactions as CSV")
        resp = supabase.table("inventory_transactions").select("*").order("created_at", desc=True).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", data=csv, file_name="all_inventory_transactions.csv", mime="text/csv")
            st.success("✅ CSV ready for download.")
        else:
st.info("No transaction data available to download.")
 
if __name__ == "__main__":
    run()
