
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import datetime, timedelta
from itertools import combinations
from collections import Counter
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from .. import models
from .notification_service import NotificationService
from ..logger import get_logger

logger = get_logger(__name__)

class AnalyticsService:
    def __init__(self, db_engine):
        self.db_engine = db_engine
        self.notifier = NotificationService()
        self.enable_declining_sales_alerts = False

    def predict_demand(self, days_ahead=7):
        """
        Predicts total sales quantity for the next X days.
        """
        try:
            # Join products to get price for revenue calculation
            query = """
                SELECT t.*, p.price 
                FROM transactions t 
                JOIN products p ON t.product_id = p.id 
                WHERE t.transaction_type = 'sale'
            """
            df = pd.read_sql(query, self.db_engine)
            
            if df.empty:
                logger.info("No transaction data found for prediction.")
                return []

            # Fix for SQLite storing datetimes with/without microseconds
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', errors='coerce')
            df = df.dropna(subset=['timestamp'])

            # Calculate revenue per transaction
            df['revenue'] = df['quantity'] * df['price']

            # Aggregate daily stats
            # Ensure groupby result is consistent
            daily_stats = df.groupby(df['timestamp'].dt.date).agg({
                'quantity': 'sum',
                'revenue': 'sum'
            }).reset_index()
            
            # Map date to ordinal for Linear Regression
            daily_stats['date_ordinal'] = pd.to_datetime(daily_stats['timestamp']).apply(lambda x: x.toordinal())
            
            if len(daily_stats) < 1:
                return []

            # Prepare models
            X = daily_stats[['date_ordinal']]
            y_qty = daily_stats['quantity']
            y_rev = daily_stats['revenue']
            
            model_qty = LinearRegression()
            model_rev = LinearRegression()
            
            if len(daily_stats) >= 2:
                model_qty.fit(X, y_qty)
                model_rev.fit(X, y_rev)
            else:
                # If only 1 day, "predict" based on that day's value (flat line)
                single_day_qty = y_qty.iloc[0]
                single_day_rev = y_rev.iloc[0]
                class FlatModel:
                    def __init__(self, val): self.val = val
                    def predict(self, X): return [self.val] * len(X)
                
                model_qty = FlatModel(single_day_qty)
                model_rev = FlatModel(single_day_rev)
            
            # Generate future dates
            last_date = pd.to_datetime(daily_stats['timestamp']).max()
            future_dates = [last_date + timedelta(days=x) for x in range(1, days_ahead + 1)]
            
            future_X = pd.DataFrame({'date_ordinal': [d.toordinal() for d in future_dates]})
            
            # Predict
            pred_qty = model_qty.predict(future_X)
            pred_rev = model_rev.predict(future_X)
            
            forecast_data = []
            for date, q, r in zip(future_dates, pred_qty, pred_rev):
                forecast_data.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "predicted_quantity": max(0, int(round(q))),
                    "predicted_revenue": max(0.0, float(round(r, 2)))
                })
            
            return forecast_data
        except Exception as e:
            logger.error(f"Error in prediction: {e}")
            return []
        except Exception as e:
            logger.error(f"Error in prediction: {e}")
            return []

    def get_market_basket_rules(self, db: Session, min_occurrence=2):
        """
        Analyzes transaction history to find product associations.
        """
        # Fetch valid transactions
        sales_data = db.query(models.Transaction.receipt_id, models.Product.name)\
            .join(models.Product)\
            .filter(models.Transaction.transaction_type == 'sale')\
            .filter(models.Transaction.receipt_id != None)\
            .all()

        if not sales_data:
            return []

        # 1. Group items by receipt
        receipts = {}
        for r_id, p_name in sales_data:
            if r_id not in receipts:
                receipts[r_id] = set()
            receipts[r_id].add(p_name)
        
        # 2. Count frequencies
        item_counts = Counter()
        pair_counts = Counter()

        for items in receipts.values():
            unique_items = list(items)
            unique_items.sort()
            
            for i in unique_items:
                item_counts[i] += 1
                
            for pair in combinations(unique_items, 2):
                pair_counts[pair] += 1

        # 3. Generate Rules
        rules = []
        for (item_a, item_b), pair_freq in pair_counts.items():
            if pair_freq >= min_occurrence:
                # Calculate Confidence
                support_a = item_counts[item_a]
                conf_a_b = (pair_freq / support_a) * 100
                
                support_b = item_counts[item_b]
                conf_b_a = (pair_freq / support_b) * 100

                # Keep only one direction per pair to avoid mirrored duplicates.
                # Choose the stronger confidence direction; tie-break by lower support antecedent.
                if conf_a_b > conf_b_a:
                    antecedent, consequent, confidence = item_a, item_b, conf_a_b
                elif conf_b_a > conf_a_b:
                    antecedent, consequent, confidence = item_b, item_a, conf_b_a
                else:
                    if support_a < support_b:
                        antecedent, consequent = item_a, item_b
                    elif support_b < support_a:
                        antecedent, consequent = item_b, item_a
                    else:
                        antecedent, consequent = sorted([item_a, item_b])
                    confidence = conf_a_b

                rules.append({
                    "antecedent": antecedent,
                    "consequent": consequent,
                    "frequency": pair_freq,
                    "confidence": round(confidence, 1)
                })

        rules.sort(key=lambda x: (x['confidence'], x['frequency']), reverse=True)
        return rules[:10]

    def _calculate_days_until_stockout(self, stock, sales_history):
        if not sales_history or stock <= 0:
            return None, 0
            
        n = len(sales_history)
        # We need at least 7 days of data to provide a 'High' confidence score
        if n < 5: 
            total_sales = sum(q for _, q in sales_history)
            avg_daily = total_sales / n
            return (stock / avg_daily if avg_daily > 0 else 999), 30 # Low confidence for new items
            
        # Linear Regression: y = mx + c
        sum_x = sum(d for d, _ in sales_history)
        sum_y = sum(q for _, q in sales_history)
        sum_xy = sum(d*q for d, q in sales_history)
        sum_xx = sum(d*d for d, _ in sales_history)
        
        denominator = (n * sum_xx - sum_x * sum_x)
        if denominator == 0:
            m = 0
            r_squared = 0
        else:
            m = (n * sum_xy - sum_x * sum_y) / denominator
            # Calculate R-squared for Confidence
            # This measures how well the data fits our line (0 to 1)
            y_mean = sum_y / n
            ss_tot = sum((q - y_mean)**2 for _, q in sales_history)
            c_temp = (sum_y - m * sum_x) / n
            ss_res = sum((q - (m * d + c_temp))**2 for d, q in sales_history)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            
        c = (sum_y - m * sum_x) / n
        predicted_daily = m * n + c
        
        if predicted_daily <= 0.1:
            predicted_daily = sum_y / n
            
        days = stock / predicted_daily if predicted_daily > 0 else 999
        
        # Map R-squared to a 0-100 Confidence Score
        # We also weigh it by data points (more days = more confidence)
        confidence_score = int(min(100, (r_squared * 80) + (min(n, 30) * 0.6)))
        
        return days, max(10, confidence_score)

    def generate_insights(self, db: Session):
        """
        Generates actionable insights based on patterns and inventory levels.
        """
        insights = []
        
        # Re-run a lightweight pair counting for insights
        # Ideally cached or passed in, but for separation we recalculate cleanly
        sales_data = db.query(models.Transaction.receipt_id, models.Product.name)\
            .join(models.Product)\
            .filter(models.Transaction.transaction_type == 'sale')\
            .filter(models.Transaction.receipt_id != None)\
            .all()

        receipts = {}
        for r_id, p_name in sales_data:
            if r_id not in receipts: receipts[r_id] = set()
            receipts[r_id].add(p_name)
        
        item_counts = Counter()
        pair_counts = Counter()
        for items in receipts.values():
            unique = list(items)
            unique.sort()
            for i in unique: item_counts[i] += 1
            for pair in combinations(unique, 2): pair_counts[pair] += 1
            
        # 1. Bundle Opportunities
        all_products = db.query(models.Product).all()
        product_map = {p.name: p for p in all_products}
        
        # Check overstock items
        overstock = [p for p in all_products if p.stock_quantity > 10 and p.stock_quantity > (item_counts[p.name] * 1.5)]
        
        processed_pairs = set()
        
        for item in overstock:
            found_bundle = False
            for (p1, p2), count in pair_counts.most_common():
                if count < 2: continue
                
                partner_name = p2 if item.name == p1 else (p1 if item.name == p2 else None)
                
                if partner_name and partner_name in product_map:
                    pair_key = tuple(sorted([p1, p2]))
                    if pair_key in processed_pairs: 
                        found_bundle = True
                        break
                        
                    partner = product_map[partner_name]
                    confidence = count / item_counts[item.name] if item_counts[item.name] > 0 else 0
                    
                    disc_price = (item.price + partner.price) * 0.85
                    
                    if confidence >= 0.5:
                        msg = (f"📦 **Smart Bundle**: '{item.name}' & '{partner_name}'. "
                               f"Sell for ${disc_price:.2f} to clear {item.stock_quantity} units.")
                        severity = "high"
                    else:
                        msg = (f"👀 **Cross-Merch**: Place '{item.name}' next to '{partner_name}'.")
                        severity = "medium"
                        
                    insights.append({"type": "promo", "message": msg, "severity": severity})
                    processed_pairs.add(pair_key)
                    found_bundle = True
                    break
            
            if not found_bundle:
                margin = (item.price - item.cost) / item.price if item.price > 0 else 0
                if margin > 0.5:
                    insights.append({
                        "type": "clearance", 
                        "message": f"🔥 **BOGO Advice**: High margin on '{item.name}'. Buy 1 Get 1 Free.",
                        "severity": "medium"
                    })
                else:
                    insights.append({
                        "type": "clearance",
                        "message": f"📉 **Clearance**: 15% off '{item.name}'.",
                        "severity": "medium"
                    })

        # 2. General Trends
        # Deterministic selection: top pairs by frequency
        top_correlated = pair_counts.most_common(10)
        
        for (item1, item2), count in top_correlated[:3]:
            if count >= 2:
                # --- Intelligent Strategy Generation ---
                # Calculate estimated monthly impact
                # (pair_freq / current_window_days) * 30 days * avg_profit_gain
                # Let's simplify: count * (Price * 0.1) * 30 / (current_data_days)
                
                prod1 = product_map.get(item1)
                prod2 = product_map.get(item2)
                
                impact_msg = ""
                if prod1 and prod2:
                    avg_price = (prod1.price + prod2.price) / 2
                    # Assume a 10% uplift in these pairs if bundled properly
                    monthly_uplift = (count / 30) * 30 * avg_price * 0.15 
                    
                    strategy_msg = (
                        f"📦 **Cross-Sell Strategy**: Bundle '{item1}' + '{item2}'\n\n"
                        f"🏷️ **Promo**: Offer 10-15% bundle discount\n\n"
                        f"📈 **Est. Monthly Uplift**: +RM {monthly_uplift:,.2f}"
                    )
                    insights.append({"type": "bundle", "message": strategy_msg, "count": count})
                else:
                    insights.append({"type": "bundle", "message": f"Verified Trend: {item1} & {item2}", "count": count})

        # 3. Stockout Risk
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        history = db.query(models.Transaction.product_id, models.Transaction.quantity, models.Transaction.timestamp)\
            .filter(models.Transaction.transaction_type == 'sale')\
            .filter(models.Transaction.timestamp >= thirty_days_ago).all()
            
        prod_hist = {}
        for pid, qty, ts in history:
            if pid not in prod_hist: prod_hist[pid] = {}
            day_idx = (ts - thirty_days_ago).days
            prod_hist[pid][day_idx] = prod_hist[pid].get(day_idx, 0) + qty
            
        for p in all_products:
            p_data = prod_hist.get(p.id, {})
            full_xy = [(d, p_data.get(d, 0)) for d in range(31)]
            days, confidence = self._calculate_days_until_stockout(p.stock_quantity, full_xy)
            
            # Show only urgent stockout risks in dashboard actions (exclude stable).
            if days is not None and days < 3:
                # --- Advanced Decision Support Logic ---
                # Risk Classification Logic
                if days < 1:
                    risk_level = "🔴 **CRITICAL RISK**"
                    urgency = "high"
                elif days < 3:
                    risk_level = "🟡 **WARNING**"
                    urgency = "medium"

                # 1. Calculate Average Daily Sales (Velocity)
                total_qty = sum(qty for _, qty in full_xy)
                avg_daily_sales = total_qty / 31 # Based on the 30-day window
                
                # 2. Potential Revenue Loss (Price * Average Daily Sales * Days of stockout we want to prevent)
                # Let's assume we want to prevent a 7-day stockout
                potential_loss = p.price * avg_daily_sales * 7
                
                # 3. Recommended Reorder (Lead time coverage + safety stock)
                # Assume 3 days lead time + 4 days safety = 7 days of stock
                reorder_qty = int(avg_daily_sales * 10) # 10 days of stock is a safe bet
                
                # Enhanced Detailed Message
                detailed_msg = (
                    f"{risk_level}: **{p.name}** stockout in **{int(days)} days**.\n\n"
                    f"🎯 **AI Confidence**: {confidence}%\n\n"
                    f"💰 **Potential Revenue Loss**: RM {potential_loss:,.2f} (7-day impact)\n\n"
                    f"📈 **Avg. Daily Sales**: {avg_daily_sales:.1f} units\n\n"
                    f"🔁 **Recommended Reorder**: {reorder_qty} units"
                )
                
                insights.append({
                    "type": "forecast",
                    "message": detailed_msg,
                    "severity": urgency,
                    "days_until": days
                })
                
        # 4. Declining Sales Alert (Sales Drop Analysis)
        if self.enable_declining_sales_alerts:
            two_weeks_ago = datetime.utcnow() - timedelta(days=14)
            one_week_ago = datetime.utcnow() - timedelta(days=7)

            recent_sales = db.query(models.Transaction.product_id, func.sum(models.Transaction.quantity))\
                .filter(models.Transaction.transaction_type == 'sale')\
                .filter(models.Transaction.timestamp >= one_week_ago)\
                .group_by(models.Transaction.product_id).all()

            prev_sales = db.query(models.Transaction.product_id, func.sum(models.Transaction.quantity))\
                .filter(models.Transaction.transaction_type == 'sale')\
                .filter(models.Transaction.timestamp >= two_weeks_ago)\
                .filter(models.Transaction.timestamp < one_week_ago)\
                .group_by(models.Transaction.product_id).all()

            recent_map = {pid: qty for pid, qty in recent_sales}
            prev_map = {pid: qty for pid, qty in prev_sales}

            for pid, prev_qty in prev_map.items():
                recent_qty = recent_map.get(pid, 0)
                product = db.query(models.Product).filter(models.Product.id == pid).first()

                if product and prev_qty >= 3 and recent_qty <= (prev_qty * 0.4):
                    msg = f"📉 **Sales Drop**: '{product.name}' sales dropped significantly this week. Promotion Recommended."
                    self.notifier.notify_admin("Sales Alert", f"Sales for {product.name} dropped by >60%!", severity="high")

                    insights.append({
                        "type": "alert",
                        "message": msg,
                        "severity": "medium",
                        "days_until": 999
                    })

        # Remove duplicates (same type + exact same message)
        deduped_insights = []
        seen = set()
        for insight in insights:
            key = (insight.get("type"), insight.get("message"))
            if key in seen:
                continue
            seen.add(key)
            deduped_insights.append(insight)

        # Sort insights by urgency (days_until)
        # We use a default of 100 for non-forecast types so they appear after stockouts
        deduped_insights.sort(key=lambda x: x.get('days_until', 100))

        return deduped_insights

