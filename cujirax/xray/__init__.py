from enum import Enum
import json
from typing import List, Union
from pydantic import BaseModel, Field
import os
import requests

xray_url = "https://xray.cloud.getxray.app"


class Endpoint(Enum):
    CREATE_TEST_CASE = "/api/v2/import/test/bulk"
    IMPORT_RESULT = "/api/v2/import/execution"
    AUTHENTICATE = "/api/v2/authenticate"


class Client(BaseModel):
    client_id: str
    client_secret: str


class Header(BaseModel):
    Content_Type: str = Field("application/json", alias="Content-Type")
    Authorization: str = None


class Authentication(BaseModel):
    client_id: str = os.getenv("XRAY_CLIENT_ID")
    client_secret: str = os.getenv("XRAY_CLIENT_SECRET")


def post(endpoint: Endpoint, payload: Union[BaseModel, List[BaseModel]], headers: Header):
    url = f"{xray_url}{endpoint.value}"
    if isinstance(payload, list):
        _payload = [p.dict(by_alias=True, exclude_none=True) for p in payload]
        _payload = json.dumps(_payload)
        print(_payload)
    else:
        _payload = payload.json(by_alias=True, exclude_none=True)

    response = requests.request(
        "POST", url,
        headers=headers.dict(by_alias=True, exclude_none=True),
        data=_payload
    )
    return response
