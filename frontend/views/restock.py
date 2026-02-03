import streamlit as st
import requests
import time

API_URL = "http://127.0.0.1:8000"

def show():
    st.header("Restock Inventory")
    
    # 1. Fetch all products for a dropdown list (in case they don't have scanner user)
    try:
        res = requests.get(f"{API_URL}/products/")
        if res.status_code == 200:
            products = res.json()
            # Create a lookup dictionary: "Duplicate Name (Barcode)" -> ID
            # Handling potential duplicate names by including barcode
            product_options = {f"{p['name']} (SKU: {p['barcode']})": p for p in products}
        else:
            st.error("Failed to load product list.")
            products = []
            product_options = {}
    except Exception as e:
        st.error(f"Connection error: {e}")
        product_options = {}

    # 2. Input Method
    tab1, tab2 = st.tabs(["Scan Barcode", "Select from List"])
    
    with tab1:
        st.write("Scan an item to quickly restock it.")
        with st.form("restock_scan"):
            scan_code = st.text_input("Scan Barcode", key="restock_scan_input")
            qty_scan = st.number_input("Quantity to Add", min_value=1, value=10, key="scan_qty")
            submit_scan = st.form_submit_button("Restock")
            
            if submit_scan and scan_code:
                # Find product by barcode
                # (Ideally backend has a lookup, but we can search our loaded list for speed uiless list is huge)
                found_p = next((p for p in products if p['barcode'] == scan_code), None)
                if found_p:
                    # Execute Restock
                    payload = {
                        "product_id": found_p['id'],
                        "transaction_type": "restock",
                        "quantity": qty_scan,
                         "receipt_id": "RESTOCK-" + str(int(time.time())) # Optional: grouping ID for restocks
                    }
                    try:
                        r = requests.post(f"{API_URL}/inventory/transaction", json=payload)
                        if r.status_code == 200:
                            st.success(f"Successfully added {qty_scan} units to {found_p['name']}")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Error: {r.text}")
                    except Exception as e:
                        st.error(str(e))
                else:
                    st.error("Product barcode not found.")

    with tab2:
        if product_options:
            selected_label = st.selectbox("Select Product", list(product_options.keys()))
            qty_manual = st.number_input("Quantity to Add", min_value=1, value=10, key="manual_qty")
            
            if st.button("Confirm Restock"):
                prod = product_options[selected_label]
                payload = {
                    "product_id": prod['id'],
                    "transaction_type": "restock",
                    "quantity": qty_manual,
                    "receipt_id": "RESTOCK-" + str(int(time.time()))
                }
                try:
                    r = requests.post(f"{API_URL}/inventory/transaction", json=payload)
                    if r.status_code == 200:
                        st.success(f"Successfully added {qty_manual} units to {prod['name']}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Error: {r.text}")
                except Exception as e:
                    st.error(str(e))
        else:
            st.info("No products available to select.")
