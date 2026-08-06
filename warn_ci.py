#!/usr/bin/env python3
"""Update version-warnings.json from a list of versions and one reason.

Used by .github/workflows/add-warning.yml (workflow_dispatch manual runs).
Each version you pass is added, or has its reason updated.

Inputs (env vars):
  WARN_VERSIONS    space/comma separated versions to mark
  WARN_REASON      reason/note applied to every selected version

Versiondb source: local committed versions.x86_64.json.min (no network).

Exit code: 0 on success, 1 if any version is invalid / missing.
"""
import json
import os
import re
import sys
from datetime import date

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
WARN_FILE = os.path.join(REPO_DIR, "version-warnings.json")
LOCAL_VDB = os.path.join(REPO_DIR, "versions.x86_64.json.min")


def natural_key(v: str):
    return [int(p) if p.isdigit() else p for p in re.split(r"\.", v)]


def load_versiondb():
    if not os.path.exists(LOCAL_VDB):
        print(f"[error] versiondb not found: {LOCAL_VDB}")
        sys.exit(1)
    with open(LOCAL_VDB) as f:
        return {e[1]: e[2] for e in json.load(f)}


def main():
    versions = re.split(r"[,\s]+", os.environ.get("WARN_VERSIONS", "").strip())
    versions = [v for v in versions if v]
    reason = os.environ.get("WARN_REASON", "").strip()

    if not versions:
        print("[error] WARN_VERSIONS (versions) input is empty")
        sys.exit(1)
    if not reason:
        print("[error] WARN_REASON (reason) input is empty")
        sys.exit(1)

    db = load_versiondb()

    missing = [v for v in versions if v not in db]
    if missing:
        print("[error] not found in versiondb:")
        for v in missing:
            close = sorted(v2 for v2 in db if v in v2)
            if close:
                print(f"  {v}  -> did you mean: {', '.join(close[:5])}?")
            else:
                print(f"  {v}")
        sys.exit(1)

    with open(WARN_FILE) as f:
        data = json.load(f)

    added = []
    updated = []
    seen = {w["version"] for w in data.get("warnings", [])}
    for v in versions:
        if v in seen:
            for w in data["warnings"]:
                if w["version"] == v:
                    w["reason"] = reason
                    break
            updated.append(v)
        else:
            data["warnings"].append({"version": v, "reason": reason})
            added.append(v)
    data["updated"] = date.today().isoformat()
    data["warnings"].sort(key=lambda w: natural_key(w["version"]), reverse=True)

    with open(WARN_FILE, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    print(f"added {len(added)}, updated {len(updated)} -> reason '{reason}'")
    for v in added:
        print(f"  + {v}")
    for v in updated:
        print(f"  ~ {v}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)