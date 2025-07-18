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
    st.title("📦 Toll Plaza Inventory Management")
 
    menu = ["User Block", "Admin Block", "Last 10 Transactions", "Download CSV"]
    choice = st.sidebar.selectbox("Select Action", menu)
 
    if choice == "Admin Block":
        st.header("🔒 Admin Block")
        password = st.text_input("Enter Admin Password", type="password")
        if password == "Sekura@2025":
            st.success("Access Granted ✅")
 
            st.info("Upload CSV with columns: toll_plaza, material_code, material_name, available_stock")
 
            csv_file = st.file_uploader("Upload CSV", type=["csv"])
            if csv_file:
                df = pd.read_csv(csv_file)
                st.dataframe(df)
 
                if st.button("Upload Data"):
                    for _, row in df.iterrows():
                        record = {
                            "toll_plaza": row["toll_plaza"],
                            "material_code": str(row["material_code"]),
                            "material_name": row["material_name"],
                            "available_stock": float(row["available_stock"])
                        }
                        supabase.table("material_stock").upsert(record).execute()
                    st.success("✅ Stock data uploaded/updated successfully.")
        else:
            if password != "":
                st.error("❌ Incorrect password.")
 
    elif choice == "User Block":
        st.header("📝 User Entry")
 
        date = st.date_input("Select Date", value=datetime.today())
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
 
        search_mode = st.radio("Search Material By", ["Material Code", "Material Name"])
        material_code = ""
        material_name = ""
        available_stock = 0
 
        if search_mode == "Material Code":
            material_code_input = st.text_input("Enter Material Code")
            if material_code_input:
                resp = supabase.table("material_stock").select("*").eq("toll_plaza", toll_plaza).eq("material_code", material_code_input).execute()
                if resp.data:
                    data = resp.data[0]
                    material_code = data["material_code"]
                    material_name = data["material_name"]
                    available_stock = data["available_stock"]
                    st.success(f"Material Found: {material_name}, Available Stock: {available_stock}")
                else:
                    st.warning("Material not found under this Toll Plaza.")
        else:
            material_name_input = st.text_input("Enter Material Name Keyword")
            if material_name_input:
                resp = supabase.table("material_stock").select("*").eq("toll_plaza", toll_plaza).ilike("material_name", f"%{material_name_input}%").execute()
                if resp.data:
                    data = resp.data[0]
                    material_code = data["material_code"]
                    material_name = data["material_name"]
                    available_stock = data["available_stock"]
                    st.success(f"Material Found: {material_name}, Code: {material_code}, Available Stock: {available_stock}")
                else:
                    st.warning("Material not found under this Toll Plaza.")
 
        if material_code:
            st.info(f"Available Stock: {available_stock} for Material Code: {material_code}")
 
            transaction_type = st.selectbox("Transaction Type", ["Stock In", "Stock Out"])
            quantity = st.number_input("Quantity", min_value=0.0)
 
            if transaction_type == "Stock In":
                source_type = st.text_input("Source Type")
                material_consumption = None
            else:
                material_consumption = st.text_input("Material Consumption")
                source_type = None
 
            remarks = st.text_area("Remarks (Optional)")
 
            if st.button("Submit Transaction"):
                if quantity <= 0:
                    st.error("❌ Quantity should be greater than zero.")
                    return
 
                if transaction_type == "Stock In":
                    updated_stock = available_stock + quantity
                else:
                    if quantity > available_stock:
                        st.error("❌ Cannot issue more than available stock.")
                        return
                    updated_stock = available_stock - quantity
 
                record = {
                    "date": date.strftime("%Y-%m-%d"),
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
 
                # Insert into transactions
                supabase.table("inventory_transactions").insert(record).execute()
                # Update material_stock
                supabase.table("material_stock").upsert({
                    "toll_plaza": toll_plaza,
                    "material_code": material_code,
                    "material_name": material_name,
                    "available_stock": updated_stock
                }).execute()
 
                st.success(f"✅ Transaction submitted successfully. Updated Stock: {updated_stock}")
                st.rerun()
 
    elif choice == "Last 10 Transactions":
        st.header("📜 Last 10 Transactions Per TP")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        resp = supabase.table("inventory_transactions").select("*").order("id", desc=True).limit(50).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            df_tp = df[df["material_code"].isin(
                pd.Series(
                    supabase.table("material_stock").select("material_code").eq("toll_plaza", toll_plaza).execute().data
                ).apply(lambda x: x["material_code"])
            )]
            st.dataframe(df_tp.head(10))
        else:
            st.info("No transactions found.")
 
    elif choice == "Download CSV":
        st.header("📥 Download All Transactions")
        resp = supabase.table("inventory_transactions").select("*").order("id", desc=True).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download All Transactions CSV", data=csv, file_name="all_inventory_transactions.csv", mime="text/csv")
        else:
            st.info("No data available to download.")
 
if __name__ == "__main__":
    run()
 
