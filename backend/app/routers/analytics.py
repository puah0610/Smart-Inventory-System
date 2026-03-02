from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from .. import database, models
from ..services.analytics_service import AnalyticsService

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

# Initialize Service
# In a larger app, we might use dependency injection for this
analytics_service = AnalyticsService(database.engine)

@router.get("/forecast")
def get_demand_forecast():
    """
    Predicts sales for the next 7 days using Linear Regression.
    """
    forecast = analytics_service.predict_demand()
    return {"forecast": forecast}

@router.get("/sales-history")
def get_sales_history(db: Session = Depends(get_db)):
    """
    Returns daily sales history for the past 30 days.
    """
    # Use localized date to avoid UTC cutoff issues
    today = datetime.now().date()
    thirty_days_ago = today - timedelta(days=30)
    
    # Aggregate sales by date
    daily_sales = db.query(
        func.date(models.Transaction.timestamp).label("date"),
        func.sum(models.Transaction.quantity).label("units"),
        func.sum(models.Product.price * models.Transaction.quantity).label("revenue")
    ).select_from(models.Transaction).join(
        models.Product, models.Transaction.product_id == models.Product.id
    ).filter(
        models.Transaction.transaction_type == 'sale',
        func.date(models.Transaction.timestamp) >= thirty_days_ago.isoformat()
    ).group_by("date").order_by("date").all()
    
    return {
        "history": [{"date": r.date, "units": r.units, "revenue": r.revenue} for r in daily_sales]
    }

@router.get("/market-basket")
def get_market_basket_rules(db: Session = Depends(get_db)):
    """
    Analyzes transaction history to find product associations.
    """
    rules = analytics_service.get_market_basket_rules(db)
    return {"rules": rules}

@router.get("/summary")
def get_analytics_summary(db: Session = Depends(get_db)):
    # --- 1. Daily Performance Logic ---
    # Use local time for "Today", consistent with how data/daily_data_pipeline.py generates data
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day)
    # Check if we have data for 'today' or 'yesterday' to avoid empty metrics
    # Otherwise fallback to 'last 24 hours' and 'prior 24' if useful
    yesterday_start = today_start - timedelta(days=1)
    
    # Revenue Today (Matching actual today's sales)
    rev_today = db.query(
        func.sum(models.Product.price * models.Transaction.quantity)
    ).select_from(models.Transaction).join(
        models.Product, models.Transaction.product_id == models.Product.id
    ).filter(
        models.Transaction.transaction_type == 'sale',
        models.Transaction.timestamp >= today_start.strftime('%Y-%m-%d %H:%M:%S')
    ).scalar() or 0.0

    # Hourly Trend (Last 12 Hours)
    # This helps see the impact of frequent hourly pumps immediately
    last_12h = now - timedelta(hours=12)
    hourly_sales = db.query(
        func.strftime('%H:00', models.Transaction.timestamp).label("hour"),
        func.sum(models.Product.price * models.Transaction.quantity).label("revenue")
    ).select_from(models.Transaction).join(
        models.Product, models.Transaction.product_id == models.Product.id
    ).filter(
        models.Transaction.transaction_type == 'sale',
        models.Transaction.timestamp >= last_12h.strftime('%Y-%m-%d %H:%M:%S')
    ).group_by("hour").order_by("hour").all()

    # Revenue Yesterday
    rev_yesterday = db.query(
        func.sum(models.Product.price * models.Transaction.quantity)
    ).select_from(models.Transaction).join(
        models.Product, models.Transaction.product_id == models.Product.id
    ).filter(
        models.Transaction.transaction_type == 'sale',
        models.Transaction.timestamp >= yesterday_start.strftime('%Y-%m-%d %H:%M:%S'),
        models.Transaction.timestamp < today_start.strftime('%Y-%m-%d %H:%M:%S')
    ).scalar() or 0.0
    
    # Calculate % Change
    if rev_yesterday > 0:
        pct_change = ((rev_today - rev_yesterday) / rev_yesterday) * 100
    else:
        pct_change = 100.0 if rev_today > 0 else 0.0

    # --- 2. Dead Stock Logic ---
    # Value of items sitting on shelf (>0 qty) with NO sales in last 30 days
    thirty_days_ago = now - timedelta(days=30)
    
    sold_recently_subquery = db.query(models.Transaction.product_id).filter(
        models.Transaction.transaction_type == 'sale',
        models.Transaction.timestamp >= thirty_days_ago
    ).distinct()
    
    dead_stock_value = db.query(
        func.sum(models.Product.cost * models.Product.stock_quantity)
    ).filter(
        models.Product.stock_quantity > 0,
        ~models.Product.id.in_(sold_recently_subquery)
    ).scalar() or 0.0

    # --- 3. Business Summary (Last 7 Days) ---
    seven_days_ago = now - timedelta(days=7)
    
    # 7-Day Revenue
    rev_7d = db.query(
        func.sum(models.Product.price * models.Transaction.quantity)
    ).select_from(models.Transaction).join(
        models.Product, models.Transaction.product_id == models.Product.id
    ).filter(
        models.Transaction.transaction_type == 'sale',
        models.Transaction.timestamp >= seven_days_ago
    ).scalar() or 0.0

    # Fastest Moving Product (7 Days)
    fastest_moving = db.query(
        models.Product.name
    ).join(models.Transaction).filter(
        models.Transaction.transaction_type == 'sale',
        models.Transaction.timestamp >= seven_days_ago
    ).group_by(models.Product.id).order_by(desc(func.sum(models.Transaction.quantity))).first()
    fastest_moving_p = fastest_moving[0] if fastest_moving else "N/A"

    # Highest Margin Product (All time or 7 days, let's go with 7 days for consistency)
    highest_margin = db.query(
        models.Product.name
    ).join(models.Transaction).filter(
        models.Transaction.transaction_type == 'sale',
        models.Transaction.timestamp >= seven_days_ago
    ).group_by(models.Product.id).order_by(desc(func.avg(models.Product.price - models.Product.cost))).first()
    highest_margin_p = highest_margin[0] if highest_margin else "N/A"

    # --- 4. General Summaries ---
    # Calculate All-Time Revenue (Price * Quantity) and Profit ((Price - Cost) * Quantity)
    revenue_profit = db.query(
        func.sum(models.Product.price * models.Transaction.quantity).label("revenue"),
        func.sum((models.Product.price - models.Product.cost) * models.Transaction.quantity).label("profit")
    ).select_from(models.Transaction).join(
        models.Product, models.Transaction.product_id == models.Product.id
    ).filter(models.Transaction.transaction_type == 'sale').first()

    total_revenue = revenue_profit.revenue if revenue_profit.revenue else 0     
    total_profit = revenue_profit.profit if revenue_profit.profit else 0        

    # 5. Low Stock Alerts (Threshold < 10)
    low_stock = db.query(models.Product).filter(models.Product.stock_quantity < 10).all()

    # 6. AI Insights (Delegated to Service)
    insights = analytics_service.generate_insights(db)
    
    # Extract At-Risk count and strongest bundle from insights
    at_risk_count = len([i for i in insights if i['type'] == 'forecast' and i.get('severity') == 'high'])
    
    # Find strongest bundle (verified trend with highest count/confidence)
    bundles = [i for i in insights if i['type'] == 'bundle']
    # Extract cleaner name: e.g. "Bundle 'Pasta' + 'Sauce'" -> "Pasta + Sauce"
    if bundles:
        raw_bundle = bundles[0]['message'].split('\n')[0].replace('📦 **Cross-Sell Strategy**: ', '')
        # Remove "Bundle " prefix and single quotes
        strongest_bundle = raw_bundle.replace('Bundle ', '').replace("'", "")
    else:
        strongest_bundle = "N/A"

    return {
        "daily": {
            "today_revenue": rev_today,
            "pct_change": pct_change,
            "dead_stock_value": dead_stock_value,
            "hourly_trend": [{"hour": r.hour, "revenue": r.revenue} for r in hourly_sales]
        },
        "business_summary_7d": {
            "revenue": rev_7d,
            "fastest_moving": fastest_moving_p,
            "highest_margin": highest_margin_p,
            "at_risk_count": at_risk_count,
            "strongest_bundle": strongest_bundle
        },
        "total_revenue": total_revenue,
        "total_profit": total_profit,
        "low_stock_items": [{"name": p.name, "stock": p.stock_quantity, "id": p.id} for p in low_stock],
        "top_selling": [], # Deprecated or can keep
        "ai_insights": insights
    }
