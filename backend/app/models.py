from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    barcode = Column(String, unique=True, index=True)
    price = Column(Float)
    cost = Column(Float)
    category = Column(String)
    stock_quantity = Column(Integer, default=0)

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    phone = Column(String, unique=True, index=True)
    email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(String, index=True) # Groups multiple items in one checkout
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    transaction_type = Column(String) # 'sale' or 'restock'
    quantity = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    product = relationship("Product")
    customer = relationship("Customer")
