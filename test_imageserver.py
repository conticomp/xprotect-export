#!/usr/bin/env python3
"""
Standalone test script for ImageServer TCP connection.

Usage:
    python test_imageserver.py

Requires environment variables from .env file.
"""

import logging
import sys
from datetime import datetime, timedelta, timezone

# Configure logging to see all debug output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from dotenv import load_dotenv
load_dotenv()

from milestone_client import MilestoneClient
from image_server import ImageServerClient


def main():
    print("=" * 60)
    print("ImageServer TCP Connection Test")
    print("=" * 60)

    # Step 1: Authenticate via REST API (OAuth)
    print("\n[1] Authenticating with Milestone server (OAuth)...")
    try:
        client = MilestoneClient()
        client.authenticate()
        print("    ✓ OAuth authentication successful")
        oauth_token = client.get_token()
        print(f"    OAuth token prefix: {oauth_token[:30]}...")
    except Exception as e:
        print(f"    ✗ OAuth authentication failed: {e}")
        sys.exit(1)

    # Step 2: Get ImageServer token via SOAP Login
    print("\n[2] Getting ImageServer token via SOAP Login...")
    try:
        imageserver_token = client.get_imageserver_token()
        print("    ✓ ImageServer token obtained")
        print(f"    ImageServer token prefix: {imageserver_token[:30]}...")
    except Exception as e:
        print(f"    ✗ SOAP Login failed: {e}")
        sys.exit(1)

    # Step 3: Get cameras
    print("\n[3] Fetching camera list...")
    try:
        cameras = client.get_cameras()
        print(f"    ✓ Found {len(cameras)} cameras")
        if not cameras:
            print("    ✗ No cameras available")
            sys.exit(1)

        # Use first camera
        camera = cameras[0]
        camera_id = camera['id']
        camera_name = camera.get('name', 'Unknown')
        print(f"    Using camera: {camera_name} ({camera_id})")
    except Exception as e:
        print(f"    ✗ Failed to get cameras: {e}")
        sys.exit(1)

    # Step 4: Get recording server
    print("\n[4] Getting recording server for camera...")
    try:
        host, port = client.get_camera_recording_server(camera_id)
        print(f"    ✓ Recording server: {host}:{port}")
    except Exception as e:
        print(f"    ✗ Failed to get recording server: {e}")
        sys.exit(1)

    # Step 5: Connect to ImageServer
    print("\n[5] Connecting to ImageServer via TCP...")
    print(f"    Host: {host}")
    print(f"    Port: {port}")
    print(f"    Camera ID: {camera_id}")

    image_client = ImageServerClient()
    try:
        # Use ImageServer token (from SOAP Login), NOT OAuth token
        response = image_client.connect(host, port, camera_id, imageserver_token)
        print("    ✓ Connected successfully!")
        print(f"    Response headers: {response}")
    except ConnectionError as e:
        print(f"    ✗ Connection failed: {e}")
        print("\n    Check the debug logs above for the server response.")
        sys.exit(1)
    except Exception as e:
        print(f"    ✗ Unexpected error: {type(e).__name__}: {e}")
        sys.exit(1)

    # Step 6: Try goto
    print("\n[6] Seeking to 1 hour ago...")
    try:
        timestamp_ms = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp() * 1000)
        response = image_client.goto(timestamp_ms)
        print(f"    ✓ Goto response: {response}")
    except Exception as e:
        print(f"    ✗ Goto failed: {e}")

    # Step 7: Try getting a frame
    print("\n[7] Requesting next frame...")
    try:
        headers, jpeg_data = image_client.next_frame()
        if jpeg_data:
            print(f"    ✓ Got frame: {len(jpeg_data)} bytes")
            print(f"    Headers: {headers}")
        else:
            print(f"    No frame data (headers: {headers})")
    except Exception as e:
        print(f"    ✗ Failed to get frame: {e}")

    # Cleanup
    image_client.close()
    print("\n" + "=" * 60)
    print("Test complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
