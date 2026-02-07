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
            mcol1, mcol2, mcol3, mcol4 = st.columns(4)
            
            daily_stats = data.get("daily", {})
            today_rev = daily_stats.get("today_revenue", 0)
            pct = daily_stats.get("pct_change", 0)
            
            mcol1.metric("Today's Revenue", f"${today_rev:,.2f}", f"{pct:+.1f}% vs Yesterday")
            mcol2.metric("Total Revenue", f"${data['total_revenue']:,.2f}")
            mcol3.metric("Total Profit", f"${data['total_profit']:,.2f}")
            mcol4.metric("Sales Count", data['sales_count'])
            
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
                            df_hist['date'] = pd.to_datetime(df_hist['date']).dt.strftime('%d %b')
                            st.line_chart(df_hist.set_index('date')['revenue'], color="#29B5E8")
                        else:
                            st.info("No historical data yet.")
                except:
                    st.caption("History engine unavailable.")

            with col_right:
                st.subheader("📈 AI Demand Forecast")
                try:
                    forecast_res = requests.get(f"{API_URL}/analytics/forecast")
                    if forecast_res.status_code == 200:
                        f_data = forecast_res.json().get("forecast", [])
                        if f_data:
                            df_forecast = pd.DataFrame(f_data)
                            df_forecast['date'] = pd.to_datetime(df_forecast['date']).dt.strftime('%a %d')
                            st.area_chart(df_forecast.set_index('date')['predicted_quantity'], color="#FF4B4B")
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
