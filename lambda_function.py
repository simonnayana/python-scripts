import json
import logging
import boto3
import botocore

logging.getLogger().setLevel(logging.INFO)
log = logging.getLogger(__name__)

# Instantiate Boto3 client on AWS service API called
iam_client = boto3.client("iam")
ec2_client = boto3.client("ec2")
ec2_resource = boto3.resource("ec2")
ssm_client = boto3.client("ssm")


def lambda_handler(event, context):

    resource_tags = []
    # Parse the passed CloudTrail event
    event_fields = cloudtrail_event_parser(event)

    # Check for IAM User initiated event & get any associated resource tags
    if event_fields.get("iam_user_name"):
        resource_tags.append(
            {"Key": "IAM User Name", "Value": event_fields["iam_user_name"]}
        )

    # Check for IAM assumed role initiated event & get any associated resource tags
    if event_fields.get("role_name"):
        resource_tags.append(
            {"Key": "IAM_Role_Name", "Value": event_fields["role_name"]}
        )
        iam_role_resource_tags = get_iam_role_tags(event_fields["role_name"])
        if iam_role_resource_tags:
            resource_tags += iam_role_resource_tags

        ssm_parameter_resource_tags = get_ssm_parameter_tags(
            role_name=event_fields["role_name"], user_id=event_fields["user_id"]
        )
        if ssm_parameter_resource_tags:
            resource_tags += ssm_parameter_resource_tags
        print(f"Resource_tags are {resource_tags}")

    # Tag EC2 instances listed in the CloudTrail event
    if event_fields.get("instances_set"):
        for item in event_fields.get("instances_set").get("items"):
            ec2_instance_id = item.get("instanceId")
            if set_ec2_instance_attached_vols_tags(ec2_instance_id, resource_tags):
                log.info("'statusCode': 200")
                log.info(f"'Resource ID': {ec2_instance_id}")
                log.info(f"'body': {json.dumps(resource_tags)}")

            else:
                log.info("'statusCode': 500")
                log.info(f"'No tags applied to Resource ID': {ec2_instance_id}")
                log.info(f"'Lambda function name': {context.function_name}")
                log.info(f"'Lambda function version': {context.function_version}")
    else:
        log.info("'statusCode': 200")
        log.info(f"'No Amazon EC2 resources to tag': 'Event ID: {event.get('id')}'")

def cloudtrail_event_parser(event):
    # Extract details from AWS CloudTrail resource creation event
    returned_event_fields = {}

    # Check if an IAM user created these EC2 instances & get that user
    if event.get("detail").get("userIdentity").get("type") == "IAMUser":
        returned_event_fields["iam_user_name"] = (
            event.get("detail").get("userIdentity").get("userName", "")
        )

    # Get the assumed IAM role name used to create the new EC2 instance(s)
    if event.get("detail").get("userIdentity").get("type") == "AssumedRole":
        # Check if optional Cloudtrail sessionIssuer field indicates assumed role credential type
        # If so, extract the IAM role named used during EC2 instance creation
        if (event.get("detail").get("userIdentity").get("sessionContext").get("sessionIssuer").get("type") == "Role"):
            role_arn = (event.get("detail").get("userIdentity").get("sessionContext").get("sessionIssuer").get("arn"))
            role_components = role_arn.split("/")
            returned_event_fields["role_name"] = role_components[-1]
            # Get the user ID who assumed the IAM role
            if event.get("detail").get("userIdentity").get("arn"):
                user_id_arn = event.get("detail").get("userIdentity").get("arn")
                user_id_components = user_id_arn.split("/")
                returned_event_fields["user_id"] = user_id_components[-1]
            else:
                returned_event_fields["user_id"] = ""
        else:
            returned_event_fields["role_name"] = ""

    # Extract & return the list of new EC2 instance(s) and their parameters
    returned_event_fields["instances_set"] = (
        event.get("detail").get("responseElements").get("instancesSet")
    )
    return returned_event_fields 

def get_iam_role_tags(role_name):
    # Get resource tags assigned to a specified IAM role.

    try:
        response = iam_client.list_role_tags(RoleName=role_name)
        return response.get("Tags")

    except botocore.exceptions.ClientError as error:
        log.error(f"Boto3 API returned error:  {error}")
        return None

def set_ec2_instance_attached_vols_tags(ec2_instance_id, resource_tags):
    # Apply resource tags to EC2 instances & attached EBS volumes
    try:
        response = ec2_client.create_tags(
            Resources=[ec2_instance_id], Tags=resource_tags
        )
        response = ec2_client.describe_volumes(
            Filters=[{"Name": "attachment.instance-id", "Values": [ec2_instance_id]}]
        )
        try:
            for volume in response.get("Volumes"):
                ec2_vol = ec2_resource.Volume(volume["VolumeId"])
                vol_tags = ec2_vol.create_tags(Tags=resource_tags)
            return True
        except botocore.exceptions.ClientError as error:
            log.error(f"Boto3 API returned error: {error}")
            log.error(f"No Tags Applied To: {volume['VolumeId']}")
            return False
    except botocore.exceptions.ClientError as error:
        log.error(f"Boto3 API returned error: {error}")
        log.error(f"No Tags Applied To: {ec2_instance_id}")
        return False

def get_ssm_parameter_tags(iam_user_name=None, role_name=None, user_id=None):
    """Get resource tags stored in AWS SSM Parameter Store.
    """
    if role_name:
        path_string = f"/auto-tag/{role_name}/tag"
    else:
        path_string = ""
    if path_string:
        try:
            get_parameter_response = ssm_client.get_parameters_by_path(
                Path=path_string, Recursive=True, WithDecryption=True
            )
            if get_parameter_response.get("Parameters"):
                tag_list = []
                for parameter in get_parameter_response.get("Parameters"):
                    path_components = parameter["Name"].split("/")
                    tag_key = path_components[-1]
                    tag_list.append({"Key": tag_key, "Value": parameter.get("Value")})
                return tag_list
            else:
                return None
        except botocore.exceptions.ClientError as error:
            log.error(f"Boto3 API returned error: {error}")
            return None
    else:
        return None
