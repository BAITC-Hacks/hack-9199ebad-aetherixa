"""Historical Flask entry point.

The website now runs within app.main alongside the API, so the former
in-memory Flask state is deliberately not used.
"""

if __name__ == "__main__":
    print("Run from the Hackathon project root:")
    print("python -m uvicorn app.main:app --reload")
    print("Website: http://127.0.0.1:8000/")
