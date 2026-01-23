# Toll_Operations.py
import importlib
import streamlit as st

st.set_page_config(page_title="Sekura Toll Ops", layout="wide")

MODULES = {
    "DG Monitoring": "diesel_monitoring_app",
    "EB Meter Reading": "eb_meter_reading_app",
    "Highway Meter Reading": "highway_reading_app",
    "Inventory Management": "inventory_management_app",
    "Solar Generation": "solar_power_module",
}

# 🔑 Module cache
_LOADED_MODULES = {}

def load_module(mod_name: str):
    try:
        if mod_name in _LOADED_MODULES:
            # 🔥 FORCE reload updated code
            return importlib.reload(_LOADED_MODULES[mod_name])
        else:
            module = importlib.import_module(mod_name)
            _LOADED_MODULES[mod_name] = module
            return module
    except Exception as e:
        st.error(f"❌ Failed to load `{mod_name}`: {e}")
        return None

def main():
    st.title("🛣️ Sekura Toll Plaza Operations Dashboard")

    choice = st.sidebar.selectbox("Select Module", list(MODULES.keys()))

    module_name = MODULES[choice]
    mod = load_module(module_name)

    if not mod:
        return

    if not hasattr(mod, "run"):
        st.error(f"❌ `{module_name}` has no `run()` function.")
        return

    try:
        mod.run()
    except Exception as e:
        st.exception(e)

if __name__ == "__main__":
    main()





