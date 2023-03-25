from enum import Enum
from typing import List

from pydantic import BaseModel
from requests import Response

from cujirax.jira import Project
from cujirax.xray import Endpoint, get, login, post


class TestType(Enum):
    CUCUMBER = "Cucumber"
    MANUAL = "Manual"
    GENERIC = "Generic"


class Steps(BaseModel):
    action: str
    data: str = ""
    result: str = ""


class Fields(BaseModel):
    summary: str
    project: Project
    description: str = None
    

class TestCase(BaseModel):
    testtype: str
    fields: Fields
    

class CucumberTestCase(TestCase):
    testtype: str = TestType.CUCUMBER.value
    gherhin_def: str = None
    xray_test_sets: List[str] = None


class ManualTestCase(TestCase):
    testtype: str = TestType.MANUAL.value
    steps: Steps = None
    xray_test_sets: List[str] = None


class GenericTestCase(TestCase):
    testtype: str = TestType.GENERIC.value
    unstructured_def: str = None
    xray_test_repository_folder: str = None


def bulk_import(requestBody: List[TestCase]) -> Response:
    header = login()
    response =  post(Endpoint.CREATE_TEST_CASE.value, requestBody, header)
    print(response.status_code, response.json())
    return response


def check_status(job_id: str) -> Response:
    header = login()
    return get(Endpoint.CHECK_IMPORT_TEST_STATUS.value.format(job_id), header)
