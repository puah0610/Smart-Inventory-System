import streamlit as st
import pandas as pd
from supabase_client import get_supabase_client

def show():
    st.header("Transaction History")
    supabase = get_supabase_client()
    
    try:
        # Product map for filters + display labels
        res_prod = supabase.table("products").select("id,name").order("name").execute()
        products = res_prod.data or []
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

        query = (
            supabase.table("transactions")
            .select("id,receipt_id,timestamp,transaction_type,product_id,quantity,customer_id,products(name)", count="exact")
            .order("timestamp", desc=True)
        )

        if tx_type != "All":
            query = query.eq("transaction_type", tx_type)
        if product_id is not None:
            query = query.eq("product_id", product_id)
        if receipt_filter:
            query = query.ilike("receipt_id", f"%{receipt_filter}%")
        if use_date_filter:
            query = query.gte("timestamp", f"{start_date.strftime('%Y-%m-%d')}T00:00:00")
            query = query.lte("timestamp", f"{end_date.strftime('%Y-%m-%d')}T23:59:59")

        res = query.range(skip, skip + page_size - 1).execute()
        transactions = res.data or []
        total = res.count or 0

        if transactions:
            df = pd.DataFrame(transactions)
            if "products" in df.columns:
                df["product_name"] = df["products"].apply(lambda x: x.get("name") if isinstance(x, dict) else None)
            else:
                df['product_name'] = df['product_id'].map(products_map)
            display_cols = ["id", "receipt_id", "timestamp", "transaction_type", "product_name", "quantity", "customer_id"]
            cols = [c for c in display_cols if c in df.columns]
            st.dataframe(df[cols], hide_index=True, use_container_width=True)

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
    except Exception as e:
        st.error(f"Error: {e}")
