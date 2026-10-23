from sqlalchemy import text

from .database import engine


def main():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        value = result.scalar_one()

    print(f"DATABASE CONNECTION: PASS (SELECT 1 -> {value})")


if __name__ == "__main__":
    main()