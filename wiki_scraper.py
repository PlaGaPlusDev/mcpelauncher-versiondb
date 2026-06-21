"""Fetch missing Bedrock versions from Minecraft Wiki and merge into versiondb.

Usage: python wiki_scraper.py [output_dir]

Scrapes specific known-missing version pages and merges codes into existing db.
"""
import json
import os
import re
import subprocess as sp
import sys
import time
import urllib.parse

CURL = ["curl", "-s", "--max-time", "15",
        "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"]
WIKI_URL = "https://minecraft.wiki"

ARCH_PREFIXES = {"armeabi-v7a": 95, "x86": 96, "arm64-v8a": 97, "x86_64": 98}
ARCHES = ["armeabi-v7a", "x86", "arm64-v8a", "x86_64"]

_B_PAD = re.compile(r"^([0-9])\.")
_M_PAD = re.compile(r"\.([0-9])\.")
_E_PAD = re.compile(r"\.b?([0-9])$")

def _natural_key(v):
    if isinstance(v, str):
        name = v
    elif isinstance(v, list):
        name = v[1]
    else:
        name = v["version_name"]
    return _E_PAD.sub(r".0\1", _M_PAD.sub(r".0\1.", _M_PAD.sub(r".0\1.", _B_PAD.sub(r"0\1.", name))))

PAGES = [
    "Bedrock Edition 26.22", "Bedrock Edition 26.23",
    "Bedrock Edition 26.30",  # release build 5
    "Bedrock Edition Preview 26.30.29", "Bedrock Edition Preview 26.30.31",
    "Bedrock Edition Preview 26.30.32", "Bedrock Edition 26.31",
    "Bedrock Edition Preview 26.40.20", "Bedrock Edition Preview 26.40.22",
    "Bedrock Edition Preview 26.40.26",
]


def curl_get(url: str) -> str:
    r = sp.run(CURL + [url], capture_output=True, text=True, timeout=30)
    return r.stdout


def fetch_wikitext(title: str) -> str:
    url_title = urllib.parse.quote(title.replace(" ", "_"))
    return curl_get(f"{WIKI_URL}/w/{url_title}?action=raw")


def parse_infobox_field(wt: str, field: str) -> str | None:
    m = re.search(rf'\|\s*{re.escape(field)}\s*=\s*(.*?)(?:\n\s*\||\n\}})', wt, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def parse_version_codes(wt: str) -> dict[str, int] | None:
    block = parse_infobox_field(wt, 'versioncode')
    if not block:
        return None
    codes = {}
    for arch, prefix in ARCH_PREFIXES.items():
        m = re.search(rf'({prefix}\d+)\s*\({arch}', block)
        if m:
            codes[arch] = int(m.group(1))
    return codes if codes else None


def parse_name_and_beta(title: str, wt: str) -> tuple[str, bool]:
    rest = title.replace("Bedrock Edition ", "", 1)
    is_beta = False

    if rest.startswith("Preview "):
        rest = rest[8:]
        is_beta = True
    elif rest.startswith("beta "):
        rest = rest[5:]
        is_beta = True

    # For releases (non-preview), try server version for proper build suffix
    if not is_beta:
        server = parse_infobox_field(wt, 'server')
        if server:
            m = re.match(r'([\d.]+)', server)
            if m:
                name = m.group(1)
                return name, False

    # For previews or fallback: normalize title name
    if re.match(r'^\d{2}\.', rest):
        rest = "1." + rest
    return rest, is_beta


def main():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    new_entries = []

    for title in PAGES:
        wt = fetch_wikitext(title)
        if not wt:
            print(f"EMPTY: {title}")
            continue
        codes = parse_version_codes(wt)
        if not codes:
            print(f"SKIP: {title} (no versioncode)")
            continue
        db_name, is_beta = parse_name_and_beta(title, wt)
        entry = {"version_name": db_name, "codes": codes}
        if is_beta:
            entry["beta"] = True
        new_entries.append(entry)
        print(f"OK: {db_name} x86_64={codes.get('x86_64','?')}")
        time.sleep(0.3)

    if not new_entries:
        print("No new entries found.")
        return

    for arch in ARCHES:
        path = os.path.join(output_dir, f"versions.{arch}.json.min")
        existing = json.load(open(path)) if os.path.exists(path) else []
        lookup = {(e[1], e[2]): e for e in existing}
        for v in new_entries:
            if arch in v["codes"]:
                entry = [v["codes"][arch], v["version_name"], 1 if v.get("beta") else 0]
                lookup[(v["version_name"], 1 if v.get("beta") else 0)] = entry
        merged = sorted(lookup.values(), key=_natural_key)
        with open(path, "w") as f:
            json.dump(merged, f, separators=(",", ":"))
        added = len(merged) - len(existing)
        print(f"{arch}: {len(merged)} entries ({added} added)")

    path = os.path.join(output_dir, "versions.json")
    existing = json.load(open(path)) if os.path.exists(path) else []
    lookup = {v["version_name"]: v for v in existing}
    for v in new_entries:
        if v["version_name"] in lookup:
            lookup[v["version_name"]]["codes"].update(v["codes"])
            if v.get("beta"):
                lookup[v["version_name"]]["beta"] = True
        else:
            lookup[v["version_name"]] = v
    merged = sorted(lookup.values(), key=_natural_key)
    with open(path, "w") as f:
        json.dump(merged, f, indent=4)
    print(f"versions.json: {len(merged)} entries")


if __name__ == "__main__":
    main()
