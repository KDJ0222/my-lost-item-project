from contextlib import closing
import hashlib
import json
import sqlite3
from zipfile import ZipFile

import pytest

from scripts.data_backup import create_backup, restore_backup


def prepare_data(root, png):
    uploads = root / "uploads"
    uploads.mkdir(parents=True)
    filename = "a" * 32 + ".png"
    (uploads / filename).write_bytes(png)
    database = root / "database.db"
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, title TEXT, image_path TEXT, owner_token_hash TEXT)")
        connection.execute("INSERT INTO items VALUES (1, ?, ?, ?)", ("지갑", "/static/uploads/" + filename, "owner-hash"))
        connection.commit()
    return database, uploads, filename


def test_online_backup_and_restore_preserve_rows_images_and_owner(tmp_path, png):
    database, uploads, filename = prepare_data(tmp_path / "source", png)
    backup = create_backup(database, uploads, tmp_path / "backup.zip")
    target = restore_backup(backup, tmp_path / "restored")
    assert (target / "uploads" / filename).read_bytes() == png
    with closing(sqlite3.connect(target / "database.db")) as connection:
        assert connection.execute("SELECT title, owner_token_hash FROM items").fetchone() == ("지갑", "owner-hash")
    with ZipFile(backup) as archive:
        assert set(archive.namelist()) == {"manifest.json", "database.db", "uploads/" + filename}
        assert json.loads(archive.read("manifest.json"))["format_version"] == 1


def test_backup_and_restore_never_overwrite_existing_data(tmp_path, png):
    database, uploads, _ = prepare_data(tmp_path / "source", png)
    backup = create_backup(database, uploads, tmp_path / "backup.zip")
    original = backup.read_bytes()
    with pytest.raises(FileExistsError):
        create_backup(database, uploads, backup)
    assert backup.read_bytes() == original
    with pytest.raises(FileExistsError):
        restore_backup(backup, tmp_path / "source")


def test_missing_referenced_photo_aborts_backup(tmp_path, png):
    database, uploads, filename = prepare_data(tmp_path / "source", png)
    (uploads / filename).unlink()
    with pytest.raises(ValueError):
        create_backup(database, uploads, tmp_path / "broken.zip")
    assert not (tmp_path / "broken.zip").exists()


def test_restore_rejects_path_traversal(tmp_path):
    backup = tmp_path / "bad.zip"
    with ZipFile(backup, "w") as archive:
        archive.writestr("../escape.txt", "unexpected")
        archive.writestr("manifest.json", "{}")
    with pytest.raises(ValueError):
        restore_backup(backup, tmp_path / "restored")
    assert not (tmp_path / "escape.txt").exists()


def test_restore_rejects_tampered_contents_and_leaves_no_target(tmp_path):
    backup = tmp_path / "bad.zip"
    with ZipFile(backup, "w") as archive:
        archive.writestr("database.db", b"tampered")
        archive.writestr("manifest.json", json.dumps({"format_version":1, "files":{"database.db":hashlib.sha256(b"original").hexdigest()}}))
    with pytest.raises(ValueError, match="checksum"):
        restore_backup(backup, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()
