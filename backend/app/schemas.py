from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ProductBase(BaseModel):
    name: str
    barcode: str
    price: float
    cost: float
    category: str
    stock_quantity: int = 0

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    id: int

    class Config:
        from_attributes = True # updated for Pydantic v2

class CustomerBase(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None

class CustomerCreate(CustomerBase):
    pass

class Customer(CustomerBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True

class CustomerProfile(BaseModel):
    customer: Customer
    total_spent: float
    visit_count: int
    last_visit: Optional[datetime] = None
    top_items: list[dict]
    segment: str

class TransactionBase(BaseModel):
    product_id: int
    transaction_type: str
    quantity: int
    receipt_id: Optional[str] = None
    customer_id: Optional[int] = None

class TransactionCreate(TransactionBase):
    pass

class BatchTransactionCreate(BaseModel):
    items: list[TransactionCreate]
    receipt_id: str
    customer_id: Optional[int] = None

class Transaction(TransactionBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class ProductAnalytics(BaseModel):
    product: Product
    total_sold_all_time: int
    total_revenue_all_time: float
    total_profit_all_time: float
    current_stock: int
    days_of_cover: float
    avg_daily_sales: float
    sales_history: list[dict] # {date: str, qty: int}

class LowStockWhatsappRequest(BaseModel):
    to_number: Optional[str] = None

class LowStockWhatsappResponse(BaseModel):
    success: bool
    notified_to: str
    low_stock_count: int
    message: str
