"""Cloud/container entry point; one process for the SQLite deployment."""

import argparse
import os

import uvicorn

from config import get_settings, validate_production


def server_options():
    port = int(os.getenv("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535.")
    return {
        "host":"0.0.0.0", "port":port, "workers":1,
        "proxy_headers":True,
        "forwarded_allow_ips":os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1"),
        "timeout_keep_alive":5,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate configuration without starting the server")
    args = parser.parse_args()
    settings = get_settings()
    validate_production(settings)
    options = server_options()
    if args.check:
        print(f"Configuration valid; environment={settings.environment}; port={options['port']}; workers=1")
        return
    uvicorn.run("main:app", **options)


if __name__ == "__main__":
    main()
