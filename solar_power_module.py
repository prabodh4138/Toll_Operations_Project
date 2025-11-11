# solar_power_module.py
# Solar Generation module for Sekura Toll Ops
# - String inputs converted to float
# - Auto-fetch Opening KWH
# - Calculates Net KWH
# - Remarks dropdown with conditional "Others"
# - Submit + Refresh
# - Shows last 10 entries
 
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
 
def _get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("❌ SUPABASE_URL / SUPABASE_KEY not set.")
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_KEY)
 
REMARKS_OPTIONS = [
    "Weather almost clear",
    "Cloudy day",
    "Rain",
    "Power cut",
    "Partly cloud",
    "Maintenance activity",
    "Others",
]
 
# -----------------------------
# Helpers
# -----------------------------
def _parse_float_str(s: str, field_name: str):
    if s is None:
        return None, f"{field_name}: value is required."
    raw = s.strip()
    if raw == "":
        return None, f"{field_name}: value is required."
 
    t = raw.replace(" ", "")
    if "," in t and "." not in t:
        t = t.replace(",", ".") if t.count(",") == 1 else t.replace(",", "")
    else:
        t = t.replace(",", "")
 
    if not re.fullmatch(r"[+-]?(\d+(\.\d+)?)([eE][+-]?\d+)?", t):
        return None, f"{field_name}: invalid number '{raw}'."
    try:
        return float(t), None
    except Exception:
        return None, f"{field_name}: could not parse '{raw}'"
 
def _get_opening_kwh(client: Client, toll_plaza: str) -> float:
    try:
        res = (
            client.table("solar_opening_status")
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
 
def _upsert_opening_kwh(client: Client, toll_plaza: str, opening_kwh: float) -> None:
    client.table("solar_opening_status").upsert(
        {"toll_plaza": toll_plaza, "opening_kwh": float(opening_kwh)}
    ).execute()
 
def _insert_generation_row(client: Client, payload: dict) -> bool:
    resp = client.table("solar_generation").insert(payload).execute()
    return bool(getattr(resp, "data", None))
 
# -----------------------------
# Main UI function
# -----------------------------
def run():
    client = _get_client()
    st.subheader("🔆 Solar Power Plant Generation")
 
    # --- Top row: Date, Plaza, Refresh ---
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        entry_date = st.date_input("Date", value=dt_date.today())
    with c2:
        toll_plaza = st.selectbox("Toll Plaza", ["TP01", "TP02", "TP03"])
    with c3:
        st.write("")
        if st.button("Refresh"):
            st.rerun()
 
    # --- Opening KWH (auto) ---
    opening_kwh = _get_opening_kwh(client, toll_plaza)
 
    # --- Inputs ---
    c4, c5, c6 = st.columns([1, 1, 1])
    with c4:
        st.number_input("Opening KWH (auto)", value=float(opening_kwh), format="%.2f", disabled=True)
    with c5:
        closing_kwh_str = st.text_input("Closing KWH (user input)", placeholder="e.g., 1234.56")
    with c6:
        st.text_input("Net KWH (auto)", value="", disabled=True, placeholder="Computed on submit")
 
    remarks = st.selectbox("Remarks", REMARKS_OPTIONS, index=0)
    remarks_other = ""
    if remarks == "Others":
        remarks_other = st.text_input("Please specify the Reason")
 
    # --- Submit ---
    if st.button("Submit"):
        closing_kwh, err = _parse_float_str(closing_kwh_str, "Closing KWH")
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
            ok = _insert_generation_row(client, payload)
            if not ok:
                st.error("❌ Insert failed.")
                st.stop()
 
            _upsert_opening_kwh(client, toll_plaza, float(closing_kwh))
            st.success(f"✅ Saved. Net KWH = {net_kwh:.2f}. Opening updated for next cycle.")
            st.rerun()
 
        except Exception as e:
            msg = str(e)
            if "duplicate key value violates unique constraint" in msg:
                st.error("❌ Entry already exists for this Date & Toll Plaza.")
            else:
                st.error(f"⚠️ Error: {e}")
 
    # --- Recent entries ---
    st.markdown("---")
    st.caption("Last 10 entries")
    try:
        rows = (
            client.table("solar_generation")
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
 
