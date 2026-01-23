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

# ---------- User credentials (1 user per plaza) ----------
USER_CREDENTIALS = {
    "TP01": {"user": "tp01", "password": "TP01@123"},
    "TP02": {"user": "tp02", "password": "TP02@123"},
    "TP03": {"user": "tp03", "password": "TP03@123"},
}

# ---------- Helpers ----------
def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def highlight_transfer_status(row, my_plaza):
    styles = [""] * len(row)

    status = row["status"]
    action = row.get("My Action", "")

    if "PENDING" in status:
        styles[row.index.get_loc("status")] = "background-color: #FFF3CD"
    elif "ACCEPTED" in status:
        styles[row.index.get_loc("status")] = "background-color: #D4EDDA"
    elif "REJECTED" in status:
        styles[row.index.get_loc("status")] = "background-color: #F8D7DA"

    if action:
        styles[row.index.get_loc("My Action")] = "background-color: #FFE5B4"

    return styles


# ---------- MAIN APP ----------
def run():
    st.set_page_config(page_title="Sekura Toll Inventory", layout="wide")
    st.title("📦 Toll Plaza Inventory Management")

    # ---------- LOGIN ----------
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_plaza = None
        st.session_state.user_id = None

    if not st.session_state.logged_in:
        st.subheader("🔐 Toll Plaza Login")

        plaza = st.selectbox("Toll Plaza", ["TP01", "TP02", "TP03"])
        username = st.text_input("User ID")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            cred = USER_CREDENTIALS.get(plaza)
            if cred and username == cred["user"] and password == cred["password"]:
                st.session_state.logged_in = True
                st.session_state.user_plaza = plaza
                st.session_state.user_id = username
                st.success(f"✅ Logged in as {plaza}")
                st.rerun()
            else:
                st.error("❌ Invalid credentials")
        return

    # ---------- SIDEBAR ----------
    st.sidebar.success(f"Logged in: {st.session_state.user_plaza}")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    menu = [
        "User Block",
        "Stock Transfer",
        "Transfer Inbox",
        "Transfer Dashboard",
        "Admin Block",
        "Audit Log",
        "Last 10 Transactions",
        "Download CSV",
    ]
    choice = st.sidebar.selectbox("Select Action", menu)

    # ---------- USER BLOCK ----------
    if choice == "User Block":
        st.header("📝 User Entry")

        date = st.date_input("Date", value=datetime.today())
        view_plaza = st.selectbox("View Stock of Plaza", ["TP01", "TP02", "TP03"])
        can_transact = view_plaza == st.session_state.user_plaza

        search_mode = st.radio("Search By", ["Material Code", "Material Name"])

        material_code = ""
        material_name = ""
        available_stock = 0.0

        if search_mode == "Material Code":
            code = st.text_input("Material Code")
            if code:
                resp = supabase.table("material_stock").select("*") \
                    .eq("toll_plaza", view_plaza) \
                    .eq("material_code", code).execute()
                if resp.data:
                    d = resp.data[0]
                    material_code = d["material_code"]
                    material_name = d["material_name"]
                    available_stock = float(d["available_stock"])
                    st.success(f"{material_name} | Avail: {available_stock}")
                else:
                    st.warning("Not found")

        else:
            keyword = st.text_input("Material Name")
            resp = supabase.table("material_stock").select("*") \
                .eq("toll_plaza", view_plaza).execute()
            rows = resp.data or []

            matches = [
                r for r in rows
                if keyword.lower() in (r["material_name"] or "").lower()
            ]

            if matches:
                df = pd.DataFrame(matches)
                st.dataframe(df)
                sel = st.selectbox("Select Material", df["material_name"])
                row = df[df["material_name"] == sel].iloc[0]
                material_code = row["material_code"]
                material_name = row["material_name"]
                available_stock = float(row["available_stock"])

        if material_code:
            st.info(f"Available Stock: {available_stock}")

            if not can_transact:
                st.error("❌ Transaction allowed only for your own plaza.")
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

                supabase.table("inventory_audit_log").insert({
                    "user_id": st.session_state.user_id,
                    "user_plaza": st.session_state.user_plaza,
                    "viewed_plaza": view_plaza,
                    "material_code": material_code,
                    "material_name": material_name,
                    "transaction_type": txn_type,
                    "quantity": float(qty),
                    "stock_before": float(available_stock),
                    "stock_after": float(updated),
                    "remarks": remarks,
                    "source": "streamlit_app"
                }).execute()

                st.success("✅ Transaction completed")
                st.rerun()

    # ---------- STOCK TRANSFER (REQUEST) ----------
    elif choice == "Stock Transfer":
        st.header("🔁 Stock Transfer (Approval Based)")

        source = st.session_state.user_plaza
        dest = st.selectbox("Destination Plaza", [p for p in ["TP01", "TP02", "TP03"] if p != source])

        resp = supabase.table("material_stock").select("*") \
            .eq("toll_plaza", source).order("material_name").execute()

        if not resp.data:
            st.info("No stock available")
            return

        df = pd.DataFrame(resp.data)
        st.dataframe(df)

        sel = st.selectbox("Material", df["material_name"])
        row = df[df["material_name"] == sel].iloc[0]

        qty = st.number_input("Transfer Quantity", min_value=0.0, max_value=float(row["available_stock"]))
        remarks = st.text_area("Remarks")

        if st.button("Send Transfer Request"):
            supabase.table("stock_transfers").insert({
                "transfer_date": datetime.today().strftime("%Y-%m-%d"),
                "source_plaza": source,
                "destination_plaza": dest,
                "material_code": row["material_code"],
                "material_name": row["material_name"],
                "quantity": float(qty),
                "status": "PENDING",
                "created_by": st.session_state.user_id,
                "remarks": remarks
            }).execute()

            st.success("📨 Transfer request sent")
            st.rerun()

    # ---------- TRANSFER INBOX ----------
    elif choice == "Transfer Inbox":
        st.header("📥 Incoming Transfers")

        my_plaza = st.session_state.user_plaza

        resp = supabase.table("stock_transfers").select("*") \
            .eq("destination_plaza", my_plaza) \
            .eq("status", "PENDING").execute()

        if not resp.data:
            st.info("No pending transfers")
            return

        df = pd.DataFrame(resp.data)
        st.dataframe(df)

        tid = st.selectbox("Transfer ID", df["id"])
        row = df[df["id"] == tid].iloc[0]

        action = st.radio("Action", ["Accept", "Reject"])
        remarks = st.text_area("Remarks")

        if st.button("Submit Decision"):
            if action == "Reject":
                supabase.table("stock_transfers").update({
                    "status": "REJECTED",
                    "accepted_by": st.session_state.user_id,
                    "accepted_at": datetime.now().isoformat(),
                    "remarks": remarks
                }).eq("id", tid).execute()

                st.warning("❌ Rejected")
                st.rerun()

            qty = float(row["quantity"])
            code = row["material_code"]
            name = row["material_name"]
            source = row["source_plaza"]

            src = supabase.table("material_stock").select("*") \
                .eq("toll_plaza", source).eq("material_code", code).execute()

            if not src.data or src.data[0]["available_stock"] < qty:
                st.error("Source stock insufficient")
                return

            src_avail = float(src.data[0]["available_stock"])
            dest_resp = supabase.table("material_stock").select("*") \
                .eq("toll_plaza", my_plaza).eq("material_code", code).execute()

            dest_avail = float(dest_resp.data[0]["available_stock"]) if dest_resp.data else 0

            supabase.table("material_stock").upsert({
                "toll_plaza": source,
                "material_code": code,
                "material_name": name,
                "available_stock": src_avail - qty
            }).execute()

            supabase.table("material_stock").upsert({
                "toll_plaza": my_plaza,
                "material_code": code,
                "material_name": name,
                "available_stock": dest_avail + qty
            }).execute()

            supabase.table("stock_transfers").update({
                "status": "ACCEPTED",
                "accepted_by": st.session_state.user_id,
                "accepted_at": datetime.now().isoformat(),
                "remarks": remarks
            }).eq("id", tid).execute()

            st.success("✅ Transfer accepted")
            st.rerun()

    # ---------- TRANSFER DASHBOARD ----------
    elif choice == "Transfer Dashboard":
        st.header("📊 Transfer Dashboard")

        resp = supabase.table("stock_transfers").select("*") \
            .order("created_at", desc=True).execute()

        if not resp.data:
            st.info("No transfers found")
            return

        df = pd.DataFrame(resp.data)

        my_plaza = st.session_state.user_plaza
        df["My Action"] = df["destination_plaza"].apply(
            lambda x: "🔔 ACTION REQUIRED" if x == my_plaza and x != df["source_plaza"].any() else ""
        )

        df["status"] = df["status"].replace({
            "PENDING": "🟡 PENDING",
            "ACCEPTED": "🟢 ACCEPTED",
            "REJECTED": "🔴 REJECTED"
        })

        display_cols = [
            "id", "transfer_date", "source_plaza", "destination_plaza",
            "material_name", "material_code", "quantity",
            "status", "created_by", "created_at",
            "accepted_by", "accepted_at", "My Action"
        ]

        styled_df = (
            df[display_cols]
            .style
            .apply(lambda row: highlight_transfer_status(row, my_plaza), axis=1)
        )

        st.dataframe(styled_df, use_container_width=True)

    # ---------- AUDIT LOG ----------
    elif choice == "Audit Log":
        resp = supabase.table("inventory_audit_log") \
            .select("*").order("action_time", desc=True).limit(500).execute()
        if resp.data:
            st.dataframe(pd.DataFrame(resp.data))
        else:
            st.info("No audit records")

    # ---------- LAST 10 ----------
    elif choice == "Last 10 Transactions":
        tp = st.selectbox("Plaza", ["TP01", "TP02", "TP03"])
        resp = supabase.table("inventory_transactions").select("*") \
            .eq("toll_plaza", tp).order("id", desc=True).limit(10).execute()
        if resp.data:
            st.dataframe(pd.DataFrame(resp.data))
        else:
            st.info("No transactions")

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
