import pandas as pd
from sklearn.linear_model import LinearRegression
import numpy as np
from datetime import datetime, timedelta

class AnalyticsEngine:
    def __init__(self, db_connection_string):
        self.db_connection_string = db_connection_string
    
    def get_sales_data(self):
        """Fetches sales transactions from the database."""
        query = "SELECT * FROM transactions WHERE transaction_type = 'sale'"
        try:
            df = pd.read_sql(query, self.db_connection_string)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        except Exception as e:
            print(f"Error fetching data: {e}")
            return pd.DataFrame()

    def predict_demand(self, days_ahead=7):
        """
        Predicts total sales quantity for the next X days.
        Returns a DataFrame with dates and predicted quantities.
        """
        df = self.get_sales_data()
        
        if df.empty:
            return pd.DataFrame(columns=['date', 'predicted_quantity'])

        # Aggregate daily sales
        daily_sales = df.groupby(df['timestamp'].dt.date)['quantity'].sum().reset_index()
        daily_sales['date_ordinal'] = pd.to_datetime(daily_sales['timestamp']).map(datetime.toordinal)
        
        if len(daily_sales) < 2:
            return pd.DataFrame(columns=['date', 'predicted_quantity'])

        # Prepare model
        X = daily_sales[['date_ordinal']]
        y = daily_sales['quantity']
        
        model = LinearRegression()
        model.fit(X, y)
        
        # Generate future dates
        last_date = pd.to_datetime(daily_sales['timestamp']).max()
        future_dates = [last_date + timedelta(days=x) for x in range(1, days_ahead + 1)]
        future_ordinals = np.array([d.toordinal() for d in future_dates]).reshape(-1, 1)
        
        # Predict
        predictions = model.predict(future_ordinals)
        
        # Format results
        forecast_df = pd.DataFrame({
            'date': future_dates,
            'predicted_quantity': [max(0, round(p)) for p in predictions] # No negative sales
        })
        
        return forecast_df

    def get_sales_trends(self):
        # Placeholder for logic to read from DB using pandas
        pass
        
    def get_low_stock_alerts(self, threshold=10):
        # Placeholder logic
        pass
