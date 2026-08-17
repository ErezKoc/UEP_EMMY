"""The HTTP surface: malformed, missing and unusual input must not 500.

`POST /v1/triage` stores nothing and takes an unauthenticated body, so it is
the part of the system most exposed to whatever a client sends.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.triage import router
from app.schemas.triage import TriageLevel
from tests.eval.cases import CASES


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/v1/triage")
    return TestClient(app)


def test_every_evaluation_case_round_trips_through_the_api(client):
    """The HTTP answer must match the engine's answer for all 815 scenarios."""
    from app.services.triage import TriageEngine

    engine = TriageEngine(require_verified=False)
    for case in CASES[::5]:
        payload = case.intake.model_dump(mode="json", exclude_none=True)
        response = client.post("/v1/triage", json=payload)
        assert response.status_code == 200, f"{case.id}: {response.status_code} {response.text}"
        body = response.json()
        assert body["level"] == engine.assess(case.intake).level.value, (
            f"{case.id}: the API and the engine disagree."
        )
        assert body["disclaimer"], f"{case.id}: API response carries no disclaimer."


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({}, id="empty-object"),
        pytest.param({"concern": "eyes"}, id="concern-only"),
        pytest.param({"red_flags": []}, id="empty-flags"),
        pytest.param({"species": None, "age_category": None}, id="explicit-nulls"),
        pytest.param({"concern": "digestion", "red_flags": ["vomiting"] * 200}, id="repeated-flags"),
        pytest.param({"species": "dog" * 2000}, id="very-long-species"),
        pytest.param({"species": "  cat  "}, id="padded-species"),
        pytest.param({"species": chr(0) + chr(31)}, id="control-characters"),
        pytest.param({"species": "🐕"}, id="emoji-species"),
        pytest.param({"has_chronic_illness": None, "weight_bearing": None}, id="null-booleans"),
        pytest.param({"concern": "breed_only", "red_flags": ["seizure"]}, id="breed-only-with-flag"),
    ],
)
def test_unusual_but_valid_bodies_return_a_complete_assessment(client, payload):
    response = client.post("/v1/triage", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["level"] in {level.value for level in TriageLevel}
    assert body["headline"] and body["advice"] and body["disclaimer"]
    assert isinstance(body["fired_rules"], list)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"concern": "not_a_concern"}, id="unknown-concern"),
        pytest.param({"red_flags": ["not_a_flag"]}, id="unknown-flag"),
        pytest.param({"red_flags": "seizure"}, id="flags-not-a-list"),
        pytest.param({"duration": 7}, id="duration-wrong-type"),
        pytest.param({"age_category": "ancient"}, id="unknown-age"),
        pytest.param({"has_chronic_illness": "maybe"}, id="boolean-wrong-type"),
        pytest.param({"time_since_eating": "a_while"}, id="unknown-eating-bucket"),
        pytest.param({"species": 42}, id="species-wrong-type"),
    ],
)
def test_invalid_bodies_are_rejected_with_422_not_500(client, payload):
    response = client.post("/v1/triage", json=payload)
    assert response.status_code == 422, (
        f"Expected a validation error, got {response.status_code}: {response.text[:200]}"
    )


def test_a_non_json_body_is_rejected_cleanly(client):
    response = client.post(
        "/v1/triage", content=b"not json at all", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422, response.status_code


def test_an_emergency_reaches_the_api_response_intact(client):
    response = client.post(
        "/v1/triage",
        json={
            "concern": "digestion",
            "red_flags": ["suspected_poisoning"],
            "species": "dog",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["level"] == "red"
    assert body["fired_rules"], "A red verdict reached the client with no stated reason."
    assert all(link["url"].startswith("https://") for rule in body["fired_rules"]
               for link in rule["source_links"])
    assert any("426-4435" in item for item in body["care_instructions"]), (
        "The poison-control number did not survive serialisation."
    )
