"""
Tests for public-facing routes.
"""


def test_homepage(client, sample_subject):
    """Homepage returns 200 and shows public subjects."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'Mathematics' in response.data


def test_keep_alive(client):
    """Keep-alive route returns active status."""
    response = client.get('/keep_alive')
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['status'] == 'alive'


def test_stats_page(client):
    """Public stats page returns 200."""
    response = client.get('/public/stats')
    assert response.status_code == 200
    assert b'Total Exams' in response.data
