"""Generate a private staging package. Never overwrite existing credentials."""

import argparse
import json
import re
import secrets
from pathlib import Path
from urllib.parse import urlsplit


def prepare(output, origin, image, target_dir=None):
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or re.fullmatch(r"[a-zA-Z0-9.-]+", parsed.hostname) is None
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("A plain HTTPS origin is required")
    port = parsed.port
    if parsed.netloc.lower() != parsed.hostname.lower() + (f":{port}" if port else ""):
        raise ValueError("Unexpected authority in staging origin")
    if (
        image != "famquest:central-ci"
        and re.fullmatch(r"ghcr.io/manclone/famquest@sha256:[a-f0-9]{64}", image)
        is None
    ):
        raise ValueError("Use the verified immutable FamQuest image")
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Output is not empty; refusing to overwrite credentials")
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    directory = target_dir or output.as_posix()
    if '"' in directory or "\n" in directory or not directory.startswith("/"):
        raise ValueError("An absolute container-host directory is required")
    origin = origin.rstrip("/")
    passwords = {key: secrets.token_hex(24) for key in ("owner", "auth", "a", "b")}
    credentials = {
        f"famquest_stage_{part}": {
            "username": f"famquest_stage_{part}_app",
            "password": passwords[part],
        }
        for part in ("a", "b")
    }
    common = {
        "POSTGRES_HOST": "central-stage-db",
        "POSTGRES_DB": "postgres",
        "PUBLIC_URL": origin,
        "CALENDAR_SYNC_MINUTES": "0",
        "LOG_LEVEL": "info",
        "CENTRAL_BACKGROUND_JOBS": "false",
        "CENTRAL_CALENDAR_JOBS": "false",
        "AUTH_DATABASE_CREDENTIALS": json.dumps(
            {"username": "famquest_auth_app", "password": passwords["auth"]},
            separators=(",", ":"),
        ),
        "FAMILY_DATABASE_CREDENTIALS": json.dumps(credentials, separators=(",", ":")),
    }
    runtime = {
        **common,
        "POSTGRES_USER": "unused_in_central_mode",
        "POSTGRES_PASSWORD": "",
    }
    bootstrap = {
        **common,
        "POSTGRES_USER": "famquest_stage_owner",
        "POSTGRES_PASSWORD": passwords["owner"],
        "FAMQUEST_STAGE_BOOTSTRAP": "new-isolated-cluster-v1",
    }
    accounts = []
    for family in ("A", "B"):
        for role, title in (("PARENT", "eltern"), ("CHILD", "kind")):
            password = secrets.token_hex(12)
            bootstrap[f"STAGE_{family}_{role}_PASSWORD"] = password
            accounts.append(
                f"Testfamilie {family}, {title}: {title}.{family.lower()}@famquest.test\nPasswort: {password}\n"
            )

    def env_file(name, values):
        (output / name).write_text(
            "".join(f"{key}={value}\n" for key, value in values.items()),
            encoding="utf-8",
        )

    env_file(
        "postgres.env",
        {
            "POSTGRES_USER": "famquest_stage_owner",
            "POSTGRES_PASSWORD": passwords["owner"],
            "POSTGRES_DB": "postgres",
        },
    )
    env_file("bootstrap.env", bootstrap)
    env_file("runtime.env", runtime)
    host = parsed.hostname
    gateway = f"""server {{
    listen 8080 default_server;
    server_name _;
    return 444;
}}
server {{
    listen 8080;
    server_name {host};
    client_max_body_size 24m;
    resolver 127.0.0.11 valid=10s ipv6=off;
    location / {{
        set $backend http://central-stage-app:8080;
        proxy_pass $backend;
        proxy_set_header Host {parsed.netloc};
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header Connection "";
        proxy_http_version 1.1;
    }}
}}
"""
    (output / "gateway.conf").write_text(gateway, encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    template = (root / "docker-compose.central-stage.template.yml").read_text(
        encoding="utf-8"
    )
    (output / "compose.yml").write_text(
        template.replace("@@DIR@@", directory).replace("@@IMAGE@@", image),
        encoding="utf-8",
    )
    (output / "TESTZUGAENGE-PRIVAT.txt").write_text(
        "Nur fuer die isolierte Testinstanz. Nicht ins Repository oder Chat kopieren.\n\n"
        + "\n".join(accounts),
        encoding="utf-8",
    )
    (output / "images.json").write_text(
        json.dumps(
            {
                "app": image,
                "origin": origin,
                "scope": "isolated two-family staging; no global superadmin console",
                "databases": ["famquest_auth", "famquest_stage_a", "famquest_stage_b"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    guide = (root / "docs/central-stage-quickstart.md").read_text(encoding="utf-8")
    (output / "README-ZUERST.md").write_text(
        guide.replace("@@ORIGIN@@", origin)
        .replace("@@DIR@@", directory)
        .replace("@@IMAGE@@", image),
        encoding="utf-8",
    )
    for private_file in (
        "postgres.env",
        "bootstrap.env",
        "runtime.env",
        "TESTZUGAENGE-PRIVAT.txt",
    ):
        (output / private_file).chmod(0o600)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--target-dir")
    args = parser.parse_args()
    result = prepare(args.output, args.origin, args.image, args.target_dir)
    print(f"Private staging package prepared in {result.name}; no secrets printed.")


if __name__ == "__main__":
    main()
