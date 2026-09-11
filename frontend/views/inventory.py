import streamlit as st
import pandas as pd
import time
from supabase_client import get_supabase_client

def show():
    st.header("Inventory Management")
    supabase = get_supabase_client()
    
    tab_list, tab_restock, tab_add = st.tabs(["📦 Stock Levels", "➕ Restock Item", "🆕 Add New Product"])

    # --- TAB 1: Inventory List ---
    with tab_list:
        try:
            res = supabase.table("products").select("*").order("name").execute()
            products = res.data or []
            if products:
                df = pd.DataFrame(products)
                
                # Reorder columns: ID first, then Name, etc.
                desired_order = ["id", "name", "category", "stock_quantity", "price", "cost", "barcode"]
                # Filter to only ensure columns that actually exist in the data are selected
                cols_to_use = [c for c in desired_order if c in df.columns]
                df = df[cols_to_use]
                
                # Rename columns to be more readable
                df = df.rename(columns={
                    "id": "ID",
                    "name": "Product Name",
                    "category": "Category",
                    "stock_quantity": "Current Stock",
                    "price": "Selling Price ($)",
                    "cost": "Unit Cost ($)",
                    "barcode": "Barcode / SKU"
                })
                
                # Display with hidden index for a cleaner look
                st.dataframe(df, hide_index=True, use_container_width=True)
            else:
                st.info("No products found.")
        except Exception as e:
            st.error(f"Connection error: {e}")

    # --- TAB 2: Restock Item (Merged from restock.py) ---
    with tab_restock:
        st.subheader("Quick Restock")

        if "restock_success" in st.session_state:
            st.success(st.session_state.pop("restock_success"))

        # Reuse logic from restock.py
        try:
            res = supabase.table("products").select("id,name,barcode,stock_quantity").order("name").execute()
            products = res.data or []
            product_options = {f"{p['name']} (SKU: {p['barcode']})": p for p in products}
        except Exception:
            products = []
            product_options = {}

        def run_restock(prod, qty):
            receipt_id = f"RESTOCK-{int(time.time())}"
            new_stock = int(prod.get("stock_quantity", 0)) + int(qty)
            supabase.table("products").update({"stock_quantity": new_stock}).eq("id", prod["id"]).execute()
            supabase.table("transactions").insert({
                "product_id": prod["id"],
                "transaction_type": "restock",
                "quantity": int(qty),
                "receipt_id": receipt_id,
                "customer_id": None,
            }).execute()

        col1, col2 = st.columns(2)
        with col1:
            with st.form("restock_scan", clear_on_submit=True):
                st.write("**Method 1: Scan Barcode**")
                scan_code = st.text_input("Scan Barcode", key="restock_scan_input")
                qty_scan = st.number_input("Quantity to Add", min_value=1, value=10, key="scan_qty")
                submit_scan = st.form_submit_button("Submit Restock")
                
                if submit_scan and scan_code:
                    found_p = next((p for p in products if p['barcode'] == scan_code), None)
                    if found_p:
                        try:
                            run_restock(found_p, qty_scan)
                            st.session_state["restock_success"] = f"Restocked {found_p['name']} (+{qty_scan})"
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                    else:
                        st.error("Barcode not found.")

        with col2:
            st.write("**Method 2: Select from List**")
            if product_options:
                with st.form("restock_manual", clear_on_submit=True):
                    selected_label = st.selectbox("Product", list(product_options.keys()))
                    qty_manual = st.number_input("Quantity", min_value=1, value=10, key="manual_qty")
                    submit_manual = st.form_submit_button("Confirm Restock")

                    if submit_manual:
                        prod = product_options[selected_label]
                        try:
                            run_restock(prod, qty_manual)
                            st.session_state["restock_success"] = f"Restocked {prod['name']} (+{qty_manual})"
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
            else:
                st.info("No products available.")

    # --- TAB 3: Add New Product (Merged from add_product.py) ---
    with tab_add:
        st.subheader("Register New Product")
        with st.form("add_product_form"):
            a_name = st.text_input("Product Name")
            a_barcode = st.text_input("Barcode")
            a_price = st.number_input("Price", min_value=0.0)
            a_cost = st.number_input("Cost", min_value=0.0)
            a_category = st.text_input("Category")
            a_stock = st.number_input("Initial Stock", min_value=0, step=1)
            
            submitted = st.form_submit_button("Create Product")
            if submitted and a_name:
                payload = {
                    "name": a_name, "barcode": a_barcode, "price": a_price, 
                    "cost": a_cost, "category": a_category, "stock_quantity": a_stock
                }
                try:
                    supabase.table("products").insert(payload).execute()
                    st.success("Product created!")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
