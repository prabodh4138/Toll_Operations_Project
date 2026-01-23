import os
from datetime import datetime
from difflib import SequenceMatcher

import pandas as pd
import streamlit as st
from supabase import create_client

# ---------- Supabase init ----------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- User credentials ----------
USER_CREDENTIALS = {
    "TP01": {"user": "tp01", "password": "TP01@123"},
    "TP02": {"user": "tp02", "password": "TP02@123"},
    "TP03": {"user": "tp03", "password": "TP03@123"},
}


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def run():
    st.set_page_config(page_title="Sekura Toll Inventory", layout="wide")
    st.title("📦 Toll Plaza Inventory Management")

    # ---------- LOGIN ----------
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_plaza = None

    if not st.session_state.logged_in:
        st.subheader("🔐 Toll Plaza Login")
        plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        username = st.text_input("User ID")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            cred = USER_CREDENTIALS.get(plaza)
            if cred and username == cred["user"] and password == cred["password"]:
                st.session_state.logged_in = True
                st.session_state.user_plaza = plaza
                st.success(f"✅ Logged in as {plaza}")
                st.experimental_rerun()
            else:
                st.error("❌ Invalid credentials")
        return

    # ---------- SIDEBAR ----------
    st.sidebar.success(f"Logged in Plaza: {st.session_state.user_plaza}")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.experimental_rerun()

    menu = ["User Block", "Admin Block", "Last 10 Transactions", "Download CSV"]
    choice = st.sidebar.selectbox("Select Action", menu)

    st.session_state.setdefault("selected_labels", [])

    # ---------- ADMIN BLOCK ----------
    if choice == "Admin Block":
        st.header("🔒 Admin Block")
        password = st.text_input("Enter Admin Password", type="password")
        if password == "Sekura@2025":
            csv_file = st.file_uploader("Upload CSV", type=["csv"])
            if csv_file:
                df = pd.read_csv(csv_file)
                st.dataframe(df)
                if st.button("Upload Data"):
                    for _, row in df.iterrows():
                        supabase.table("material_stock").upsert({
                            "toll_plaza": row["toll_plaza"],
                            "material_code": str(row["material_code"]),
                            "material_name": row["material_name"],
                            "available_stock": float(row["available_stock"]),
                        }).execute()
                    st.success("✅ Stock uploaded")
        elif password:
            st.error("❌ Wrong password")

    # ---------- USER BLOCK ----------
    elif choice == "User Block":
        st.header("📝 User Entry")

        date = st.date_input("Date", value=datetime.today())
        view_plaza = st.selectbox("View Stock of Toll Plaza", ["TP01", "TP02", "TP03"])

        can_transact = view_plaza == st.session_state.user_plaza

        search_mode = st.radio("Search By", ["Material Code", "Material Name"])

        material_code = ""
        material_name = ""
        available_stock = 0.0

        # ---- SEARCH BY CODE ----
        if search_mode == "Material Code":
            code_input = st.text_input("Material Code")
            if code_input:
                resp = supabase.table("material_stock").select("*") \
                    .eq("toll_plaza", view_plaza) \
                    .eq("material_code", code_input).execute()
                if resp.data:
                    d = resp.data[0]
                    material_code = d["material_code"]
                    material_name = d["material_name"]
                    available_stock = float(d["available_stock"])
                    st.success(f"{material_name} | Avail: {available_stock}")
                else:
                    st.warning("Not found")

        # ---- SEARCH BY NAME ----
        else:
            keyword = st.text_input("Material Name")
            resp = supabase.table("material_stock").select("*") \
                .eq("toll_plaza", view_plaza).execute()

            rows = resp.data or []
            suggestions = []
            for r in rows:
                if keyword.lower() in (r["material_name"] or "").lower():
                    suggestions.append(r)

            if suggestions:
                df = pd.DataFrame(suggestions)
                st.dataframe(df)
                sel = st.selectbox("Select Material", df["material_name"])
                row = df[df["material_name"] == sel].iloc[0]
                material_code = row["material_code"]
                material_name = row["material_name"]
                available_stock = float(row["available_stock"])

        # ---- TRANSACTION ----
        if material_code:
            st.info(f"Available Stock: {available_stock}")

            if not can_transact:
                st.error(
                    f"❌ You are logged in as {st.session_state.user_plaza}. "
                    f"Transaction allowed only for your plaza."
                )
                return

            txn_type = st.selectbox("Transaction Type", ["Stock In", "Stock Out"])
            qty = st.number_input("Quantity", min_value=0.0)
            remarks = st.text_area("Remarks")

            if st.button("Submit Transaction"):
                updated = available_stock + qty if txn_type == "Stock In" else available_stock - qty

                supabase.table("inventory_transactions").insert({
                    "date": date.strftime("%Y-%m-%d"),
                    "toll_plaza": view_plaza,
                    "material_code": material_code,
                    "material_name": material_name,
                    "transaction_type": txn_type,
                    "quantity": float(qty),
                    "updated_available_stock": float(updated),
                    "remarks": remarks,
                    "created_at": datetime.now().isoformat()
                }).execute()

                supabase.table("material_stock").upsert({
                    "toll_plaza": view_plaza,
                    "material_code": material_code,
                    "material_name": material_name,
                    "available_stock": float(updated)
                }).execute()

                st.success("✅ Transaction completed")
                st.experimental_rerun()

    # ---------- LAST 10 ----------
    elif choice == "Last 10 Transactions":
        tp = st.selectbox("Select Plaza", ["TP01", "TP02", "TP03"])
        resp = supabase.table("inventory_transactions").select("*") \
            .order("id", desc=True).limit(10).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            st.dataframe(df[df["toll_plaza"] == tp])

    # ---------- DOWNLOAD ----------
    elif choice == "Download CSV":
        resp = supabase.table("inventory_transactions").select("*").execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            st.download_button(
                "Download CSV",
                df.to_csv(index=False).encode(),
                "inventory_transactions.csv",
                "text/csv"
            )


if __name__ == "__main__":
    run()
