import sqlite3

conn = sqlite3.connect("backend/app/database/products.db")
cur = conn.cursor()

product_name = "HP ProBook 450 G2"

cur.execute("SELECT * FROM product WHERE product_name = ?", (product_name,))
rows = cur.fetchall()

print(rows)
conn.close()
