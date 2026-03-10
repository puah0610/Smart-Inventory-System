import streamlit as st
import requests
import pandas as pd
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import API_URL

def show():
    st.header("Transaction History")
    
    try:
        # Product map for filters + display labels
        res_prod = requests.get(f"{API_URL}/products/")
        products = res_prod.json() if res_prod.status_code == 200 else []
        products_map = {p['id']: p['name'] for p in products}

        fcol1, fcol2, fcol3, fcol4 = st.columns(4)
        with fcol1:
            tx_type = st.selectbox("Type", ["All", "sale", "restock"])
        with fcol2:
            product_options = ["All"] + [f"{p['name']} (ID:{p['id']})" for p in products]
            selected_product = st.selectbox("Product", product_options)
        with fcol3:
            start_date = st.date_input("Start Date")
        with fcol4:
            end_date = st.date_input("End Date")

        use_date_filter = st.checkbox("Use date range filter", value=False)

        receipt_filter = st.text_input("Receipt ID contains", value="")

        page_col1, page_col2, page_col3 = st.columns([1, 1, 2])
        with page_col1:
            page_size = st.selectbox("Rows per page", [25, 50, 100], index=1)

        if "history_page" not in st.session_state:
            st.session_state["history_page"] = 1

        skip = (st.session_state["history_page"] - 1) * page_size

        product_id = None
        if selected_product != "All":
            product_id = int(selected_product.split("ID:")[1].rstrip(")"))

        params = {
            "skip": skip,
            "limit": page_size,
            "transaction_type": None if tx_type == "All" else tx_type,
            "product_id": product_id,
            "receipt_id": receipt_filter or None,
            "start_date": start_date.strftime("%Y-%m-%d") if use_date_filter else None,
            "end_date": end_date.strftime("%Y-%m-%d") if use_date_filter else None,
        }
        params = {k: v for k, v in params.items() if v is not None}

        res = requests.get(f"{API_URL}/inventory/transactions/query", params=params)
        if res.status_code == 200:
            payload = res.json()
            transactions = payload.get("items", [])
            total = payload.get("total", 0)

            if transactions:
                df = pd.DataFrame(transactions)
                df['product_name'] = df['product_id'].map(products_map)
                display_cols = ["id", "receipt_id", "timestamp", "transaction_type", "product_name", "quantity", "customer_id"]
                cols = [c for c in display_cols if c in df.columns]
                st.dataframe(df[cols], hide_index=True, width='stretch')

                total_pages = max(1, (total + page_size - 1) // page_size)
                with page_col2:
                    st.markdown(f"Page **{st.session_state['history_page']} / {total_pages}**")

                nav_col1, nav_col2 = st.columns(2)
                with nav_col1:
                    if st.button("⬅️ Previous", disabled=st.session_state["history_page"] <= 1):
                        st.session_state["history_page"] -= 1
                        st.rerun()
                with nav_col2:
                    if st.button("Next ➡️", disabled=st.session_state["history_page"] >= total_pages):
                        st.session_state["history_page"] += 1
                        st.rerun()
            else:
                st.info("No transactions found for current filters.")
        else:
            st.error("Failed to load transactions.")
    except Exception as e:
        st.error(f"Error: {e}")
