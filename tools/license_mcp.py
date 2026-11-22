#!/usr/bin/env python3
"""Локальный stdio MCP-сервер справочника свободных лицензий для books-api."""

import json
import os
import sys
from typing import TypedDict


class LicenseInfo(TypedDict):
    spdx: str
    requires_attribution: bool
    share_alike: bool
    allows_commercial: bool
    can_bundle_with: list[str]
    notice_template: str


STRICT_MODE = os.environ.get("BOOKS_LICENSE_POLICY", "strict")

LICENSES: dict[str, LicenseInfo] = {
    "PUBLIC_DOMAIN": {
        "spdx": "CC-PDDC",
        "requires_attribution": False,
        "share_alike": False,
        "allows_commercial": True,
        "can_bundle_with": ["PUBLIC_DOMAIN", "CC0", "CC_BY", "CC_BY_SA"],
        "notice_template": "This work is in the public domain.",
    },
    "CC0": {
        "spdx": "CC0-1.0",
        "requires_attribution": False,
        "share_alike": False,
        "allows_commercial": True,
        "can_bundle_with": ["PUBLIC_DOMAIN", "CC0", "CC_BY", "CC_BY_SA"],
        "notice_template": "Dedicated to the public domain under CC0 1.0 Universal.",
    },
    "CC_BY": {
        "spdx": "CC-BY-4.0",
        "requires_attribution": True,
        "share_alike": False,
        "allows_commercial": True,
        "can_bundle_with": ["PUBLIC_DOMAIN", "CC0", "CC_BY", "CC_BY_SA"],
        "notice_template": "Licensed under CC BY 4.0. Attribution to {authors} is required.",
    },
    "CC_BY_SA": {
        "spdx": "CC-BY-SA-4.0",
        "requires_attribution": True,
        "share_alike": True,
        "allows_commercial": True,
        "can_bundle_with": ["PUBLIC_DOMAIN", "CC0", "CC_BY", "CC_BY_SA"],
        "notice_template": "Licensed under CC BY-SA 4.0. Attribution to {authors} and ShareAlike required.",
    },
}

TOOLS = [
    {
        "name": "inspect_free_license",
        "description": "Return SPDX code, notice template, and bundling rules for a books-api license.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "License code (PUBLIC_DOMAIN, CC0, CC_BY, CC_BY_SA, or any candidate code).",
                }
            },
            "required": ["code"],
        },
    }
]


def reply(req_id: int | str, result: dict[str, object]) -> None:
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}) + "\n")
    sys.stdout.flush()


def main() -> None:
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        msg: object = json.loads(line)
        if not isinstance(msg, dict):
            continue
        req_id = msg.get("id")
        method = msg.get("method")
        if not isinstance(req_id, (int, str)):
            continue
        if method == "initialize":
            reply(
                req_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "books-license-catalog", "version": "0.1.0"},
                },
            )
        elif method == "tools/list":
            reply(req_id, {"tools": TOOLS})
        elif method == "tools/call":
            params = msg.get("params")
            args = params.get("arguments") if isinstance(params, dict) else None
            raw_code = args.get("code", "") if isinstance(args, dict) else ""
            code = str(raw_code).strip().upper()
            info = LICENSES.get(code)
            payload: dict[str, object] = (
                {"allowed_in_catalog": True, "policy_mode": STRICT_MODE, "code": code, **info}
                if info is not None
                else {
                    "allowed_in_catalog": False,
                    "policy_mode": STRICT_MODE,
                    "code": code,
                    "reason": "Non-free license (e.g. NC/ND or proprietary) is forbidden in books-api.",
                }
            )
            reply(req_id, {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]})
        else:
            reply(req_id, {})


if __name__ == "__main__":
    main()
