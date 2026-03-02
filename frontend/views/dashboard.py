import streamlit as st
import requests
import pandas as pd
import sys
import os

# Add parent directory to path to allow importing config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import API_URL

def show():
    st.header("Smart Dashboard")
    
    try:
        response = requests.get(f"{API_URL}/analytics/summary")
        if response.status_code == 200:
            data = response.json()
            
            # --- 1. Top Metrics (Key Performance Indicators) ---
            st.markdown("### 🔑 Key Performance Indicators")
            mcol1, mcol2, mcol3 = st.columns(3)
            
            daily_stats = data.get("daily", {})
            today_rev = daily_stats.get("today_revenue", 0)
            pct = daily_stats.get("pct_change", 0)
            
            summary_7d = data.get("business_summary_7d", {})

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
                render_metric_card("Total Revenue", f"RM {data['total_revenue']:,.2f}")
            with mcol3:
                render_metric_card("Total Profit", f"RM {data['total_profit']:,.2f}")

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
                    hist_res = requests.get(f"{API_URL}/analytics/sales-history")
                    if hist_res.status_code == 200:
                        h_data = hist_res.json().get("history", [])
                        if h_data:
                            df_hist = pd.DataFrame(h_data)
                            # Sort by actual datetime objects, not strings
                            df_hist['date'] = pd.to_datetime(df_hist['date'])
                            df_hist = df_hist.sort_values('date')
                            # Map revenue to the sorted date index
                            st.line_chart(df_hist.set_index('date')['revenue'], color="#29B5E8")
                        else:
                            st.info("No historical data yet.")
                except:
                    st.caption("History engine unavailable.")

            with col_right:
                st.subheader("📈 AI Revenue Forecast")
                try:
                    forecast_res = requests.get(f"{API_URL}/analytics/forecast")
                    if forecast_res.status_code == 200:
                        f_data = forecast_res.json().get("forecast", [])
                        if f_data:
                            df_forecast = pd.DataFrame(f_data)
                            df_forecast['date'] = pd.to_datetime(df_forecast['date'])
                            df_forecast = df_forecast.sort_values('date')
                            
                            # Calculate total forecasted revenue for the week
                            total_forecast = df_forecast['predicted_revenue'].sum()
                            st.metric("Total 7-Day Forecast", f"RM {total_forecast:,.2f}")

                            # Improved Bar Chart for clearer daily breakdown
                            df_forecast['date_label'] = df_forecast['date'].dt.strftime('%a %d')
                            st.bar_chart(
                                df_forecast.set_index('date_label')['predicted_revenue'], 
                                color="#FF4B4B",
                                use_container_width=True
                            )
                        else:
                            st.info("Record more sales for AI predictions.")
                except:
                    st.caption("Forecast engine unavailable.")

            st.divider()

            # --- 3. "Actionable" AI Section ---
            st.subheader("🤖 Smart Insights & Recommendations")
            
            c_patterns, c_actions = st.columns([1, 1.5])
            
            with c_patterns:
                st.markdown("#### 🛍️ Shopping Patterns")
                patterns = [i for i in data.get("ai_insights", []) if i['type'] == 'bundle']
                
                with st.container(height=300): # Scrollable container
                    if patterns:
                        for p in patterns:
                            st.info(f"**Pattern:** {p['message']}")
                    else:
                        st.caption("No patterns detected yet.")
                
            with c_actions:
                st.markdown("#### 🚀 Recommended Actions")
                actions = [i for i in data.get("ai_insights", []) if i['type'] in ['promo', 'clearance', 'forecast', 'alert']]
                
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
                mba_res = requests.get(f"{API_URL}/analytics/market-basket")
                if mba_res.status_code == 200:
                    rules = mba_res.json().get("rules", [])
                    if rules:
                        # Format for display
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
                if data['top_selling']:
                    st.bar_chart(pd.DataFrame(data['top_selling']).set_index("name"))
            
            with q_right:
                st.subheader("⚠️ Low Stock Alert")
                if data['low_stock_items']:
                    st.table(pd.DataFrame(data['low_stock_items'])[['name', 'stock']])
                    if st.button("Generate Supplier Email"):
                        st.code("Subject: Restock Request\n\nItems needed: " + ", ".join([p['name'] for p in data['low_stock_items']]))
                else:
                    st.success("Stock levels are healthy!")

        else:
            st.error("Failed to load analytics.")
    except Exception as e:
        st.error(f"Error connecting to backend: {e}")
