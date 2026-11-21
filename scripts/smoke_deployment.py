"""Check an isolated production deployment and verify persistence across restart.

Set APP_ACCESS_USERNAME / APP_ACCESS_PASSWORD in the environment.
First run --save-state, restart the server/container, then run --verify-state.
"""

import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import struct
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import zlib


def sample_png():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\x00\x14\x5f\x4c")) + chunk(b"IEND", b"")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--save-state", type=Path)
    modes.add_argument("--verify-state", type=Path)
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    parsed = urlparse(args.url)
    if parsed.username or parsed.password or parsed.scheme not in ("http", "https"):
        parser.error("Use a service URL without credentials.")
    if parsed.scheme != "https" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        parser.error("Remote checks require HTTPS.")
    password = os.getenv("APP_ACCESS_PASSWORD", "")
    if not password:
        parser.error("APP_ACCESS_PASSWORD must be set in the environment.")
    user = os.getenv("APP_ACCESS_USERNAME", "campus")
    origin = args.url.rstrip("/")
    value = base64.b64encode((user + ":" + password).encode()).decode()

    def request(path, *, method="GET", data=None, content_type=None, owner=None):
        headers = {"Authorization":"Basic " + value}
        if content_type:
            headers["Content-Type"] = content_type
        if owner:
            headers["X-Owner-Token"] = owner
        with urlopen(Request(origin + path, data=data, method=method, headers=headers), timeout=15) as response:
            return response.read()

    assert json.loads(urlopen(origin + "/api/health", timeout=15).read()) == {"status":"ok"}
    try:
        urlopen(origin + "/", timeout=15)
        raise AssertionError("Unauthenticated access was allowed.")
    except HTTPError as error:
        assert error.code == 401
    assert b"/assets/js/app.js" in request("/")
    assert b"function App" in request("/assets/js/app.js")
    assert b"CampusMap" in request("/assets/js/campus-map.js")
    assert b"Leaflet" in request("/assets/vendor/leaflet/leaflet.js")
    assert b"leaflet-container" in request("/assets/vendor/leaflet/leaflet.css")
    assert request("/assets/vendor/leaflet/images/marker-icon.png").startswith(b"\x89PNG")
    if args.save_state:
        if args.save_state.exists():
            parser.error("Choose a new state filename.")
        owner = secrets.token_hex(32)
        boundary = secrets.token_hex(16)
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"check.png\"\r\nContent-Type: image/png\r\n\r\n".encode()
                + sample_png() + f"\r\n--{boundary}--\r\n".encode())
        upload = json.loads(request("/api/images", method="POST", data=body, content_type="multipart/form-data; boundary=" + boundary))
        payload = {"title":"deployment-check-" + secrets.token_hex(8), "category":"검증용",
                   "location":"학생회관 시연용", "author":"배포 검증", "contact":"check@example.com",
                   "keywords":["deployment-check"], "image_path":upload["image_path"],
                   "latitude":37.4966, "longitude":126.9544}
        item = json.loads(request("/api/items", method="POST", data=json.dumps(payload).encode(), content_type="application/json", owner=owner))
        state = {"id":item["id"], "title":item["title"], "image_path":item["image_path"], "owner":owner,
                 "latitude":item["latitude"], "longitude":item["longitude"]}
        args.save_state.parent.mkdir(parents=True, exist_ok=True)
        with args.save_state.open("x", encoding="utf-8") as output:
            json.dump(state, output)
        print("Health, access protection, frontend, image upload and report creation passed.")
    else:
        state = json.loads(args.verify_state.read_text(encoding="utf-8"))
        item = json.loads(request(f"/api/items/{state['id']}", owner=state["owner"]))
        assert item["title"] == state["title"] and item["title"].startswith("deployment-check-")
        assert item["image_path"] == state["image_path"] and item["is_mine"] is True
        assert item["latitude"] == state["latitude"] and item["longitude"] == state["longitude"]
        assert request(item["image_path"]) == sample_png()
        if args.cleanup:
            request(f"/api/items/{state['id']}", method="DELETE", owner=state["owner"])
        print("Restart persistence of report, photo and owner identity passed.")


if __name__ == "__main__":
    main()
