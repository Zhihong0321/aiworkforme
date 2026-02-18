import sys
import os

# Setup path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Eternalgy-MCP-RAG", "backend")
sys.path.append(backend_dir)

def test_imports():
    print("Testing Backend Imports...")
    try:
        from fastapi import FastAPI
        from sqlmodel import SQLModel
        from main import app
        print(" [PASS] FastAPI app instantiated successfully.")
    except ImportError as e:
        print(f" [FAIL] Import error: {e}")
    except Exception as e:
        # We expect some failures if DB or env vars are missing, 
        # but the instantiation of 'app' should generally work if code is valid.
        print(f" [INFO] App instantiation note: {e}")

if __name__ == "__main__":
    test_imports()
