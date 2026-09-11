# Smart Inventory Management System

A comprehensive inventory management solution featuring a FastAPI backend and a Streamlit frontend. This system helps businesses manage products, track inventory, handle sales transactions (POS), and analyze sales data with built-in intelligence.

## 🚀 Features

- **Real-time Inventory Tracking**: Monitor stock levels and receive automated notifications.
- **POS Terminal**: Streamlined interface for processing sales and updates inventory automatically.
- **Product Management**: Create, update, and categorize products with barcode support.
- **Advanced Analytics**:
  - **Demand Forecasting**: Predicts sales for the next 7 days using Linear Regression.
  - **Market Basket Analysis**: Identifies product associations to suggest bundles.
  - **Performance Metrics**: Track revenue trends, dead stock, and top-performing categories.
- **Notification System**: Integrated alerts via WhatsApp (Simulation/Twilio) and Email.

## 📁 Project Structure

```
Smart-Inventory-System/
├── backend/                # FastAPI Application
│   ├── app/                # Core logic, models, and routes
│   │   ├── routers/        # API Endpoints (Product, Inventory, Analytics)
│   │   ├── services/       # Business logic (Analytics, Notifications)
│   │   └── models.py       # Database models
│   └── requirements.txt    # Backend dependencies
├── frontend/               # Streamlit Application
│   ├── views/              # Frontend pages (Dashboard, POS, History, etc.)
│   └── streamlit_app.py    # Main entry point
├── data/                   # Seed data and population scripts
└── README.md               # Project documentation
```

## 🛠 Prerequisites

- Python 3.9 or higher
- `pip` (Python package installer)

## ⚙️ Setup and Installation

### 1. Database Setup

The system uses SQLite by default. To initialize the database with demo data:

1. Follow the **Backend Setup** steps below to install dependencies.
2. Run the population scripts from the project root:
   ```bash
   python data/populate_inventory.py
   python data/generate_history.py
   ```

### 2. Backend Setup (FastAPI)

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the backend server:
   ```bash
   uvicorn app.main:app --reload
   ```
   The API will be available at [http://127.0.0.1:8000](http://127.0.0.1:8000). Interactive docs at [/docs](http://127.0.0.1:8000/docs).

### 3. Frontend Setup (Streamlit)

1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   pip install streamlit requests pandas
   ```
3. Run the frontend application:
   ```bash
   streamlit run streamlit_app.py
   ```
   The application will open at [http://localhost:8501](http://localhost:8501).

## 🔔 Notification Service Configuration

The system currently runs in **Simulation Mode** (logs notifications to the console). To enable real WhatsApp alerts:

1. Sign up for [Twilio](https://www.twilio.com/).
2. Get your `Account SID`, `Auth Token`, and a `Twilio Sandbox Number`.
3. Configure environment variables in `backend/app/services/notification_service.py` or a `.env` file.

## 🧪 Testing

You can test the notification trigger logic by running the included test script:
```bash
python test_notification.py
```

