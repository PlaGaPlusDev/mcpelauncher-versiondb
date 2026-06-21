"""Compare wiki pages vs existing db to find missing versions."""
import json
import re
import subprocess as sp
import sys
import time

CURL = ["curl", "-s", "--max-time", "15",
        "-A", "Mozilla/5.0"]
WIKI_URL = "https://minecraft.wiki"

def curl_get(url):
    return sp.run(CURL + [url], capture_output=True, text=True, timeout=30).stdout

# Get all 26.x pages from wiki
pages = []
cmcontinue = None
while True:
    params = "action=query&list=categorymembers&cmtitle=Category:Bedrock_Edition_versions&cmlimit=max&cmtype=page&format=json"
    if cmcontinue:
        params += f"&cmcontinue={cmcontinue}"
    data = json.loads(curl_get(f"{WIKI_URL}/api.php?{params}"))
    for m in data["query"]["categorymembers"]:
        t = m["title"]
        if t.startswith("Bedrock Edition ") and "version_history" not in t:
            pages.append(t)
    cont = data.get("continue", {})
    if "cmcontinue" in cont:
        cmcontinue = cont["cmcontinue"]
    else:
        break

# Filter to 26.x and newer (starts with 2 digit)
wiki_versions = set()
for p in pages:
    rest = p.replace("Bedrock Edition ", "", 1)
    if rest.startswith("Preview "):
        rest = rest[8:]
    elif rest.startswith("beta "):
        rest = rest[5:]
    if re.match(r'^\d{2}\.', rest):
        if re.match(r'^\d{2}\.\d{2,}$', rest):
            wiki_versions.add(rest)

# Existing versions (normalized)
existing = set()
for arch in ["x86_64", "arm64-v8a", "x86", "armeabi-v7a"]:
    try:
        data = json.load(open(f"versions.{arch}.json.min"))
        for e in data:
            existing.add(e[1])
    except:
        pass

# Normalize wiki name to db name
def to_db(v):
    return "1." + v

wiki_db = {to_db(v) for v in wiki_versions}
missing = wiki_db - existing
found = wiki_db & existing

print(f"Total 26.x wiki pages: {len(wiki_versions)}")
print(f"Existing in db: {len(found)}")
print(f"Missing in db: {len(missing)}")
if missing:
    print("\nMissing versions:")
    for v in sorted(missing):
        print(f"  {v}")
