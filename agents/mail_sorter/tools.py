import os
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from utils.Tool import Tool, tool
from typing import List, Dict, Tuple, Any


# Scopes: the permissions that the application will request from the user
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def login():
    load_dotenv()

    creds = None
    token_path = 'token.json'
    credentials_path = 'credentials.json'

    # Load existing credentials
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Refresh credentials if expired
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        # Initiate OAuth flow
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
        creds = flow.run_local_server(port=0)

        # Save the credentials for future use
        with open(token_path, 'w') as token_file:
            token_file.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds)
    return service


### Let's see if the snippet is enough to sort the emails
@tool
def getUnclassifiedEmails(max_emails: int = 100) -> List[Dict[str, Any]]:
    """
    Returns a list of unclassified emails from the inbox, wether read or unread.
    
    Arguments:
        max_emails (int): Maximum number of emails to retrieve.
        
    Returns:
        List[Dict[str, Any]]: A list of email details including id, subject, sender, date, and snippet.
    """
    service = login()

    # get the emails
    results = service.users().messages().list(
        userId='me',
        labelIds=['INBOX'],
        maxResults=max_emails
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
def getUnreadUnclassifiedEmails(max_emails: int = 100) -> List[Dict[str, Any]]:
    """
    Returns a list of unread unclassified emails from the inbox.
    
    Arguments:
        max_emails (int): Maximum number of emails to retrieve.
        
    Returns:
        List[Dict[str, Any]]: A list of email details including id, subject, sender, date, and snippet.
    """
    service = login()

    # get the emails
    results = service.users().messages().list(
        userId='me',
        labelIds=['INBOX'],
        q='is:unread',
        maxResults=max_emails
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
        number_existing_labels = getExistingLabels().__len__
        if number_existing_labels + names.__len__ > 25:
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
def sortEmails(
    emails: List[Dict[str, str]],
    label: str,
    mark_as_read: bool = False
) -> List[Dict[str, str]]:
    """
    Sorts emails into a specified label (folder).
    
    Arguments:
        emails (List[Dict[str, str]]): List of email IDs to sort.
        label (str): Name of the label to sort emails into.
        mark_as_read (bool): Whether to mark the emails as read.
        
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
            msg = service.users().messages().modify(
                userId='me',
                id=email['id'],
                body={
                    'addLabelIds': [label_id],
                    'removeLabelIds': ['INBOX']
                }
            ).execute()
            
            # Mark as read if specified
            if mark_as_read:
                service.users().messages().modify(
                    userId='me',
                    id=email['id'],
                    body={'removeLabelIds': ['UNREAD']}
                ).execute()
            
            results.append({'id': email['id'], 'status': 'sorted'})
        except Exception as e:
            results.append({'id': email['id'], 'error': str(e)})
    
    return results