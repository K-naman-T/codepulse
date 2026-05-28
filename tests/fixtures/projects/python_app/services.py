class Logger:
    def log(self, message: str) -> None:
        print(f"[LOG] {message}")


def create_user(name: str, email: str) -> dict:
    return {"name": name, "email": email}


def send_email(to: str, subject: str) -> bool:
    print(f"Sending email to {to}")
    return True


def validate(data: str) -> bool:
    """Same name as models.py:User.validate — cross-file duplicate."""
    return len(data) > 0


def get_logger(name: str = "app") -> Logger:
    return Logger()
