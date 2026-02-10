import streamlit as st
from views import dashboard, pos, restock, add_product, inventory, history, customers

# Configure the page only once
st.set_page_config(page_title="Smart Inventory", layout="wide")

# --- KAMUS TERJEMAHAN (SIMPLE WORDING) ---
translations = {
    "English": {
        "title": "Smart Inventory Management System",
        "nav_label": "Choose Page",
        "menu": ["Dashboard", "Sales Counter (POS)", "Order Stock", "Register New Item", "Stock List", "Past Sales", "Customer List"]
    },
    "Bahasa Melayu": {
        "title": "Sistem Pengurusan Stok Pintar",
        "nav_label": "Pilih Halaman",
        "menu": ["Papan Pemuka", "Kaunter Jualan (POS)", "Pesan Stok Baru", "Daftar Barang Baru", "Senarai Stok", "Rekod Jualan", "Senarai Pelanggan"]
    }
}

# 1. Sidebar untuk pilih bahasa
lang = st.sidebar.radio("Bahasa / Language", ["English", "Bahasa Melayu"])

# 2. Guna teks berdasarkan bahasa yang dipilih
st.title(translations[lang]["title"])

# Initialize Session State
if "cart" not in st.session_state:
    st.session_state.cart = []

# 3. Update Sidebar Navigation dengan nama yang mudah
# Kita guna index untuk tahu mana satu yang dipilih
menu_options = translations[lang]["menu"]
sidebar_selection = st.sidebar.selectbox(translations[lang]["nav_label"], menu_options)

# Mapping balik ke views asal (Guna index supaya logic tidak lari)
choice_index = menu_options.index(sidebar_selection)

# Routing Logic
if choice_index == 0: # Dashboard
    dashboard.show()
elif choice_index == 1: # POS
    pos.show()
elif choice_index == 2: # Restock
    restock.show()
elif choice_index == 3: # Add Product
    add_product.show()
elif choice_index == 4: # Inventory
    inventory.show()
elif choice_index == 5: # History
    history.show()
elif choice_index == 6: # Customers
    customers.show()
