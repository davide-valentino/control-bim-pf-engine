"""CAD Tests - DXF to BIM & BOM Pipeline Package"""
from pathlib import Path
from dotenv import load_dotenv

# Automatically load environment variables from .env.local or .env if present
_root_dir = Path(__file__).resolve().parent.parent
if (_root_dir / ".env.local").is_file():
    load_dotenv(_root_dir / ".env.local")
if (_root_dir / ".env").is_file():
    load_dotenv(_root_dir / ".env")

