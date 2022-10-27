import json
import os
import sys
from urllib import request
from urllib.error import HTTPError

API_KEY = os.getenv("DIGRAPH_API_KEY")
TEST_MODE = os.getenv("TEST_MODE")
ORGANIZATION = os.getenv("CIRCLE_PROJECT_USERNAME")
REPOSITORY = os.getenv("CIRCLE_PROJECT_REPONAME")
TF_PLAN_JSON_PATH = os.getenv("TF_PLAN_JSON_PATH")
VALIDATION_URL = "https://app.getdigraph.com/api/validate/terraform"


def main():
    try:
        f = open(TF_PLAN_JSON_PATH, "r")
    except FileNotFoundError as e:
        sys.exit("No tf-plan-json file found")

    terraform_plan_file = f.read()
    terraform_plan_json_output = json.loads(terraform_plan_file)
    f.close()
    resource_changes = terraform_plan_json_output.get("resource_changes") or {}
    actual_changes = []
    for rc in resource_changes:
        if (
            rc.get("change")["actions"]
            and len(rc["change"]["actions"]) > 0
            and rc["change"]["actions"][0] != "no-op"
        ):
            actual_changes.append(rc)

    parsed_json_plan = {"resource_changes": actual_changes}
    if TEST_MODE == "1":
        print(
            f"TEST MODE: Terraform Plan resource_changes are {resource_changes}. Exiting..."
        )
        return
    issue_number = (
        int(os.getenv("CIRCLE_PULL_REQUEST").split("/")[-1])
        if os.getenv("CIRCLE_PULL_REQUEST")
        else ""
    )
    if not issue_number:
        # Fail gracefully if no CIRCLE_PULL_REQUEST variable is present
        print(
            "Skipping validation.\nReason: The CIRCLE_PULL_REQUEST variable does not exist.\nPlease check if this is a pull request related build"
        )
        return

    print(f"The event issue number: {issue_number}")
    body = {
        "terraform_plan": parsed_json_plan,
        "organization": ORGANIZATION,
        "repository": REPOSITORY,
        "event_name": "pull_request",
        "issue_number": issue_number,
    }

    data = json.dumps(body).encode("utf-8")
    print(f"API Request Data is \n{data}")
    headers = {"X-Digraph-Secret-Key": API_KEY}
    api_request = request.Request(VALIDATION_URL, headers=headers, data=data)
    try:
        api_response = request.urlopen(api_request)
    except HTTPError as e:
        sys.exit(f"API failed with {str(e)}: {json.dumps(body)}")
    except TypeError as e:
        sys.exit(f"API failed with {str(e)}: {json.dumps(body)}")

    if api_response.code == 200:
        print(f"API Response is: {api_response.msg}")
        return
    else:
        sys.exit(
            f"API exited with a non-200 code {api_response.code}: {json.dumps(body)}"
        )


if __name__ == "__main__":
    main()
