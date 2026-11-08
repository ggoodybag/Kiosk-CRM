import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta

def render(get_connection):
    st.subheader("📜 System Transaction Logs & Audit Trail")
    st.markdown("Comprehensive, timestamped history of all financial and inventory transactions across the kiosk.")

    # Filter controls layout
    col_f1, col_f2, col_f3 = st.columns([1.5, 1, 1])
    with col_f1:
        log_type = st.selectbox("Select Log Category", ["Sales Transactions", "Operating Expenses", "Stock Shipments / Intake"])
    with col_f2:
        date_filter = st.selectbox("Timeframe", ["All Time", "Today", "This Week", "This Month"])
    with col_f3:
        staff_search = st.text_input("🔍 Search Staff / Keyword", placeholder="e.g. Mummy, Cashier1...")

    # Calculate date boundary
    today_date = date.today()
    date_condition = "WHERE 1=1"
    
    if date_filter == "Today":
        date_condition += f" AND timestamp >= '{today_date} 00:00:00'"
    elif date_filter == "This Week":
        start_of_week = today_date - timedelta(days=today_date.weekday())
        date_condition += f" AND timestamp >= '{start_of_week} 00:00:00'"
    elif date_filter == "This Month":
        start_of_month = today_date.replace(day=1)
        date_condition += f" AND timestamp >= '{start_of_month} 00:00:00'"

    conn = get_connection()

    if log_type == "Sales Transactions":
        st.markdown("### 🛒 Sales & Checkout History")
        
        # Add staff search condition if provided
        staff_clause = ""
        if staff_search:
            staff_clause = f" AND LOWER(staff_name) LIKE LOWER('%{staff_search.strip()}%')"

        query = f"""
            SELECT receipt_no AS "Receipt ID", client_name AS "Customer", 
                   total_revenue AS "Revenue (₦)", total_cost AS "Cost (₦)", 
                   gross_profit AS "Gross Profit (₦)", staff_name AS "Attendant", timestamp AS "Timestamp" 
            FROM sales {date_condition} {staff_clause} ORDER BY timestamp DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            st.download_button(
                label="📥 Export Sales Logs (.csv)",
                data=df.to_csv(index=False).encode('utf-8'),
                file_name=f"sales_logs_{date.today()}.csv",
                mime="text/csv"
            )
        else:
            st.info("No matching sales transactions found.")

    elif log_type == "Operating Expenses":
        st.markdown("### 💸 Operating Expenses Log")
        
        # Search filter across category or description/notes
        desc_clause = ""
        if staff_search:
            desc_clause = f" AND (LOWER(category) LIKE LOWER('%{staff_search.strip()}%') OR LOWER(description) LIKE LOWER('%{staff_search.strip()}%'))"

        query = f"""
            SELECT id AS "Expense ID", category AS "Category", 
                   amount AS "Amount (₦)", description AS "Description", timestamp AS "Timestamp" 
            FROM operating_expenses {date_condition} {desc_clause} ORDER BY timestamp DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            st.download_button(
                label="📥 Export Expense Logs (.csv)",
                data=df.to_csv(index=False).encode('utf-8'),
                file_name=f"expense_logs_{date.today()}.csv",
                mime="text/csv"
            )
        else:
            st.info("No matching operating expenses found.")

    elif log_type == "Stock Shipments / Intake":
        st.markdown("### 🚚 Stock Shipment & Landed Cost Logs")
        
        item_clause = ""
        if staff_search:
            item_clause = f" AND LOWER(item_name) LIKE LOWER('%{staff_search.strip()}%')"

        query = f"""
            SELECT id AS "Batch ID", sku AS "SKU", item_name AS "Item Name", 
                   quantity AS "Qty", base_cost_per_unit AS "Base Cost (₦)", 
                   total_additional_cost AS "Add. Costs (₦)", total_landed_cost AS "Total Landed (₦)", 
                   effective_unit_cost AS "True Unit Cost (₦)", timestamp AS "Timestamp" 
            FROM stock_shipments {date_condition} {item_clause} ORDER BY timestamp DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            st.download_button(
                label="📥 Export Shipment Logs (.csv)",
                data=df.to_csv(index=False).encode('utf-8'),
                file_name=f"shipment_logs_{date.today()}.csv",
                mime="text/csv"
            )
        else:
            st.info("No matching stock shipments found.")