import requests
from typing import Dict


def get_account_amount(region_url: str, region_token: str) -> Dict:
    """
    Request the account amount from the api/account/getAmount endpoint.

    Args:
        region_url (str): The region's base URL (without protocol).
        region_token (str): The region token for authentication.

    Returns:
        dict: The response data from the API (the 'data' field if present, else the whole result).
    """
    url = f"https://{region_url}/api/account/getAmount"
    headers = {
        "Authorization": region_token,
        "Content-Type": "application/json",
    }
    response = requests.post(url, headers=headers)
    response.raise_for_status()
    result = response.json()
    return result.get("data", result)


def get_auth_info(region_url: str, region_token: str) -> Dict:
    """
    Request authentication info from the api/auth/info endpoint.

    Args:
        region_url (str): The region's base URL (without protocol).
        region_token (str): The region token for authentication.

    Returns:
        dict: The response data from the API (the 'data' field if present, else the whole result).
    """
    url = f"https://{region_url}/api/auth/info"
    headers = {
        "Authorization": region_token,
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    result = response.json()
    return result.get("data", result)
