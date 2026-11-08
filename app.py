from xml.sax.handler import all_features

import streamlit as st
import pandas as pd
import psycopg2

# Import modular view files
from views import pos, inventory, expenses, pnl, shipments, sudo, transactions

st.set_page_config(page_title="Kiosk POS & Modular Hub", layout="wide", initial_sidebar_state="expanded")

# --- THEME SELECTOR STATE & CSS INJECTION ---
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "Dark"

with st.sidebar:
    st.markdown("### 🎨 Interface Theme")
    selected_theme = st.radio("Choose Mode", ["Dark", "Light"], index=0 if st.session_state.theme_mode == "Dark" else 1, horizontal=True)
    if selected_theme != st.session_state.theme_mode:
        st.session_state.theme_mode = selected_theme
        st.rerun()

# Apply Light Theme Styling if selected
if st.session_state.theme_mode == "Light":
    st.markdown("""
        <style>
            .stApp {
                background-color: #F8F9FA;
                color: #212529;
            }
            sidebar .stSidebar {
                background-color: #E9ECEF;
            }
        </style>
    """, unsafe_allow_html=True)

def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["url"])

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    
    # 1. Create tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            sku TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            base_cost REAL NOT NULL,
            overhead_cost REAL DEFAULT 0.0,
            cost_price REAL NOT NULL,
            selling_price REAL NOT NULL,
            stock INT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS stock_shipments (
            id SERIAL PRIMARY KEY,
            sku TEXT,
            item_name TEXT,
            quantity INT,
            base_cost_per_unit REAL,
            additional_costs_json TEXT,
            total_additional_cost REAL,
            total_landed_cost REAL,
            effective_unit_cost REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sales (
            id SERIAL PRIMARY KEY,
            receipt_no TEXT UNIQUE,
            client_name TEXT,
            total_revenue REAL,
            total_cost REAL,
            gross_profit REAL,
            staff_name TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sale_items (
            id SERIAL PRIMARY KEY,
            receipt_no TEXT,
            sku TEXT,
            item_name TEXT,
            qty INT,
            unit_cost REAL,
            unit_price REAL
        );
        CREATE TABLE IF NOT EXISTS operating_expenses (
            id SERIAL PRIMARY KEY,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS expense_categories (
            id SERIAL PRIMARY KEY,
            category_name TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY,
            role_name TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS role_permissions (
            role_id INT REFERENCES roles(id) ON DELETE CASCADE,
            feature_name TEXT NOT NULL,
            PRIMARY KEY (role_id, feature_name)
        );
        CREATE TABLE IF NOT EXISTS app_users (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            pin TEXT UNIQUE NOT NULL,
            role_id INT REFERENCES roles(id)
        );
    """)
    
    cur.execute("ALTER TABLE sales ADD COLUMN IF NOT EXISTS staff_name TEXT;")
    cur.execute("ALTER TABLE stock_shipments ADD COLUMN IF NOT EXISTS additional_costs_json TEXT;")
    cur.execute("ALTER TABLE stock_shipments ADD COLUMN IF NOT EXISTS total_additional_cost REAL;")
    cur.execute("ALTER TABLE stock_shipments ADD COLUMN IF NOT EXISTS timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
    cur.execute("ALTER TABLE operating_expenses ADD COLUMN IF NOT EXISTS timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")

    # 2. Seed Default Roles & Users if empty
    cur.execute("SELECT COUNT(*) FROM roles;")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO roles (role_name) VALUES ('Admin'), ('Store Owner'), ('Cashier') ON CONFLICT DO NOTHING;")
        conn.commit()
        
        cur.execute("SELECT id, role_name FROM roles;")
        role_map = {name: rid for rid, name in cur.fetchall()}
        
        cur.execute("""
            INSERT INTO app_users (username, pin, role_id) 
            VALUES (%s, %s, %s), (%s, %s, %s), (%s, %s, %s) 
            ON CONFLICT DO NOTHING;
        """, (
            "Lead Developer", "9999", role_map["Admin"],
            "Mummy", "1234", role_map["Store Owner"],
            "Cashier1", "0000", role_map["Cashier"]
        ))
        
        all_features = [
            "POS Checkout", "Inventory Control", "Operating Expenses", 
            "Net P&L Overview", "Shipment Audit", "Transaction Logs", "User & Role Management"
        ]
        for f in all_features:
            cur.execute("INSERT INTO role_permissions (role_id, feature_name) VALUES (%s, %s) ON CONFLICT DO NOTHING;", (role_map["Admin"], f))
        
        owner_features = [
            "POS Checkout", "Inventory Control", "Operating Expenses", 
            "Net P&L Overview", "Shipment Audit", "Transaction Logs"
        ]
        for f in owner_features:
            cur.execute("INSERT INTO role_permissions (role_id, feature_name) VALUES (%s, %s) ON CONFLICT DO NOTHING;", (role_map["Store Owner"], f))
            
        cur.execute("INSERT INTO role_permissions (role_id, feature_name) VALUES (%s, %s) ON CONFLICT DO NOTHING;", (role_map["Cashier"], "POS Checkout"))
        conn.commit()

    conn.commit()
    cur.close()
    conn.close()

try:
    init_db()
except Exception as e:
    st.error(f"Database connection error: {e}")

# ----------------- LOGIN SYSTEM -----------------
if "logged_user" not in st.session_state:
    st.session_state.logged_user = None

if "failed_attempts" not in st.session_state:
    st.session_state.failed_attempts = 0

max_attempts = 3

if st.session_state.logged_user is None:
    st.title("🔒 Kiosk Secure User Identification")
    st.markdown("Please enter your registered username and security PIN to access your dashboard.")

    if st.session_state.failed_attempts >= max_attempts:
        st.error("🚨 System locked due to multiple incorrect attempts. Please contact your system administrator.")
    else:
        username_input = st.text_input("Username (e.g., Mummy, Cashier1, Lead Developer)")
        pin_input = st.text_input("Security PIN / Password", type="password")
        
        if st.button("Verify & Login", type="primary"):
            if not username_input or not pin_input:
                st.warning("⚠️ Please provide both your username and PIN.")
            else:
                with st.spinner("Connecting to secure database and verifying credentials..."):
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT u.username, r.role_name, r.id 
                        FROM app_users u 
                        JOIN roles r ON u.role_id = r.id 
                        WHERE LOWER(u.username) = LOWER(%s) AND u.pin = %s
                    """, (username_input.strip(), pin_input.strip()))
                    user_record = cur.fetchone()
                    cur.close()
                    conn.close()

                if user_record:
                    st.session_state.failed_attempts = 0
                    st.success("✅ PIN correct!")
                    st.info("🔄 Logging in...")
                    st.success(f"🎉 Welcome, {user_record[0]}! Loading your customized dashboard...")
                    
                    st.session_state.logged_user = {
                        "username": user_record[0],
                        "role": user_record[1],
                        "role_id": user_record[2]
                    }
                    st.rerun()
                else:
                    st.session_state.failed_attempts += 1
                    attempts_left = max_attempts - st.session_state.failed_attempts
                    st.error("❌ PIN incorrect or username not found, try again.")
                    
                    if attempts_left > 0:
                        st.warning(f"⚠️ You have **{attempts_left} attempt(s)** remaining before system lockout.")
                    else:
                        st.error("🚨 Maximum attempts reached. System is now locked.")
                        st.rerun()
    st.stop()

def get_user_permissions(role_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT feature_name FROM role_permissions WHERE role_id = %s", (role_id,))
    perms = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return perms

user_info = st.session_state.logged_user
user_permissions = get_user_permissions(user_info["role_id"])

# Top Bar
c_title, c_user = st.columns([3, 1])
with c_title:
    st.title("🛍️ Kiosk Operations & Management Hub")
with c_user:
    st.write(f"User: **{user_info['username']}**\nRole: *{user_info['role']}*")
    if st.button("🔒 Logout"):
        st.session_state.logged_user = None
        st.session_state.failed_attempts = 0
        st.rerun()

available_tabs = []
feature_tab_mapping = {
    "POS Checkout": "🛒 POS Checkout",
    "Inventory Control": "📦 Inventory Control",
    "Operating Expenses": "💸 Operating Expenses",
    "Net P&L Overview": "📊 Net P&L Overview",
    "Shipment Audit": "🚚 Shipment Audit",
    "Transaction Logs": "📜 Transaction Logs",
    "User & Role Management": "⚙️ Sudo & User Control"
}

for feat, tab_name in feature_tab_mapping.items():
    if feat in user_permissions:
        available_tabs.append(tab_name)

if not available_tabs:
    st.error("No permissions assigned to your role.")
    st.stop()

tabs = st.tabs(available_tabs)

# ----------------- RENDER MODULAR TABS -----------------
def has_tab(name):
    return name in available_tabs

if has_tab("🛒 POS Checkout"):
    with tabs[available_tabs.index("🛒 POS Checkout")]:
        pos.render(get_connection, user_info)

if has_tab("📦 Inventory Control"):
    with tabs[available_tabs.index("📦 Inventory Control")]:
        inventory.render(get_connection)

if has_tab("💸 Operating Expenses"):
    with tabs[available_tabs.index("💸 Operating Expenses")]:
        expenses.render(get_connection)

if has_tab("📊 Net P&L Overview"):
    with tabs[available_tabs.index("📊 Net P&L Overview")]:
        pnl.render(get_connection)

if has_tab("🚚 Shipment Audit"):
    with tabs[available_tabs.index("🚚 Shipment Audit")]:
        shipments.render(get_connection)

if has_tab("⚙️ Sudo & User Control"):
    with tabs[available_tabs.index("⚙️ Sudo & User Control")]:
        sudo.render(get_connection)

if has_tab("📜 Transaction Logs"):
    with tabs[available_tabs.index("📜 Transaction Logs")]:
        transactions.render(get_connection)