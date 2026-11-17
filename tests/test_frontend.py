from datetime import date

import pytest


TOKEN_A = 'a' * 64
TOKEN_B = 'b' * 64


def test_home_serves_supplied_design_and_local_assets(client):
    response = client.get('/')
    assert response.status_code == 200
    assert '캠퍼스 찾음' in response.text
    for asset in ('css/site.css', 'css/integration.css', 'js/app.js',
                  'vendor/react.production.min.js', 'vendor/react-dom.production.min.js'):
        assert client.get('/assets/' + asset).status_code == 200
    assert 'esm.sh' not in response.text


def test_browser_identity_and_event_date_round_trip(client, payload):
    headers = {'X-Owner-Token': TOKEN_A}
    response = client.post('/api/items', headers=headers, json={**payload, 'event_date':'2026-10-01'})
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved['event_date'] == '2026-10-01'
    assert saved['is_mine'] is True
    assert 'owner_token_hash' not in saved
    assert TOKEN_A not in response.text
    assert client.get('/api/items', headers=headers).json()[0]['is_mine'] is True
    assert client.get('/api/items').json()[0]['is_mine'] is False
    assert client.get(f"/api/items/{saved['id']}", headers=headers).json()['is_mine'] is True
    with client.app.state.session_factory() as db:
        from models import Item
        item = db.get(Item, saved['id'])
        assert item.owner_token_hash != TOKEN_A
        assert len(item.owner_token_hash) == 64
        assert item.event_date == date(2026, 10, 1)


def test_my_items_are_not_based_on_display_name(client, payload):
    own = client.post('/api/items', headers={'X-Owner-Token':TOKEN_A}, json=payload).json()
    client.post('/api/items', headers={'X-Owner-Token':TOKEN_B}, json=payload)
    client.post('/api/items', json=payload)
    assert client.get('/api/items', params={'mine':True}).status_code == 401
    response = client.get('/api/items', params={'mine':True}, headers={'X-Owner-Token':TOKEN_A})
    assert [item['id'] for item in response.json()] == [own['id']]


def test_delete_requires_matching_browser_and_removes_record(client, payload):
    item = client.post('/api/items', headers={'X-Owner-Token':TOKEN_A}, json=payload).json()
    path = f"/api/items/{item['id']}"
    assert client.delete(path).status_code == 403
    assert client.delete(path, headers={'X-Owner-Token':TOKEN_B}).status_code == 403
    assert client.get(path).status_code == 200
    assert client.delete(path, headers={'X-Owner-Token':TOKEN_A}).status_code == 204
    assert client.get(path).status_code == 404
    assert client.get('/api/items').json() == []
    assert client.delete(path, headers={'X-Owner-Token':TOKEN_A}).status_code == 404


def test_protected_update_cannot_be_spoofed_with_author(client, payload):
    item = client.post('/api/items', headers={'X-Owner-Token':TOKEN_A}, json=payload).json()
    path = f"/api/items/{item['id']}"
    assert client.put(path, json=payload).status_code == 403
    assert client.put(path, headers={'X-Owner-Token':TOKEN_B}, json=payload).status_code == 403
    updated = client.put(path, headers={'X-Owner-Token':TOKEN_A}, json={**payload, 'status':'resolved'})
    assert updated.status_code == 200
    assert updated.json()['status'] == 'resolved'


def test_legacy_items_are_visible_but_cannot_be_claimed_for_deletion(client, payload):
    item = client.post('/api/items', json=payload).json()
    assert client.get('/api/items', params={'mine':True}, headers={'X-Owner-Token':TOKEN_A}).json() == []
    assert client.delete(f"/api/items/{item['id']}", headers={'X-Owner-Token':TOKEN_A}).status_code == 403


@pytest.mark.parametrize('event_date', ['not-a-date', '2026-13-02'])
def test_invalid_event_date(client, payload, event_date):
    assert client.post('/api/items', json={**payload, 'event_date':event_date}).status_code == 422


def test_cors_supports_browser_identity_and_delete(client):
    response = client.options('/api/items/1', headers={
        'Origin':'http://localhost:5500', 'Access-Control-Request-Method':'DELETE',
        'Access-Control-Request-Headers':'X-Owner-Token',
    })
    assert response.status_code == 200
    assert 'DELETE' in response.headers['access-control-allow-methods']
