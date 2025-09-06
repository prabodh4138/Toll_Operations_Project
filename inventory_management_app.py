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
 
    # session storage
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
        st.header("📝 User Entry (Live Suggestions)")
 
        date = st.date_input("Select Date", value=datetime.today())
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        search_mode = st.radio("Search Material By", ["Material Code", "Material Name"])
 
        # reset search if TP/mode changed
        if st.session_state.get("last_tp") != toll_plaza or st.session_state.get("last_mode") != search_mode:
            st.session_state["search_results"] = []
            st.session_state["selected_labels"] = []
        st.session_state["last_tp"] = toll_plaza
        st.session_state["last_mode"] = search_mode
 
        material_code = ""
        material_name = ""
        available_stock = 0.0
 
        # Material Code search (kept same)
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
        # Material Name search with LIVE suggestions
        else:
            st.markdown("**Type to see suggestions (autocomplete)**")
            mode = st.selectbox("Mode", ["Basic (contains - fast)", "Advanced (fuzzy + contains)"])
            material_name_input = st.text_input("Enter Material Name Keyword", key="live_name_input")
            show_raw = st.checkbox("Show raw DB rows (debug)", value=False)
 
            def build_suggestions(keyword: str):
                resp_all = supabase.table("material_stock").select("*").eq("toll_plaza", toll_plaza).order("material_name", desc=False).execute()
                rows = resp_all.data or []
                if show_raw:
                    st.write("DEBUG: raw rows fetched:", rows)
 
                keyword = (keyword or "").strip()
                suggestions = []
                if mode.startswith("Basic"):
                    k = keyword.lower()
                    for r in rows:
                        name = (r.get("material_name") or "").lower()
                        if k == "" or k in name:
                            suggestions.append({"material_code": r.get("material_code"), "material_name": r.get("material_name"), "available_stock": r.get("available_stock") or 0.0})
                else:
                    threshold = 0.35
                    scored = []
                    for r in rows:
                        name = r.get("material_name") or ""
                        code = str(r.get("material_code") or "")
                        score = max(similarity(keyword, name), similarity(keyword, code))
                        contains = keyword.lower() in name.lower() if keyword else True
                        if contains or score >= threshold:
                            scored.append({"material_code": r.get("material_code"), "material_name": r.get("material_name"), "available_stock": r.get("available_stock") or 0.0, "score": round(score,3)})
                    suggestions = sorted(scored, key=lambda x: x.get("score", 0), reverse=True)
                return suggestions
 
            suggestions = build_suggestions(material_name_input)
 
            labels, mapping = [], {}
            for s in suggestions:
                if "score" in s:
                    lbl = f"{s['material_name']} | Code:{s['material_code']} | Avail:{s['available_stock']} | Score:{s['score']}"
                else:
                    lbl = f"{s['material_name']} | Code:{s['material_code']} | Avail:{s['available_stock']}"
                labels.append(lbl); mapping[lbl] = s
 
            if labels:
                selected_labels = st.multiselect("Suggestions", labels, key="live_suggestions_multiselect")
                st.session_state["selected_labels"] = selected_labels
                selected_items = [mapping[l] for l in selected_labels] if selected_labels else []
                if selected_items:
                    first = selected_items[0]
                    material_code = first["material_code"]
                    material_name = first["material_name"]
                    available_stock = float(first.get("available_stock") or 0.0)
                st.dataframe(pd.DataFrame(suggestions).reset_index(drop=True))
            else:
st.info("No suggestions yet. Start typing a material keyword.")
 
        # Bulk or single transaction flows
        selected_items = []
        if st.session_state.get("selected_labels"):
            for lbl in st.session_state["selected_labels"]:
                if lbl in mapping:
                    selected_items.append(mapping[lbl])
 
        if selected_items:
            st.markdown("### Bulk transaction for selected materials")
            transaction_type = st.selectbox("Transaction Type (Bulk)", ["Stock In", "Stock Out"])
            qty_inputs = {}
            with st.form("bulk_txn_form"):
                for idx, item in enumerate(selected_items):
                    lbl = f"{item['material_name']} | {item['material_code']} (Avail: {item['available_stock']})"
                    qty = st.number_input(f"Qty for {lbl}", min_value=0.0, format="%f", key=f"bulk_qty_{idx}")
                    qty_inputs[item["material_code"]] = float(qty)
                remarks_bulk = st.text_area("Remarks (Bulk, optional)")
                if st.form_submit_button("Submit Bulk Transaction"):
                    for item in selected_items:
                        code, name = item["material_code"], item["material_name"]
                        avail = float(item.get("available_stock") or 0.0)
                        qty = qty_inputs.get(code, 0.0)
                        if qty <= 0: continue
                        updated = avail + qty if transaction_type == "Stock In" else avail - qty
                        record = {"date": date.strftime("%Y-%m-%d"), "toll_plaza": toll_plaza,
                                  "material_code": code, "material_name": name,
                                  "transaction_type": transaction_type, "quantity": float(qty),
                                  "updated_available_stock": float(updated),
                                  "remarks": remarks_bulk, "created_at": datetime.now().isoformat()}
                        supabase.table("inventory_transactions").insert(record).execute()
                        supabase.table("material_stock").upsert({"toll_plaza": toll_plaza, "material_code": code, "material_name": name, "available_stock": float(updated)}).execute()
                    st.success("✅ Bulk transaction completed successfully.")
                    st.experimental_rerun()
 
        elif material_code:
st.info(f"Available Stock: {available_stock} for Material Code: {material_code}")
            transaction_type = st.selectbox("Transaction Type", ["Stock In", "Stock Out"])
            quantity = st.number_input("Quantity", min_value=0.0, format="%f")
            remarks = st.text_area("Remarks (Optional)")
            if st.button("Submit Transaction (Single)"):
                if quantity > 0:
                    updated_stock = available_stock + quantity if transaction_type == "Stock In" else available_stock - quantity
                    record = {"date": date.strftime("%Y-%m-%d"), "toll_plaza": toll_plaza,
                              "material_code": material_code, "material_name": material_name,
                              "transaction_type": transaction_type, "quantity": float(quantity),
                              "updated_available_stock": float(updated_stock),
                              "remarks": remarks, "created_at": datetime.now().isoformat()}
                    supabase.table("inventory_transactions").insert(record).execute()
                    supabase.table("material_stock").upsert({"toll_plaza": toll_plaza, "material_code": material_code, "material_name": material_name, "available_stock": float(updated_stock)}).execute()
                    st.success(f"✅ Transaction submitted. Updated Stock: {updated_stock}")
                    st.experimental_rerun()
 
    elif choice == "Last 10 Transactions":
        st.header("📜 Last 10 Transactions Per TP")
        tp = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        resp = supabase.table("inventory_transactions").select("*").order("id", desc=True).limit(50).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            codes = [row["material_code"] for row in supabase.table("material_stock").select("material_code").eq("toll_plaza", tp).execute().data]
            st.dataframe(df[df["material_code"].isin(codes)].head(10))
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
