import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta

def render(get_connection):
    st.subheader("Financial Overview & Net P&L")
    
    # Date Range Filter Controls
    col_filter_type, col_start, col_end = st.columns([1.5, 1, 1])
    
    with col_filter_type:
        filter_option = st.selectbox(
            "📅 Date Range Filter Mode", 
            ["All Time", "Today", "This Week", "This Month", "Custom Date Range"]
        )
    
    today_date = date.today()
    start_date = today_date
    end_date = today_date

    if filter_option == "Custom Date Range":
        with col_start:
            start_date = st.date_input("Start Date", value=today_date.replace(day=1))
        with col_end:
            end_date = st.date_input("End Date", value=today_date)
    
    # Build SQL condition
    date_condition = ""
    if filter_option == "Today":
        date_condition = f"WHERE timestamp >= '{today_date} 00:00:00' AND timestamp <= '{today_date} 23:59:59'"
    elif filter_option == "This Week":
        start_of_week = today_date - timedelta(days=today_date.weekday())
        date_condition = f"WHERE timestamp >= '{start_of_week} 00:00:00'"
    elif filter_option == "This Month":
        start_of_month = today_date.replace(day=1)
        date_condition = f"WHERE timestamp >= '{start_of_month} 00:00:00'"
    elif filter_option == "Custom Date Range":
        date_condition = f"WHERE timestamp >= '{start_date} 00:00:00' AND timestamp <= '{end_date} 23:59:59'"
    else:
        date_condition = ""

    conn = get_connection()
    
    sales_query = f"SELECT total_revenue, total_cost, gross_profit, staff_name, timestamp FROM sales {date_condition}"
    exp_query = f"SELECT amount, timestamp FROM operating_expenses {date_condition}"
    
    sales_df = pd.read_sql_query(sales_query, conn)
    exp_df = pd.read_sql_query(exp_query, conn)
    conn.close()
    
    rev = sales_df["total_revenue"].sum() if not sales_df.empty else 0
    cogs = sales_df["total_cost"].sum() if not sales_df.empty else 0
    gross = sales_df["gross_profit"].sum() if not sales_df.empty else 0
    opex = exp_df["amount"].sum() if not exp_df.empty else 0
    net = gross - opex

    # Executive Metrics Display
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Sales", f"₦{rev:,.2f}")
    m2.metric("Gross Profit", f"₦{gross:,.2f}")
    m3.metric("Operating Expenses", f"₦{opex:,.2f}")
    m4.metric("True Net Profit", f"₦{net:,.2f}")

    st.markdown("---")
    st.markdown("### 📈 Monthly Revenue vs. Operating Expenses Trend")

    # --- MONTHLY AGGREGATION & CHART LOGIC ---
    if not sales_df.empty or not exp_df.empty:
        # Prepare Sales by Month
        if not sales_df.empty:
            sales_df["timestamp"] = pd.to_datetime(sales_df["timestamp"])
            sales_monthly = sales_df.groupby(sales_df["timestamp"].dt.to_period("M"))["total_revenue"].sum().reset_index()
            sales_monthly["Month"] = sales_monthly["timestamp"].astype(str)
            sales_monthly = sales_monthly.rename(columns={"total_revenue": "Sales Revenue (₦)"})
            sales_monthly = sales_monthly[["Month", "Sales Revenue (₦)"]]
        else:
            sales_monthly = pd.DataFrame(columns=["Month", "Sales Revenue (₦)"])

        # Prepare Expenses by Month
        if not exp_df.empty:
            exp_df["timestamp"] = pd.to_datetime(exp_df["timestamp"])
            exp_monthly = exp_df.groupby(exp_df["timestamp"].dt.to_period("M"))["amount"].sum().reset_index()
            exp_monthly["Month"] = exp_monthly["timestamp"].astype(str)
            exp_monthly = exp_monthly.rename(columns={"amount": "Operating Expenses (₦)"})
            exp_monthly = exp_monthly[["Month", "Operating Expenses (₦)"]]
        else:
            exp_monthly = pd.DataFrame(columns=["Month", "Operating Expenses (₦)"])

        # Merge both datasets by Month
        if not sales_monthly.empty and not exp_monthly.empty:
            chart_data = pd.merge(sales_monthly, exp_monthly, on="Month", how="outer").fillna(0)
        elif not sales_monthly.empty:
            chart_data = sales_monthly
            chart_data["Operating Expenses (₦)"] = 0
        else:
            chart_data = exp_monthly
            chart_data["Sales Revenue (₦)"] = 0

        chart_data = chart_data.sort_values("Month").set_index("Month")

        # Display toggle for chart type
        chart_type = st.radio("Select Chart View", ["Bar Chart", "Line Chart"], horizontal=True)
        
        if chart_type == "Bar Chart":
            st.bar_chart(chart_data)
        else:
            st.line_chart(chart_data)
    else:
        st.info("No financial data available to generate trends for the selected period.")

    st.markdown("---")
    st.markdown("### 👩‍💼 Employee Sales Performance Tracking (Selected Range)")
    if not sales_df.empty and "staff_name" in sales_df.columns:
        staff_perf = sales_df.groupby("staff_name").agg(
            total_transactions=("total_revenue", "count"),
            total_revenue_generated=("total_revenue", "sum"),
            total_gross_profit_generated=("gross_profit", "sum")
        ).reset_index().rename(columns={
            "staff_name": "Staff Name",
            "total_transactions": "Transactions Count",
            "total_revenue_generated": "Revenue Generated (₦)",
            "total_gross_profit_generated": "Gross Profit Generated (₦)"
        })
        st.dataframe(staff_perf, use_container_width=True)
    else:
        st.info("No sales transactions recorded for this selected date range.")