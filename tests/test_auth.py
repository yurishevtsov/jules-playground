from flask import session, url_for
from app.app import User, db # Assuming User, db can be imported

# (No specific registration test as it's tied to Google OAuth)

def test_logout(client, create_test_user, init_database): # Added init_database
    # Create and "log in" a user by manually setting session keys
    user = create_test_user()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True 
        # Flask-Login also sets '_id' for CSRF token if CSRFProtect is used,
        # but we've disabled WTF_CSRF_ENABLED in conftest.py for tests.
        # It might also set 'user_id' directly depending on version/config.
        # For basic Flask-Login, '_user_id' and '_fresh' are key.

    response = client.get(url_for('logout'), follow_redirects=True)
    assert response.status_code == 200
    # After logout, user is redirected to home page, which shows login link
    assert b"Please login" in response.data 
    assert b"You have been logged out." in response.data # Flash message

    with client.session_transaction() as sess:
        assert '_user_id' not in sess
        assert 'user_id' not in sess # Check common alternative too

def test_profile_access_unauthenticated(client, init_database): # Added init_database
    response = client.get(url_for('profile')) # follow_redirects=True by default for client.get
    # Unauthenticated users should be redirected to the login page.
    # The login page itself then redirects to Google.
    # So, the direct response to /profile might be a 302 to /login.
    # And /login is a 302 to Google.
    # For simplicity, let's check the final landing if we follow all.
    # However, our login page for now directly goes to google.authorize
    # Let's check the redirect to login_manager.login_view
    assert response.status_code == 302 # Redirect to login page
    assert response.location == url_for('login', _external=False)

    # Test the login page itself
    login_response = client.get(url_for('login'), follow_redirects=False)
    assert login_response.status_code == 302 # Redirect to Google
    assert 'google.com/o/oauth2/auth' in login_response.location.lower()


def test_profile_access_authenticated(client, create_test_user, init_database): # Added init_database
    user = create_test_user(email='auth_user@example.com', name='Auth User')
    # Simulate login by setting session
    with client.session_transaction() as sess:
        sess['user_id'] = str(user.id) # Flask-Login uses '_user_id'
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True
    
    response = client.get(url_for('profile'))
    assert response.status_code == 200
    assert b"My Profile" in response.data
    assert b"Auth User" in response.data # Check for user's name
    assert b"auth_user@example.com" in response.data

# Note: Testing the actual Google OAuth flow is complex and usually out of scope for unit tests.
# It would require mocking external services and handling redirects.
# The current tests focus on behavior *after* a user is considered authenticated.
# The `create_test_user` and manual session setup simulate this authenticated state.
