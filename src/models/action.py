from dataclasses import dataclass

from src.models.share import Share


@dataclass()
class Action:

    type: str  # TODO Enum
    quantity: int
    share: Share
