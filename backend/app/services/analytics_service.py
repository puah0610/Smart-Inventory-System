
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

    def predict_demand(self, days_ahead=7):
        """
        Predicts total sales quantity for the next X days.
        """
        query = "SELECT * FROM transactions WHERE transaction_type = 'sale'"
        try:
            df = pd.read_sql(query, self.db_engine)
            
            if df.empty:
                return []

            # Fix for SQLite storing datetimes with/without microseconds
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', errors='coerce')
            df = df.dropna(subset=['timestamp'])

            # Aggregate daily sales
            daily_sales = df.groupby(df['timestamp'].dt.date)['quantity'].sum().reset_index()
            daily_sales['date_ordinal'] = pd.to_datetime(daily_sales['timestamp']).map(datetime.toordinal)
            
            if len(daily_sales) < 2:
                return []

            # Prepare model
            X = daily_sales[['date_ordinal']]
            y = daily_sales['quantity']
            
            model = LinearRegression()
            model.fit(X, y)
            
            # Generate future dates
            last_date = pd.to_datetime(daily_sales['timestamp']).max()
            future_dates = [last_date + timedelta(days=x) for x in range(1, days_ahead + 1)]
            
            # Create DataFrame with same feature name to avoid warnings
            future_X = pd.DataFrame({'date_ordinal': [d.toordinal() for d in future_dates]})
            
            # Predict
            predictions = model.predict(future_X)
            
            forecast_data = []
            for date, qty in zip(future_dates, predictions):
                forecast_data.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "predicted_quantity": max(0, int(round(qty)))
                })
            
            return forecast_data
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
                
                rules.append({
                    "antecedent": item_a,
                    "consequent": item_b,
                    "frequency": pair_freq,
                    "confidence": round(conf_a_b, 1)
                })
                rules.append({
                    "antecedent": item_b,
                    "consequent": item_a,
                    "frequency": pair_freq,
                    "confidence": round(conf_b_a, 1)
                })

        rules.sort(key=lambda x: x['confidence'], reverse=True)
        return rules[:10]

    def _calculate_days_until_stockout(self, stock, sales_history):
        if not sales_history or stock <= 0:
            return None
            
        n = len(sales_history)
        if n < 5: 
            total_sales = sum(q for _, q in sales_history)
            avg_daily = total_sales / n
            return stock / avg_daily if avg_daily > 0 else 999
            
        # Linear Regression: y = mx + c
        sum_x = sum(d for d, _ in sales_history)
        sum_y = sum(q for _, q in sales_history)
        sum_xy = sum(d*q for d, q in sales_history)
        sum_xx = sum(d*d for d, _ in sales_history)
        
        denominator = (n * sum_xx - sum_x * sum_x)
        if denominator == 0:
            m = 0
        else:
            m = (n * sum_xy - sum_x * sum_y) / denominator
            
        c = (sum_y - m * sum_x) / n
        predicted_daily = m * n + c
        
        if predicted_daily <= 0.1:
            predicted_daily = sum_y / n
            
        return stock / predicted_daily if predicted_daily > 0 else 999

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
        for (item1, item2), count in pair_counts.most_common(3):
            if count >= 2:
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
            days = self._calculate_days_until_stockout(p.stock_quantity, full_xy)
            
            if days is not None and days < 14:
                urgency = "high" if days < 5 else "medium"
                icon = "🚨" if days < 5 else "🔮"
                insights.append({
                    "type": "forecast",
                    "message": f"{icon} **AI Forecast**: '{p.name}' stockout in **{int(days)} days**.",
                    "severity": urgency
                })
                
        # 4. Declining Sales Alert (Sales Drop Analysis)
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
            # Fetch product only if we have a match to avoid N+1 queries ideally, but acceptable here
            product = db.query(models.Product).filter(models.Product.id == pid).first()
            
            if product and prev_qty >= 3 and recent_qty <= (prev_qty * 0.4):
                 msg = f"📉 **Sales Drop**: '{product.name}' sales dropped significantly this week. Promotion Recommended."
                 
                 # --- TRIGGER NOTIFICATION (Logic Layer -> Notification Engine) ---
                 self.notifier.notify_admin("Sales Alert", f"Sales for {product.name} dropped by >60%!", severity="high")
                 
                 insights.append({
                    "type": "alert",
                    "message": msg,
                    "severity": "medium"
                })

        return insights

