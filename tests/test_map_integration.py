OWNER = {"X-Owner-Token": "a" * 64}


def test_report_coordinates_create_move_and_remove(client, payload):
    created = client.post('/api/items', headers=OWNER, json={
        **payload, 'latitude':37.4966, 'longitude':126.9544,
    })
    assert created.status_code == 201
    path = f"/api/items/{created.json()['id']}"
    assert client.get(path).json()['latitude'] == 37.4966
    for latitude, longitude in [(0, 0), (37.497, 126.955), (None, None)]:
        response = client.put(path, headers=OWNER, json={
            **payload, 'latitude':latitude, 'longitude':longitude,
        })
        assert response.status_code == 200
        stored = client.get(path, headers=OWNER).json()
        assert (stored['latitude'], stored['longitude']) == (latitude, longitude)
        assert stored['location'] == payload['location']


def test_map_assets_are_served_locally(client):
    home = client.get('/').text
    assert '/assets/js/campus-map.js' in home
    for name in ('leaflet.js', 'leaflet.css', 'LICENSE', 'images/marker-icon.png',
                 'images/marker-icon-2x.png', 'images/marker-shadow.png'):
        response = client.get('/assets/vendor/leaflet/' + name)
        assert response.status_code == 200
        assert response.content
    assert client.get('/assets/js/campus-map.js').status_code == 200
