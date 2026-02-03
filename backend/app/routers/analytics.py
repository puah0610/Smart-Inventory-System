from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
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

@router.get("/market-basket")
def get_market_basket_rules(db: Session = Depends(get_db)):
    """
    Analyzes transaction history to find product associations.
    """
    rules = analytics_service.get_market_basket_rules(db)
    return {"rules": rules}

@router.get("/summary")
def get_analytics_summary(db: Session = Depends(get_db)):
    # 1. Total Sales Count & Revenue
    sales_query = db.query(models.Transaction).filter(models.Transaction.transaction_type == 'sale')
    total_sales_count = sales_query.count()
    
    # Calculate Revenue (Price * Quantity) and Profit ((Price - Cost) * Quantity)
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

    # 4. AI Insights (Delegated to Service)
    insights = analytics_service.generate_insights(db)
    
    return {
        "total_revenue": total_revenue,
        "total_profit": total_profit,
        "sales_count": total_sales_count,
        "low_stock_items": [{"name": p.name, "stock": p.stock_quantity, "id": p.id} for p in low_stock],
        "top_selling": [{"name": r.name, "value": r.total_sold} for r in top_selling],
        "ai_insights": insights
    }
