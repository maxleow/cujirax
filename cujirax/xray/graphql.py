from loguru import logger
from cujirax.xray import Endpoint, login, get


def get_testset(issue_key: str, limit=10):
    
    payload = "{\"query\":\"{\\n  getTestSets(jql: \\\"key=__key__\\\", limit: 1) {\\n    total\\n    start\\n    limit\\n    results {\\n      issueId\\n      jira(fields: [\\\"key\\\"])\\n      projectId\\n      tests(limit: __limit__) {\\n        total\\n        start\\n        limit\\n        results {\\n          issueId\\n          jira(fields: [\\\"key\\\"])\\n        }\\n      }\\n    }\\n  }\\n}\",\"variables\":{}}"
    payload = payload.replace("__key__", issue_key).replace("__limit__", str(limit))
    
    logger.info(f"Get Testset details from: [key='{issue_key}', limit='{limit}']")
    
    header = login()
    response = get(endpoint=Endpoint.GRAPHQL.value, payload=payload, headers=header)
    
    logger.info("Get Testset status: " + str(response.status_code))
    logger.info(response.json())

    return response