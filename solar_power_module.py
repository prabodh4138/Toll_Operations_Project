# solar_power_module.py  — string inputs + safe float conversion
import os
import re
from datetime import date as dt_date
import streamlit as st
from supabase import create_client, Client
 
# -----------------------------
# Supabase connection (env or Streamlit secrets)
# -----------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("SUPABASE_URL / SUPABASE_KEY not set.")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
 
REMARKS_OPTIONS = [
    "Normal weather",
    "Cloudy weather",
    "Raining",
    "Power cut",
    "Partially cloud",
    "Maintenance activity",
    "Others",
]
 
# -----------------------------
# Helpers
# -----------------------------
def parse_float_str(s: str, field_name: str):
    """
    Robustly parse a numeric string to float.
    - Accepts commas or spaces as thousands separators
    - Accepts comma as decimal separator (e.g., '1,25') -> 1.25 IF there is only one comma and no dots
    - Rejects mixed separators (e.g., '1,234.56' with both thousands and decimal in odd places)
    Returns (value, error_message)
    """
    if s is None:
        return None, f"{field_name}: value is required."
 
    raw = s.strip()
    if raw == "":
        return None, f"{field_name}: value is required."
 
    # If the string has only digits and separators, try to normalize
    # Remove spaces
    t = raw.replace(" ", "")
    # Case 1: comma used as decimal and no dot present -> replace comma with dot
    if "," in t and "." not in t:
        # Ensure only one comma (decimal) or it looks like thousands grouped input
        if t.count(",") == 1:
            t = t.replace(",", ".")
        else:
            # multiple commas -> likely thousands group; remove commas
            t = t.replace(",", "")
    else:
        # Remove thousands commas like 1,234 -> 1234
        # but keep decimal dot if present
        # Disallow patterns like 1,234.56, we will just strip commas
        t = t.replace(",", "")
 
    # Final sanity: allow optional sign, digits, optional decimal, optional exponent
    if not re.fullmatch(r"[+-]?(\d+(\.\d+)?)([eE][+-]?\d+)?", t):
        return None, f"{field_name}: invalid number '{raw}'. Use digits only (e.g., 1234.56)."
 
    try:
        val = float(t)
        return val, None
    except Exception:
        return None, f"{field_name}: could not parse '{raw}' as a number."
 
def get_opening_kwh(toll_plaza: str) -> float:
    """Fetch current opening_kwh; return 0.0 if not initialized."""
    try:
        res = (
            supabase.table("solar_opening_status")
            .select("opening_kwh")
            .eq("toll_plaza", toll_plaza)
            .single()
            .execute()
        )
        if getattr(res, "data", None) and "opening_kwh" in res.data:
            return float(res.data["opening_kwh"])
        return 0.0
    except Exception:
        return 0.0
 
def upsert_opening_kwh(toll_plaza: str, opening_kwh: float) -> None:
    supabase.table("solar_opening_status").upsert(
        {"toll_plaza": toll_plaza, "opening_kwh": float(opening_kwh)}
    ).execute()
 
def insert_generation_row(payload: dict) -> bool:
    resp = supabase.table("solar_generation").insert(payload).execute()
    return bool(getattr(resp, "data", None))
 
# -----------------------------
# UI Module
# -----------------------------
def solar_power_module():
    st.subheader("🔆 Solar Power Plant Generation")
 
    # --- Top row: Date, Plaza, Refresh ---
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        entry_date = st.date_input("Date", value=dt_date.today())
    with c2:
        toll_plaza = st.selectbox("Toll Plaza", ["TP01", "TP02", "TP03"])
    with c3:
        st.write("")  # spacer
        if st.button("Refresh"):
            st.rerun()
 
    # --- Fetch Opening (auto) ---
    opening_kwh = get_opening_kwh(toll_plaza)
 
    # --- Inputs as strings (safe), opening displayed as disabled number ---
    c4, c5, c6 = st.columns([1, 1, 1])
    with c4:
        st.number_input(
            "Opening KWH (auto)",
            value=float(opening_kwh),
            format="%.2f",
            disabled=True,
        )
    with c5:
        closing_kwh_str = st.text_input(
            "Closing KWH (user input)",
            placeholder="e.g., 1234.56",
        )
    with c6:
        # Show computed Net as read-only text (computed after validation on submit)
        st.text_input("Net KWH (auto)", value="", disabled=True, placeholder="Will compute after Submit")
 
    remarks = st.selectbox("Remarks", REMARKS_OPTIONS, index=0)
    remarks_other = ""
    if remarks == "Others":
        remarks_other = st.text_input("Please specify the Reason")
 
    # --- Submit ---
    if st.button("Submit"):
        # Validate closing_kwh (string -> float)
        closing_kwh, err = parse_float_str(closing_kwh_str, "Closing KWH")
        if err:
            st.error(err)
            st.stop()
 
        if closing_kwh < 0:
            st.error("Closing KWH cannot be negative.")
            st.stop()
 
        if closing_kwh < opening_kwh:
            st.error("❌ Closing KWH must be ≥ Opening KWH.")
            st.stop()
 
        net_kwh = closing_kwh - opening_kwh
 
        payload = {
            "date": str(entry_date),
            "toll_plaza": toll_plaza,
            "opening_kwh": float(opening_kwh),
            "closing_kwh": float(closing_kwh),
            "net_kwh": float(net_kwh),
            "remarks": remarks,
            "remarks_other": remarks_other if remarks == "Others" else None,
        }
 
        try:
            ok = insert_generation_row(payload)
            if not ok:
                st.error("❌ Insert failed. Check constraints or Supabase logs.")
                st.stop()
 
            # After insert, set next opening = this closing
            upsert_opening_kwh(toll_plaza, float(closing_kwh))
 
            st.success(f"✅ Saved. Net KWH = {net_kwh:.2f}. Opening KWH updated for next cycle.")
            st.rerun()
 
        except Exception as e:
            msg = str(e)
            if "duplicate key value violates unique constraint" in msg:
                st.error("❌ An entry for this Date & Toll Plaza already exists. Change the date or edit the existing record.")
            else:
                st.error(f"⚠️ Error: {e}")
 
    # --- Recent entries viewer ---
    st.markdown("---")
    st.caption("Last 10 entries")
    try:
        rows = (
            supabase.table("solar_generation")
            .select("*")
            .order("id", desc=True)
            .limit(10)
            .execute()
        )
        if getattr(rows, "data", None):
            st.dataframe(rows.data, use_container_width=True)
        else:
            st.info("No records yet.")
    except Exception as e:
        st.error(f"Error fetching recent entries: {e}")
 
# Local test
if __name__ == "__main__":
    solar_power_module()
 
