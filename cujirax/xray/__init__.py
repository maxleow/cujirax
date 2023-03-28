from enum import Enum
import json
from typing import List, Union
from pydantic import BaseModel, Field
import os
import requests

xray_url = "https://xray.cloud.getxray.app"


class Endpoint(Enum):
    CREATE_TEST_CASE = "/api/v2/import/test/bulk"
    AUTHENTICATE = "/api/v2/authenticate"
    CHECK_IMPORT_TEST_STATUS = "/api/v2/import/test/bulk/{}/status"
    IMPORT_XRAY_JSON_RESULTS = "/api/v2/import/execution"


class Header(BaseModel):
    Content_Type: str = Field("application/json", alias="Content-Type")
    Authorization: str = None


class Authentication(BaseModel):
    client_id: str = os.getenv("XRAY_CLIENT_ID")
    client_secret: str = os.getenv("XRAY_CLIENT_SECRET")


def login()-> Header:
    header = Header()
    response = post(Endpoint.AUTHENTICATE.value, Authentication(), header)
    if response.status_code == 200:
        header.Authorization = "Bearer " + eval(response.text)
        return header
    raise Exception("Authentication error: Invalid credentials")

def post(endpoint: str, payload: Union[BaseModel, List[BaseModel]], headers: Header)-> requests.Response:
    url = f"{xray_url}{endpoint}"
    if isinstance(payload, list):
        _payload = [p.dict(by_alias=True, exclude_none=True) for p in payload]
        _payload = json.dumps(_payload)
        # print("payload", _payload)
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

def get(endpoint: str,headers: Header) -> requests.Response:
    url = f"{xray_url}{endpoint}"

    return requests.get(
        url=url, 
        headers=headers.dict(by_alias=True, exclude_none=True))
