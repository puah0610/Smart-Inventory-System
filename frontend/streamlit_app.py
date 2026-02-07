import streamlit as st
from views import dashboard, pos, inventory, history, customers, product_performance

# Configure the page only once at the very start
st.set_page_config(page_title='Smart Inventory', layout='wide')

st.title('Smart Inventory Management System')

# Initialize Session State
if 'cart' not in st.session_state:
    st.session_state.cart = []

# Sidebar Navigation
sidebar_option = st.sidebar.selectbox(
    'Navigation',
    ['Dashboard', 'POS Terminal', 'Inventory', 'Sales History', 'Customers', 'Product Intelligence']
)

# Routing Logic
if sidebar_option == 'Dashboard':
    dashboard.show()
elif sidebar_option == 'POS Terminal':
    pos.show()
elif sidebar_option == 'Inventory':
    inventory.show()
elif sidebar_option == 'Sales History':
    history.show()
elif sidebar_option == 'Customers':
    customers.show()
elif sidebar_option == 'Product Intelligence':
    product_performance.show()
