"""
Cucumber result to Jira Xray Test repository

"""
__version__ = "0.7.6"


import datetime

import cujirax.cucumber as cucumber
import cujirax.xray.import_results as result
import cujirax.xray.import_tests as test
from cujirax.cucumber import Element
from cujirax.jira import Jirakey, JiraX, Project
from loguru import logger
from collections import Counter


class DuplicateValueError(Exception):
    """Raised when a duplicate Scenario is found."""
    pass


class CuJiraX:
    def __init__(self, jira_project: str, parent_testset_key: str = None, addional_identifier: str = None) -> None:
        self.jira_project = jira_project
        self.jira = JiraX(jira_project)
        
        self.testexecution = None
        self.testexecution_name = None
        self.testexecution_desc = None
        self.parent_testset_key = parent_testset_key
        self.result_info = result.Info(summary="TBA", description="TBA")
        self.addional_identifier = addional_identifier

    def set_testsut_version(self, version: str):
        self.result_info.version = version
    
    def set_test_user(self, user: str):
        self.result_info.user = user

    def set_test_revision(self, rev: str):
        self.result_info.revision = rev

    def set_test_startdate(self, date):
        self.result_info.startDate = date

    def set_test_finishdate(self, date):
        self.result_info.finishDate = date

    def set_testexecution(self, jira_key: str):
        try:
            self.testexecution = str(Jirakey(jira_key))
        except ValueError:
            self.testexecution = None

    def set_testplan(self, testplan_key: str):
        try:
            self.result_info.testPlanKey = str(Jirakey(testplan_key))
        except ValueError:
            self.result_info.testPlanKey = None

    def set_test_environments(self, environments: list):
        self.result_info.testEnvironments = environments


    def set_testexecution_name(self, testexecution_name: str):
        self.testexecution_name = testexecution_name if testexecution_name else None

    def set_testexecution_desc(self, description: str):
        self.testexecution_desc = description


    def to_xray(
            self, 
            cucumber_json: str,
            import_result=True, 
            import_testcase=True,
            ignore_duplicate=True
        )-> list:

        s1 = cucumber.Model.parse_file(cucumber_json)
        output = []
        for f in s1.__root__:
            root = {}
            testset_name = f.uri.split("/")[-1]
            testexecution_name = self.testexecution_name or testset_name + " :: " + datetime.date.today().strftime("%Y%m%d") 
            if self.addional_identifier:
                testexecution_name = f"{self.addional_identifier} :: {testexecution_name}"

            ticket_ts, ticket_te = [
                self.jira.create_testset(
                    summary=testset_name, 
                    description=f.description or "TBA"
                ),
                self.testexecution or self.jira.create_testexecution(
                    summary=testexecution_name, 
                    description=self.testexecution_desc or f.description or "TBA",
                    labels=[f'c{datetime.date.today().strftime("%Y%m%d")}', self.addional_identifier]
                ),
            ]
            root.update({
                'test_set': str(ticket_ts),
                'testset_name': testset_name,
                'parent_testset': self.parent_testset_key,
                'test_execution': str(ticket_te),
                'testexecution_name': testexecution_name,
                'test_plan': self.result_info.testPlanKey,
                'test_environments': self.result_info.testEnvironments
            })

            # Import Test cases
            if import_testcase:
                try:
                    exists, new = self._split_elements_to_exist_and_new(
                        elements=f.elements, 
                        j=self.jira, 
                        ignore_duplicate=ignore_duplicate
                    )
                except ValueError as e:
                    raise DuplicateValueError(f"{str(ticket_te)}:{f.uri}:{str(e)}")
                
                tests = [str(n) for n in map(
                    lambda x: self._update_description_if_exist(x,self.jira), exists)]
                root.update({
                    'existing_tests': tests,
                })

                logger.info(root)
                
                test_cases = [n for n in map(lambda x: self._new_testcase(x, self.jira_project, ticket_ts, self.parent_testset_key), new)]
                test.bulk_import(test_cases) if test_cases else None
            
            # Import Results
            if import_result:
                self.result_info.summary = testexecution_name
                self.result_info.description = self.testexecution_desc or f.description or "TBA"
                
                _tests, _result = self._get_results(f.elements, self.jira, ignore_duplicate)
                logger.debug("tests:" + str(_tests) + ", result: " + _result)
                req = result.RequestBody(
                    info=self.result_info,
                    tests= _tests,
                    testExecutionKey=str(ticket_te)
                )
                res = result.import_xray_json_results(req)
                root.update({
                    'result': _result,
                    'import_result_status': res.status_code,
                    'import_result_response': res.json()
                })
            output.append(root)
        return output    
        
    
    def create_testplan(self, testplan_name:str, testplan_desc: str) -> Jirakey:
        """
        This function return Jira key, create new test plan when not found.

        It is idempotent, which means that call it multiple times with same input 
        produces the same result as call it once.
        """
        assert testplan_name, "Test plan name cannot be None"
        return self.jira.create_testplan(summary=testplan_name, description=testplan_desc)

    @classmethod
    def _get_results(cls, elements: Element, j: JiraX, ignore_duplicate):
        test_request_obj = []
        results = []
        logger.info(elements)
        if elements:
            for el in elements:
                test_name = cls.scenarioid_to_tescasename(el.id, el.keyword)
                tests = j.get_tests(test_name)
                if not tests:
                    raise ValueError("Test not created: {}".format(test_name))
                
                test_key = tests[0]
                if not ignore_duplicate:
                    if len(tests) > 1:
                        logger.error(test_name)
                        logger.error(["{}".format(t) for t in tests])
                        raise ValueError("More than 1 test key detected: ", tests, test_name)
                        
                statuses = [step.result.status.value for step in el.steps]
                agg_result = "passed" if all(s == 'passed' for s in statuses) else "failed"
                test_request_obj.append(result.Test(testKey=str(test_key), status=agg_result))
                results.append(agg_result)
            grand_result = "passed" if all(s == 'passed' for s in results) else "failed"
        else:
            grand_result = "failed"
        return test_request_obj, grand_result

    @classmethod
    def _split_elements_to_exist_and_new(cls, elements: Element, j: JiraX, ignore_duplicate):
        found= []
        not_found = []
        logger.info(elements)
        if elements:
            for el in elements:
                test_name = cls.scenarioid_to_tescasename(el.id, el.keyword)
                logger.info("searching_test_name: " + test_name)

                tests = j.get_tests(test_name)

                if tests and not ignore_duplicate:
                    if len(tests) > 1:
                        logger.error(test_name)
                        logger.error(["{}".format(t) for t in tests])
                        raise ValueError("More than 1 test key detected: ", tests, test_name)
                logger.info("found_in_jira: " + str(tests))
                found.append(el) if j.get_tests(test_name) else not_found.append(el)
            
            # check duplicate for new test
            if not ignore_duplicate:
                new_testnames = [cls.scenarioid_to_tescasename(el.id, el.keyword) for el in not_found]
                duplicates = [item for item, count in Counter(new_testnames).items() if count > 1]
                if duplicates:
                    raise ValueError("More than 1 same test detected: ", duplicates)

        return found, not_found
    
    @classmethod
    def _new_testcase(
        cls, 
        element: Element, 
        project_key: str, 
        testset_key: Jirakey=None, 
        parent_testset_key: Jirakey = None
    ):
        step_definitions = [(f"{step.keyword} {step.name}", step.result.status.value) for step in element.steps]
        test_name = cls.scenarioid_to_tescasename(element.id, element.keyword)
        test_sets = [str(x) for x in [testset_key, parent_testset_key] if x] if parent_testset_key else []
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
            # Update all Step Definition in the description
            j.update_issue_field(jira_key[0], fields={"description": "\n".join([s[0] for s in step_definitions])})
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
        