from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .routers import product, inventory, analytics

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Inventory System API")

# Configure CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(product.router)
app.include_router(inventory.router)
app.include_router(analytics.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Smart Inventory System API"}
