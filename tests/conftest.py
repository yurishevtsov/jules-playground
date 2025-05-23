import pytest
from app.app import app as flask_app, db, User # Make sure to import your app and db, User model

@pytest.fixture(scope='session')
def app():
    # Setup for the Flask app for testing
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", # Use in-memory SQLite for tests
        "LOGIN_DISABLED": False, # Ensure login is not disabled unless specifically testing that
        "WTF_CSRF_ENABLED": False, # Disable CSRF for simpler form testing, if you use Flask-WTF
        "SECRET_KEY": "test_secret_key", # Consistent secret key for tests
        "GOOGLE_CLIENT_ID": "TEST_GOOGLE_CLIENT_ID", # Test placeholder
        "GOOGLE_CLIENT_SECRET": "TEST_GOOGLE_CLIENT_SECRET" # Test placeholder
    })
    
    # Any other test-specific configurations
    # For example, if you have Google OAuth settings, you might want to mock them or use test values

    with flask_app.app_context():
        db.create_all() # Create all tables

    yield flask_app

    # Teardown: drop all tables after tests run (if using a session-scoped app fixture and db)
    # This might be better handled per-test if tests modify db state significantly
    # For now, creating tables once is fine.
    # with flask_app.app_context():
    #     db.drop_all()


@pytest.fixture()
def client(app):
    # Test client fixture
    return app.test_client()

@pytest.fixture(scope='function') # function scope for db to ensure clean db for each test
def init_database(app):
    # Fixture to create and drop database for each test function
    with app.app_context():
        db.create_all()
        yield db # provide the db object to tests
        db.session.remove()
        db.drop_all()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def create_test_user(init_database): # Depends on init_database to ensure db is clean
    def _create_test_user(email='test@example.com', name='Test User'):
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email, name=name)
            db.session.add(user)
            db.session.commit()
        return user
    return _create_test_user

# The auth_client fixture as originally proposed is less ideal than
# having tests explicitly log in a user.
# The `create_test_user` along with manual session setting in tests
# (as shown in test_auth.py) is a more direct approach for now.
# So, no auth_client fixture here, tests will use `create_test_user`
# and then simulate login if needed by setting session variables.
