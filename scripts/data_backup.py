"""Back up SQLite and referenced uploads; restore only into a new directory.

python -m scripts.data_backup backup --output backups/campus.zip
python -m scripts.data_backup restore backups/campus.zip --target data-restored
"""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import stat
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED


IMAGE_REFERENCE = re.compile(r"/static/uploads/([0-9a-f]{32}\.(?:jpg|png|webp))")
ARCHIVE_IMAGE = re.compile(r"uploads/[0-9a-f]{32}\.(?:jpg|png|webp)")
MAX_RESTORE_BYTES = 2 * 1024 * 1024 * 1024


def checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def create_backup(database: Path, uploads: Path, output: Path):
    database, uploads, output = database.resolve(), uploads.resolve(), output.resolve()
    if not database.is_file():
        raise FileNotFoundError("Database does not exist; no empty backup was created.")
    if output.exists():
        raise FileExistsError("Choose a new backup filename; existing backups are never overwritten.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="campus-backup-") as directory:
        snapshot = Path(directory) / "database.db"
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source:
            with closing(sqlite3.connect(snapshot)) as target:
                source.backup(target)
        with closing(sqlite3.connect(snapshot)) as connection:
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Database integrity check failed.")
            references = connection.execute("SELECT image_path FROM items WHERE image_path IS NOT NULL").fetchall()
        files = {"database.db":snapshot}
        for (reference,) in references:
            match = IMAGE_REFERENCE.fullmatch(reference)
            if not match:
                raise ValueError("Database contains an unsupported image reference.")
            path = uploads / match.group(1)
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(uploads):
                raise ValueError("A referenced upload is missing or unsafe; backup aborted.")
            files["uploads/" + path.name] = path
        manifest = {"format_version":1, "created_at":datetime.now(timezone.utc).isoformat(),
                    "files":{name:checksum(path) for name, path in files.items()}}
        archive = ZipFile(output, "x", compression=ZIP_DEFLATED)
        try:
            with archive:
                for name, path in files.items():
                    archive.write(path, name)
                archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        except Exception:
            output.unlink(missing_ok=True)
            raise
    return output


def restore_backup(backup: Path, target: Path):
    target = target.resolve()
    if target.exists():
        raise FileExistsError("Restore target must be a new directory; existing data is never overwritten.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(backup) as archive:
        members = archive.infolist()
        names = [member.filename for member in members]
        if len(names) != len(set(names)) or "manifest.json" not in names:
            raise ValueError("Invalid or duplicate archive members.")
        if sum(member.file_size for member in members) > MAX_RESTORE_BYTES:
            raise ValueError("Backup exceeds the 2 GiB restore limit.")
        for member in members:
            if member.filename not in ("database.db", "manifest.json") and not ARCHIVE_IMAGE.fullmatch(member.filename):
                raise ValueError("Unsafe backup path.")
            if stat.S_ISLNK(member.external_attr >> 16) or member.is_dir():
                raise ValueError("Backup contains an unsupported entry.")
        manifest = json.loads(archive.read("manifest.json"))
        expected = manifest.get("files", {})
        if not isinstance(expected, dict) or manifest.get("format_version") != 1 or "database.db" not in expected or set(expected) != set(names) - {"manifest.json"}:
            raise ValueError("Invalid backup manifest.")
        if any(not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest) for digest in expected.values()):
            raise ValueError("Invalid backup checksums.")
        # Both staging and destination stay under the explicitly selected parent.
        with TemporaryDirectory(prefix=".campus-restore-", dir=target.parent) as directory:
            staging = Path(directory).resolve()
            if staging.parent != target.parent:
                raise ValueError("Unexpected restore staging directory.")
            for name, digest in expected.items():
                destination = staging / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as source, destination.open("xb") as output:
                    shutil.copyfileobj(source, output)
                if checksum(destination) != digest:
                    raise ValueError("Backup checksum mismatch.")
            with closing(sqlite3.connect(staging / "database.db")) as connection:
                if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise ValueError("Restored database integrity check failed.")
            (staging / "uploads").mkdir(exist_ok=True)
            if target.exists():
                raise FileExistsError("Restore target was created by another process.")
            staging.rename(target)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup")
    backup.add_argument("--output", type=Path, required=True)
    restore = commands.add_parser("restore")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "backup":
        from config import get_settings
        from sqlalchemy.engine import make_url
        settings = get_settings()
        url = make_url(settings.database_url)
        if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
            parser.error("Backup requires a file-backed SQLite database.")
        result = create_backup(Path(url.database), settings.upload_dir, args.output)
    else:
        result = restore_backup(args.archive, args.target)
    print(f"Completed: {result}")


if __name__ == "__main__":
    main()
