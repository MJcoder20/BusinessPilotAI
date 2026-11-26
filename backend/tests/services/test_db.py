from sqlalchemy import text


def test_database_connection(test_engine):
    with test_engine.connect() as connection:
        result = connection.execute(text("SELECT version()"))

        print("Test database connection successful!")
        print(result.scalar())