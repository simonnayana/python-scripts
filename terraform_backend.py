#!/usr/bin/env python

import argparse
import base64
import boto3
import datetime
import requests
import os
import shutil
import subprocess
import textwrap
import yaml
import zipfile
import re

TERRAFORM_REPO = "https://gitlab.com/api/v4/projects/36654020/repository/files/"

def log(message):
    if type(message) == str:
        print(textwrap.dedent(message))
    else:
        print(message)


def throw(message):
    if type(message) == str:
        raise Exception(textwrap.dedent(message))
    else:
        raise Exception(message)


def main():

    args = get_args()

    root_dir = os.path.abspath(os.path.dirname(__file__))
    config_file_path = os.path.join(
        root_dir, f"../../configs/{ args.env }.yaml")
    with open(config_file_path, "r") as config_file:
        config = yaml.full_load(config_file)

    #boto3.setup_default_session(region_name=config["aws"]["defaultRegion"])

    log(f"""
        Changing file:
            Client: { args.client_name }  
            ENV:    { args.env }
            Commit Email:      { args.commit_email }
            Commit User: { args.commit_user }
            Commit Msg:       { args.commit_msg }
    """)

    validate(args, config)

    update_terraform_main_file(args, manifest_name)

    update_manifest_ui(args,manifest_name)


def get_args():

    parser = argparse.ArgumentParser(
        allow_abbrev=False
    )

    parser.add_argument(
        "--client-name",
        help="client name",
        required=True
    )
    parser.add_argument(
        "--commit-email",
        help="commit author email",
        required=True
    )
    parser.add_argument(
        "--commit-msg",
        help="commit message",
        required=True
    )
    parser.add_argument(
        "--commit-user",
        help="commit author name",
        required=True
    )
    parser.add_argument(
        "--git-token",
        help="GitHub access token",
        required=True
    )
    parser.add_argument(
        "--env",
        choices=["ci", "qa", "stg", "prod"],
        help="source environment",
        required=True
    )
    parser.add_argument(
        "--folder",
        help="source folder",
        required=True
    )    

    args = parser.parse_args()

    return args


def validate(args):

    source_mainfile = f"{ TERRAFORM_REPO }/repository/files/%2F{ args.env }%2F{ args.client_name }%2Fmain.tf?ref=main"

    response = requests.get(source_mainfile, headers={"PRIVATE-TOKEN": args.git_token })

    if response.status_code != 200:
        throw(f"""
            Unable to get terraform main file for client: '{ args.client_name }' from env: '{ args.env }'
            URL:      { source_mainfile }
            Code:     { response.status_code }
            Response: { response.text }
        """)


def update_terraform_main_file(args):

    #
    # get source main file
    #
        
    source_mainfile = f"{ TERRAFORM_REPO }/repository/files/{args.folder}%2F{ args.env }%2F{ args.client_name }%2Fmain.tf?ref=main"

    response = requests.get(source_mainfile, headers={"PRIVATE-TOKEN": args.git_token })
       
    if response.status_code != 200:
        throw(f"""
            Unable to get source manifest:
            URL:      { source_mainfile }
            Code:     { response.status_code }
            Response: { response.text }
        """)
    response = response.json()
    source_main_b64 = response["content"]
    source_main_tf = base64.b64decode(
        source_main_b64).decode("utf8")

    source_main = list(yaml.safe_load_all(source_main_tf))

        # extract values from source manifest

        source_container = None

        for manifest in source_manifest:
            try:
                if manifest == None:
                    print("Check source manifest.yaml and delete empty content")
                    continue
                elif manifest["kind"] == "Deployment":

                    containers = manifest["spec"]["template"]["spec"]["containers"]

                    if len(containers) != 1:
                        throw(f"""
                            Expected source Deployment manifest to contain 1 and only 1 container definition.
                            Please check: { source_manifest_url }
                        """)

                    source_container = containers[0]
            except Exception as e:
                print("Error in yaml manifest, continuing with next one")
                continue

        # get target manifests

        target_manifests_url = f"{ TERRAFORM_REPO }/repository/files/{ app }%2F{ args.account }%2F{ args.target_env }%2F{ manifest_name }?ref=master"

        git_response = requests.get(target_manifests_url, headers={"PRIVATE-TOKEN": args.git_token })

        
        if git_response.status_code != 200:
            throw(f"""
                Unable to get target manifests directory:
                URL:      { target_manifests_url }
                Code:     { git_response.status_code }
                Response: { git_response.text }
            """)

        response = git_response.json()
        target_file_path = response["file_path"]
        target_manifest_b64 = response["content"]
        target_manifest_yaml = base64.b64decode(
            target_manifest_b64).decode("utf8")

        target_manifest = list(yaml.safe_load_all(target_manifest_yaml))

            # update values in target manifest

        update = False

        for manifest in target_manifest:
            try:
                if manifest == None:
                    print("Check yaml manifest and delete empty content")
                    continue
                if manifest["kind"] == "Deployment":

                    containers = manifest["spec"]["template"]["spec"]["containers"]

                    if len(containers) != 1:
                        throw(f"""
                            Expected target Deployment manifest to contain 1 and only 1 container definition.
                            Please check: { target_manifests_url }
                        """)

                    target_container = containers[0]

                    # update container (if needed)

                    if target_container["image"] != source_container["image"]:
                        target_container["image"] = source_container["image"]
                        update = True

                    if target_container["ports"][0]["containerPort"] != source_container["ports"][0]["containerPort"]:
                        target_container["ports"][0]["containerPort"] = source_container["ports"][0]["containerPort"]
                        update = True

                elif manifest["kind"] == "CronJob":

                    containers = manifest["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"]

                    if len(containers) != 1:
                        throw(f"""
                            Expected target Deployment manifest to contain 1 and only 1 container definition.
                            Please check: { target_manifests_url }
                        """)

                    target_container = containers[0]

                    if target_container["image"] != source_container["image"]:
                        target_container["image"] = source_container["image"]
                        update = True
                    # create blob
            except Exception as e:
                print("Error in yaml manifest, continuing with next one")
                continue

        if update:

            new_manifest_yaml = yaml.safe_dump_all(target_manifest)
            # prepend leading ---
            new_manifest_yaml = f"---\n{ new_manifest_yaml }"

            new_manifest_b64 = base64.b64encode(
                new_manifest_yaml.encode("utf-8")).decode("utf-8")

            payload = {
            
                "branch": "master",
                "author_email": args.commit_email,
                "content": new_manifest_b64,
                "commit_message": args.commit_msg,
                "encoding": "base64"
            
            }

            response = requests.put(target_manifests_url, headers={"PRIVATE-TOKEN": args.git_token }, json=payload)
              
            if response.status_code != 200:

                throw(f"""
                    Unable to change target for app '{ app }'.
                    Code:     { response.status_code }
                    Response: { response.text }            
                """)
            else:

                log(f"""
                    Manifest updated successfully!
                    Status Code:    { response.status_code }
                    File info:      { response.text }            
                """)

        else:

            log(f"""
                API app '{ app }' will not be updated in { target_file_path } as there were no changes detected or manifest doesn't have image.
            """)


#############################################
def create_manifest(args, manifest_name, target_app):

    current_manifest_url = f"{ TERRAFORM_REPO }/repository/files/{ target_app }%2F{ args.account }%2F{ args.target_env }%2Fmanifest.yaml?ref=master"
    new_manifest_url = f"{ TERRAFORM_REPO }/repository/files/{ target_app }%2F{ args.account }%2F{ args.target_env }%2F{ manifest_name }?ref=master"
    clean_version = re.sub(r'[^a-zA-Z0-9]', '-', args.target_version)
    
    #
    # get manifest
    #

    response = requests.get(current_manifest_url, headers={"PRIVATE-TOKEN": args.git_token})

    if response.status_code != 200:
        throw(f"""
            Unable to get existing manifest:
            URL:      { current_manifest_url }
            Code:     { response.status_code }
            Response: { response.text }
        """)

    response = response.json()

    current_manifest_b64 = response["content"]
    current_manifest_sha = response["content_sha256"]

    current_manifest_yaml = base64.b64decode(
                                current_manifest_b64).decode("utf8")

    log(f"""
        Current Manifest:
        { current_manifest_yaml }
    """)

    #
    # update manifest
    #

    new_manifest = list(
                        yaml.safe_load_all(current_manifest_yaml.replace(
                            f"{ target_app }-{ args.target_env }", 
                            f"{ target_app }-{ args.target_env }-{ clean_version }"
                            )
                        )
                    )

    new_manifest_yaml = yaml.safe_dump_all(new_manifest)
    new_manifest_yaml = f"---\n{ new_manifest_yaml }"  # prepend leading ---

    log(f"""
        New Manifest:
        { new_manifest_yaml }
    """)

    #
    # update repo
    #

    new_manifest_b64 = base64.b64encode(
        new_manifest_yaml.encode("utf-8")).decode("utf-8")

    payload = {
        "branch": "master",
        "author_email": args.commit_email,
        "content": new_manifest_b64,
        "commit_message": f"Adding manifest for version { args.target_version } for app { target_app }",
        "encoding": "base64",
    }

    response = requests.post(new_manifest_url, headers={"PRIVATE-TOKEN": args.git_token}, json=payload)

    if response.status_code == 201:
        log(f"""
            Added manifest successfully!
        """)
        update_ingress(args, target_app)
        
    else:
        throw(f"""
            Unable to update manifest:
            Code:     { response.status_code }
            Response: { response.text }
        """)


def update_ingress(args, app):

    # get source manifest
    if args.account == "build":
        path_for_ingress = "build"
    else:
        path_for_ingress = f"prod%2F{args.target_env}"
    
    ingress_url = f"{ TERRAFORM_REPO }/repository/files/{ app }%2F{ path_for_ingress }%2Fingress.yaml?ref=master"
    clean_version = re.sub(r'[^a-zA-Z0-9]', '-', args.target_version)

    #
    # get manifest
    #

    response = requests.get(ingress_url, headers={"PRIVATE-TOKEN": args.git_token})

    if response.status_code != 200:
        throw(f"""
            Unable to get existing ingress file for version update:
            URL:      { ingress_url }
            Code:     { response.status_code }
            Response: { response.text }
        """)

    response = response.json()

    current_ingress_b64 = response["content"]
    current_ingress_sha = response["content_sha256"]

    current_ingress_yaml = base64.b64decode(
        current_ingress_b64).decode("utf8")

    log(f"""
        Ingress file is :
        { current_ingress_yaml }
    """)

    #
    # update ingress
    #

    new_ingress = list(yaml.safe_load_all(current_ingress_yaml))

    for ingress in new_ingress:

        if ingress["kind"] == "Ingress":
            if { args.target_env } == "stg":
                path = f'/{ args.target_version }/'
            else:
                path = f'/{ args.target_version }/*'
            for rule in ingress["spec"]["rules"]:
                if rule["host"] in[ f"{ app }-{ args.target_env }.build.xyz.in", f"{ app }-{ args.target_env }.xyz.in", f"{ app }.xyz.in", f"{ app }-{ args.target_env }.stg.xyz.in", f"{ app }-{ args.target_env }.prod.xyz.in"]:
                    new_backend = [{'backend': 
                                        {'service': 
                                            {'name': f'{ app }-{ args.target_env }-{clean_version}-service', 
                                            'port': {'number': 443}
                                            }
                                        }, 
                                    'path': f'/{ args.target_version }', 
                                    'pathType': 'Prefix'
                                    },
                                    {'backend': 
                                        {'service': 
                                            {'name': f'{ app }-{ args.target_env }-{clean_version}-service', 
                                            'port': {'number': 443}
                                            }
                                        }, 
                                    'path': f'{ path }', 
                                    'pathType': 'Prefix'
                                    }
                                ]
                    for new_rule in new_backend: 
                        rule["http"]["paths"].insert(0, new_rule)


    new_ingress_yaml = yaml.safe_dump_all(new_ingress)
    new_ingress_yaml = f"---\n{ new_ingress_yaml }"  # prepend leading ---

    log(f"""
        New Ingress:
        { new_ingress_yaml }
    """)

    #
    # update repo
    #

    new_ingress_b64 = base64.b64encode(
        new_ingress_yaml.encode("utf-8")).decode("utf-8")

    payload = {
        "branch": "master",
        "author_email": args.commit_email,
        "content": new_ingress_b64,
        "commit_message": f"Adding ingress for version { args.target_version } for app { app }",
        "encoding": "base64",
    }

    response = requests.put(ingress_url, headers={"PRIVATE-TOKEN": args.git_token}, json=payload)

    if response.status_code == 200:

        log(f"""
            Updated ingress successfully!
        """)
        
    else:

        throw(f"""
            Unable to update manifest:
            Code:     { response.status_code }
            Response: { response.text }
        """)


if __name__ == "__main__":
    main()
