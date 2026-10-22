#!/usr/bin/env python3
"""Offline checks for the instance listing in RTMonLibs/ResultsApi.py.

No Grafana, no SENSE-O, no SiteRM. A state file is written the way the worker
writes one, from the manifest in test/BGP.json, and the store and the HTTP
handler are asked about it.

Why this is worth a test: /api/v1/instances is how a caller holding only an
instance UUID - the SENSE dashboard, which gets one per rule from DMM - finds
the sites and switches a path crosses, and from those the bgp_session_state
series to read. If the split from the manifest's ``SITE:device`` drifts from
the one Template uses for the BGP panels, the caller asks Prometheus about a
switch the dashboard never drew.

Run from the repository root:

    python3 test/test_resultsapi.py

Exits non-zero on the first failure and prints what failed.
"""

# pylint: disable=line-too-long,too-many-locals

import json
import logging
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "autogole-api", "src", "python"))

from RTMonLibs.ResultsApi import (  # noqa: E402  pylint: disable=wrong-import-position
    Authenticator,
    ResultsStore,
    makeHandler,
)

LOGGER = logging.getLogger("test_resultsapi")
UUID = "11111111-2222-3333-4444-555555555555"
OTHER = "99999999-2222-3333-4444-555555555555"


def check(name, cond, detail=""):
    """Fail loudly on the first broken expectation."""
    if not cond:
        print(f"FAIL {name} {detail}")
        sys.exit(1)
    print(f"ok   {name}")


def main():
    """Write two state files and ask the store and the server about them."""
    with open(os.path.join(ROOT, "test", "BGP.json"), encoding="utf-8") as fd:
        ports = json.load(fd)
    workdir = tempfile.mkdtemp(prefix="rtmon-results-")
    states = {
        UUID: {"referenceUUID": UUID, "orchestrator": "sense-o", "state": "running", "instance": {"alias": "fnal-ucsd"}, "manifest": {"Ports": ports}, "action_results": {"ping": []}},
        OTHER: {"referenceUUID": OTHER, "orchestrator": "sense-o", "state": "running", "instance": {"alias": "empty"}, "manifest": {}},
    }
    for uuid, state in states.items():
        with open(os.path.join(workdir, f"rtmon-debug-test-{uuid}"), "w", encoding="utf-8") as fd:
            json.dump(state, fd)

    config = {"workdir": workdir, "http_api_token": "t0ken"}
    store = ResultsStore(config, LOGGER)
    rows = {row["instance"]: row for row in store.instances()}
    row = rows[UUID]
    expect = []
    for port in ports:
        site, sep, host = port["Node"].partition(":")
        if sep and {"sitename": site, "hostname": host} not in expect:
            expect.append({"sitename": site, "hostname": host})
    check("switches: every SITE:device in the manifest, once, in path order", row["switches"] == expect, row["switches"])
    check("switches: split on the first colon, as Template does", all(":" not in s["sitename"] for s in row["switches"]))
    check("sites: the sitenames of those switches, in order", row["sites"][: len({s["sitename"] for s in expect})] == list(dict.fromkeys(s["sitename"] for s in expect)), row["sites"])
    check("an instance with no manifest lists no devices, and is still listed", rows[OTHER]["switches"] == [] and rows[OTHER]["sites"] == [])
    check("filter: instance", [r["instance"] for r in store.instances({"instance": UUID})] == [UUID])
    check("filter: sitename keeps only paths crossing that site", [r["instance"] for r in store.instances({"sitename": expect[0]["sitename"]})] == [UUID])
    check("filter: action is applied, not dropped", [r["instance"] for r in store.instances({"action": "ping"})] == [UUID])

    # The server: the listing is behind the same auth, and takes the filters.
    httpd = __import__("http.server").server.ThreadingHTTPServer(("127.0.0.1", 0), makeHandler(store, Authenticator(config, LOGGER), LOGGER))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def get(path, token="t0ken"):
        req = urllib.request.Request(base + path, headers={"Authorization": f"Bearer {token}"} if token else {})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as ex:
            body = ex.read()
            return ex.code, (json.loads(body) if body else None)

    status, body = get(f"/api/v1/instances?instance={UUID}")
    check("http: filtered listing", status == 200 and len(body) == 1 and body[0]["switches"] == expect, (status, body))
    status, _ = get("/api/v1/instances", token=None)
    check("http: no credential is refused", status == 401, status)
    status, body = get("/api/v1/instances?colour=red")
    check("http: an unknown filter is a 400, not everything", status == 400 and body["filters"] == ["colour"], (status, body))
    httpd.shutdown()
    print("all passed")


if __name__ == "__main__":
    main()
