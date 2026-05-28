class User:
    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email

    def save(self) -> bool:
        return True

    def validate(self) -> bool:
        return '@' in self.email


class AdminUser(User):
    def __init__(self, name: str, email: str, role: str):
        super().__init__(name, email)
        self.role = role

    def save(self) -> bool:
        return True

    def validate(self) -> bool:
        return '@' in self.email and self.role in ('admin', 'superadmin')


def validate(data: str) -> bool:
    return bool(data.strip())
