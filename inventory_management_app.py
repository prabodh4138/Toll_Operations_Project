import os
from datetime import datetime
from difflib import SequenceMatcher

import pandas as pd
import streamlit as st
from supabase import create_client

# Initialize Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def similarity(a: str, b: str) -> float:
    """Return a 0..1 similarity score between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


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
        material_code = ""
        material_name = ""
        available_stock = 0

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
                    available_stock = data["available_stock"]
                    st.success(f"Material Found: {material_name}, Available Stock: {available_stock}")
                else:
                    st.warning("Material not found under this Toll Plaza.")

        else:
            # Advanced search options
            st.markdown("**Search options:**")
            basic_or_advanced = st.selectbox("Mode", ["Basic (contains)", "Advanced (fuzzy + contains)"])

            # Common input
            material_name_input = st.text_input("Enter Material Name Keyword")
            st.write(
                "Advanced mode will rank results by similarity (typo-tolerant). "
                "If Basic, it uses DB-side ilike('%keyword%')."
            )

            # Advanced controls
            if basic_or_advanced == "Advanced (fuzzy + contains)":
                similarity_threshold = st.slider(
                    "Similarity threshold (show results with score ≥)", 0.0, 1.0, 0.55, 0.01
                )
                max_results = st.number_input("Max results to show", min_value=1, max_value=200, value=25, step=1)
            else:
                similarity_threshold = None
                max_results = 50

            search_button = st.button("Search")

            results_df = None
            results_list = []

            if search_button and material_name_input:
                # First attempt: DB-side contains search (fast)
                resp = (
                    supabase.table("material_stock")
                    .select("*")
                    .eq("toll_plaza", toll_plaza)
                    .ilike("material_name", f"%{material_name_input}%")
                    .order("material_name", desc=False)
                    .execute()
                )

                if resp.data:
                    results = resp.data
                else:
                    # If no direct contains result, fetch all materials for toll plaza to allow fuzzy matching
                    resp_all = (
                        supabase.table("material_stock").select("*").eq("toll_plaza", toll_plaza).order("material_name").execute()
                    )
                    results = resp_all.data if resp_all.data else []

                # If advanced, compute similarity and filter/sort
                if basic_or_advanced == "Advanced (fuzzy + contains)":
                    scored = []
                    for r in results:
                        score = max(
                            similarity(material_name_input, r.get("material_name", "")),
                            # also check code similarity as a secondary signal
                            similarity(material_name_input, str(r.get("material_code", ""))),
                        )
                        if score >= similarity_threshold:
                            row = {
                                "material_code": r.get("material_code"),
                                "material_name": r.get("material_name"),
                                "available_stock": r.get("available_stock"),
                                "score": round(score, 3),
                            }
                            scored.append(row)
                    scored_sorted = sorted(scored, key=lambda x: x["score"], reverse=True)[:int(max_results)]
                    results_list = scored_sorted
                else:
                    # Basic: use DB results directly
                    results_list = [
                        {
                            "material_code": r.get("material_code"),
                            "material_name": r.get("material_name"),
                            "available_stock": r.get("available_stock"),
                        }
                        for r in results
                    ][: int(max_results)]

                if results_list:
                    results_df = pd.DataFrame(results_list)
                    st.success(f"Found {len(results_df)} result(s).")
                else:
                    st.warning("No matching materials found for this Toll Plaza / keyword.")

            # Display results (if any) and provide selection (single or multi)
            selected_items = []
            if results_df is not None and not results_df.empty:
                # Show table
                st.dataframe(results_df.reset_index(drop=True))

                # Build labels for selection
                labels = []
                mapping = {}
                for r in results_list:
                    if "score" in r:
                        label = f"{r['material_name']} | Code: {r['material_code']} | Avail: {r['available_stock']} | Score: {r['score']}"
                    else:
                        label = f"{r['material_name']} | Code: {r['material_code']} | Avail: {r['available_stock']}"
                    labels.append(label)
                    mapping[label] = r

                st.info("Select one or more materials from results for transaction.")
                selected_labels = st.multiselect("Select Material(s)", labels)

                # If user selected one, prefill single-selection variables (use first)
                if selected_labels:
                    # If only 1 selected we'll populate material_code for the single-item flow too
                    first_choice = mapping[selected_labels[0]]
                    material_code = first_choice["material_code"]
                    material_name = first_choice["material_name"]
                    available_stock = first_choice["available_stock"]

                    # Prepare a list of selected items for bulk processing
                    for lbl in selected_labels:
                        selected_items.append(mapping[lbl])

            # If either single material selected earlier via code search or via the mapping, show transaction UI
        # end of search block

        # Transaction UI (handles both single and bulk)
        # If we have selected_items (bulk) show bulk flow; else if single material_code present, show single flow.
        if 'selected_items' in locals() and selected_items:
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
                    # Validate and apply each
                    errors = []
                    for item in selected_items:
                        code = item["material_code"]
                        name = item["material_name"]
                        avail = item["available_stock"] or 0.0
                        qty = qty_inputs.get(code, 0.0)
                        if qty <= 0:
                            continue  # skip zero entries
                        if transaction_type == "Stock Out" and qty > avail:
                            errors.append(f"{name} (Code {code}): requested {qty} > available {avail}")
                            continue
                        updated = avail + qty if transaction_type == "Stock In" else avail - qty
                        # transactions record
                        record = {
                            "date": date.strftime("%Y-%m-%d"),
                            "toll_plaza": toll_plaza,
                            "material_code": code,
                            "material_name": name,
                            "transaction_type": transaction_type,
                            "quantity": float(qty),
                            "source_type": None if transaction_type == "Stock Out" else "Bulk Upload",
                            "material_consumption": None if transaction_type == "Stock In" else "Bulk Issue",
                            "updated_available_stock": float(updated),
                            "remarks": remarks_bulk,
                            "created_at": datetime.now().isoformat(),
                        }
                        supabase.table("inventory_transactions").insert(record).execute()
                        supabase.table("material_stock").upsert(
                            {
                                "toll_plaza": toll_plaza,
                                "material_code": code,
                                "material_name": name,
                                "available_stock": float(updated),
                            }
                        ).execute()
                    if errors:
                        st.error("Some items failed:\n" + "\n".join(errors))
                    else:
                        st.success("✅ Bulk transaction completed successfully.")
                        st.experimental_rerun()

        elif material_code:
            st.info(f"Available Stock: {available_stock} for Material Code: {material_code}")
            transaction_type = st.selectbox("Transaction Type", ["Stock In", "Stock Out"], key="single_txn_type")
            quantity = st.number_input("Quantity", min_value=0.0, format="%f", key="single_qty")
            source_type = None
            material_consumption = None

            if transaction_type == "Stock In":
                source_type = st.text_input("Source Type", key="single_source")
            else:
                material_consumption = st.text_input("Material Consumption", key="single_consumption")

            remarks = st.text_area("Remarks (Optional)", key="single_remarks")

            if st.button("Submit Transaction (Single)"):
                if quantity <= 0:
                    st.error("❌ Quantity should be greater than zero.")
                else:
                    if transaction_type == "Stock In":
                        updated_stock = available_stock + float(quantity)
                    else:
                        if float(quantity) > available_stock:
                            st.error("❌ Cannot issue more than available stock.")
                            return
                        updated_stock = available_stock - float(quantity)

                    record = {
                        "date": date.strftime("%Y-%m-%d"),
                        "toll_plaza": toll_plaza,
                        "material_code": material_code,
                        "material_name": material_name,
                        "transaction_type": transaction_type,
                        "quantity": float(quantity),
                        "source_type": source_type,
                        "material_consumption": material_consumption,
                        "updated_available_stock": float(updated_stock),
                        "remarks": remarks,
                        "created_at": datetime.now().isoformat(),
                    }

                    # Insert into transactions
                    supabase.table("inventory_transactions").insert(record).execute()
                    # Update material_stock
                    supabase.table("material_stock").upsert(
                        {
                            "toll_plaza": toll_plaza,
                            "material_code": material_code,
                            "material_name": material_name,
                            "available_stock": float(updated_stock),
                        }
                    ).execute()

                    st.success(f"✅ Transaction submitted successfully. Updated Stock: {updated_stock}")
                    st.experimental_rerun()

    elif choice == "Last 10 Transactions":
        st.header("📜 Last 10 Transactions Per TP")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"], key="last10_tp")
        resp = supabase.table("inventory_transactions").select("*").order("id", desc=True).limit(50).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)

            # Get list of material_codes for this toll plaza
            ms_resp = supabase.table("material_stock").select("material_code").eq("toll_plaza", toll_plaza).execute()
            if ms_resp.data:
                codes = [row["material_code"] for row in ms_resp.data]
                df_tp = df[df["material_code"].isin(codes)]
            else:
                df_tp = pd.DataFrame([])

            st.dataframe(df_tp.head(10))
        else:
            st.info("No transactions found.")

    elif choice == "Download CSV":
        st.header("📥 Download All Transactions")
        resp = supabase.table("inventory_transactions").select("*").order("id", desc=True).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download All Transactions CSV",
                data=csv,
                file_name="all_inventory_transactions.csv",
                mime="text/csv",
            )
        else:
            st.info("No data available to download.")


if __name__ == "__main__":
    run()
