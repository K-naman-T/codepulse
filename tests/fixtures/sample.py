import os
from datetime import datetime


class BaseModel:
    def __init__(self, name: str):
        self.name = name


class UserModel(BaseModel):
    def get_full_name(self) -> str:
        return self.name.upper()

    def save(self) -> bool:
        return True


def calculate_total(items: list[float]) -> float:
    return sum(items)


def format_date(dt: datetime) -> str:
    return dt.isoformat()


def unused_helper():
    pass
