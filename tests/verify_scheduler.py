
import sys
import os
import schedule
import time
from services import scheduler

# Mock logger
class MockLogger:
    def info(self, msg): print(f"[INFO] {msg}")
    def error(self, msg): print(f"[ERROR] {msg}")

scheduler.logger = MockLogger()

def test_interval_update():
    print("Initial Scheduler Jobs:")
    print(schedule.get_jobs())
    
    # 1. Start with default (setup mock env if needed, but here we just call update directly)
    print("\nUpdating interval to 1 minute...")
    scheduler.update_market_gate_interval(1)
    
    jobs = schedule.get_jobs()
    found = False
    for job in jobs:
        if 'market_gate' in job.tags:
            print(f"✅ Found job with tags: {job.tags} and interval: {job.interval}")
            if job.interval == 1 and job.unit == 'minutes':
                found = True
    
    if found:
        print("SUCCESS: Job interval updated to 1 minute")
    else:
        print("FAILURE: Job interval not updated correctly")

if __name__ == "__main__":
    test_interval_update()
