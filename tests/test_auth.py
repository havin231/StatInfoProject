"""
Tests for authentication: staff login/logout and student access codes.
"""
from app.models import Student


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


def test_student_login_success(client, sample_student):
    """Student can login with valid access code."""
    with client.session_transaction() as sess:
        sess.clear()
        
    response = client.post('/student/login', data={
        'access_code': 'ABC123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Welcome, Test Student' in response.data


def test_student_login_failure(client):
    """Student login fails with invalid access code."""
    response = client.post('/student/login', data={
        'access_code': 'INVALID123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Access Code provided is invalid' in response.data


def test_protected_route_redirects(client):
    """Accessing protected route without login redirects to login."""
    response = client.get('/teacher/dashboard', follow_redirects=True)
    assert b'Please log in to access this page' in response.data


def test_logout(client, admin_user):
    """Logout clears session and redirects."""
    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    response = client.get('/logout', follow_redirects=True)
    assert b'Session ended' in response.data
