"""
Tests for authentication: staff login/logout and access control.
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


def test_removed_student_routes_return_404(client):
    """Removed student routes are completely gone (404)."""
    assert client.get('/student/login').status_code == 404
    assert client.get('/student/signup').status_code == 404
    assert client.get('/student/dashboard').status_code == 404


def test_test_lang_requires_admin(client, teacher_user, admin_user):
    """Debug /test-lang route requires admin authentication."""
    # Unauthenticated -> redirect to login
    assert client.get('/test-lang').status_code == 302

    # Non-admin teacher -> 403 Forbidden
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'teacher123'})
    assert client.get('/test-lang').status_code == 403
    client.get('/logout')

    # Admin -> 200 OK
    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    assert client.get('/test-lang').status_code == 200


def test_protected_route_redirects(client):
    """Accessing protected route without login redirects to login."""
    response = client.get('/teacher/dashboard', follow_redirects=True)
    assert b'Please log in to access this page' in response.data


def test_logout(client, admin_user):
    """Logout clears session and redirects."""
    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    response = client.get('/logout', follow_redirects=True)
    assert b'Session ended' in response.data
