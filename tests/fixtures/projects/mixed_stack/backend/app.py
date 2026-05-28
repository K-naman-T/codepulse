from .models import BaseModel


class UserModel(BaseModel):
    def get_name(self) -> str:
        return self.name


def create_user(name: str) -> UserModel:
    return UserModel(name)
