"""
Tests for authentication: staff login/logout and deprecated student redirects.
"""


def test_staff_login_success(client, admin_user):
    """Admin can login with correct credentials."""
    response = client.post('/login', data={
        'email': 'admin@test.com',
        'password': 'admin123',
        'remember': False
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Logged in successfully' in response.data or b'Dashboard' in response.data


def test_staff_login_failure(client, admin_user):
    """Login fails with wrong password."""
    response = client.post('/login', data={
        'email': 'admin@test.com',
        'password': 'wrongpassword',
        'remember': False
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Authentication failed' in response.data


def test_deprecated_student_routes_redirect(client):
    """Accessing deprecated student login/signup redirects to staff login."""
    response = client.get('/student/login')
    assert response.status_code == 302
    assert '/login' in response.location

    response_signup = client.get('/student/signup')
    assert response_signup.status_code == 302
    assert '/login' in response_signup.location


def test_protected_route_redirects(client):
    """Accessing protected route without login redirects to login."""
    response = client.get('/teacher/dashboard', follow_redirects=True)
    assert b'Please log in to access this page' in response.data


def test_logout(client, admin_user):
    """Logout clears session and redirects."""
    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    response = client.get('/logout', follow_redirects=True)
    assert b'Session ended' in response.data
