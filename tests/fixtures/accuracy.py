"""Accuracy test fixture: Python — must contain exactly these symbols and calls."""

import os
from datetime import datetime
from os.path import join as path_join
from . import sibling_module


class User:
    """User model with authentication."""

    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email
        self._name = name

    def get_display_name(self) -> str:
        return self.name.upper()

    def save(self) -> bool:
        print("saving user")
        return True

    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        return cls(data['name'], data['email'])

    @staticmethod
    def validate_email(email: str) -> bool:
        return '@' in email

    @property
    def domain(self) -> str:
        return self._name.split('@')[1]


class AdminUser(User):
    """Admin with extra permissions."""

    def get_display_name(self) -> str:
        name = super().get_display_name()
        return f"{name} [ADMIN]"


def create_user(name: str, email: str) -> User:
    user = User(name, email)
    user.save()
    logger = get_logger()
    logger.log(f"Created user: {name}")
    return user


def send_welcome_email(user: User) -> None:
    display = user.get_display_name()
    send_email(user.email, f"Welcome {display}")


def format_date(dt: datetime) -> str:
    return dt.isoformat()


def get_logger():
    return Logger()


async def fetch_data(url: str) -> dict:
    result = await get(url)
    return result.json()


def outer_function():
    x = 10

    def inner_function():
        return x + 5

    return inner_function()


class Logger:
    def log(self, message: str) -> None:
        print(f"[LOG] {message}")
