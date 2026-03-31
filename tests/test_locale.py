def test_set_lang_guest(client):
    """Verify that a guest can toggle language via session."""
    with client.session_transaction() as sess:
        sess.clear()
    response = client.get('/set-lang/ku', follow_redirects=True)
    with client.session_transaction() as sess:
        assert sess.get('lang') == 'ku'

def test_set_lang_invalid(client):
    """Verify that an invalid lang code is rejected."""
    response = client.get('/set-lang/fr', follow_redirects=True)
    assert response.status_code == 200
    # Should flash a danger message and not set the lang in session
    with client.session_transaction() as sess:
        assert sess.get('lang') != 'fr'
