import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
key = os.environ.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY")

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

print("Testing direct REST API to Supabase...")

try:
    # 1. Test Read Access
    res = requests.get(f"{url}/rest/v1/users?select=*", headers=headers)
    print("GET /users status:", res.status_code)
    print("GET /users response:", res.text[:200])

    if res.status_code == 200 and len(res.json()) == 0:
        print("\nWARNING: The list is empty. If you just inserted a user and it is empty, Row Level Security (RLS) is likely enabled and blocking reads/writes for anonymous keys.")

except Exception as e:
    import traceback
    print("Error:")
    print(traceback.format_exc())
