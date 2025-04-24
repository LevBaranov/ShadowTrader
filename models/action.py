from dataclasses import dataclass

from models.share import Share


@dataclass()
class Action:

    type: str  # TODO Enum
    quantity: int
    share: Share
