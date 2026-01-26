import boto3
import time

# --- Config ---
snapshot_id = 'xyz'
s3_bucket_name = 'rds-snapshot-archive-build'
iam_role_arn = 'arn:aws:iam::xxxxxxxxxxxx:role/test-export-role'
export_task_identifier = f"export-{snapshot_id}"
kms_key_id = 'arn:aws:kms:us-west-2:xxxxxxxxxxxx:key/kms-ket-id'
region = 'us-west-2'
status = ''

# --- RDS Client ---
rds = boto3.client('rds', region_name=region)

# --- Start Export Task ---
try:
    response = rds.start_export_task(
        ExportTaskIdentifier=export_task_identifier,
        SourceArn=f'arn:aws:rds:{region}:xxxxxxxxxxxx:snapshot:{snapshot_id}',
        S3BucketName=s3_bucket_name,
        IamRoleArn=iam_role_arn,
        KmsKeyId=kms_key_id,
        ExportOnly=[]  
    )
    print(response)
    print(f"✅ Export task started: {response['ExportTaskIdentifier']}")
except Exception as e:
    print(f"❌ Failed to start export task: {e}")

print("Checking status of export task")
while status!='COMPLETE':
    try:
        response = rds.describe_export_tasks(
            ExportTaskIdentifier=export_task_identifier
        )

        export_task = response['ExportTasks'][0]
        status = export_task['Status']
        snapshot = export_task['SourceArn']
        s3 = export_task.get('S3Bucket', 'N/A')

        print(f"📦 Export Task ID: {export_task_identifier}")
        print(f"📸 Snapshot: {snapshot}")
        print(f"🪣 S3 Bucket: {s3}")
        print(f"⏳ Status: {status}")

        if status == 'FAILED':
            print(f"❌ Failure Reason: {export_task.get('FailureCause', 'Unknown')}")
        elif status == 'COMPLETE':
            print("✅ Export completed successfully.")
        time.sleep(20)

    except Exception as e:
        print(f"❌ Error fetching export task status: {e}")
