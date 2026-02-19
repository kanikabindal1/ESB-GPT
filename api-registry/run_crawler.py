#!/usr/bin/env python3
"""
Convenience script to run the API metadata crawler.
Usage:
  python run_crawler.py <source> [-o output.json] [--fastapi] [--base-url URL]
Examples:
  python run_crawler.py http://localhost:8000/openapi.json -o crawled-apis.json
  python run_crawler.py ../airtel-africa-mock-apis --fastapi -o crawled-apis.json
"""
import sys
from pathlib import Path

# Ensure crawler is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from crawler.openapi_to_registry import main

if __name__ == "__main__":
    main()
