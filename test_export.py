#!/usr/bin/env python3
"""
Test export for specific time range.
1/29/2026 12:35 PM to 12:37 PM PST
"""

import logging
import sys
from datetime import datetime, timezone, timedelta

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from dotenv import load_dotenv
load_dotenv()

from milestone_client import MilestoneClient
from image_server import ImageServerClient

# PST is UTC-8
PST = timezone(timedelta(hours=-8))

# Target time range: 1/29/2026 12:35 PM to 12:37 PM PST
START_TIME = datetime(2026, 1, 29, 12, 35, 0, tzinfo=PST)
END_TIME = datetime(2026, 1, 29, 12, 37, 0, tzinfo=PST)

# Convert to Unix milliseconds
START_MS = int(START_TIME.timestamp() * 1000)
END_MS = int(END_TIME.timestamp() * 1000)

print("=" * 60)
print("Export Test: 1/29/2026 12:35 PM - 12:37 PM PST")
print("=" * 60)
print(f"Start time: {START_TIME} = {START_MS} ms")
print(f"End time:   {END_TIME} = {END_MS} ms")
print(f"Duration:   {(END_MS - START_MS) / 1000} seconds")

# Authenticate
print("\n[1] Authenticating...")
client = MilestoneClient()
client.authenticate()
print("    ✓ OAuth OK")

imageserver_token = client.get_imageserver_token()
print(f"    ✓ ImageServer token: {imageserver_token[:30]}...")

# Get cameras
print("\n[2] Getting cameras...")
cameras = client.get_cameras()
camera = cameras[0]
camera_id = camera['id']
print(f"    Using: {camera['name']} ({camera_id})")

# Get recording server
print("\n[3] Getting recording server...")
host, port = client.get_camera_recording_server(camera_id)
print(f"    Server: {host}:{port}")

# Connect to ImageServer
print("\n[4] Connecting to ImageServer...")
image_client = ImageServerClient()
response = image_client.connect(host, port, camera_id, imageserver_token)
print(f"    ✓ Connected: {response}")

# Goto start time
print(f"\n[5] Seeking to start time ({START_MS})...")
headers, data = image_client.goto(START_MS)
print(f"    Headers: {headers}")
print(f"    Data size: {len(data)} bytes")
if data:
    print(f"    First 20 bytes: {data[:20]}")
    # Check if it's JPEG (starts with FF D8)
    if data[:2] == b'\xff\xd8':
        print("    ✓ Data is JPEG!")
    else:
        print(f"    Data starts with: {data[:10].hex()}")

# Get current timestamp from response
current_ts = headers.get('Current')
print(f"    Current timestamp: {current_ts}")
if current_ts:
    current_dt = datetime.fromtimestamp(int(current_ts) / 1000, tz=PST)
    print(f"    Current datetime: {current_dt}")

# Try getting next frames
print("\n[6] Getting next frames...")
frame_count = 0
max_frames = 10  # Limit for testing

for i in range(max_frames):
    print(f"\n    Frame {i+1}:")
    headers, data = image_client.next_frame()
    print(f"    Headers: {headers}")
    print(f"    Data size: {len(data)} bytes")

    if not data:
        print("    No data - stopping")
        break

    frame_count += 1

    # Check timestamp
    current_ts = headers.get('Current')
    if current_ts:
        ts_int = int(current_ts)
        current_dt = datetime.fromtimestamp(ts_int / 1000, tz=PST)
        print(f"    Timestamp: {current_ts} = {current_dt}")

        if ts_int >= END_MS:
            print("    Reached end time - stopping")
            break

    # Save first frame for inspection
    if i == 0 and data:
        with open('/tmp/test_frame.bin', 'wb') as f:
            f.write(data)
        print("    Saved to /tmp/test_frame.bin")

print(f"\n[7] Summary:")
print(f"    Frames retrieved: {frame_count}")

image_client.close()
print("\nDone!")
