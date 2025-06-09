import pytest
from providers.resource.account.account_provider import (
    get_account_amount,
    get_auth_info,
)
from tests.fixtures import region_url, region_token


# python -m pytest -s tests/test_account_provider.py::test_get_account_amount
def test_get_account_amount(region_url, region_token):
    result = get_account_amount(region_url, region_token)
    print(f"Account amount: {result}")
    assert isinstance(result, dict)
    # Optionally, check for expected keys if known, e.g.:
    # assert "amount" in result


# python -m pytest -s tests/test_account_provider.py::test_get_auth_info
def test_get_auth_info(region_url, region_token):
    result = get_auth_info(region_url, region_token)
    print(f"Auth info: {result}")
    assert isinstance(result, dict)
    # Optionally, check for expected keys if known, e.g.:
    # assert "user" in result
