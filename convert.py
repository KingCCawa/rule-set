#!/usr/bin/env python3
"""Convert SingBox rule-set JSON files into Surge / QuantumultX / Shadowrocket rule lists.

Zero third-party dependencies. Run from the repo root:  python convert.py

Source : SingBox/*.list   (sing-box rule-set, version 2)
Output : Surge/*.list, QuantumultX/*.list, Shadowrocket/*.list
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def today_cn() -> str:
    """Beijing time (UTC+8) date, stable regardless of the runner timezone."""
    return datetime.now(timezone(timedelta(hours=8))).date().isoformat()


ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "SingBox"

# Surge: policy suffix appended as the third column. Empty means no policy token.
# Kept consistent with the existing Surge files in the upstream repo.
SURGE_POLICY = {
    "video-direct": "DIRECT",
    "must-direct": "",
    "data-app": "",
    "game-download": "",
}
DEFAULT_SURGE_POLICY = ""

# QuantumultX: policy group written into the third column.
QX_GROUP = {
    "video-direct": "影视资源网站",
    "must-direct": "强制直连",
    "data-app": "数据类应用",
    "game-download": "游戏下载",
}
DEFAULT_QX_GROUP = "直连规则"
QX_AUTHOR = "ChatGPT"

# Shadowrocket: an explicit policy on every rule (Surge-compatible syntax).
SHADOWROCKET_POLICY = "DIRECT"

# sing-box field -> (Surge token, QuantumultX token, Shadowrocket token)
TYPE_MAP = {
    "domain_suffix": ("DOMAIN-SUFFIX", "HOST-SUFFIX", "DOMAIN-SUFFIX"),
    "domain": ("DOMAIN", "HOST", "DOMAIN"),
    "domain_keyword": ("DOMAIN-KEYWORD", "HOST-KEYWORD", "DOMAIN-KEYWORD"),
    "ip_cidr": ("IP-CIDR", "IP-CIDR", "IP-CIDR"),
}


def extract_rules(data: dict) -> list[tuple[str, str]]:
    """Return de-duplicated (sing_box_field, value) pairs in first-seen order."""
    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []
    for rule in data.get("rules", []):
        for field in TYPE_MAP:
            for value in rule.get(field, []) or []:
                key = (field, str(value))
                if key in seen:
                    continue
                seen.add(key)
                result.append(key)
    return result


def render_surge(name: str, rules: list[tuple[str, str]]) -> str:
    policy = SURGE_POLICY.get(name, DEFAULT_SURGE_POLICY)
    lines = []
    for field, value in rules:
        token = TYPE_MAP[field][0]
        suffix = f",{policy}" if policy else ""
        lines.append(f"{token},{value}{suffix}")
    return "\n".join(lines) + "\n"


def render_quantumultx(name: str, rules: list[tuple[str, str]]) -> str:
    group = QX_GROUP.get(name, DEFAULT_QX_GROUP)
    count = len(rules)
    header = [
        f"# NAME: {group}",
        f"# AUTHOR: {QX_AUTHOR}",
        f"# UPDATED: {today_cn()}",
        f"# DOMAIN-SUFFIX: {count}",
        f"# TOTAL: {count}",
        "",
    ]
    lines = [f"{TYPE_MAP[field][1]},{value},{group}" for field, value in rules]
    return "\n".join(header + lines) + "\n"


def render_shadowrocket(name: str, rules: list[tuple[str, str]]) -> str:
    lines = [
        f"# Shadowrocket / {name}",
        f"# Generated from SingBox/{name}.list",
        f"# Updated: {today_cn()}",
        f"# Rules: {len(rules)}",
        "",
    ]
    for field, value in rules:
        token = TYPE_MAP[field][2]
        lines.append(f"{token},{value},{SHADOWROCKET_POLICY}")
    return "\n".join(lines) + "\n"


def main() -> int:
    if not SRC_DIR.is_dir():
        print(f"Source directory not found: {SRC_DIR}")
        return 1

    targets = {
        "Surge": render_surge,
        "QuantumultX": render_quantumultx,
        "Shadowrocket": render_shadowrocket,
    }
    for folder in targets:
        (ROOT / folder).mkdir(exist_ok=True)

    source_files = sorted(SRC_DIR.glob("*.list"))
    converted = 0
    for src in source_files:
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"[skip] {src.name}: invalid JSON ({exc})")
            continue

        rules = extract_rules(data)
        name = src.stem
        for folder, render in targets.items():
            out = ROOT / folder / src.name
            out.write_text(render(name, rules), encoding="utf-8")
            print(f"[ok] {folder}/{src.name}  ({len(rules)} rules)")
        converted += 1

    # Full sync: remove any generated output whose source rule-set no longer exists.
    valid_names = {src.stem for src in source_files}
    removed = 0
    for folder in targets:
        for out in sorted((ROOT / folder).glob("*.list")):
            if out.stem not in valid_names:
                out.unlink()
                print(f"[del] {folder}/{out.name} (source removed)")
                removed += 1

    print(f"Done. {converted} rule-set(s) converted, {removed} orphaned output(s) removed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
