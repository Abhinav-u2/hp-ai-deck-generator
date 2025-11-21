prompt = """
You are processing an HP product catalog page.

TASK:
Extract ALL product information visible in this page image and return a clean JSON array.

SUPPORTED PRODUCT TYPES:
- Notebook
- Laptop
- Desktop
- Workstation
- Thin Client
- Tablet
- Display / Monitor
- Retail System
- Accessories

REQUIREMENTS:
1. Extract every product mentioned on the page.
2. For EACH product, return the following JSON structure:

{
  "product_id": "",
  "product_name": "",
  "category": "",
  "description": "",
  "specs": {
      "ram": "",
      "cpu": "",
      "gpu": "",
      "storage": "",
      "display": "",
      "battery": "",
      "weight": "",
      "dimensions": "",
      "ports": "",
      "wireless": "",
      "os": ""
  }
}

RULES:
- If a value is missing or unreadable, set it to "N/A".
- DO NOT include price.
- DO NOT guess or infer missing specifications.
- DO NOT write explanations.
- DO NOT summarize.
- Output ONLY a valid JSON array.
- If multiple products appear on the page, extract ALL of them.
- Do not add fields outside the defined schema.

VISUAL INPUT MARKER:
<image>

Return only the JSON array.
"""