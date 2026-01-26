import boto3
import argparse

from time import sleep
from datetime import datetime
from botocore.exceptions import ClientError

profile = ''
session = boto3.session.Session(profile_name=profile) if profile != '' else boto3

sts = session.client('sts')

def get_args():
    parser = argparse.ArgumentParser(
        allow_abbrev=False
    )

    parser.add_argument(
        "--storename",
        help="Target instance",
        required=True
    )

    parser.add_argument(
        "--aws_environment",
        help="AWS environment",
        required=True
    )

    args = parser.parse_args()

    return args


def main(storename, aws_environment):
    ssm = session.client('ssm', region_name="us-west-2")
    s3 = session.client('s3')
    remove_ssm_resources(s3,ssm, storename, aws_environment)

def remove_ssm_resources(s3, ssm, storename, aws_environment):
    """Look for SSM resources and delete them and backup values in S3

    @param ssm: Boto3 SSM client
    @param storename: Client Name
    @type storename: str
    @param aws_environment: aws env
    @type aws_environment: str
    @return: None
    @rtype: None
    """

    search_string = f'/myfolder/{storename}/'
    all_parameters_list = []

    response = ssm.get_parameters_by_path(
        Path=search_string,
        WithDecryption=True,
        Recursive=True
    )
    
    all_parameters_list = [(x['Name'], x['Value']) for x in response.get('Parameters',[])]

    while response.get('NextToken') is not None:
        response = ssm.get_parameters_by_path(
            Path=search_string,
            WithDecryption=True,
            Recursive=True,
            NextToken=response.get('NextToken')
        )
        # Append parameters from the response to the list
        all_parameters_list.extend([(x['Name'], x['Value']) for x in response.get('Parameters',[])])

    print(f"all_parameters_list is {all_parameters_list}")


    if aws_environment != "build":
        print(f"writing SSM to file")
        ssm_file_name = f'{storename}.txt'
        with open(ssm_file_name, 'w') as file:
            for param_name, param_value in all_parameters_list:
                write_to_file = f"{param_name} : {param_value}\n"
                file.write(write_to_file)
        file.close()
        print("Upload file to s3 prod-churned-ssm")
        try:
            upload_response = s3.put_object(Bucket='prod-churned-ssm', Key=ssm_file_name, Body=open(ssm_file_name, 'rb'))
            if upload_response is not None and 'ResponseMetadata' in upload_response and 'HTTPStatusCode' in upload_response['ResponseMetadata']:
                print("Upload successful. Response status code:", upload_response['ResponseMetadata']['HTTPStatusCode'])
                for param_name, param_value in all_parameters_list:
                    print(f"Deleting from SSM: {param_name}")
                    ssm.delete_parameter(Name=param_name)                
            else:
                print("Upload failed: No response or missing metadata. SSM parameters not deleted.")
        except Exception as e:
            print("Exception:", e)
                
    else:
        print("No SSM values will be saved for build")
        for param_name, param_value in all_parameters_list:
            print(f"Deleting from SSM: {param_name}")
            ssm.delete_parameter(Name=param_name)

if __name__ == '__main__':


    storename = "test-ubuntu-patch"
    aws_environment = "build"
    #args = get_args()
    #main(args.storename, args.aws_environment)
    main(storename, aws_environment)
