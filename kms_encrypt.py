"""This script encrypts the any plain testx data passed to variable plaintext_data using an aws kms key"""
import boto3
import base64
from datetime import datetime
from botocore.exceptions import ClientError
import pprint

region = "us-west-2"

def main(aws_region):

    session = boto3
    kms_client = session.client('kms',region_name='us-west-2')

    encoded_string = "This is a test"  
    key_alias = 'testing-kms'
    
    # Create a new KMS key
    new_key_response = kms_client.create_key()
    new_key_id = new_key_response['KeyMetadata']['KeyId']
    print(f"New Key ID: {new_key_id}")
    
    #Update alias name with new key id
    response = kms_client.update_alias(
        AliasName=f'alias/{key_alias}',
        TargetKeyId=new_key_id,
    )
    print(response)

    response = kms_client.describe_key(KeyId=f'alias/{key_alias}')
    key_id = response['KeyMetadata']['KeyId']
    encrypt_response = kms_client.encrypt(
        KeyId=f"{key_id}",
        Plaintext=encoded_string
    )
    ############ ENCRYPTION ############
    kms_encrypted_data = encrypt_response['CiphertextBlob']
    print(f"My encrypted data is: {kms_encrypted_data}") 

    
    ############ DECRYPTION ############
    decrypt_response = kms_client.decrypt(
        CiphertextBlob=kms_encrypted_data,
        KeyId=f"{key_id}"
    )
    print(decrypt_response["Plaintext"]) 
    

    
   
if __name__ == '__main__':

    main(region)