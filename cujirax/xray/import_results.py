from enum import Enum
from typing import List
from pydantic import BaseModel
from cujirax.cucumber import Feature


class Status(str, Enum):
    PASSED = "PASSED"
    EXECUTING = "EXECUTING"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    OUTOFSCOPE = "OUT-OF-SCOPE"
    DEFERRED = "DEFERRED"
    TODO = "TO DO"


class Info(BaseModel):
    summary: str
    description: str
    testPlanKey: str
    testEnvironments: List[str] = None
    version: str = None
    user: str = None
    revision: str = None
    startDate: str = None
    finishDate: str = None


class Evidence(BaseModel):
    data: str
    filename: str
    contentType: str


class Step(BaseModel):
    status: Status
    comment: str = None
    actualResult: str = None
    evidences: List[Evidence] = None

    def to_dict(self):
        return {
            "status": self.status.value,
            "comment": self.comment,
            "actualResult": self.actualResult,
            "evidences": self.evidences
        }


class Test(BaseModel):
    testKey: str
    status: str
    actualResult: str = None
    start: str = None
    finish: str = None
    evidence: List[Evidence] = None
    examples: List[str] = None
    steps: List[Step] = None
    defects: List[str] = None


class RequestBody(BaseModel):
    info: Info
    tests: List[Test]
    testExecutionKey: str = None

