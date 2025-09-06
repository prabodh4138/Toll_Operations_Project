# ---------- PART 1 ----------
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
 
 
def similarity(a: str, b: str) -> float:
    """0..1 similarity score (case-insensitive)."""
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()
 
 
def run():
    st.set_page_config(page_title="Sekura Toll Inventory", layout="wide")
    st.title("📦 Toll Plaza Inventory Management")
 
    menu = ["User Block", "Admin Block", "Last 10 Transactions", "Download CSV"]
    choice = st.sidebar.selectbox("Select Action", menu)
 
    # session state for search results & selection
    st.session_state.setdefault("search_results", [])
    st.session_state.setdefault("selected_labels", [])
 
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
                            "available_stock": float(row["available_stock"]),
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
 
        # reset search when tp or mode changes
        if st.session_state.get("last_tp") != toll_plaza or st.session_state.get("last_mode") != search_mode:
            st.session_state["search_results"] = []
            st.session_state["selected_labels"] = []
        st.session_state["last_tp"] = toll_plaza
        st.session_state["last_mode"] = search_mode
 
        material_code = ""
        material_name = ""
        available_stock = 0.0
 
        # ---- Material Code search (single) ----
        if search_mode == "Material Code":
            material_code_input = st.text_input("Enter Material Code")
            if material_code_input:
                resp = (
                    supabase.table("material_stock")
                    .select("*")
                    .eq("toll_plaza", toll_plaza)
                    .eq("material_code", material_code_input)
                    .execute()
                )
                if resp.data:
                    data = resp.data[0]
                    material_code = data["material_code"]
                    material_name = data["material_name"]
                    available_stock = float(data.get("available_stock") or 0.0)
                    st.success(f"Material Found: {material_name} — Avail: {available_stock}")
                else:
                    st.warning("Material not found under this Toll Plaza.")
# ---------- PART 2 ----------
        # ---- Material Name search (multiple results) ----
        else:
            st.markdown("**Search options**")
            mode = st.selectbox("Mode", ["Basic (contains)", "Advanced (fuzzy + contains)"])
            material_name_input = st.text_input("Enter Material Name Keyword", key="name_search_input")
            st.write("Basic: DB ilike search. Advanced: fetch all items and rank by fuzzy similarity.")
 
            if mode.startswith("Advanced"):
                similarity_threshold = st.slider("Similarity threshold (score ≥)", 0.0, 1.0, 0.50, 0.01)
                max_results = int(st.number_input("Max results to show", min_value=1, max_value=200, value=50))
            else:
                similarity_threshold = None
                max_results = int(st.number_input("Max results to show", min_value=1, max_value=200, value=100))
 
            if st.button("Search", key="execute_search"):
                if mode.startswith("Basic"):
                    resp = (
                        supabase.table("material_stock")
                        .select("*")
                        .eq("toll_plaza", toll_plaza)
                        .ilike("material_name", f"%{material_name_input}%")
                        .order("material_name", desc=False)
                        .execute()
                    )
                    items = resp.data or []
                    results = [
                        {
                            "material_code": r.get("material_code"),
                            "material_name": r.get("material_name"),
                            "available_stock": r.get("available_stock") or 0.0,
                        }
                        for r in items
                    ][:max_results]
                else:
                    resp_all = (
                        supabase.table("material_stock").select("*").eq("toll_plaza", toll_plaza).order("material_name").execute()
                    )
                    all_items = resp_all.data or []
                    scored = []
                    for r in all_items:
                        name = r.get("material_name", "") or ""
                        code = str(r.get("material_code", "") or "")
                        score = max(similarity(material_name_input, name), similarity(material_name_input, code))
                        contains = material_name_input.lower() in name.lower() if material_name_input else False
                        if score >= similarity_threshold or contains:
                            scored.append(
                                {
                                    "material_code": r.get("material_code"),
                                    "material_name": r.get("material_name"),
                                    "available_stock": r.get("available_stock") or 0.0,
                                    "score": round(score, 3),
                                }
                            )
                    results = sorted(scored, key=lambda x: x.get("score", 0), reverse=True)[:max_results]
 
                st.session_state["search_results"] = results
                st.session_state["selected_labels"] = []
 
            if st.session_state["search_results"]:
                df_results = pd.DataFrame(st.session_state["search_results"])
                st.success(f"Found {len(df_results)} result(s).")
                st.dataframe(df_results.reset_index(drop=True))
 
                labels, mapping = [], {}
                for r in st.session_state["search_results"]:
                    if "score" in r:
                        lbl = f"{r['material_name']} | Code:{r['material_code']} | Avail:{r['available_stock']} | Score:{r['score']}"
                    else:
                        lbl = f"{r['material_name']} | Code:{r['material_code']} | Avail:{r['available_stock']}"
                    labels.append(lbl)
                    mapping[lbl] = r
 
                selected_labels = st.multiselect("Select Material(s)", labels, key="select_results")
                st.session_state["selected_labels"] = selected_labels
                selected_items = [mapping[l] for l in selected_labels] if selected_labels else []
 
                if selected_items:
                    first = selected_items[0]
                    material_code = first["material_code"]
                    material_name = first["material_name"]
                    available_stock = float(first.get("available_stock") or 0.0)
            else:
st.info("No results yet. Enter a keyword and click Search.")
 
        # ---- Transaction UI ----
        selected_items = []
        if st.session_state.get("selected_labels") and st.session_state.get("search_results"):
            mapping = {}
            for r in st.session_state["search_results"]:
                if "score" in r:
                    lbl = f"{r['material_name']} | Code:{r['material_code']} | Avail:{r['available_stock']} | Score:{r['score']}"
                else:
                    lbl = f"{r['material_name']} | Code:{r['material_code']} | Avail:{r['available_stock']}"
                mapping[lbl] = r
            for lbl in st.session_state["selected_labels"]:
                if lbl in mapping:
                    selected_items.append(mapping[lbl])
 
        if selected_items:
            st.markdown("### Bulk transaction for selected materials")
            transaction_type = st.selectbox("Transaction Type (Bulk)", ["Stock In", "Stock Out"], key="bulk_txn_type")
            qty_inputs = {}
            with st.form("bulk_txn_form"):
                st.write("Provide quantity for each selected material:")
                for idx, item in enumerate(selected_items):
                    lbl = f"{item['material_name']} | {item['material_code']} (Avail: {item['available_stock']})"
                    qty = st.number_input(f"Qty for {lbl}", min_value=0.0, format="%f", key=f"bulk_qty_{idx}")
                    qty_inputs[item["material_code"]] = float(qty)
                remarks_bulk = st.text_area("Remarks (Bulk, optional)")
                submitted_bulk = st.form_submit_button("Submit Bulk Transaction")
                if submitted_bulk:
                    for item in selected_items:
                        code = item["material_code"]
                        name = item["material_name"]
                        avail = float(item.get("available_stock") or 0.0)
                        qty = qty_inputs.get(code, 0.0)
                        if qty <= 0:
                            continue
                        updated = avail + qty if transaction_type == "Stock In" else avail - qty
                        record = {
                            "date": date.strftime("%Y-%m-%d"),
                            "toll_plaza": toll_plaza,
                            "material_code": code,
                            "material_name": name,
                            "transaction_type": transaction_type,
                            "quantity": float(qty),
                            "updated_available_stock": float(updated),
                            "remarks": remarks_bulk,
                            "created_at": datetime.now().isoformat(),
                        }
                        supabase.table("inventory_transactions").insert(record).execute()
                        supabase.table("material_stock").upsert(
                            {"toll_plaza": toll_plaza, "material_code": code, "material_name": name, "available_stock": float(updated)}
                        ).execute()
                    st.success("✅ Bulk transaction completed successfully.")
                    st.experimental_rerun()
 
        elif material_code:
st.info(f"Available Stock: {available_stock} for Material Code: {material_code}")
            transaction_type = st.selectbox("Transaction Type", ["Stock In", "Stock Out"], key="single_txn_type")
            quantity = st.number_input("Quantity", min_value=0.0, format="%f", key="single_qty")
            remarks = st.text_area("Remarks (Optional)", key="single_remarks")
 
            if st.button("Submit Transaction (Single)"):
                if quantity <= 0:
                    st.error("❌ Quantity should be greater than zero.")
                else:
                    updated_stock = available_stock + quantity if transaction_type == "Stock In" else available_stock - quantity
                    record = {
                        "date": date.strftime("%Y-%m-%d"),
                        "toll_plaza": toll_plaza,
                        "material_code": material_code,
                        "material_name": material_name,
                        "transaction_type": transaction_type,
                        "quantity": float(quantity),
                        "updated_available_stock": float(updated_stock),
                        "remarks": remarks,
                        "created_at": datetime.now().isoformat(),
                    }
                    supabase.table("inventory_transactions").insert(record).execute()
                    supabase.table("material_stock").upsert(
                        {"toll_plaza": toll_plaza, "material_code": material_code, "material_name": material_name, "available_stock": float(updated_stock)}
                    ).execute()
                    st.success(f"✅ Transaction submitted. Updated Stock: {updated_stock}")
                    st.experimental_rerun()
 
    elif choice == "Last 10 Transactions":
        st.header("📜 Last 10 Transactions Per TP")
        last_tp = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"], key="last10_tp")
        resp = supabase.table("inventory_transactions").select("*").order("id", desc=True).limit(50).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            ms_resp = supabase.table("material_stock").select("material_code").eq("toll_plaza", last_tp).execute()
            codes = [row["material_code"] for row in ms_resp.data] if ms_resp.data else []
            df_tp = df[df["material_code"].isin(codes)] if codes else pd.DataFrame([])
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
# ---------- END PART 2 ----------
