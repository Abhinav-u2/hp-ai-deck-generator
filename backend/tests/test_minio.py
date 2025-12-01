# Create a temporary check script
import sqlite3
conn = sqlite3.connect(r'C:\Users\kaustubh.bhor\Music\code\hp-ai-deck-generator\backend\app\database\products.db')
cursor = conn.cursor()
cursor.execute('SELECT product_name, cloud_url FROM products WHERE cloud_url IS NOT NULL LIMIT 5')
rows = cursor.fetchall()
print('\n--- Database Check ---')
for row in rows:
    print(f'Product: {row[0]}')
    print(f'URL:     {row[1]}\n')
conn.close()


