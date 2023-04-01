import os
import re
from atlassian import Jira
from typing import List
from pydantic import BaseModel


class Jirakey:
    value: str

    def __init__(self, value) -> None:
        self.value = value
        if not re.match(r'[A-Z][A-Z0-9_]*-[1-9][0-9]*$', value):
            raise ValueError('Invalid Jira key')

    def __repr__(self) -> str:
        return self.value


class Project(BaseModel):
    key: str


class IssueType(BaseModel):
    name: str


class Issue(BaseModel):
    summary: str
    project: Project
    issuetype: IssueType
    description: str


class JiraX(Jira):
    def __init__(self, key: str,
                 domain: str = None,
                 email: str = None,
                 secret: str = None
                 ):
        jira_domain = domain or os.getenv("JIRA_DOMAIN")
        jira_email = email or os.getenv("JIRA_EMAIL")
        jira_secret = secret or os.getenv("JIRA_SECRET")

        self.key = key
        super().__init__(
            url=f'https://{jira_domain}',
            username=jira_email,
            password=jira_secret)
        

    def get_testsets(self, summary: str) -> List[Jirakey]:
        return self.get_issues(summary=summary, type="Test Set")

    def get_testplan(self, summary: str) -> List[Jirakey]:
        return self.get_issues(summary=summary, type="Test Plan")

    def get_tests(self, summary: str) -> List[Jirakey]:
        return self.get_issues(summary=summary, type="Test")

    def get_issues(self, summary: str, type: str) -> List[Jirakey]:
        _summary = summary.replace("[", "").replace("]", "")
        query = f'issuetype="{type}" AND summary~"{_summary}" AND project="{self.key}"'
        issues = self.jql(query).get("issues")
        
        return [Jirakey(issue.get('key')) for issue in issues if issue.get('fields')['summary'] == summary]

    def link(self, parent_jira: str, child_jira: str, type="Parents"):
        """
        Common Types:
        Name, Inward, Outward
        'Blocks', 'is blocked by', 'blocks'
        'Cloners', 'is cloned by', 'clones'
        'Defect', 'created by', 'created'
        'Duplicate', 'is duplicated by', 'duplicates'
        'Issue split', 'split from', 'split to'
        'Parents', 'Child', 'Parent'
        'Problem/Incident', 'is caused by', 'causes'
        'Relates', 'relates to', 'relates to'
        'Require', 'required by', 'requires'
        'Test', 'is tested by', 'tests

        """
        return self.create_issue_link({
            "type": {"name": type},
            "inwardIssue": {"key": str(Jirakey(child_jira))},
            "outwardIssue": {"key": str(Jirakey(parent_jira))}
        })

    def _create(self, summary: str, description: str, issue_type: str) -> Jirakey:
        issue = self.get_issues(summary, issue_type)
        if issue:
            self.update_issue_field
            jira_key = issue[0]
            return jira_key

        issue = Issue(
            summary=summary,
            project=Project(key=self.key),
            issuetype=IssueType(name=issue_type),
            description=description)
        
        response = self.create_issue(fields=issue.dict())
        return Jirakey(response.get('key'))

    def create_testset(self, summary: str, description: str) -> Jirakey:
        return self._create(summary, description, "Test Set")

    def create_testexecution(self, summary: str, description: str) -> Jirakey:
        return self._create(summary, description, "Test Execution")

    def create_testplan(self, summary: str, description: str) -> Jirakey:
        return self._create(summary, description, "Test Plan")
