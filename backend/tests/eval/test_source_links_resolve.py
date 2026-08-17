"""Opt-in live check that every cited URL still resolves.

Deselected by default: a clinical test suite must not fail because a publisher's
CDN was slow. The audit fetched and read every page on 2026-08-16 and recorded
what each one says in `evidence.py`; this file only re-checks reachability.

    python -m pytest tests/eval/test_source_links_resolve.py --run-network -q
"""

from __future__ import annotations

import pytest

from app.services.triage.sources import ALL_SOURCES

pytestmark = pytest.mark.network


@pytest.mark.parametrize("source", ALL_SOURCES, ids=lambda s: s.name[:50])
def test_source_url_resolves(source, network_enabled):
    if not network_enabled:
        pytest.skip("live network checks are opt-in; pass --run-network")
    httpx = pytest.importorskip("httpx")
    try:
        response = httpx.get(
            source.url,
            timeout=20.0,
            follow_redirects=True,
            headers={"User-Agent": "UEP-EMMY-source-audit/1.0"},
        )
    except httpx.HTTPError as exc:  # pragma: no cover - network dependent
        pytest.fail(f"{source.name}: {source.url} could not be reached ({exc}).")

    # A bot wall is not a dead link. Cornell's vet.cornell.edu returns 403 to a
    # plain scripted client while serving the article normally to a browser —
    # confirmed on 2026-08-16 by loading all four Cornell URLs in one. Treating
    # that as a broken source would make this sweep cry wolf every run, so it is
    # reported as needing a manual check instead of failing.
    if response.status_code in (401, 403, 429):  # pragma: no cover - network dependent
        pytest.skip(
            f"{source.name}: HTTP {response.status_code} — the publisher blocks scripted "
            "clients. Open the URL in a browser to confirm it still resolves."
        )

    assert response.status_code < 400, (
        f"{source.name}: {source.url} returned HTTP {response.status_code}."
    )
    body = response.text.lower()
    assert len(body) > 2000, f"{source.name}: the page returned almost no content."
    for marker in ("search results", "page not found", "404 error"):
        assert marker not in body[:4000], (
            f"{source.name}: the page looks like a {marker!r} page, not an article."
        )
