# Toll_Operations.py
import importlib
import sys
import streamlit as st

st.set_page_config(page_title="Sekura Toll Ops", layout="wide")

MODULES = {
    "DG Monitoring": "diesel_monitoring_app",
    "EB Meter Reading": "eb_meter_reading_app",
    "Highway Meter Reading": "highway_reading_app",
    "Inventory Management": "inventory_management_app",
    "Solar Generation": "solar_power_module",
}

def load_module(mod_name: str):
    try:
        if mod_name in sys.modules:
            # 🔥 THIS IS THE KEY LINE
            return importlib.reload(sys.modules[mod_name])
        else:
            return importlib.import_module(mod_name)
    except Exception as e:
        st.error(f"❌ Failed to load `{mod_name}`")
        st.exception(e)
        return None

def main():
    st.title("🛣️ Sekura Toll Plaza Operations Dashboard")

    choice = st.sidebar.selectbox(
        "Select Module",
        list(MODULES.keys())
    )

    module_name = MODULES[choice]
    mod = load_module(module_name)

    if not mod:
        return

    if not hasattr(mod, "run"):
        st.error(f"❌ `{module_name}` has no run() function")
        return

    mod.run()

if __name__ == "__main__":
    main()
