import boto3
import requests
import json
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
users_to_delete = [
  {
    "username": "abcxyz",
    "email": "abc@gmail.com"
  }
]
def create_session_with_retries():
    """
    Create a requests session with retry logic
    """
    session = requests.Session()
    
    retry_strategy = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


def get_user_id_by_email(access_token, environment, email, http_session):
    """
    Get user ID by email address
    """
    url_users = f"https://api.pingone.com/v1/environments/{environment}/users"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    params = {
        "filter": f'email eq "{email}"'
    }
    
    try:
        response = http_session.get(url_users, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        users_data = response.json()
        
        if '_embedded' in users_data and 'users' in users_data['_embedded']:
            users = users_data['_embedded']['users']
            if users:
                return users[0].get('id')
        
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"  Error getting user ID for {email}: {e}")
        return None


def delete_user(access_token, environment, user_id, http_session):
    """
    Delete a user by ID
    """
    url_delete = f"https://api.pingone.com/v1/environments/{environment}/users/{user_id}"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = http_session.delete(url_delete, headers=headers, timeout=30)
        response.raise_for_status()
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"  Error deleting user: {e}")
        return False


def delete_users_from_pingone():
    """
    Delete specified users from PingOne
    """
    environment = '<environment_id>'
    url_auth = '<auth_url>'
    basic_auth = '<auth_token>'

    # Create session with retry logic
    http_session = create_session_with_retries()

    # Get access token
    print("Getting access token...")
    payload = 'grant_type=client_credentials'
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Basic {basic_auth}'
    }

    try:
        response = http_session.post(url_auth, headers=headers, data=payload, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error getting token: {e}")
        return
        
    access_token = response.json()["access_token"]
    print("Access token obtained successfully\n")

    # Delete users
    print("=" * 80)
    print(f"DELETING {len(users_to_delete)} USERS FROM PINGONE")
    print("=" * 80 + "\n")
    
    deleted_count = 0
    not_found_count = 0
    failed_count = 0
    
    results = []
    
    for idx, user in enumerate(users_to_delete, 1):
        email = user['email']
        username = user['username']
        
        print(f"{idx}. Processing: {email}")
        print(f"   Username: {username}")
        
        # Get user ID
        user_id = get_user_id_by_email(access_token, environment, email, http_session)
        
        if not user_id:
            print(f"   Status: ❌ User not found")
            not_found_count += 1
            results.append({
                'email': email,
                'username': username,
                'status': 'NOT_FOUND'
            })
        else:
            print(f"   User ID: {user_id}")
            
            # Delete user
            if delete_user(access_token, environment, user_id, http_session):
                print(f"   Status: ✅ Successfully deleted")
                deleted_count += 1
                results.append({
                    'email': email,
                    'username': username,
                    'user_id': user_id,
                    'status': 'DELETED'

                })
            else:
                print(f"   Status: ❌ Failed to delete")
                failed_count += 1
                results.append({
                    'email': email,
                    'username': username,
                    'user_id': user_id,
                    'status': 'FAILED'
                })
        
        print("-" * 80)
        
        # Small delay to avoid rate limiting
        time.sleep(0.5)
    
    # Summary
    print("\n" + "=" * 80)
    print("DELETION SUMMARY")
    print("=" * 80)
    print(f"Total users to delete: {len(users_to_delete)}")
    print(f"Successfully deleted: {deleted_count}")
    print(f"Not found: {not_found_count}")
    print(f"Failed to delete: {failed_count}")
    print("=" * 80)
    
    # Save results to file
    with open('deletion_results.json', 'w', encoding='utf-8') as f:
        json.dump({
            'total': len(users_to_delete),
            'deleted': deleted_count,
            'not_found': not_found_count,
            'failed': failed_count,
            'results': results
        }, f, indent=2, ensure_ascii=False)
    
    print("\nDeletion results saved to deletion_results.json")
    
    # Show detailed results
    if not_found_count > 0:
        print("\n⚠️  Users not found:")
        for result in results:
            if result['status'] == 'NOT_FOUND':
                print(f"  - {result['email']}")
    
    if failed_count > 0:
        print("\n❌ Failed deletions:")
        for result in results:
            if result['status'] == 'FAILED':
                print(f"  - {result['email']}")
    
    if deleted_count > 0:
        print("\n✅ Successfully deleted users:")
        for result in results:
            if result['status'] == 'DELETED':
                print(f"  - {result['email']}")


if __name__ == '__main__':
    print("\n⚠️  WARNING: This will permanently delete users from PingOne!")
    print("=" * 80)
    
    delete_users_from_pingone()                    
