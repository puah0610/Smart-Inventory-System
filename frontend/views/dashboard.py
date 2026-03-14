import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from itertools import combinations
from supabase_client import get_supabase_client


def _pair_rules(sales_df: pd.DataFrame):
    if sales_df.empty or "receipt_id" not in sales_df.columns:
        return []
    pair_counts = {}
    grouped = sales_df.groupby("receipt_id")["product_name"].apply(lambda x: sorted(set([v for v in x if v]))).tolist()
    for names in grouped:
        if len(names) < 2:
            continue
        for a, b in combinations(names, 2):
            pair_counts[(a, b)] = pair_counts.get((a, b), 0) + 1
    if not pair_counts:
        return []
    total_baskets = len([g for g in grouped if len(g) >= 2]) or 1
    rules = []
    for (a, b), freq in sorted(pair_counts.items(), key=lambda x: x[1], reverse=True):
        confidence = round((freq / total_baskets) * 100, 1)
        rules.append(
            {
                "antecedent": a,
                "consequent": b,
                "confidence": confidence,
                "frequency": freq,
            }
        )
    return rules[:10]


def _build_data(supabase):
    tx_res = (
        supabase.table("transactions")
        .select("receipt_id,quantity,timestamp,transaction_type,products(name,price,cost,category)")
        .execute()
    )
    product_res = supabase.table("products").select("id,name,stock_quantity").execute()

    tx_rows = tx_res.data or []
    products = product_res.data or []
    raw = pd.DataFrame(tx_rows)
    if raw.empty:
        return raw, pd.DataFrame(), products, []

    raw["timestamp"] = pd.to_datetime(raw["timestamp"], errors="coerce")
    raw["product_name"] = raw["products"].apply(lambda x: x.get("name") if isinstance(x, dict) else "Unknown")
    raw["unit_price"] = raw["products"].apply(lambda x: float(x.get("price", 0) or 0) if isinstance(x, dict) else 0.0)
    raw["unit_cost"] = raw["products"].apply(lambda x: float(x.get("cost", 0) or 0) if isinstance(x, dict) else 0.0)
    raw["category"] = raw["products"].apply(lambda x: x.get("category") if isinstance(x, dict) else "Uncategorized")
    raw["quantity"] = raw["quantity"].fillna(0).astype(int)

    sales = raw[raw["transaction_type"] == "sale"].copy()
    sales["revenue"] = sales["quantity"] * sales["unit_price"]
    sales["profit"] = sales["quantity"] * (sales["unit_price"] - sales["unit_cost"])
    sales["date"] = sales["timestamp"].dt.date

    rules = _pair_rules(sales)
    return raw, sales, products, rules

def show():
    st.header("Smart Dashboard")
    supabase = get_supabase_client()
    
    try:
        _, sales_df, products, rules = _build_data(supabase)
        if not sales_df.empty:
            total_revenue = float(sales_df["revenue"].sum())
            total_profit = float(sales_df["profit"].sum())

            today = datetime.now().date()
            yesterday = today - timedelta(days=1)
            today_rev = float(sales_df[sales_df["date"] == today]["revenue"].sum())
            yesterday_rev = float(sales_df[sales_df["date"] == yesterday]["revenue"].sum())
            pct = ((today_rev - yesterday_rev) / yesterday_rev * 100) if yesterday_rev else 0

            last_7_cutoff = today - timedelta(days=6)
            sales_7d = sales_df[sales_df["date"] >= last_7_cutoff]
            revenue_7d = float(sales_7d["revenue"].sum())

            fastest = "N/A"
            if not sales_7d.empty:
                fastest = sales_7d.groupby("product_name")["quantity"].sum().sort_values(ascending=False).index[0]

            margin_name = "N/A"
            if not sales_7d.empty:
                margin_series = sales_7d.groupby("product_name")["profit"].sum().sort_values(ascending=False)
                if not margin_series.empty:
                    margin_name = margin_series.index[0]

            low_stock = [p for p in products if int(p.get("stock_quantity", 0) or 0) < 10]
            strongest_bundle = f"{rules[0]['antecedent']} + {rules[0]['consequent']}" if rules else "N/A"

            ai_insights = []
            if rules:
                ai_insights.append({"type": "bundle", "message": f"Customers often buy {rules[0]['antecedent']} with {rules[0]['consequent']}"})
            if low_stock:
                ai_insights.append({"type": "alert", "severity": "high", "message": f"{len(low_stock)} item(s) are below stock threshold."})
            if fastest != "N/A":
                ai_insights.append({"type": "promo", "message": f"Promote '{fastest}' bundle add-ons to increase basket size."})

            top_selling = (
                sales_df.groupby("product_name")["profit"]
                .sum()
                .sort_values(ascending=False)
                .head(8)
                .rename_axis("name")
                .reset_index(name="margin")
                .to_dict(orient="records")
            )
            
            # --- 1. Top Metrics (Key Performance Indicators) ---
            st.markdown("### 🔑 Key Performance Indicators")
            mcol1, mcol2, mcol3 = st.columns(3)
            
            summary_7d = {
                "revenue": revenue_7d,
                "fastest_moving": fastest,
                "highest_margin": margin_name,
                "at_risk_count": len(low_stock),
                "strongest_bundle": strongest_bundle,
            }

            # Standardized Metric Style for all metrics
            def render_metric_card(label, value, delta=None):
                delta_html = "<p style='font-size: 14px; margin-top: -15px; visibility: hidden;'>placeholder</p>"
                if delta is not None:
                    try:
                        delta_val = float(delta.strip('%+'))
                        color = "#008148" if delta_val >= 0 else "#FF4B4B"
                        arrow = "↑" if delta_val >= 0 else "↓"
                        delta_html = f"<p style='color: {color}; font-size: 14px; margin-top: -15px;'>{arrow} {delta}% vs Yesterday</p>"
                    except:
                        delta_html = f"<p style='color: #808495; font-size: 14px; margin-top: -15px;'>{delta} vs Yesterday</p>"
                
                st.markdown(f"""
                    <div style='background-color: #1e2130; padding: 20px; border-radius: 10px; border-left: 5px solid #29B5E8; margin-bottom: 20px; min-height: 130px; display: flex; flex-direction: column; justify-content: center;'>
                        <p style='color: #808495; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;'>{label}</p>
                        <p style='font-size: 28px; font-weight: 700; margin: 0;'>{value}</p>
                        {delta_html}
                    </div>
                """, unsafe_allow_html=True)

            with mcol1:
                render_metric_card("Today's Revenue", f"RM {today_rev:,.2f}", f"{pct:+.1f}")
            with mcol2:
                render_metric_card("Total Revenue", f"RM {total_revenue:,.2f}")
            with mcol3:
                render_metric_card("Total Profit", f"RM {total_profit:,.2f}")

            # --- 1.2 Business Summary (Last 7 Days) ---
            st.markdown("### 📊 Business Summary (Last 7 Days)")
            sm_cols = st.columns(5)
            
            summary_items = [
                ("Last 7D Revenue", f"RM {summary_7d.get('revenue', 0):,.2f}", "#FF4B4B"),
                ("Fast Moving Item", summary_7d.get('fastest_moving', 'N/A'), "#29B5E8"),
                ("Highest Margin Product", summary_7d.get('highest_margin', 'N/A'), "#00D488"),
                ("At-Risk Items", summary_7d.get('at_risk_count', 0), "#FFD700"),
                ("Top Bundle", summary_7d.get('strongest_bundle', 'N/A'), "#A020F0")
            ]

            for i, (label, value, color) in enumerate(summary_items):
                with sm_cols[i]:
                    st.markdown(f"""
                        <div style='background-color: #1e2130; padding: 15px; border-radius: 10px; border-top: 3px solid {color}; height: 120px; display: flex; flex-direction: column; justify-content: space-between;'>
                            <p style='color: #808495; font-size: 12px; text-transform: uppercase; font-weight: 600; margin: 0;'>{label}</p>
                            <p style='font-size: 20px; font-weight: 700; color: white; margin: 0; line-height: 1.2;'>{value}</p>
                        </div>
                    """, unsafe_allow_html=True)

            st.divider()

            # --- 2. Historical & Predictive Charts ---
            col_left, col_right = st.columns(2)
            
            with col_left:
                st.subheader("📉 Past 30 Days Trend")
                try:
                    last_30 = datetime.now().date() - timedelta(days=30)
                    hist = sales_df[sales_df["date"] >= last_30].groupby("date")["revenue"].sum().reset_index()
                    if not hist.empty:
                        hist["date"] = pd.to_datetime(hist["date"])
                        hist = hist.sort_values("date")
                        st.line_chart(hist.set_index("date")["revenue"], color="#29B5E8")
                    else:
                        st.info("No historical data yet.")
                except Exception:
                    st.caption("History engine unavailable.")

            with col_right:
                st.subheader("📈 AI Revenue Forecast")
                try:
                    daily_rev = sales_df.groupby("date")["revenue"].sum().sort_index()
                    if len(daily_rev) >= 3:
                        baseline = float(daily_rev.tail(7).mean())
                        forecast_dates = [datetime.now().date() + timedelta(days=i) for i in range(1, 8)]
                        forecast_values = [baseline for _ in forecast_dates]
                        df_forecast = pd.DataFrame({"date": pd.to_datetime(forecast_dates), "predicted_revenue": forecast_values})

                        total_forecast = df_forecast["predicted_revenue"].sum()
                        st.metric("Total 7-Day Forecast", f"RM {total_forecast:,.2f}")
                        df_forecast["date_label"] = df_forecast["date"].dt.strftime("%a %d")
                        forecast_chart = alt.Chart(df_forecast).mark_bar(color="#FF4B4B").encode(
                            x=alt.X("date_label:N", title=None, axis=alt.Axis(labelAngle=0)),
                            y=alt.Y("predicted_revenue:Q", title="Predicted Revenue"),
                        )
                        st.altair_chart(forecast_chart, use_container_width=True)
                    else:
                        st.info("Record more sales for AI predictions.")
                except Exception:
                    st.caption("Forecast engine unavailable.")

            st.divider()

            # --- 3. "Actionable" AI Section ---
            st.subheader("🤖 Smart Insights & Recommendations")
            
            c_patterns, c_actions = st.columns([1, 1.5])
            
            with c_patterns:
                st.markdown("#### 🛍️ Shopping Patterns")
                patterns = [i for i in ai_insights if i.get("type") == "bundle"]
                
                with st.container(height=300): # Scrollable container
                    if patterns:
                        for p in patterns:
                            st.info(f"**Pattern:** {p['message']}")
                    else:
                        st.caption("No patterns detected yet.")
                
            with c_actions:
                st.markdown("#### 🚀 Recommended Actions")
                actions = [i for i in ai_insights if i.get("type") in ["promo", "clearance", "forecast", "alert"]]
                
                with st.container(height=300): # Scrollable container
                    if actions:
                        for a in actions:
                            if a.get('severity') == 'high':
                                st.error(a['message'])
                            elif a['type'] == 'promo':
                                st.success(a['message'])
                            else:
                                st.warning(a['message'])
                    else:
                        st.caption("No urgent actions identified.")

            # --- 3.5 Detailed Market Basket Analysis ---
            st.markdown("#### 🔍 Detailed Product Associations")
            try:
                if rules:
                    display_data = []
                    for rule in rules:
                        display_data.append({
                            "If Client Buys...": rule['antecedent'],
                            "They Also Buy...": rule['consequent'],
                            "Likelihood (%)": f"{rule['confidence']}%",
                            "Occurrences": rule['frequency']
                        })
                    st.dataframe(pd.DataFrame(display_data), use_container_width=True, hide_index=True)
                else:
                    st.caption("Not enough diversity in transactions to show associations.")
            except: pass

            st.divider()

            # --- 4. Inventory Quick Look ---
            q_left, q_right = st.columns(2)
            with q_left:
                st.subheader("🏆 Top Sellers")
                if top_selling:
                    df_top_selling = pd.DataFrame(top_selling)
                    top_sellers_chart = alt.Chart(df_top_selling).mark_bar(color="#29B5E8").encode(
                        x=alt.X('name:N', title=None, sort='-y', axis=alt.Axis(labelAngle=0)),
                        y=alt.Y('margin:Q', title='Margin')
                    )
                    st.altair_chart(top_sellers_chart, use_container_width=True)
            
            with q_right:
                st.subheader("⚠️ Low Stock Alert")
                try:
                    low_stock_items = [
                        {
                            "name": p.get("name"),
                            "stock": p.get("stock_quantity", 0),
                            "id": p.get("id"),
                        }
                        for p in products
                        if int(p.get("stock_quantity", 0) or 0) < 10
                    ]

                    if low_stock_items:
                        st.table(pd.DataFrame(low_stock_items)[["name", "stock"]])
                        if st.button("Generate Supplier Email"):
                            st.code("Subject: Restock Request\n\nItems needed: " + ", ".join([p["name"] for p in low_stock_items]))
                    else:
                        st.success("Stock levels are healthy!")
                except Exception:
                    st.caption("Inventory service unavailable.")

        else:
            st.info("Not enough sales data yet to render dashboard analytics.")
    except Exception as e:
        st.error(f"Error loading dashboard data: {e}")
