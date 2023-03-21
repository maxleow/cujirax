# cujirax
`Cu`cumber `Ji`ra and `X`ray

## Setup environment variables
```sh
export JIRA_DOMAIN="urdomain.atlassian.net"
export JIRA_EMAIL="youremail@yourcompany.com"
export JIRA_SECRET="xxxxx",

export XRAY_CLIENT_ID="xxxxx"
export XRAY_CLIENT_SECRET="xxxxx"
```

## Maintaining cucumber result json file
Make sure it is alway updated from 
`https://raw.githubusercontent.com/cucumber/cucumber-json-schema/main/schema.json`

Generating model from 
`datamodel-codegen --input schema.json --output cujirax/cucumber.py`

