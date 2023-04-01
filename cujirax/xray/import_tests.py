import time
from enum import Enum
from typing import List

from pydantic import BaseModel
from requests import Response

from cujirax.jira import Project
from cujirax.xray import Endpoint, get, login, post

from loguru import logger

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


def bulk_import(requestBody: List[TestCase], wait_until_success=True) -> Response:
    header = login()
    response =  post(Endpoint.CREATE_TEST_CASE.value, requestBody, header)
    logger.info("Test bulk import status: " + str(response.status_code))
    logger.info(response.json())
    if wait_until_success and response.status_code == 200:
        return check_status_retry(response.json().get('jobId'))
    return response


def check_status(job_id: str) -> Response:
    header = login()
    return get(Endpoint.CHECK_IMPORT_TEST_STATUS.value.format(job_id), header)

def check_status_retry(job_id: str) -> Response:
    max_retries = 60
    retry_interval_secs = 1
    
    for i in range(max_retries):
        response = check_status(job_id)
        status = response.json().get('status')
        if status == 'successful':
            return response
        else:
            logger.info(f'Retry {i+1} - status: {status}')
            time.sleep(retry_interval_secs)
    
    raise Exception('Max retries exceeded - import test status not successful')

