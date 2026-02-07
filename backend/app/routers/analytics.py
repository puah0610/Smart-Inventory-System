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
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Aggregate sales by date
    daily_sales = db.query(
        func.date(models.Transaction.timestamp).label("date"),
        func.sum(models.Transaction.quantity).label("units"),
        func.sum(models.Product.price * models.Transaction.quantity).label("revenue")
    ).select_from(models.Transaction).join(
        models.Product, models.Transaction.product_id == models.Product.id
    ).filter(
        models.Transaction.transaction_type == 'sale',
        models.Transaction.timestamp >= thirty_days_ago
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
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    yesterday_start = today_start - timedelta(days=1)
    
    # Revenue Today
    rev_today = db.query(
        func.sum(models.Product.price * models.Transaction.quantity)
    ).select_from(models.Transaction).join(
        models.Product, models.Transaction.product_id == models.Product.id
    ).filter(
        models.Transaction.transaction_type == 'sale',
        models.Transaction.timestamp >= today_start
    ).scalar() or 0.0

    # Revenue Yesterday
    rev_yesterday = db.query(
        func.sum(models.Product.price * models.Transaction.quantity)
    ).select_from(models.Transaction).join(
        models.Product, models.Transaction.product_id == models.Product.id
    ).filter(
        models.Transaction.transaction_type == 'sale',
        models.Transaction.timestamp >= yesterday_start,
        models.Transaction.timestamp < today_start
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

    # --- 3. General Summaries ---
    sales_query = db.query(models.Transaction).filter(models.Transaction.transaction_type == 'sale')
    total_sales_count = sales_query.count()

    # Calculate All-Time Revenue (Price * Quantity) and Profit ((Price - Cost) * Quantity)
    revenue_profit = db.query(
        func.sum(models.Product.price * models.Transaction.quantity).label("revenue"),
        func.sum((models.Product.price - models.Product.cost) * models.Transaction.quantity).label("profit")
    ).select_from(models.Transaction).join(
        models.Product, models.Transaction.product_id == models.Product.id
    ).filter(models.Transaction.transaction_type == 'sale').first()

    total_revenue = revenue_profit.revenue if revenue_profit.revenue else 0     
    total_profit = revenue_profit.profit if revenue_profit.profit else 0        

    # 4. Low Stock Alerts (Threshold < 10)
    low_stock = db.query(models.Product).filter(models.Product.stock_quantity < 10).all()

    # 5. Top Selling Products
    top_selling = db.query(
        models.Product.name,
        func.sum(models.Transaction.quantity).label("total_sold")
    ).join(models.Transaction).filter(models.Transaction.transaction_type == 'sale')\
    .group_by(models.Product.id).order_by(desc("total_sold")).limit(5).all()    

    # 6. AI Insights (Delegated to Service)
    insights = analytics_service.generate_insights(db)

    return {
        "daily": {
            "today_revenue": rev_today,
            "pct_change": pct_change,
            "dead_stock_value": dead_stock_value
        },
        "total_revenue": total_revenue,
        "total_profit": total_profit,
        "sales_count": total_sales_count,
        "low_stock_items": [{"name": p.name, "stock": p.stock_quantity, "id": p.id} for p in low_stock],
        "top_selling": [{"name": r.name, "value": r.total_sold} for r in top_selling],
        "ai_insights": insights
    }
