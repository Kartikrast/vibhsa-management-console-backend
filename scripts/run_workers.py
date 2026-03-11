import time
from app.tasks.walmart_feed_sync import sync_walmart_feed_status


while True:

    print("Running Walmart feed sync...")

    sync_walmart_feed_status()

    time.sleep(30)