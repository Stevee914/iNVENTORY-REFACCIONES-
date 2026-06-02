import json
import os
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/config", tags=["config"])

_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "business_config.json"
)


@router.get("/business")
def get_business_config():
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="business_config.json not found")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid config JSON: {e}")
