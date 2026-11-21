"""Exercise production startup, persistence and backup/restore with disposable data.

This uses only the standard library and the project's runtime requirements.
No real Gemini request or project database is used.
"""

import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.error import URLError
from urllib.request import urlopen


def main():
    project = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix="campus-runtime-check-") as directory:
        root = Path(directory)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        env = os.environ.copy()
        for name in ("DATABASE_URL", "UPLOAD_DIR"):
            env.pop(name, None)
        env.update(APP_ENV="production", DATA_DIR=str(root / "data"), PORT=str(port),
                   GEMINI_API_KEY="runtime-check-placeholder-key", APP_ACCESS_USERNAME="campus",
                   APP_ACCESS_PASSWORD=secrets.token_urlsafe(24), ALLOWED_HOSTS="127.0.0.1,localhost",
                   CORS_ORIGINS="", ENABLE_API_DOCS="false", PYTHONUTF8="1")
        url = f"http://127.0.0.1:{port}"
        process = None
        log = (root / "server.log").open("w+", encoding="utf-8")

        def start():
            nonlocal process
            process = subprocess.Popen([sys.executable, "-m", "scripts.start_server"], cwd=project,
                                       env=env, stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    break
                try:
                    with urlopen(url + "/api/health", timeout=1) as response:
                        if response.status == 200:
                            return
                except (URLError, TimeoutError, ConnectionError):
                    pass
                time.sleep(0.1)
            log.flush(); log.seek(0)
            raise RuntimeError("Production test server did not become ready.\n" + log.read())

        def stop():
            nonlocal process
            if process is not None:
                if process.poll() is None:
                    if os.name == "nt":
                        # Windows venv python.exe can launch a child interpreter.
                        # Stop the owned process tree, not just the venv launcher.
                        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                       capture_output=True, timeout=10)
                    else:
                        process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=5)
                process = None
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                            pass
                    except OSError:
                        return
                    time.sleep(0.05)
                raise RuntimeError("Disposable server port did not close; restart check aborted.")

        def run(module, *arguments):
            result = subprocess.run([sys.executable, "-m", module, *map(str, arguments)], cwd=project,
                                    env=env, capture_output=True, text=True, encoding="utf-8", timeout=45)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            print(result.stdout.strip())

        try:
            state = root / "state.json"
            start()
            run("scripts.smoke_deployment", "--url", url, "--save-state", state)
            stop(); start()
            run("scripts.smoke_deployment", "--url", url, "--verify-state", state)
            backup = root / "campus.zip"
            run("scripts.data_backup", "backup", "--output", backup)
            restored = root / "restored"
            run("scripts.data_backup", "restore", backup, "--target", restored)
            stop()
            env["DATA_DIR"] = str(restored)
            start()
            run("scripts.smoke_deployment", "--url", url, "--verify-state", state, "--cleanup")
            print("Isolated production runtime and backup/restore checks passed.")
        finally:
            stop()
            log.close()


if __name__ == "__main__":
    main()
