import os
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from core.tool import Tool, tool
from typing import List, Dict, Tuple, Any
import base64


# Scopes: the permissions that the application will request from the user
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

@tool
def login():
    """ Logs in to the Gmail API using OAuth2 credentials."""
    load_dotenv()

    creds = None
    token_path = 'auth/mail_sorter/user_credentials.json'
    credentials_path = 'auth/mail_sorter/credentials.json'

    # Step 1: Try to load credentials only if file exists and is not empty
    if os.path.exists(token_path) and os.path.getsize(token_path) > 0:
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as e:
            print(f"⚠️ Invalid credentials file. Will prompt login. Reason: {e}")
            creds = None

    # Step 2: Refresh expired credentials if possible
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            print(f"⚠️ Failed to refresh credentials. Will prompt login. Reason: {e}")
            creds = None

    # Step 3: If no valid creds, trigger browser login and save token
    if not creds or not creds.valid:
        if not os.path.exists(credentials_path):
            raise FileNotFoundError(
                f"Missing '{credentials_path}'! Get this from the Google Cloud Console "
                "(OAuth client ID, Desktop App, download JSON)."
            )
        # Inside your login() function, after the flow line:
        print("🔐 No valid credentials found. Opening browser for Google login...")
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
        creds = flow.run_local_server(port=0)

        # 👇 Add these debug prints
        print(f"✅ Received credentials: {creds is not None}")
        print(f"📄 Token JSON preview: {creds.to_json()[:100]}...")  # peek at the first 100 chars

        # Save token
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        with open(token_path, 'w') as token_file:
            token_file.write(creds.to_json())
        print("💾 Token saved.")


    # Step 5: Return Gmail API service
    return build('gmail', 'v1', credentials=creds)



### Let's see if the snippet is enough to sort the emails
@tool
def getUnclassifiedEmails(number: int = 20) -> List[Dict[str, Any]]:
    """
    Returns a list of unclassified emails from the inbox, wether read or unread.
    
    Arguments:
        number (int): Maximum number of emails to retrieve.
        
    Returns:
        List[Dict[str, Any]]: A list of email details including id, subject, sender, date, and snippet.
    """
    service = login()

    # get the emails
    results = service.users().messages().list(
        userId='me',
        labelIds=['INBOX'],
        maxResults=number
        ).execute()
    # extract the messages from the request
    messages = results.get('messages', [])

    if not messages:
        print("No unsorted emails found.")
        return []
    
    emails = []
    for message in messages:
        # get the message details
        msg = service.users().messages().get(userId='me', id=message['id']).execute()

        # extract the header information
        headers = msg['payload']['headers']
        subject = next((header['value'] for header in headers if header['name'].lower() == 'subject'), 'No Subject')
        sender = next((header['value'] for header in headers if header['name'].lower() == 'from'), 'Unknown')
        date = next((header['value'] for header in headers if header['name'].lower() == 'date'), 'Unknown')

        emails.append({
            'id': message['id'],
            'subject': subject,
            'sender': sender,
            'date': date,
            'snippet': msg['snippet']
        })
    
    return emails

@tool
def getUnreadUnclassifiedEmails(number: int = 20) -> List[Dict[str, Any]]:
    """
    Returns a list of unread unclassified emails from the inbox.
    
    Arguments:
        number (int): Maximum number of emails to retrieve.
        
    Returns:
        List[Dict[str, Any]]: A list of email details including id, subject, sender, date, and snippet.
    """
    service = login()

    # get the emails
    results = service.users().messages().list(
        userId='me',
        labelIds=['INBOX'],
        q='is:unread',
        maxResults=number
        ).execute()
    # extract the messages from the request
    messages = results.get('messages', [])

    if not messages:
        print("No unsorted emails found.")
        return []
    
    emails = []
    for message in messages:
        # get the message details
        msg = service.users().messages().get(userId='me', id=message['id']).execute()

        # extract the header information
        headers = msg['payload']['headers']
        subject = next((header['value'] for header in headers if header['name'].lower() == 'subject'), 'No Subject')
        sender = next((header['value'] for header in headers if header['name'].lower() == 'from'), 'Unknown')
        date = next((header['value'] for header in headers if header['name'].lower() == 'date'), 'Unknown')

        emails.append({
            'id': message['id'],
            'subject': subject,
            'sender': sender,
            'date': date,
            'snippet': msg['snippet']
        })
    
    return emails


@tool
def getEmailFullBody(id: str) -> str:
    """
    Gets the full body (contents) of an email, in case the snippet wasn't enough.

    Arguments:
        id (str): The ID of the email to retrieve.

    Returns:
        str: The full body of the email as plain text.
    """
    service = login()

    try:
        # Get the email details
        msg = service.users().messages().get(userId='me', id=id, format='full').execute()

        # Extract the body from the payload
        payload = msg.get('payload', {})
        parts = payload.get('parts', [])
        
        # Helper function to extract the body content
        def get_body(parts):
            for part in parts:
                if part.get('mimeType') == 'text/plain' and 'data' in part.get('body', {}):
                    return part['body']['data']
                elif 'parts' in part:
                    result = get_body(part['parts'])
                    if result:
                        return result
            return None

        body_data = get_body(parts)
        if not body_data:
            return "⚠️ Unable to retrieve the email body."

        # Decode the body content
        body = base64.urlsafe_b64decode(body_data).decode('utf-8')
        return body

    except Exception as e:
        return f"⚠️ Failed to retrieve email body. Reason: {e}"

@tool
def getExistingLabels() -> List[Dict[str, str]]:
    """
    Gets all existing Gmail labels (folders).
    
    Returns:
        List[Dict[str, str]]: A list of dictionaries containing label name and ID.
    """
    service = login()
    
    # Retrieve all labels
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])
    
    return [{'name': label['name'], 'id': label['id']} for label in labels]


@tool
def createLabels(names: List[str]) -> List[Dict[str, str]]:
    """
    Creates multiple new Gmail labels (folders). Be careful, the maximum number of labels is 25.
    
    Arguments:
        names (List[str]): List of names for the new labels.
        
    Returns:
        List[Dict[str, str]]: Information about the created labels or errors if any.
    """
    service = login()
    results = []
    
    try:
        # Check if the labels already exist
        number_existing_labels = len(getExistingLabels())
        if number_existing_labels + len(names) > 25:
            raise Exception(f"Since {number_existing_labels} labels already exist, you can only create {25 - number_existing_labels} more labels. The maximum amount allowed is 25.")
    except Exception as e:
        return [{'error': str(e)}]

    for name in names:
        # Create a new label
        label_object = {'name': name, 'messageListVisibility': 'show', 'labelListVisibility': 'labelShow'}
        try:
            created_label = service.users().labels().create(userId='me', body=label_object).execute()
            results.append({'name': created_label['name'], 'id': created_label['id']})
        except Exception as e:
            results.append({'name': name, 'error': str(e)})
    
    return results


@tool
def deleteLabels(names: List[str]) -> List[Dict[str, str]]:
    """
    Deletes multiple Gmail labels (folders).
    Be careful, this should ONLY be used to undo the creation a useless label.
    
    Arguments:
        names (List[str]): List of names for the labels to delete.
        
    Returns:
        List[Dict[str, str]]: Information about the deleted labels or errors if any.
    """
    service = login()
    results = []
    
    for name in names:
        # Get the label ID
        labels = getExistingLabels()
        label_id = next((l['id'] for l in labels if l['name'] == name), None)
        
        if not label_id:
            results.append({'name': name, 'error': 'Label not found'})
            continue
        
        # Delete the label
        try:
            service.users().labels().delete(userId='me', id=label_id).execute()
            results.append({'name': name, 'status': 'deleted'})
        except Exception as e:
            results.append({'name': name, 'error': str(e)})
    
    return results


@tool
def sortEmails(
    emails: List[Dict[str, str]],
    label: str
) -> List[Dict[str, str]]:
    """
    Sorts emails into a specified label (folder).
    
    Arguments:
        emails (List[Dict[str, str]]): List of email IDs to sort.
        label (str): Name of the label to sort emails into.
        
    Returns:
        List[Dict[str, str]]: A list of dictionaries containing email ID and status.
    """
    service = login()
    
    # Get the label ID
    labels = getExistingLabels()
    label_id = next((l['id'] for l in labels if l['name'] == label), None)
    
    if not label_id:
        return [{'error': f"Label '{label}' not found."}]
    
    results = []
    
    for email in emails:
        try:
            # Modify the email
            service.users().messages().modify(
                userId='me',
                id=email['id'],
                body={
                    'addLabelIds': [label_id],
                    'removeLabelIds': ['INBOX']
                }
            ).execute()
            
            results.append({'id': email['id'], 'status': 'sorted'})
        except Exception as e:
            results.append({'id': email['id'], 'error': str(e)})
    
    return results
