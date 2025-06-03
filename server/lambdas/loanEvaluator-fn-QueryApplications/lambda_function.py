from listApplications import process as listApplicationsActions
from applicationsOvertime import process as applicationsOverTimeActions
from riskDistribution import process as riskDistributionActions

def lambda_handler(event, context):
    if event["action"] == "list":
        if event["type"] == "getApplicationsOverTime":
            return applicationsOverTimeActions(event["action"], event["body"])
        elif event["type"] == "getRiskDistribution":
            return riskDistributionActions(event["action"], event["body"])
    return listApplicationsActions(event["action"], event["body"])