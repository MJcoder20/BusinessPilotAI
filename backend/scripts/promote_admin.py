
import argparse
import sys

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import User


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Promote an existing BusinessPilot AI user to administrator."
    )

    parser.add_argument(
        "--email",
        required=True,
        help="Email address of the existing account.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm the administrator promotion.",
    )
    parser.add_argument(
        "--confirm-production",
        action="store_true",
        help="Explicitly authorize changes to a production database.",
    )

    args = parser.parse_args()
    email = args.email.strip().lower()

    print("\nBusinessPilot AI — Administrator Provisioning")
    print("----------------------------------------------")
    print(f"Environment: {settings.app_env}")
    print(f"Database host: {settings.db_host}")
    print(f"Database name: {settings.db_name}")
    print(f"Target email: {email}")

    if not args.confirm:
        print("\nAborted: pass --confirm to authorize this operation.")
        sys.exit(1)

    if (
        settings.app_env == "production"
        and not args.confirm_production
    ):
        print(
            "\nAborted: production promotion also requires "
            "--confirm-production."
        )
        sys.exit(1)

    confirmation = input(
        f"\nType '{email}' to confirm administrator promotion: "
    ).strip().lower()

    if confirmation != email:
        print("Confirmation mismatch. No changes were made.")
        sys.exit(1)

    db: Session = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.email == email)
            .with_for_update()
            .first()
        )

        if user is None:
            print("\nError: no account exists with that email.")
            sys.exit(1)

        if user.role == "admin":
            print("\nThis account is already an administrator.")
            return

        user.role = "admin"
        db.commit()

        print(
            f"\nSuccessfully promoted {user.email} "
            "to administrator."
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
