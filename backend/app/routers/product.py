from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List
from .. import crud, models, schemas, database
from datetime import datetime, timedelta

router = APIRouter(
    prefix="/products",
    tags=["products"],
    responses={404: {"description": "Not found"}},
)

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/customers/", response_model=schemas.Customer, tags=["customers"])
def create_customer(customer: schemas.CustomerCreate, db: Session = Depends(get_db)):
    db_customer = crud.get_customer_by_phone(db, phone=customer.phone)
    if db_customer:
        raise HTTPException(status_code=400, detail="Customer already exists")
    return crud.create_customer(db=db, customer=customer)

@router.get("/customers/", response_model=List[schemas.Customer], tags=["customers"])
def read_customers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_customers(db, skip=skip, limit=limit)

@router.get("/customers/{phone}", response_model=schemas.Customer, tags=["customers"])
def get_customer(phone: str, db: Session = Depends(get_db)):
    db_customer = crud.get_customer_by_phone(db, phone=phone)
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return db_customer

@router.get("/customers/id/{customer_id}/profile", response_model=schemas.CustomerProfile, tags=["customers"])
def get_customer_profile(customer_id: int, db: Session = Depends(get_db)):
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Aggregations
    # Total Spend & Visits (Count unique receipts)
    stats = db.query(
        func.sum(models.Product.price * models.Transaction.quantity).label("spent"),
        func.count(models.Transaction.receipt_id.distinct()).label("visits"),
        func.max(models.Transaction.timestamp).label("last_visit")
    ).join(models.Product).filter(models.Transaction.customer_id == customer_id).first()
    
    total_spent = stats.spent if stats.spent else 0
    visit_count = stats.visits if stats.visits else 0
    last_visit = stats.last_visit
    
    # Top Items
    top_items_query = db.query(
        models.Product.name,
        func.sum(models.Transaction.quantity).label("qty")
    ).join(models.Transaction).filter(models.Transaction.customer_id == customer_id)\
    .group_by(models.Product.id).order_by(desc("qty")).limit(3).all()
    
    top_items = [{"name": r.name, "qty": r.qty} for r in top_items_query]
    
    # --- RFM Segmentation Logic ---
    now = datetime.utcnow()
    recency_days = 999
    if last_visit:
        recency_days = (now - last_visit).days
        
    segment = "New"
    
    # 1. Champions: Bought recently, buy often, spend a lot
    if recency_days <= 30 and visit_count >= 3 and total_spent >= 300:
        segment = "🏆 Champion"
        
    # 2. Loyal Customers: Spend good money
    elif total_spent >= 200:
        segment = "💎 Loyal"
        
    # 3. Potential Loaylist: Recent visitor with decent spend
    elif recency_days <= 30 and total_spent >= 50:
        segment = "🌟 Potential Loyalist"
        
    # 4. At Risk: Big spenders who haven't visited in a while (> 60 days)
    elif recency_days > 60 and total_spent > 100:
        segment = "⚠️ At Risk"
        
    # 5. Hibernating: Low spend, long time ago
    elif recency_days > 90:
        segment = "💤 Hibernating"
        
    # 6. About to Sleep: Below average recency
    elif recency_days > 30:
        segment = "👀 About to Sleep"
        
    else:
        segment = "Regular"
        
    return {
        "customer": customer,
        "total_spent": total_spent,
        "visit_count": visit_count,
        "last_visit": last_visit,
        "top_items": top_items,
        "segment": segment
    }

@router.post("/", response_model=schemas.Product)
def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):
    db_product = crud.get_product_by_barcode(db, barcode=product.barcode)
    if db_product:
        raise HTTPException(status_code=400, detail="Product with this barcode already registered")
    return crud.create_product(db=db, product=product)

@router.get("/", response_model=List[schemas.Product])
def read_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    products = crud.get_products(db, skip=skip, limit=limit)
    return products

@router.get("/{barcode}", response_model=schemas.Product)
def read_product(barcode: str, db: Session = Depends(get_db)):
    db_product = crud.get_product_by_barcode(db, barcode=barcode)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return db_product

@router.get("/id/{product_id}/analytics", response_model=schemas.ProductAnalytics)
def get_product_analytics(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # 1. Total Stats (All Time)
    stats = db.query(
        func.sum(models.Transaction.quantity).label("total_qty"),
        func.sum(models.Transaction.quantity * models.Product.price).label("revenue"),
        func.sum(models.Transaction.quantity * (models.Product.price - models.Product.cost)).label("profit")
    ).select_from(models.Transaction).join(
        models.Product, models.Transaction.product_id == models.Product.id
    ).filter(
        models.Transaction.product_id == product_id,
        models.Transaction.transaction_type == 'sale'
    ).first()

    total_qty = stats.total_qty or 0
    total_revenue = stats.revenue or 0.0
    total_profit = stats.profit or 0.0

    # 2. Days of Cover Logic (Based on last 30 days)
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    
    qty_last_30 = db.query(func.sum(models.Transaction.quantity))\
        .filter(
            models.Transaction.product_id == product_id,
            models.Transaction.transaction_type == 'sale',
            models.Transaction.timestamp >= thirty_days_ago
        ).scalar() or 0
        
    avg_daily_sales = qty_last_30 / 30.0
    
    if avg_daily_sales > 0:
        days_of_cover = product.stock_quantity / avg_daily_sales
    else:
        days_of_cover = 999.0 # Infinite cover (Dead stock)

    # 3. Sales History (Daily for chart)
    # SQLite 'date' function compatible
    history_query = db.query(
        func.date(models.Transaction.timestamp).label("date"),
        func.sum(models.Transaction.quantity).label("qty")
    ).filter(
        models.Transaction.product_id == product_id,
        models.Transaction.transaction_type == 'sale',
        models.Transaction.timestamp >= thirty_days_ago
    ).group_by("date").order_by("date").all()
    
    history_data = [{"date": str(r.date), "qty": r.qty} for r in history_query]

    return {
        "product": product,
        "total_sold_all_time": total_qty,
        "total_revenue_all_time": total_revenue,
        "total_profit_all_time": total_profit,
        "current_stock": product.stock_quantity,
        "days_of_cover": round(days_of_cover, 1),
        "avg_daily_sales": round(avg_daily_sales, 2),
        "sales_history": history_data
    }
