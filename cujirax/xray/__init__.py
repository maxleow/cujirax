from enum import Enum
import json
from typing import List, Union, AnyStr
from loguru import logger
from pydantic import BaseModel, Field
import os
import requests
import time
import functools


xray_url = "https://xray.cloud.getxray.app"


class Endpoint(Enum):
    CREATE_TEST_CASE = "/api/v2/import/test/bulk"
    AUTHENTICATE = "/api/v2/authenticate"
    CHECK_IMPORT_TEST_STATUS = "/api/v2/import/test/bulk/{}/status"
    IMPORT_XRAY_JSON_RESULTS = "/api/v2/import/execution"
    GRAPHQL = "/api/v1/graphql"


class Header(BaseModel):
    Content_Type: str = Field("application/json", alias="Content-Type")
    Authorization: str = None


class Authentication(BaseModel):
    client_id: str = os.getenv("XRAY_CLIENT_ID")
    client_secret: str = os.getenv("XRAY_CLIENT_SECRET")


def retry(max_retries=3, delay=1):
    def decorator_retry(func):
        @functools.wraps(func)
        def wrapper_retry(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    print(f"Retry {retries}/{max_retries} - Error: {e}")
                    time.sleep(delay)
            raise Exception(f"Failed after {max_retries} retries")
        return wrapper_retry
    return decorator_retry


@retry(max_retries=5, delay=2)
def login()-> Header:
    header = Header()
    response = post(Endpoint.AUTHENTICATE.value, Authentication(), header)
    if response.status_code == 200:
        header.Authorization = "Bearer " + eval(response.text)
        return header
    raise Exception("Authentication error: Invalid credentials")

def post(endpoint: str, payload: Union[BaseModel, List[BaseModel], AnyStr], headers: Header)-> requests.Response:
    url = f"{xray_url}{endpoint}"
    if isinstance(payload, list):
        _payload = [p.dict(by_alias=True, exclude_none=True) for p in payload]
        _payload = json.dumps(_payload)
        # print("payload", _payload)
    elif isinstance(payload, str): 
        logger.info("is string type")
        _payload = payload
    else:
        _payload = payload.json(by_alias=True, exclude_none=True)

    parameters = {
        "url": url,
        "method": "POST", 
        "headers": headers.dict(by_alias=True, exclude_none=True),
        "data": _payload
    }
    
    response = requests.request(**parameters)
    return response

def get(endpoint: str, headers: Header, payload: str= None) -> requests.Response:
    url = f"{xray_url}{endpoint}"
    logger.info(f"GET '{url}'")
    return requests.get(
        url=url, 
        data=payload,
        headers=headers.dict(by_alias=True, exclude_none=True),)
