# tests/test_app.py

def test_home_page(client):
    # Test that the home page loads and shows expected content
    response = client.get('/')
    assert response.status_code == 200
    assert b"Welcome to Your Productivity Hub!" in response.data # From base.html or index.html
    assert b"Please login" in response.data # Assuming user is not logged in

def test_login_page_loads(client):
    # Test that the login page (which redirects to Google) loads
    response = client.get('/login', follow_redirects=False) # Test the redirect itself
    assert response.status_code == 302 # Expecting a redirect to Google
    assert b'google.com/o/oauth2/auth' in response.location.lower().encode()
