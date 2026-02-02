
import sys
import os
import json
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chatbot.core import HistoryManager

def test_timestamp_backfill():
    # Load history manager
    history_manager = HistoryManager('test_user')
    
    # List sessions
    sessions = history_manager.get_all_sessions()
    if not sessions:
        print("No sessions found to test.")
        return

    # Pick the first session
    session_id = sessions[0]['id']
    print(f"Testing session: {session_id}")
    
    # Get messages
    messages = history_manager.get_messages(session_id)
    
    # Check timestamps
    for i, msg in enumerate(messages):
        print(f"Message {i} role: {msg['role']}")
        if 'timestamp' in msg:
            print(f"  Timestamp: {msg['timestamp']}")
        else:
            print("  FAIL: Timestamp missing")

if __name__ == "__main__":
    test_timestamp_backfill()
