import json
from loguru import logger
from jinja2 import Template
from cujirax.xray import login
from retrying import retry
from graphqlclient import GraphQLClient

from cujirax.xray.import_results import Status


class TMS():

    def __init__(self, testplan_key: str):
        """
        Initialize the TMS instance with authentication and test plan details.

        :param testplan_key: Key for the test plan.
        """
        self.header = login()
        self.testplan_key = testplan_key
        self.client = GraphQLClient(
            'https://xray.cloud.getxray.app/api/v2/graphql')
        self.client.inject_token(self.header.Authorization)
        self.testplan_id = self.fetch_issue_id('getTestPlans', testplan_key)

    def run_graphql_query(self, query_template, **kwargs) -> dict:
        """
        Execute a GraphQL query with specified parameters.

        :param query_template: A Jinja template string for the GraphQL query.
        :param kwargs: Arguments to render in the Jinja template.
        :return: The 'data' portion of the GraphQL response.
        """
        query = Template(query_template).render(**kwargs)
        logger.info(query)
        result = json.loads(self.client.execute(query))

        if 'errors' in result:
            logger.error(result['errors'])
            raise ValueError(result['errors'])

        logger.info(result)
        return result['data']

    def fetch_issue_id(self, method: str, key: str) -> str:
        """
        Retrieve an issue ID based on a specified method and key.

        :param method: The GraphQL method to use for retrieving the issue ID.
        :param key: The key associated with the issue.
        :return: The issue ID.
        """
        logger.info(f"Fetching issue id by key: {key} using method: {method}")
        query_template = '''
            {
                {{ method }}(jql: "key={{ key }}", limit: 1) {
                    results {
                        issueId
                    }
                }
            }
        '''
        result = self.run_graphql_query(query_template, method=method, key=key)
        return result[method]['results'][0]['issueId']

    @retry(stop_max_attempt_number=10, wait_fixed=5000)
    def fetch_testplan_id(self, key) -> str:
        """
        Retrieve a test plan ID based on its key.

        :param key: The key associated with the test plan.
        :return: The test plan ID.
        """
        return self.fetch_issue_id('getTestPlans', key)

    def assign_test_to_testset(self, test_key, testset_key) -> dict:
        """
        Add a test to a test set.

        :param test_key: The key of the test.
        :param testset_key: The key of the test set.
        :return: The result of the mutation.
        """
        mutation_template = '''
            mutation {
                addTestsToTestSet(
                    issueId: "{{ testset_id }}",
                    testIssueIds: ["{{ test_id }}"]
                ) {
                    addedTests
                    warning
                }
            }
        '''
        return self.run_graphql_query(
            mutation_template,
            testset_id=self.fetch_issue_id('getTestSets', testset_key),
            test_id=self.fetch_issue_id('getTests', test_key)
        )

    def assign_tests_to_plan(self, test_id: str, testplan_id: str) -> dict:
        """
        Add a test to a test plan.

        :param test_id: The ID of the test.
        :param testplan_id: The ID of the test plan.
        :return: The result of the mutation.
        """
        mutation_template = '''
            mutation {
                addTestsToTestPlan(
                    issueId: "{{ testplan_id }}",
                    testIssueIds: ["{{ test_id }}"]
                ) {
                    addedTests
                    warning
                }
            }
        '''
        return self.run_graphql_query(
            mutation_template,
            testplan_id=testplan_id,
            test_id=test_id
        )

    def assign_tests_to_execution(self, test_id: str, test_execution: str) -> dict:
        """
        Add tests to a test execution.

        :param test_id: The ID of the test.
        :param test_execution: The key of the test execution.
        :return: The result of the mutation.
        """
        mutation_template = '''
            mutation {
                addTestsToTestExecution(
                    issueId: "{{ te_id }}",
                    testIssueIds: ["{{ test_id }}"]
                ) {
                    addedTests
                    warning
                }
            }
        '''
        return self.run_graphql_query(
            mutation_template,
            te_id=self.fetch_issue_id('getTestExecutions', test_execution),
            test_id=test_id
        )

    def set_testrun_status(self, testrun_id: str, status: str):
        """
        Update the status of a test run.

        :param testrun_id: The ID of the test run.
        :param status: The new status to set.
        :return: The result of the mutation.
        """
        mutation_template = '''
            mutation {
                updateTestRunStatus(
                    id: "{{ testrun_id }}",
                    status: "{{ status }}"
                )
            }
        '''
        return self.run_graphql_query(
            mutation_template,
            testrun_id=testrun_id,
            status=Status[status]
        )

    def assign_execution_to_plan(self, testexecution_id: str):
        """
        Add a test execution to a test plan.

        :param testexecution_id: The ID of the test execution.
        :return: The result of the mutation.
        """
        mutation_template = '''
            mutation {
                addTestExecutionsToTestPlan(
                    issueId: "{{ testplan_id }}",
                    testExecIssueIds: ["{{ testexecution_id }}"]
                ) {
                    addedTestExecutions
                    warning
                }
            }
        '''
        return self.run_graphql_query(
            mutation_template,
            testplan_id=self.testplan_id,
            testexecution_id=testexecution_id
        )
