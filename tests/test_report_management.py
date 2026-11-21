import pytest


OWNER = {'X-Owner-Token': 'a' * 64}
OTHER = {'X-Owner-Token': 'b' * 64}


def test_resolve_and_reopen_change_only_status(client, payload, png):
    image_path = client.post('/api/images', files={'file':('wallet.png', png, 'image/png')}).json()['image_path']
    saved = client.post('/api/items', headers=OWNER, json={
        **payload, 'image_path':image_path, 'event_date':'2026-11-16',
        'latitude':37.5, 'longitude':126.9, 'description':'원래 설명',
    }).json()
    path = f"/api/items/{saved['id']}/status"
    for status in ('resolved', 'open'):
        response = client.patch(path, headers=OWNER, json={'status':status})
        assert response.status_code == 200, response.text
        assert response.json() == {**saved, 'status':status}
        assert client.get(f"/api/items/{saved['id']}", headers=OWNER).json() == response.json()
        assert client.get(image_path).content == png


def test_status_update_retains_latest_content_edit(client, payload):
    saved = client.post('/api/items', headers=OWNER, json=payload).json()
    path = f"/api/items/{saved['id']}"
    updated = client.put(path, headers=OWNER, json={**payload, 'title':'변경된 제목', 'contact':'new@example.com'}).json()
    resolved = client.patch(path + '/status', headers=OWNER, json={'status':'resolved'})
    assert resolved.status_code == 200
    assert resolved.json() == {**updated, 'status':'resolved'}


def test_status_update_requires_owner(client, payload):
    saved = client.post('/api/items', headers=OWNER, json=payload).json()
    path = f"/api/items/{saved['id']}/status"
    assert client.patch(path, json={'status':'resolved'}).status_code == 403
    assert client.patch(path, headers=OTHER, json={'status':'resolved'}).status_code == 403
    assert client.get(f"/api/items/{saved['id']}").json()['status'] == 'open'
    legacy = client.post('/api/items', json=payload).json()
    assert client.patch(f"/api/items/{legacy['id']}/status", headers=OWNER, json={'status':'resolved'}).status_code == 403
    assert client.patch('/api/items/999999/status', headers=OWNER, json={'status':'resolved'}).status_code == 404


@pytest.mark.parametrize('data', [{}, {'status':'done'}, {'status':None}, {'status':'resolved', 'title':'unexpected'}])
def test_invalid_status_requests_do_not_modify_report(client, payload, data):
    saved = client.post('/api/items', headers=OWNER, json=payload).json()
    path = f"/api/items/{saved['id']}"
    assert client.patch(path + '/status', headers=OWNER, json=data).status_code == 422
    assert client.get(path, headers=OWNER).json() == saved


def test_status_filters_combine_with_search_building_type_and_owner(client, payload):
    first = client.post('/api/items', headers=OWNER, json=payload).json()
    client.post('/api/items', headers=OWNER, json={**payload, 'location':'학생회관', 'report_type':'lost'})
    client.post('/api/items', headers=OTHER, json={**payload, 'status':'resolved'})
    client.patch(f"/api/items/{first['id']}/status", headers=OWNER, json={'status':'resolved'})
    query = {'keyword':'가죽', 'location':'도서관', 'report_type':'found', 'status':'resolved', 'mine':True}
    result = client.get('/api/items', params=query, headers=OWNER)
    assert [item['id'] for item in result.json()] == [first['id']]
    assert client.get('/api/items', params={**query, 'status':'open'}, headers=OWNER).json() == []
    client.patch(f"/api/items/{first['id']}/status", headers=OWNER, json={'status':'open'})
    assert client.get('/api/items', params=query, headers=OWNER).json() == []


def test_status_patch_cors(client):
    response = client.options('/api/items/1/status', headers={
        'Origin':'http://localhost:5500', 'Access-Control-Request-Method':'PATCH',
        'Access-Control-Request-Headers':'X-Owner-Token,Content-Type',
    })
    assert response.status_code == 200
    assert 'PATCH' in response.headers['access-control-allow-methods']
