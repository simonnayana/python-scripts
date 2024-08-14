"""This script tags ec2 instance after checking the instance use"""
import boto3
from botocore.exceptions import ClientError


session = boto3.session.Session(region_name = 'us-west-2')
ec2 = session.resource('ec2')

instance_iterator = ec2.instances.all()

success = 0
fail = 0
for instance in instance_iterator:
    try:
        instance_name = next(
            item['Value'] for
            item in instance.tags
            if item.get('Key') == 'Name'
        )

        for item in instance.tags:
            if item.get('Key') == 'Use' and item.get('Value') == 'testing':
                instance.create_tags(
                    Tags=[
                        {
                            'Key': 'client',
                            'Value': "No"
                        },
                    ]
                )
                print(instance_name)
                success += 1
    except StopIteration:
        print(instance.tags)
        fail += 1
print(f'Success: {success}; Fail: {fail}')

