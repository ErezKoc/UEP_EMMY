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

    Anything that creates a notification asks the email sender to send it, and
    with no SMTP configured the sender writes a real `.eml` file. Under test
    that meant every run littered `backend/storage/outbox` with messages
    addressed to fixtures - dozens of them before anybody noticed.

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
