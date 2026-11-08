import streamlit as st
import pandas as pd
from datetime import datetime

def render(get_connection, user_info):
    st.subheader("Fast Checkout & Item Intake")
    
    if "cart" not in st.session_state:
        st.session_state.cart = {}  # Store as a dictionary keyed by SKU for easy quantity management

    if "last_receipt" not in st.session_state:
        st.session_state.last_receipt = None

    # Fetch product catalog for manual lookup/dropdown
    conn = get_connection()
    products_df = pd.read_sql_query("SELECT sku, name, cost_price, selling_price, stock FROM products WHERE stock > 0", conn)
    conn.close()

    col_scan, col_cart = st.columns([1.1, 1.2])
    
    with col_scan:
        st.markdown("#### 🔍 Item Selection")
        
        # Method 1: Barcode Scanner Input
        scanned_sku = st.text_input("1. Scan Barcode / Enter SKU", key="scanner_input", placeholder="Scan item code...")
        if scanned_sku:
            item_match = products_df[products_df["sku"].str.lower() == scanned_sku.strip().lower()]
            if not item_match.empty:
                row = item_match.iloc[0]
                sku = row["sku"]
                
                # Check stock limits and update quantity
                current_qty = st.session_state.cart.get(sku, {}).get("qty", 0)
                if current_qty < row["stock"]:
                    if sku in st.session_state.cart:
                        st.session_state.cart[sku]["qty"] += 1
                    else:
                        st.session_state.cart[sku] = {
                            "sku": sku,
                            "name": row["name"],
                            "cost": row["cost_price"],
                            "price": row["selling_price"],
                            "qty": 1,
                            "stock": row["stock"]
                        }
                    st.success(f"Added: {row['name']}")
                    st.rerun()
                else:
                    st.error("Cannot add more: Reached available stock limit!")
            else:
                st.error("Item not found or out of stock.")

        st.markdown("**— OR —**")

        # Method 2: Manual Search & Dropdown Selection
        if not products_df.empty:
            product_options = {
                f"{row['name']} ({row['sku']}) - ₦{row['selling_price']:,.2f} [Stock: {row['stock']}]": row
                for _, row in products_df.iterrows()
            }
            
            selected_display = st.selectbox(
                "2. Manual Search by Name or SKU",
                options=["-- Select Item from Catalog --"] + list(product_options.keys())
            )
            
            # Quantity picker for manual selection
            add_qty = st.number_input("Quantity to Add", min_value=1, value=1, step=1)
            
            if st.button("➕ Add Item(s) to Cart", use_container_width=True):
                if selected_display != "-- Select Item from Catalog --":
                    selected_item = product_options[selected_display]
                    sku = selected_item["sku"]
                    current_qty = st.session_state.cart.get(sku, {}).get("qty", 0)
                    
                    if current_qty + add_qty <= selected_item["stock"]:
                        if sku in st.session_state.cart:
                            st.session_state.cart[sku]["qty"] += add_qty
                        else:
                            st.session_state.cart[sku] = {
                                "sku": sku,
                                "name": selected_item["name"],
                                "cost": selected_item["cost_price"],
                                "price": selected_item["selling_price"],
                                "qty": add_qty,
                                "stock": selected_item["stock"]
                            }
                        st.success(f"Added {add_qty}x {selected_item['name']} to cart!")
                        st.rerun()
                    else:
                        st.error("Requested quantity exceeds available stock limit.")
                else:
                    st.warning("Please select a valid product from the list.")
        else:
            st.warning("No products available in stock.")

    with col_cart:
        st.markdown("#### 🛒 Current Cart & Quantity Control")
        
        if st.session_state.cart:
            tot_rev = 0
            tot_cost = 0
            
            # Display interactive rows for each cart item with +, -, and delete controls
            for sku, item in list(st.session_state.cart.items()):
                item_total = item["price"] * item["qty"]
                tot_rev += item_total
                tot_cost += item["cost"] * item["qty"]
                
                with st.container(border=True):
                    st.markdown(f"**{item['name']}**")
                    c_info, c_plus, c_minus, c_del = st.columns([2, 1, 1, 1])
                    
                    c_info.text(f"₦{item['price']:,.2f} × {item['qty']} = ₦{item_total:,.2f}")
                    
                    if c_plus.button("➕", key=f"plus_{sku}"):
                        if item["qty"] < item["stock"]:
                            st.session_state.cart[sku]["qty"] += 1
                            st.rerun()
                        else:
                            st.toast("Max stock reached!")
                            
                    if c_minus.button("➖", key=f"minus_{sku}"):
                        if item["qty"] > 1:
                            st.session_state.cart[sku]["qty"] -= 1
                            st.rerun()
                        else:
                            del st.session_state.cart[sku]
                            st.rerun()
                            
                    if c_del.button("🗑️", key=f"del_{sku}"):
                        del st.session_state.cart[sku]
                        st.rerun()

            st.markdown(f"### Total Amount: **₦{tot_rev:,.2f}**")
            
            col_cust, col_clear = st.columns([2, 1])
            with col_cust:
                cust_name = st.text_input("Customer Name", value="Walk-in")
            with col_clear:
                st.write("") 
                if st.button("🗑️ Clear All"):
                    st.session_state.cart = {}
                    st.rerun()

            if st.button("💳 Complete Sale & Print Receipt", type="primary", use_container_width=True):
                rec_id = f"REC-{datetime.now().strftime('%y%m%d%H%M%S')}"
                sale_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                conn = get_connection()
                cur = conn.cursor()
                
                cur.execute("""
                    INSERT INTO sales (receipt_no, client_name, total_revenue, total_cost, gross_profit, staff_name) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (rec_id, cust_name, tot_rev, tot_cost, tot_rev - tot_cost, user_info["username"]))

                receipt_items_text = ""
                for sku, item in st.session_state.cart.items():
                    cur.execute("""
                        INSERT INTO sale_items (receipt_no, sku, item_name, qty, unit_cost, unit_price) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (rec_id, sku, item["name"], item["qty"], item["cost"], item["price"]))
                    
                    cur.execute("UPDATE products SET stock = stock - %s WHERE sku = %s", (item["qty"], sku))
                    receipt_items_text += f"- {item['qty']}x {item['name']} @ ₦{item['price']:,.2f} = ₦{item['price']*item['qty']:,.2f}\n"

                conn.commit()
                cur.close()
                conn.close()

                st.session_state.last_receipt = {
                    "rec_id": rec_id,
                    "time": sale_time,
                    "customer": cust_name,
                    "staff": user_info["username"],
                    "items": receipt_items_text,
                    "total": tot_rev
                }

                st.session_state.cart = {}
                st.success(f"Transaction completed by {user_info['username']}. Receipt #{rec_id}")
                st.rerun()
        else:
            st.info("Cart is currently empty. Scan or search items to begin.")

    if st.session_state.last_receipt:
        rec = st.session_state.last_receipt
        st.markdown("---")
        st.success(f"🧾 **Receipt Ready for Last Transaction ({rec['rec_id']})**")
        
        receipt_formatted_text = f"""
========================================
           KIOSK RECEIPT          
========================================
Receipt No : {rec['rec_id']}
Date/Time  : {rec['time']}
Customer   : {rec['customer']}
Attendant  : {rec['staff']}
----------------------------------------
ITEMS PURCHASED:
{rec['items']}
----------------------------------------
TOTAL AMOUNT : ₦{rec['total']:,.2f}
========================================
     THANK YOU FOR YOUR PATRONAGE!     
========================================
"""
        st.code(receipt_formatted_text, language="text")
        st.download_button(
            label="📥 Download Receipt (.txt)",
            data=receipt_formatted_text,
            file_name=f"{rec['rec_id']}.txt",
            mime="text/plain"
        )
        
        if st.button("Dismiss Receipt View"):
            st.session_state.last_receipt = None
            st.rerun()