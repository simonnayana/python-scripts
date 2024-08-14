"""This script receives gitlab access token and uses it to rotates group tokens in gitlab and stores the new token value in aws ssm"""
#!/usr/bin/env python

import argparse
import boto3
import requests
import json
import re
from datetime import datetime, timedelta

profile = None
session = boto3.session.Session(profile_name=profile, region_name='us-west-2') 
ssm_target = session.client('ssm')


#GITLAB
group_id_array = ['XXXXX']
gitlab_api = f"https://gitlab.com/api/v4/"

date_today = datetime.now()
td = timedelta(days=180)
future_datetime = date_today + td
future_date = future_datetime.date()


def get_args():

    parser = argparse.ArgumentParser(
        allow_abbrev=False
    )
    parser.add_argument(
        "--gitlab_token",
        help="GitLab access token",
        required=True
    )

    args = parser.parse_args()
    return args


def get_group_ids(headers, gitlab_token):
    
    #For Maingroups
    git_response = requests.get(f"{gitlab_api}/groups/", headers=headers)
    groups_set = json.loads(git_response.text)
    for group in groups_set:
        print(f"Main groups : {group['id']} : {group['name']} : {group['web_url']}")
        group_id_array.append(f"{group['id']}")
        #For Subgroups
        git_subgroup_response = requests.get(f"{gitlab_api}/groups/XXXXXXX/subgroups?per_page=100", headers=headers)
        print(f"{git_subgroup_response.text}")
        subgroups_set = json.loads(git_subgroup_response.text)
        for subgroups in subgroups_set:
            print(f"Subgroups : {subgroups['id']} : {subgroups['name']} : {subgroups['web_url']}")
            group_id_array.append(f"{subgroups['id']}")    

    for group_id in group_id_array:
        check_tokens_for_expiry(group_id, headers, gitlab_token)

def check_tokens_for_expiry(group_id, headers, gitlab_token):
    
    """Get the tokens for each group id passed and check if it expires within 10 days
    headers: passes the gitlab bearer token in json form
    group_id: group id to check the expiration date of
    """   

    print(f"Getting tokens of group id {group_id}")
    git_response = requests.get(f"{gitlab_api}/groups/{group_id}/access_tokens/", headers=headers)
    #print(f"{git_response.text}")
    
    tokens_set = json.loads(git_response.text)
    for token in tokens_set:
        if(token['expires_at'] is not None):
            token_expire_date = datetime.strptime(token['expires_at'], '%Y-%m-%d')
            delta = token_expire_date - date_today
            print(f"ID: {token['id']}, Name: {token['name']}")

            if(delta.days < 10):
                git_group = requests.get(f"{gitlab_api}/groups/{group_id}/", headers=headers)
                git_group_details = json.loads(git_group.text)
                web_url = f"{git_group_details['web_url']}"
                group_name = f"{git_group_details['name']}"
                print(f"Token {token['name']} will expire in {delta.days} days. Expires on: {token['expires_at']} Group name : {group_name}, Web URL : {web_url}")
                token_name = f"{token['name']}"
                access_level = f"{token['access_level']}"
                scopes = f"{token['scopes']}"
                old_token_id = f"{token['id']}"
                print(f"old token id is : {old_token_id}")
                create_token(token_name, access_level, scopes, group_id, headers, gitlab_token)
                
def create_token(token_name, access_level, scopes, group_id, headers, gitlab_token):    
    
    """Creates new token with the same name, scope and access levels as that of the old token that expries within 10 days
    token_name: name of token to create
    access_level: access level of new token. eg. 40, 30
    scopes: scope of token to be created ["api"]
    group_id: group id to check the expiration date of
    headers: passes the gitlab bearer token in json form
    """   

    print(f"Creating new token for Name: {token_name}, Scope: {scopes}, Access level : {access_level}")    
    
    scope_convert = scopes.split(",")
    out_list = [re.sub(r'[^a-zA-Z0-9_]','',string) for string in scope_convert]
    
    data = {
        "name":f'{token_name}', 
        "scopes": out_list,
        "expires_at":f'{future_date}', 
        "access_level": f'{access_level}'
    }
        
    headers = {
        'content-type': 'application/json',
        'Authorization': f'Bearer {gitlab_token}'
    } 
            
    response = requests.post(f"{gitlab_api}/groups/{group_id}/access_tokens/", headers=headers, json=data)
    print(f"Response status code is { response.status_code }")
    if response.status_code == 201:
        
        print(f"{ response.status_code } : { response.text }")
        new_token_response = json.loads(response.text)
        print(f"{new_token_response}")
        new_token_value = f"{new_token_response['token']}"
        user_id = f"{new_token_response['user_id']}"
        print(f"Adding new token value of token {token_name} to SSM")
        ssm_target.put_parameter(
            Name=f"/gitlab/{group_id}/{token_name}/token_value",
            Value=f"{new_token_value}",
            Type='SecureString',
            Overwrite=True
        )
        update_cicd_variables(group_id, headers, new_token_value, user_id)
    

def update_cicd_variables(group_id, headers, new_token_value, user_id):

    """Update the CI/CD variables for the passed group
    group_id: groups id to update the variables for
    headers: passes the gitlab bearer token in json form
    new_token_value: token value to update
    user_id: user_id to update
    """
    print(f"Updating CI/CD variables")

    response = requests.get(f"{gitlab_api}/users/{user_id}/", headers=headers)
    
    username_response = json.loads(response.text)
    username = f"{username_response['username']}"
    user_email = username + "@noreply.gitlab.com"

    token = {
        "value":f"{new_token_value}", 
    }

    ci_username = {
        "value":f"{username}", 
    }

    ci_email = {
        "value":f"{user_email}", 
    }    
    
    ##Update Token
    group_variables_update_token = requests.put(f"{gitlab_api}/groups/{group_id}/variables/TEST_TOKEN", headers=headers, json=token)
    if group_variables_update_token.status_code == 200:
        print(f"Value of CI/CD variable TEST_TOKEN has been updated for group {group_id}")
    else:
        print(f"No value in CI/CD variable has been updated for variable TEST_TOKEN in group {group_id}")

    ##Update CI username
    group_variables_update_username = requests.put(f"{gitlab_api}/groups/{group_id}/variables/TEST_USERNAME", headers=headers, json=ci_username)
    if group_variables_update_username.status_code == 200:
        print(f"Value of CI/CD variable TEST_USERNAME has been updated for group {group_id}")
    else:
        print(f"No value in CI/CD variable has been updated for variable TEST_USERNAME in group {group_id}")

    ##Update CI email
    group_variables_update_email = requests.put(f"{gitlab_api}/groups/{group_id}/variables/TEST_EMAIL", headers=headers, json=ci_email)
    if group_variables_update_email.status_code == 200:
        print(f"Value of CI/CD variable TEST_EMAIL has been updated for group {group_id}")        
    else:
        print(f"No value in CI/CD variable has been updated for variable TEST_EMAIL in group {group_id}")

if __name__ == "__main__":
    args = get_args()    
    headers={"PRIVATE-TOKEN": args.gitlab_token }
    get_group_ids(headers, args.gitlab_token)

