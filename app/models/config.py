from pydantic import BaseModel
from typing import Any, Optional

class APIResponse(BaseModel):
    code: int = 0
    data: Optional[Any] = None
    msg: str = ""
    
    class Config:
        json_encoders = {
            # Add custom encoders if needed
        }