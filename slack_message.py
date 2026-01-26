"""This script is used to send message to slack channels based on service url"""
import requests
from bs4 import BeautifulSoup
import sys
import json


def slack_message():

    service_url = "https://hooks.slack.com/services/XXXXXXXXXXXXXXXXXXX"  #slack webhook url; can be fetched from slack
    message = "['test']"
    title = (f"This is a test message:zap:")
    trimmed_string = message[1:][:-1]
    trimmed_length = len(trimmed_string)
    if trimmed_length == 0:
        slack_message = message
    else:
        slack_message = f' {message} \n <!subteam^XXXXXXX>  for viz'
        
    slack_data = {
        "username": "qa-bot",
        "attachments": [
            {
                "color": "#E01E5A",
                "fields": [
                    {
                        "title": title,
                        "value": slack_message,
                        "short": "true",
                    }
                ]
            }
        ]
    }
    byte_length = str(sys.getsizeof(slack_data))
    headers = {'Content-Type': "application/json", 'Content-Length': byte_length}
    response = requests.post(service_url, data=json.dumps(slack_data), headers=headers)
    if response.status_code != 200:
        raise Exception(response.status_code, response.text)

def main():

    slack_message()

if __name__ == "__main__":
    main()
