from sqlalchemy import select

from app.auth import hash_password
from app.database import SessionLocal
from app.models import User


ADMIN_USERNAME = "admin@vorxa.com"
ADMIN_PASSWORD = "admin123"


def main() -> int:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == ADMIN_USERNAME))
        if user is None:
            user = User(
                username=ADMIN_USERNAME,
                full_name="Vorxa Admin",
                role="admin",
                password_hash=hash_password(ADMIN_PASSWORD),
                is_active=True,
            )
            db.add(user)
            action = "created"
        else:
            user.full_name = "Vorxa Admin"
            user.role = "admin"
            user.password_hash = hash_password(ADMIN_PASSWORD)
            user.is_active = True
            action = "updated"

        db.commit()
        print(f"{action}: {ADMIN_USERNAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
