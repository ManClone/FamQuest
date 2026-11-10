"""Prepare a permanent isolated QNAP test application, never touching live inputs."""

import argparse
import importlib.util
import ipaddress
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "stage_generator", ROOT / "scripts/prepare-central-stage.py"
)
STAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STAGE)
DEFAULT_MCP = (
    "ghcr.io/manclone/famquest-mcp@sha256:"
    "31ef5593c50ae2db0edeac6d5d18b593aca5bd7d93fdd8d5131d30e0b4d2bb2e"
)


def validate_image(image, repository, local=None):
    if image == local:
        return
    if not re.fullmatch(
        re.escape(repository) + r"(?::(?:sha|test)-[a-f0-9]{40}|@sha256:[a-f0-9]{64})", image
    ):
        raise ValueError(
            "Use an immutable commit/digest image, not latest or an untrusted repository"
        )


def prepare(output, origin, image, target_dir, listen_host="127.0.0.1", mcp_image=DEFAULT_MCP):
    validate_image(image, "ghcr.io/manclone/famquest", "famquest:sternchen-review-20261109-aclfix")
    validate_image(mcp_image, "ghcr.io/manclone/famquest-mcp")
    ipaddress.IPv4Address(listen_host)
    if Path(target_dir).name != "famquest-test":
        raise ValueError("Use a new dedicated famquest-test directory")
    # Existing generator validates HTTPS, uses fresh credentials, and refuses overwrite.
    result = STAGE.prepare(output, origin, "famquest:central-ci", target_dir, spare_families=2)
    origin = origin.rstrip("/")
    host = urlsplit(origin).netloc
    template = (ROOT / "docker-compose.test.template.yml").read_text()
    for key, value in {
        "@@IMAGE@@": image,
        "@@MCP_IMAGE@@": mcp_image,
        "@@DIR@@": target_dir,
        "@@LISTEN@@": listen_host,
        "@@ORIGIN@@": origin,
    }.items():
        template = template.replace(key, value)
    (result / "compose.yml").write_text(template)
    # Gateway resolves upstream names at request time, allowing image-only restarts.
    headers = f"""        proxy_set_header Host {host};
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header Connection "";
        proxy_http_version 1.1;
"""
    gateway = f"""server {{ listen 8080 default_server; server_name _; return 444; }}
server {{
    listen 8080;
    server_name {urlsplit(origin).hostname};
    client_max_body_size 24m;
    resolver 127.0.0.11 valid=10s ipv6=off;
    location ~ ^/mcp(/|$) {{
        set $mcp http://central-stage-mcp:8000;
        proxy_pass $mcp;
        proxy_buffering off;
        proxy_read_timeout 300s;
{headers}    }}
    location / {{
        set $backend http://central-stage-app:8080;
        proxy_pass $backend;
{headers}    }}
}}
"""
    (result / "gateway.conf").write_text(gateway)
    # Only this isolated test registry enables registration for testing MCP clients.
    for name in ("runtime.env", "bootstrap.env"):
        with (result / name).open("a") as stream:
            stream.write("OAUTH_DYNAMIC_REGISTRATION=true\n")
    metadata = json.loads((result / "images.json").read_text())
    metadata.update(app=image, mcp=mcp_image, project="famquest-test")
    (result / "images.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (result / "README-ZUERST.md").write_text(
        (ROOT / "docs/famquest-test.md")
        .read_text()
        .replace("@@DIR@@", target_dir)
        .replace("@@ORIGIN@@", origin)
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--origin", default="https://famtest.websiteclone.de")
    parser.add_argument("--image", default="famquest:sternchen-review-20261109-aclfix")
    parser.add_argument("--target-dir", default="/share/Container/famquest-test")
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--mcp-image", default=DEFAULT_MCP)
    args = parser.parse_args()
    result = prepare(
        args.output, args.origin, args.image, args.target_dir, args.listen_host, args.mcp_image
    )
    print(f"Private famquest-test package prepared at {result}; no secrets printed.")


if __name__ == "__main__":
    main()
