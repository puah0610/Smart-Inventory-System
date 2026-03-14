import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase_client import get_supabase_client

def show():
    st.header("🔎 Product Performance Deep-Dive")
    st.caption("Analyze profitability, trends, and stock health for individual items.")
    supabase = get_supabase_client()

    # 1. Product Search
    # Fetch all products for the dropdown
    try:
        res = supabase.table("products").select("*").order("name").execute()
        products = res.data or []
        if not products:
            st.warning("No products found in inventory.")
            return

        # Create a searchable dictionary: "Name (Barcode)" -> product
        prod_map = {f"{p['name']} ({p['barcode']})": p for p in products}

        selected_label = st.selectbox(
            "Search Product (Name or Barcode)",
            options=list(prod_map.keys()),
            index=0,
        )

        if selected_label:
            product = prod_map[selected_label]
            selected_id = product["id"]

            tx_res = (
                supabase.table("transactions")
                .select("quantity,timestamp,transaction_type")
                .eq("product_id", selected_id)
                .order("timestamp", desc=False)
                .execute()
            )
            tx_rows = tx_res.data or []
            tx_df = pd.DataFrame(tx_rows)

            if not tx_df.empty:
                tx_df["timestamp"] = pd.to_datetime(tx_df["timestamp"], errors="coerce")
                tx_df["quantity"] = tx_df["quantity"].fillna(0).astype(int)
                sales_df = tx_df[tx_df["transaction_type"] == "sale"].copy()
            else:
                sales_df = pd.DataFrame(columns=["timestamp", "quantity"])

            total_sold_all_time = int(sales_df["quantity"].sum()) if not sales_df.empty else 0
            unit_profit = float(product.get("price", 0) or 0) - float(product.get("cost", 0) or 0)
            total_profit_all_time = total_sold_all_time * unit_profit

            last_30_start = datetime.now().date() - timedelta(days=29)
            if not sales_df.empty:
                sales_df["date"] = sales_df["timestamp"].dt.date
                sales_30 = sales_df[sales_df["date"] >= last_30_start]
                daily_30 = sales_30.groupby("date")["quantity"].sum()
                avg_daily_sales = round(float(daily_30.mean()), 2) if not daily_30.empty else 0.0
                history_df = daily_30.reset_index(name="qty") if not daily_30.empty else pd.DataFrame(columns=["date", "qty"])
            else:
                avg_daily_sales = 0.0
                history_df = pd.DataFrame(columns=["date", "qty"])

            stock_qty = int(product.get("stock_quantity", 0) or 0)
            days_of_cover = 999 if avg_daily_sales <= 0 else int(stock_qty / avg_daily_sales)

            st.divider()

            # --- Header Section ---
            c1, c2 = st.columns([3, 1])
            with c1:
                st.subheader(f"📦 {product['name']}")
                st.text(f"Barcode: {product['barcode']} | Category: {product['category']}")
            with c2:
                st.metric("Current Stock", product["stock_quantity"])

            # --- Key Metrics Row ---
            m1, m2, m3, m4 = st.columns(4)

            m1.metric("All-Time Sold", f"{total_sold_all_time} units")
            m2.metric("All-Time Profit", f"${total_profit_all_time:,.2f}")

            doc = days_of_cover
            doc_label = "Infinity" if doc >= 999 else f"{doc} days"
            delta_msg = "Stockout Imminent" if doc < 7 else "Healthy"

            m3.metric("Days of Cover", doc_label, delta_msg, delta_color="normal" if doc > 7 else "inverse")
            m4.metric("Avg Daily Sales", f"{avg_daily_sales} / day")

            # --- Profitability & Health ---
            st.markdown("#### 📊 Profitability & Health")
            p1, p2 = st.columns(2)

            with p1:
                margin = 0
                if float(product.get("price", 0) or 0) > 0:
                    margin = ((float(product.get("price", 0)) - float(product.get("cost", 0))) / float(product.get("price", 0))) * 100

                st.info(f"**Profit Margin:** {margin:.1f}%")
                st.caption(f"Cost: ${float(product.get('cost', 0) or 0):.2f} | Selling Price: ${float(product.get('price', 0) or 0):.2f}")

                if margin < 20:
                    st.warning("⚠️ Low margin product.")
                elif margin > 50:
                    st.success("✅ High margin product.")

            with p2:
                if doc >= 999:
                    st.error("💀 **Dead Stock Alert**: No sales in last 30 days.")
                elif doc < 7:
                    st.error("🚨 **Stockout Risk**: Less than 1 week of supply.")
                elif doc < 14:
                    st.warning("⚠️ **Restock Soon**: 2 weeks supply left.")
                else:
                    st.success("✅ **Healthy Stock Level**")

            # --- Chart Section ---
            st.subheader("📈 Sales Trend (Last 30 Days)")
            if not history_df.empty:
                history_df["date"] = pd.to_datetime(history_df["date"])
                st.area_chart(history_df.set_index("date")["qty"], color="#29B5E8")
            else:
                st.caption("No sales recorded in the last 30 days.")
            
    except Exception as e:
        st.error(f"Connection Error: {e}")
