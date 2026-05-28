from .models import User, AdminUser
from .services import create_user as create_user_alias
from .services import send_email as notify
from .services import get_logger


def run():
    user = User("Alice", "alice@example.com")
    user.save()
    if user.validate():
        admin = AdminUser("Bob", "bob@example.com", "admin")
        admin.save()
        u = create_user_alias("Charlie", "charlie@example.com")
        notify("bob@example.com", "Welcome!")
    logger = get_logger("main")
    logger.log("run complete")
