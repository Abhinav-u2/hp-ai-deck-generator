from chromadb import PersistentClient

# Path must match what is in your agents
client = PersistentClient(path="backend/app/database/chroma")

try:
    collection = client.get_collection("product_specs")
    count = collection.count()
    print(f"📉 Current Document Count: {count}")
except Exception as e:
    print(f"❌ Collection not found: {e}")