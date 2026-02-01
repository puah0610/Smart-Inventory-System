from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from .. import database, models
from collections import Counter
from itertools import combinations
from datetime import datetime, timedelta

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    responses={404: {"description": "Not found"}},
)

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- PREDICTIVE AI ENGINE (Lightweight Linear Regression) ---
def calculate_days_until_stockout(stock, sales_history):
    """
    sales_history: list of (date_index, quantity_sold)
    Estimates when stock will hit 0 based on trend.
    """
    if not sales_history or stock <= 0:
        return None
        
    n = len(sales_history)
    if n < 5: # Not enough data for trend, use simple average
        total_sales = sum(q for _, q in sales_history)
        avg_daily = total_sales / n
        return stock / avg_daily if avg_daily > 0 else 999
        
    # Linear Regression: y = mx + c
    # x = days (0, 1, 2...), y = sales
    sum_x = sum(d for d, _ in sales_history)
    sum_y = sum(q for _, q in sales_history)
    sum_xy = sum(d*q for d, q in sales_history)
    sum_xx = sum(d*d for d, _ in sales_history)
    
    # Slope (m)
    denominator = (n * sum_xx - sum_x * sum_x)
    if denominator == 0:
        m = 0
    else:
        m = (n * sum_xy - sum_x * sum_y) / denominator
        
    # Intercept (c)
    c = (sum_y - m * sum_x) / n
    
    # Predict future demand
    # If slope is positive (sales increasing), we deplete faster
    # If slope is negative (sales dropping), we last longer
    
    # Predicted daily sales for tomorrow (day n)
    predicted_daily = m * n + c
    
    # Safety: If prediction is negative/zero, fallback to average
    if predicted_daily <= 0.1:
        predicted_daily = sum_y / n
        
    return stock / predicted_daily if predicted_daily > 0 else 999

@router.get("/summary")
def get_analytics_summary(db: Session = Depends(get_db)):
    # 1. Total Sales Count & Revenue
    sales_query = db.query(models.Transaction).filter(models.Transaction.transaction_type == 'sale')
    total_sales_count = sales_query.count()
    
    # Calculate Revenue (Price * Quantity) and Profit ((Price - Cost) * Quantity)
    # We need to join Transaction with Product
    revenue_profit = db.query(
        func.sum(models.Product.price * models.Transaction.quantity).label("revenue"),
        func.sum((models.Product.price - models.Product.cost) * models.Transaction.quantity).label("profit")
    ).join(models.Product).filter(models.Transaction.transaction_type == 'sale').first()
    
    total_revenue = revenue_profit.revenue if revenue_profit.revenue else 0
    total_profit = revenue_profit.profit if revenue_profit.profit else 0
    
    # 2. Low Stock Alerts (Threshold < 10)
    low_stock = db.query(models.Product).filter(models.Product.stock_quantity < 10).all()
    
    # 3. Top Selling Products
    top_selling = db.query(
        models.Product.name,
        func.sum(models.Transaction.quantity).label("total_sold")
    ).join(models.Transaction).filter(models.Transaction.transaction_type == 'sale')\
    .group_by(models.Product.id).order_by(desc("total_sold")).limit(5).all()

    # 4. Market Basket Analysis (Pattern Finder)
    # Fetch all sales transactions with receipts
    sales_data = db.query(models.Transaction.receipt_id, models.Product.name)\
        .join(models.Product)\
        .filter(models.Transaction.transaction_type == 'sale')\
        .filter(models.Transaction.receipt_id != None)\
        .all()

    # Group items by receipt_id
    receipts = {}
    for r_id, p_name in sales_data:
        if r_id not in receipts:
            receipts[r_id] = set()
        receipts[r_id].add(p_name)
    
    # Count individual items & pairs
    item_counts = Counter()
    pair_counts = Counter()
    
    for items in receipts.values():
        unique_items = list(items)
        unique_items.sort()
        
        # Count individual items for confidence metrics
        for i in unique_items:
            item_counts[i] += 1
            
        if len(unique_items) < 2:
            continue
        
        for pair in combinations(unique_items, 2):
            pair_counts[pair] += 1
            
    # Format insights (Only strictly valid patterns)
    insights = []
    
    # 5. Inventory Optimization Engine (Dead Stock vs Patterns)
    # Define "Overstock": Items with stock > 15 (Demo threshold)
    # inventory optimization engine
    # Pre-fetch product details for pricing logic
    all_products = db.query(models.Product).all()
    product_map = {p.name: p for p in all_products}

    # Define "Overstock": Items where Stock is significantly higher than sales velocity
    # For this demo, we verify: Stock > 10 AND Stock > (Lifetime Sales * 1.5) 
    # (Meaning: You have 1.5x the stock of what you have ever sold - rough proxy for slow moving)
    overstock_candidates = []
    for p in all_products:
        total_sold = item_counts[p.name]
        # Basic Demo Heuristic for Overstock
        if p.stock_quantity > 10 and p.stock_quantity > (total_sold * 1.5):
            overstock_candidates.append(p)
    
    # Track processed pairs to avoid duplicate advice (e.g. A->B and B->A)
    processed_pairs = set()

    # Analyze Overstock
    for item in overstock_candidates:
        # Check if this item is part of any strong pattern
        found_bundle = False
        
        # We look for a STRONG trend (count >= 2) for this specific item
        for (p1, p2), count in pair_counts.most_common():
            # NOISE FILTER: Ignore bundles that happened only once
            if count < 2:
                continue

            # Identify target (overstock) and partner
            partner_name = None
            if item.name == p1:
                partner_name = p2
            elif item.name == p2:
                partner_name = p1
            
            if partner_name and partner_name in product_map:
                # Deduplication Check
                pair_key = tuple(sorted([p1, p2]))
                if pair_key in processed_pairs:
                    # Already recommended this pair. Mark as found so we don't suggest Clearance
                    # and skip creating a duplicate message.
                    found_bundle = True
                    break

                partner_obj = product_map[partner_name]
                
                # Confidence Calculation
                item_total_sales = item_counts[item.name]
                confidence = (count / item_total_sales) if item_total_sales > 0 else 0
                
                # Calculate Bundle Pricing
                original_total = item.price + partner_obj.price
                discounted_price = original_total * 0.85 # 15% discount
                
                # Logic: Smart Differentiation
                if confidence >= 0.5: # Strong Combo
                    msg = (f"📦 **Smart Bundle Strategy**: Customers love '{item.name}' & '{partner_name}'.\n"
                           f"   • **Proposal**: 'Weekend Duo Pack'\n"
                           f"   • **Pricing**: Sell both for **${discounted_price:.2f}** (Save 15%)\n"
                           f"   • **Goal**: Clear your {item.stock_quantity} units of {item.name}.")
                    severity = "high"
                else: # Loose Association
                    msg = (f"👀 **Cross-Merchandising**: Place '{item.name}' next to '{partner_name}'.\n"
                           f"   • Don't discount yet. Just improve visibility to catch that {int(confidence*100)}% crossover traffic.")
                    severity = "medium"

                insights.append({
                    "type": "promo",
                    "message": msg,
                    "severity": severity
                })
                
                # Mark pair as processed
                processed_pairs.add(pair_key)
                found_bundle = True
                break
        
        # If no strong bundle found, fallback to MARGIN-BASED advice
        if not found_bundle:
             # Calculate Profit Margin: (Price - Cost) / Price
             margin = (item.price - item.cost) / item.price if item.price > 0 else 0
             
             if margin > 0.5:
                 # High Margin: We can afford BOGO
                 strategy = "🔥 **Buy 1 Get 1 Free**"
                 reason = f"High Margin Item ({int(margin*100)}%). You can afford to give one away to triple your sales velocity."
             else:
                 # Low Margin: Small discount only
                 disc_price = item.price * 0.85
                 strategy = f"🏷️ **15% Off Clearance (Sale: ${disc_price:.2f})**"
                 reason = f"Low Margin Item ({int(margin*100)}%). A deep discount would cause a loss. Stick to 15%."

             insights.append({
                "type": "clearance",
                "message": f"📉 **Clearance Advice for '{item.name}'**\n   • **Problem**: Stock ({item.stock_quantity}) is high vs Sales.\n   • **Strategy**: {strategy}\n   • **Why**: {reason}",
                "severity": "medium"
            })
            
    # Add the general trends for the "Patterns" display (Separate from Actions)
    # We can still show "Top Trends" even if they aren't actionable yet, but let's filter noise there too
    for (item1, item2), count in pair_counts.most_common(3):
        if count >= 2: # Only show credible trends
            insights.append({
                "type": "bundle",
                "message": f"Verified Trend: {item1} & {item2}",
                "count": count
            })
            
    # 6. Sales Forecasting AI
    # Fetch last 30 days sales for trend analysis
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    history_query = db.query(models.Transaction.product_id, models.Transaction.quantity, models.Transaction.timestamp)\
        .filter(models.Transaction.transaction_type == 'sale')\
        .filter(models.Transaction.timestamp >= thirty_days_ago).all()
        
    # Organize data: {product_id: {day_index: daily_qty}}
    product_history = {}
    for pid, qty, ts in history_query:
        if pid not in product_history:
            product_history[pid] = {}
        
        # Convert timestamp to relative day index (0 to 30)
        day_idx = (ts - thirty_days_ago).days
        product_history[pid][day_idx] = product_history[pid].get(day_idx, 0) + qty
        
    # Analyze each product using our Linear Regression Helper
    for p in all_products:
        p_data = product_history.get(p.id, {})
        
        # Create full 30-day vector (including 0 sales days) to map true velocity
        full_xy = []
        for d in range(31): 
             full_xy.append((d, p_data.get(d, 0)))
             
        days_left = calculate_days_until_stockout(p.stock_quantity, full_xy)
        
        if days_left is not None and days_left < 14: # Warn if less than 2 weeks stock
             # High urgency if < 5 days
             urgency = "high" if days_left < 5 else "medium"
             icon = "🚨" if days_left < 5 else "🔮"
             
             insights.append({
                "type": "forecast",
                "message": f"{icon} **AI Forecast**: Demand for '{p.name}' is rising. Stockout predicted in **{int(days_left)} days**.",
                "severity": urgency
            })
    
    return {
        "total_revenue": total_revenue,
        "total_profit": total_profit,
        "sales_count": total_sales_count,
        "low_stock_items": [{"name": p.name, "stock": p.stock_quantity, "id": p.id} for p in low_stock],
        "top_selling": [{"name": r.name, "value": r.total_sold} for r in top_selling],
        "ai_insights": insights
    }
