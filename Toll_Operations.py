import streamlit as st
import importlib
 
st.set_page_config(page_title="Sekura Toll Ops", layout="wide")
 
MODULES = {
    "DG Monitoring": "diesel_monitoring_app",
    "EB Meter Reading": "eb_meter_reading_app",
    "Highway Meter Reading": "highway_reading_app",
    "Inventory Management": "inventory_management_app",
}
 
def load_module(mod_name: str):
    try:
        return importlib.import_module(mod_name)
    except Exception as e:
        st.error(f"❌ Failed to import `{mod_name}`: {e}")
        return None
 
def main():
    st.title("🛣️ Sekura Toll Plaza Operations Dashboard")
    choice = st.sidebar.selectbox("Select Module", list(MODULES.keys()))
 
    mod = load_module(MODULES[choice])
    if not mod:
        return
 
    if not hasattr(mod, "run"):
        st.error(f"❌ `{MODULES[choice]}` has no `run()` function.")
        return
 
    try:
        mod.run()
    except Exception as e:
        st.exception(e)  # show full stacktrace
 
if __name__ == "__main__":
    main()
HOME | Model Media Group
Model Media is the leader of Aisian adult film, producing and distributing high-quality domestic AV, committed to promoting the internationalization of the Aisian AV market. Our services include ad...
 
