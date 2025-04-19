import os
import sys
import json
from dotenv import load_dotenv
from typing import List, Dict, Any

# Fix the relative import issue by adding the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Now import the tools
from MailSorter.mail_sorting_tools import (
    login,
    getUnclassifiedEmails,
    getUnreadUnclassifiedEmails,
    getExistingLabels,
    createLabels,
    sortEmails
)

def pretty_print(data):
    """Helper function to pretty print JSON data"""
    if isinstance(data, list) and data:
        if isinstance(data[0], dict):
            print(json.dumps(data, indent=2))
        else:
            print(data)
    elif isinstance(data, dict):
        print(json.dumps(data, indent=2))
    else:
        print(data)


def test_login():
    """Test the login functionality"""
    print("\n=== Testing login ===")
    try:
        service = login()
        print("✅ Login successful")
        return True
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return False


def test_get_existing_labels():
    """Test getting existing labels"""
    print("\n=== Testing getExistingLabels ===")
    try:
        labels = getExistingLabels()
        print(f"Found {len(labels)} labels:")
        pretty_print(labels)
        return labels
    except Exception as e:
        print(f"❌ Failed to get labels: {e}")
        return []


def test_create_labels():
    """Test creating new labels"""
    print("\n=== Testing createLabels ===")
    test_labels = ["Test_Label_1", "Test_Label_2"]
    
    # First check if test labels already exist
    existing_labels = getExistingLabels()
    existing_label_names = [label['name'] for label in existing_labels]
    
    labels_to_create = [l for l in test_labels if l not in existing_label_names]
    
    if not labels_to_create:
        print("Test labels already exist, skipping creation")
        return True
        
    try:
        result = createLabels(labels_to_create)
        print("Label creation result:")
        pretty_print(result)
        return True
    except Exception as e:
        print(f"❌ Failed to create labels: {e}")
        return False


def test_get_unclassified_emails(limit=5):
    """Test getting unclassified emails"""
    print(f"\n=== Testing getUnclassifiedEmails (limit: {limit}) ===")
    try:
        emails = getUnclassifiedEmails(max_emails=limit)
        print(f"Found {len(emails)} unclassified emails:")
        pretty_print(emails[:limit])
        return emails[:limit]
    except Exception as e:
        print(f"❌ Failed to get unclassified emails: {e}")
        return []


def test_get_unread_emails(limit=5):
    """Test getting unread emails"""
    print(f"\n=== Testing getUnreadUnclassifiedEmails (limit: {limit}) ===")
    try:
        emails = getUnreadUnclassifiedEmails(max_emails=limit)
        print(f"Found {len(emails)} unread emails:")
        pretty_print(emails[:limit])
        return emails[:limit]
    except Exception as e:
        print(f"❌ Failed to get unread emails: {e}")
        return []


def test_sort_emails(emails, label_name="Test_Label_1"):
    """Test sorting emails"""
    if not emails:
        print("\n=== Skipping sortEmails test (no emails found) ===")
        return False
        
    print(f"\n=== Testing sortEmails (to label: {label_name}) ===")
    try:
        result = sortEmails(emails, label_name)
        print("Sort result:")
        pretty_print(result)
        return True
    except Exception as e:
        print(f"❌ Failed to sort emails: {e}")
        return False


def run_all_tests():
    """Run all tests in sequence"""
    load_dotenv()
    
    # Test login first since other functions depend on it
    if not test_login():
        print("Login failed, aborting further tests")
        return
        
    # Test getting existing labels
    labels = test_get_existing_labels()
    
    # Test creating labels
    test_create_labels()
    
    # Test getting emails
    emails = test_get_unclassified_emails(3)
    
    # Test getting unread emails
    unread_emails = test_get_unread_emails(3)
    
    # Test sorting some emails if we have any
    if emails:
        test_sort_emails(emails[:1], "Test_Label_1")
    
    print("\n=== All tests completed ===")


if __name__ == "__main__":
    run_all_tests()