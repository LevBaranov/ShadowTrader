from dataclasses import dataclass
from typing import Any, Optional


@dataclass()
class Error(Exception):

    source: str  # TODO Enum
    source_data: Any
    data: Any
    description: Optional[str] = None
