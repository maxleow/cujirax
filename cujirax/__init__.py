"""
Cucumber result to Jira Xray Test repository

"""
from atlassian import Jira
import json
import requests
import os
from enum import Enum
from typing import Union
import datetime
import base64
from . import cucumber
__version__ = "0.1.0"


class Xray(Enum):
    CREATE_TEST_CASE = "/api/v2/import/test/bulk"
    IMPORT_RESULT = "/api/v2/import/execution"


class IssueType(Enum):
    TEST_SET = "Test Set"
    TEST = "Test"


class TestType(Enum):
    CUCUMBER = "Cucumber"
    MANUAL = "Manual"


class CuJiraX:
    def __init__(self, root_node: str) -> None:
        jira_domain = os.getenv("JIRA_DOMAIN")
        jira_email = os.getenv("JIRA_EMAIL")
        jira_secret = os.getenv("JIRA_SECRET")

        xray_domain = os.getenv("XRAY_DOMAIN")
        xray_client_id = os.getenv("XRAY_CLIENT_ID")
        xray_client_secret = os.getenv("XRAY_CLIENT_SECRET")

        self.xray_url = f"https://{xray_domain}"
        self.root_node = root_node

        payload = json.dumps({
            "client_id": xray_client_id,
            "client_secret": xray_client_secret
        })

        response = requests.request("POST", f"{self.xray_url}/api/v2/authenticate", headers={
                                    'Content-Type': 'application/json'}, data=payload)
        self.xray_headers = {
            'Authorization': f'Bearer {eval(response.text)}',
            'Content-Type': 'application/json'
        }

        self.jira = Jira(
            url=f'https://{jira_domain}',
            username=jira_email,
            password=jira_secret)


    def update_testcase(self, payloads: list):
        keys = [i['key'] for item in payloads 
                for i in self.search(item['fields']['summary'], IssueType.TEST, item['fields']['project']['key'])]
        return keys


    def create_testcase(self, payloads: list):
        new_testcase = [p for p in payloads if not self.search(
            p['fields']['summary'], IssueType.TEST, p['fields']['project']['key'])]

        return self.xray_post(Xray.CREATE_TEST_CASE, new_testcase)

    def xray_post(self, xray_endpoint: Xray, payload: list):
        url = f"{self.xray_url}{xray_endpoint.value}"
        print("POST", url)
        response = requests.request(
            "POST", url, headers=self.xray_headers, data=json.dumps(payload))

        if response.status_code == 200:
            self.job_id = response.json().get('jobId')
        return response

    def check_testcase_creation_status(self):
        url = f"{self.xray_url}/api/v2/import/test/bulk/{self.job_id}/status"
        response = requests.request("GET", url, headers=self.xray_headers)
        print(response)
        return response

    def update_result_from_cucumber_json(
        self, json_file: str,
        project_key: str,
        test_plan_key: str,
        test_execution_name: str,
        test_execution_desc: str,
        test_environment: str = "",
        create_testcase=True,
    ):
        features = cucumber.from_result_file(json_file)

        if create_testcase:
            for f in features:
                testset_key = self.create_testset(
                        f.name, f.description, key=project_key)
                # Link to parent automation ticket
                self.create_link(testset_key, self.root_node)
                
                payloads = []
                for s in f.scenarios:
                    summary = f"{f.name} :: {s.name}"
                    payloads.append(CuJiraX.construct_xray_tc_import(
                        summary=summary,
                        project_key=testset_key.split('-')[0],
                        testsets=[testset_key, self.root_node],
                        description='\n'.join(s.steps)
                    ))
                self.create_testcase(payloads)
        
        tests = []
        for f in features:
            for s in f.scenarios:
                jira_key = self.search(
                    summary=f"{f.name} :: {s.name}",
                    issue_type=IssueType.TEST,
                    project_key=project_key)[0]

                statuses = [step.result.status for step in s.steps]
                status = "PASSED" if s['passed'] else "FAILED"
                tests.append(CuJiraX.construct_xray_result_test(
                    test_key=jira_key['key'],
                    test_plan_key=test_plan_key,
                    status=status
                ))

        payload = CuJiraX.construct_xray_result_import(
            testrun_summary=test_execution_name,
            test_plan_key= test_plan_key,
            test_environment=test_environment,
            testrun_description=test_execution_desc,
            tests=tests
        )
        print(payload)
        return self.xray_post(Xray.IMPORT_RESULT, payload)

    @staticmethod
    def from_cucumber_json(json_file: str) -> dict:
        with open(json_file) as f:
            results = json.load(f)
            features = [{
                "test_set": r.get('uri').split("/")[-1],
                "description": r.get('description'),
                "elements": r.get('elements')
            } for r in results]

            scenarios = [{
                'feature_name': f.get('test_set'),
                'feature_desc': f.get('description'),
                'test_name': CuJiraX.scenarioid_to_tescasename(e.get('id'), e.get('keyword')),
                'steps': e.get('steps')
            } for f in features for e in f['elements'] if f.get('elements')]

            for s in scenarios:
                step_definitions = [
                    (f"{sd['keyword']} {sd['name']}", sd['result']['status']) for sd in s['steps']]

                s['steps'] = "\n".join([s[0] for s in step_definitions])
                s['passed'] = all(
                    [True if s[1] == 'passed' else False for s in step_definitions])

            return scenarios

    @staticmethod
    def scenarioid_to_tescasename(scenario_id: str, scenario_type: str):
        translation_table = str.maketrans('+-', '  ')

        if scenario_type == "Scenario Outline":
            featurename_testname, version = scenario_id.split(";;")
            feature_name, test_name = featurename_testname.split(";")
            feature_name = feature_name.translate(translation_table)
            test_name = test_name.translate(translation_table)

            return f"[{feature_name}] {test_name} {version}"
        else:
            feature_name, test_name = scenario_id.split(";")
            feature_name = feature_name.translate(translation_table)
            test_name = test_name.translate(translation_table)

            return f"{feature_name} :: {test_name}"

    @staticmethod
    def construct_xray_tc_import(summary: str, description: str,
                                 project_key: str, testsets: list,
                                 steps: Union[str, list, None] = None, test_type: TestType = TestType.CUCUMBER):
        payload = {
            "testtype": test_type.value,
            "fields": {
                "summary": summary,
                "description": description,
                "project": {
                    "key": project_key
                }
            },
            "steps": steps,
            "xray_test_sets": testsets
        }

        if not steps or test_type == TestType.CUCUMBER:
            payload.pop('steps')
        if test_type == TestType.CUCUMBER and steps:
            payload['gherkin_def'] = steps

        return payload

    @staticmethod
    def construct_xray_result_import(
        testrun_summary: str,
        test_plan_key: str,
        test_environment: str,
        tests: list,
        testrun_description: str = "TBA"
    ):

        payload = {
            "info": {
                "summary": testrun_summary,
                "description": testrun_description,
                "testPlanKey": test_plan_key,
                "testEnvironments": [test_environment]
            },
            "tests": tests
        }
        return payload

    @staticmethod
    def construct_xray_result_test(
        test_key: str,
        status: str,
        test_plan_key: str,
        cucumber_json_file: str = "",
        test_comment: str = "TBA"
    ) -> dict:
        now = datetime.datetime.now()
        
        payload = {
            "testKey": test_key,
            "comment": test_comment,
            "status": status,
            "evidence": None
        }
        if cucumber_json_file:
            with open(cucumber_json_file, 'rb') as file:
                file_content = file.read()
                data_base64 = base64.b64encode(file_content).decode('utf-8')
                evidence = [
                    {
                        "data": data_base64,
                        "filename": f"{test_plan_key}_{test_key}_{now.isoformat()}.json",
                        "contentType": "application/json"
                    }
                ]
                payload['evidence'] = evidence
        else:
            payload.pop("evidence")
        
        return payload
