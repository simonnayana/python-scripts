""" Script to find the db instance type of an rds instance when we pass db instance name """
import boto3
import argparse
from time import sleep
from datetime import datetime
from decimal import *
from botocore.exceptions import ClientError


max_db_volume_size = 0
profile = ''
session = boto3.session.Session(profile_name=profile) if profile != '' else boto3

sts = session.client('sts')

aws_account = session.client('sts').get_caller_identity()['Account']

class CustomError(Exception):
    pass


def get_db_instance_size(db_instance_name, aws_environment):
    print(f"store is {db_instance_name}")
    max_db_volume_size = 0
    db_instance_size = ''
    if aws_environment == 'dev':
        assumed_role_object = sts.assume_role(
            RoleArn="XXXXX ROLE ARN from dev XXXXXX",
            RoleSessionName="XXXXX",
            ExternalId="XXXXX"
        )  
    else:  
        assumed_role_object=sts.assume_role(
            RoleArn="XXXXX ROLE ARN from non-dev XXXXXX",
            RoleSessionName="XXXXX",
            ExternalId="XXXXX"
        )


    credentials=assumed_role_object['Credentials']

    try:
        print("Checking if rds is in us-west-2")
        rds = session.client('rds',     
                            aws_access_key_id=credentials['AccessKeyId'],
                            aws_secret_access_key=credentials['SecretAccessKey'],
                            aws_session_token=credentials['SessionToken'],
                            region_name="us-west-2")
        response = rds.describe_db_instances(
            DBInstanceIdentifier=db_instance_name
            )             
        db_volume_size = response['DBInstances'][0]['AllocatedStorage']
        max_db_volume_size = response['DBInstances'][0].get('MaxAllocatedStorage', db_volume_size + 40) 
        db_instance_size = response['DBInstances'][0]['DBInstanceClass']                       
    except:
        try:
            print("Checking if snapshot is present in us-west-2")
            response = rds.describe_db_snapshots(DBSnapshotIdentifier=f"{db_instance_name}-final-snapshot")

            # Get the snapshot size
            db_volume_size = response['DBSnapshots'][0]['AllocatedStorage']
            print(f"Snapshot Size: {db_volume_size}")
        except:
            try:            
                print("Checking if rds is in us-east-2")
                rds = session.client('rds',     
                                    aws_access_key_id=credentials['AccessKeyId'],
                                    aws_secret_access_key=credentials['SecretAccessKey'],
                                    aws_session_token=credentials['SessionToken'],
                                    region_name="us-east-2")        
                response = rds.describe_db_instances(
                    DBInstanceIdentifier=db_instance_name
                    )
                #print(f'{response}')             
                db_volume_size = response['DBInstances'][0]['AllocatedStorage']
                max_db_volume_size = response['DBInstances'][0].get('MaxAllocatedStorage', db_volume_size + 40) 
                db_instance_size = response['DBInstances'][0]['DBInstanceClass']  
            except:
                print("Checking if snapshot is present in us-east-2")
                response = rds.describe_db_snapshots(DBSnapshotIdentifier=f"{db_instance_name}-final-snapshot")

                # Get the snapshot size
                db_volume_size = response['DBSnapshots'][0]['AllocatedStorage']
                print(f"Snapshot Size: {db_volume_size}")                

    expected_max_db_volume_size = db_volume_size + round(Decimal(f"{db_volume_size}") * Decimal(.2))
    print(f"expected_max_db_volume_size: {expected_max_db_volume_size}")

    
    if expected_max_db_volume_size >= max_db_volume_size:
        required_max_db_volume_size = expected_max_db_volume_size
    else:
        required_max_db_volume_size = max_db_volume_size

    if not db_instance_size:
        print("Setting default rds size for snapshot restoration")        
        db_instance_size = 'db.t3.medium'

    print(f"DB Volume: {db_volume_size}\nDB Max Volume: {required_max_db_volume_size}\nDB Instance Size: {db_instance_size}")
    """with open('db_volume_size.txt', 'w') as f:
        f.write(str(db_volume_size)) 
        f.close() 

    with open('required_max_db_volume_size.txt', 'w') as f:
        f.write(str(required_max_db_volume_size)) 
        f.close() 

    with open('db_instance_size.txt', 'w') as f:
        f.write(str(db_instance_size)) 
        f.close() """

def get_args():
    parser = argparse.ArgumentParser(
        allow_abbrev=False
    )

    parser.add_argument(
        "--db_instance_name",
        help="client store name",
        required=True
    )

    parser.add_argument(
        "--aws-environment",
        help="AWS environment",
        required=True
    )

    args = parser.parse_args()

    return args

if __name__ == '__main__':

    args = get_args()
    get_db_instance_size(args.db_instance_name, args.aws_environment)
