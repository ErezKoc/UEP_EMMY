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
