from pydantic import BaseModel

from cujirax.cucumber import Feature
from cujirax.jira import Project
from cujirax.xray import Authentication, Endpoint, Header, post
from enum import Enum
from typing import List


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


class TestCase(BaseModel):
    testtype: str
    fields: Fields
    description: str = None


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


def bulk_import(
        authentication: Authentication,
        requestBody: List[TestCase]
):
    header = Header()
    response = post(Endpoint.AUTHENTICATE, authentication, header)
    if response.status_code == 200:
        header.Authorization = "Bearer " + eval(response.text)
        return post(Endpoint.CREATE_TEST_CASE, requestBody, header)
    
    raise Exception("Authentication error: Invalid credentials")
