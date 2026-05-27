"""Accuracy test fixture: Python — must contain exactly these symbols and calls."""

import os
from datetime import datetime


class User:
    """User model with authentication."""

    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email

    def get_display_name(self) -> str:
        return self.name.upper()

    def save(self) -> bool:
        print("saving user")
        return True


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


# Expected: 3 classes (User, AdminUser, Logger), 7 functions/methods
# Expected call edges: 
#   create_user → User.__init__ (via User(name, email))
#   create_user → user.save
#   create_user → get_logger
#   create_user → logger.log
#   AdminUser.get_display_name → User.get_display_name (via super())
#   send_welcome_email → user.get_display_name
#   send_welcome_email → send_email


class Logger:
    def log(self, message: str) -> None:
        print(f"[LOG] {message}")
