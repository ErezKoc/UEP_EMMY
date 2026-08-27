"""Shared pytest configuration.

The only thing configured here is the opt-in switch for live network checks;
everything else in the suite is offline and deterministic.
"""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-network",
        action="store_true",
        default=False,
        help="Also fetch every cited source URL to check it still resolves.",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "network: needs internet access; opt in with --run-network")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-network"):
        return
    skip = pytest.mark.skip(reason="live network check; pass --run-network to run it")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def network_enabled(request) -> bool:
    return bool(request.config.getoption("--run-network"))


@pytest.fixture(autouse=True)
def outbox_in_tmp_path(tmp_path, monkeypatch):
    """Keep the email outbox out of the project directory.

    Delivery happens in the queue sweep rather than inline, so far fewer tests
    reach the sender at all now - but any test that drains the queue with the
    real sender still writes a genuine `.eml` file, and with no SMTP configured
    that is exactly what the sender is meant to do. Under test it meant every
    run littered `backend/storage/outbox` with messages addressed to fixtures.

    Autouse because the tests that trigger it do not look like email tests:
    they create a reminder, or confirm an appointment, and the email is a
    consequence three layers down.
    """
    from app.services import email as email_module

    sender = email_module.EmailSender()
    sender.outbox = tmp_path / "outbox"
    monkeypatch.setattr(email_module, "_sender", sender)
    yield
    monkeypatch.setattr(email_module, "_sender", None)
