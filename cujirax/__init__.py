"""
Cucumber result to Jira Xray Test repository

"""
__version__ = "0.1.0"


import datetime

import cujirax.cucumber as cucumber
import cujirax.xray.import_results as result
import cujirax.xray.import_tests as test
from cujirax.cucumber import Element
from cujirax.jira import Jirakey, JiraX, Project


class CuJiraX:
    def __init__(self, jira_project: str, parent_testset=None) -> None:
        self.jira_project = jira_project
        self.jira = JiraX(jira_project)
        
        self.testexecution = None
        self.testset = None
        self.testset_name = None
        self.testexecution_name = None
        self.parent_testset = parent_testset

    def set_testexcution(self, test_execution: str):
        self.testexecution = Jirakey(test_execution)

    def set_testexecution_name(self, testexecution_name: str):
        self.testexecution_name = testexecution_name

    def set_testset(self, test_set: str):
        self.testset = Jirakey(test_set)

    def set_testset_name(self, testset_name: str):
        self.testset_name = testset_name

    def to_xray(
            self, 
            cucumber_json: str, 
            testplan_key: str = None, 
            import_result=True, 
            ignore_duplicate=True
        )-> dict:

        s1 = cucumber.Model.parse_file(cucumber_json)
        output = {}
        for f in s1.__root__:
            testset_name = self.testset_name or f.uri.split("/")[-1]
            testexecution_name = self.testexecution_name or datetime.date.today().strftime("%Y%m%d") + " :: " + testset_name

            ticket_ts, ticket_te = [
                self.testset or self.jira.create_testset(testset_name, f.description or "TBA"),
                self.testexecution or self.jira.create_testexecution(testexecution_name, f.description or "TBA"),
            ]

            output['test_set'] = ticket_ts
            output['testset_name'] = testset_name
            output['parent_testset'] = self.parent_testset
            output['test_execution'] = ticket_te
            output['test_execution_name'] = testexecution_name
            output['test_plan'] = testplan_key
            
            # Import Test cases
            exists, new = self._split_elements_to_exist_and_new(f.elements, self.jira, ignore_duplicate)
            
            print("new:", len(new))
            print("exists", len(exists))
            tests = [n for n in map(lambda x: self._update_description_if_exist(x,self.jira), exists)]
            output['tests'] = tests
            
            test_cases = [n for n in map(lambda x: self._new_testcase(x,ticket_ts, self.parent_testset, self.jira_project), new)]
            test.bulk_import(test_cases) if test_cases else None
            
            # Import Results
            if import_result:
                _tests = self._get_results(f.elements, self.jira, ignore_duplicate)
                req = result.RequestBody(
                    info=result.Info(
                        summary=testexecution_name,
                        description=f.description or "TBA",
                        testPlanKey=str(testplan_key) if testplan_key else testplan_key
                    ),
                    tests= _tests,
                    testExecutionKey=str(ticket_te)
                )
                res = result.import_xray_json_results(req)
                print(res.status_code, res.json())
                output['import_status'] = res.status_code
        return output    
        
    
    def create_testplan(self, testplan_name:str, testplan_desc: str) -> Jirakey:
        assert testplan_name, "Test plan name cannot be None"
        return self.jira.create_testplan(summary=testplan_name, description=testplan_desc)

    @classmethod
    def _get_results(cls, elements: Element, j: JiraX, ignore_duplicate):
        result_tests = []
        for el in elements:
            test_name = cls.scenarioid_to_tescasename(el.id, el.keyword)
            tests = j.get_tests(test_name)
            assert tests, "Test not created: {}".format(test_name)
            
            test_key = tests[0] if ignore_duplicate else None
            assert test_key, "Test key cannot be None"
            
            # result.Test(testKey=test_key, status=result.Status.EXECUTING.value)
            statuses = [step.result.status.value for step in el.steps]
            agg_result = "passed" if all(s == 'passed' for s in statuses) else "failed"
            print(test_key, agg_result)
            result_tests.append(result.Test(testKey=str(test_key), status=agg_result))
        return result_tests

    @classmethod
    def _split_elements_to_exist_and_new(cls, elements: Element, j: JiraX, ignore_duplicate):
        found= []
        not_found = []
        
        for el in elements:
            test_name = cls.scenarioid_to_tescasename(el.id, el.keyword)
            tests = j.get_tests(test_name)
            if tests and not ignore_duplicate:
                assert len(tests) == 1, "Duplicate key detected: {}".format(tests)
            print("[searching...]", test_name, tests)
            found.append(el) if j.get_tests(test_name) else not_found.append(el)

        return found, not_found
    
    @classmethod
    def _new_testcase(cls, element: Element, testset_key: Jirakey, parent_testset_key: Jirakey, project_key: str):
        step_definitions = [(f"{step.keyword} {step.name}", step.result.status.value) for step in element.steps]
        test_name = cls.scenarioid_to_tescasename(element.id, element.keyword)
        test_sets = [str(x) for x in [testset_key, parent_testset_key] if x]

        return test.CucumberTestCase(
            fields=test.Fields(
                summary=test_name, 
                project=Project(key=project_key),
                description="\n".join([s[0] for s in step_definitions])
            ),
            xray_test_sets=test_sets
        )
    
    @classmethod
    def _update_description_if_exist(cls, el: Element, j: JiraX)-> Jirakey:
        test_name = cls.scenarioid_to_tescasename(el.id, el.keyword)
        step_definitions = [(f"{step.keyword} {step.name}", step.result.status.value) for step in el.steps]

        jira_key = j.get_tests(test_name)
        if jira_key: 
            print("found test:", jira_key[0])
            j.jira.update_issue_field(jira_key[0], fields={"description": "\n".join([s[0] for s in step_definitions])})
            return jira_key[0]

    @staticmethod
    def scenarioid_to_tescasename(scenario_id: str, scenario_type: str):
        translation_table = str.maketrans('+-', '  ')

        if scenario_type == "Scenario Outline":
            featurename_testname, version = scenario_id.split(";;")
            feature_name, test_name = featurename_testname.split(";")
            feature_name = feature_name.translate(translation_table)
            test_name = test_name.translate(translation_table)

            return f"{feature_name} :: {test_name} {version}"
        else:
            feature_name, test_name = scenario_id.split(";")
            feature_name = feature_name.translate(translation_table)
            test_name = test_name.translate(translation_table)

            return f"{feature_name} :: {test_name}"
        