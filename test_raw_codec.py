#!/usr/bin/env python3
"""
Test script to capture raw H.264 data from Milestone ImageServer.

This script connects with alwaysstdjpeg=no to receive raw codec data
instead of transcoded JPEG. The goal is to analyze Milestone's
"generic byte data" format to see if we can extract usable H.264.
"""

import logging
import socket
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from milestone_client import MilestoneClient

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Output directory for captured frames
OUTPUT_DIR = Path(__file__).parent / "exports" / "raw_codec_test"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def hex_dump(data: bytes, length: int = 200) -> str:
    """Create a hex dump of the first N bytes."""
    lines = []
    for i in range(0, min(len(data), length), 16):
        chunk = data[i:i+16]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        lines.append(f'{i:04x}: {hex_part:<48} {ascii_part}')
    return '\n'.join(lines)


def detect_format(data: bytes) -> str:
    """Detect the video format based on magic bytes."""
    if len(data) < 4:
        return "unknown (too short)"

    # Check for common signatures
    if data[:3] == b'\xff\xd8\xff':
        return "JPEG"
    if data[:4] == b'\x00\x00\x00\x01':
        return "H.264 Annex B (4-byte start code)"
    if data[:3] == b'\x00\x00\x01':
        return "H.264 Annex B (3-byte start code)"
    if data[0] == 0x47:
        return "MPEG-TS"
    if data[:4] == b'ftyp' or data[4:8] == b'ftyp':
        return "MP4/MOV"

    # Check for Milestone generic byte data header
    # Look for any recognizable patterns
    if b'GenericByteData' in data[:100]:
        return "Milestone GenericByteData container"

    return f"unknown (starts with: {data[:4].hex()})"


def parse_headers(header_block: bytes) -> dict:
    """Parse HTTP-style headers into a dictionary."""
    headers = {}
    lines = header_block.decode("utf-8", errors="ignore").split("\r\n")
    for line in lines:
        if "=" in line:
            key, value = line.split("=", 1)
            headers[key.strip()] = value.strip()
        elif ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()
    return headers


def recv_until(sock: socket.socket, delimiter: bytes) -> bytes:
    """Receive data until delimiter is found."""
    data = b""
    while delimiter not in data:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("Connection closed by server")
        data += chunk
    return data


def fetch_frame(sock: socket.socket, request_id: int, method: str, **params) -> tuple[dict, bytes]:
    """Send a request and receive the frame response."""
    # Build XML request
    parts = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<methodcall>',
        f'<requestid>{request_id}</requestid>',
        f'<methodname>{method}</methodname>',
    ]
    for key, value in params.items():
        parts.append(f'<{key}>{value}</{key}>')
    parts.append('</methodcall>')
    xml = ''.join(parts) + "\r\n\r\n"

    logger.debug(f"Sending: {xml.strip()}")
    sock.sendall(xml.encode("utf-8"))

    # Receive response
    response = recv_until(sock, b"\r\n\r\n")

    # Split headers from any data
    header_end = response.find(b"\r\n\r\n")
    header_block = response[:header_end]
    extra_data = response[header_end + 4:]

    headers = parse_headers(header_block)
    logger.info(f"Response headers: {headers}")

    # Check for content
    if "Content-length" not in headers:
        return headers, b""

    content_length = int(headers["Content-length"])
    if content_length == 0:
        return headers, b""

    # Read the data
    data = extra_data
    while len(data) < content_length:
        remaining = content_length - len(data)
        chunk = sock.recv(min(remaining, 65536))
        if not chunk:
            raise ConnectionError("Connection closed while reading frame data")
        data += chunk

    # Consume trailing terminator
    sock.setblocking(False)
    try:
        sock.recv(4)
    except BlockingIOError:
        pass
    finally:
        sock.setblocking(True)

    return headers, data[:content_length]


def test_connection(host: str, port: int, camera_id: str, token: str, use_jpeg: bool) -> list[tuple[dict, bytes]]:
    """
    Connect to ImageServer and fetch frames.

    Args:
        host: Recording server hostname
        port: ImageServer port (7563)
        camera_id: Camera GUID
        token: ImageServer token from SOAP Login
        use_jpeg: If True, use alwaysstdjpeg=yes. If False, omit it for raw codec.

    Returns:
        List of (headers, data) tuples for each frame
    """
    mode = "JPEG" if use_jpeg else "RAW CODEC"
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing {mode} mode")
    logger.info(f"{'='*60}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(30)
    sock.connect((host, port))

    try:
        # Build connect XML
        request_id = 1
        parts = [
            '<?xml version="1.0" encoding="utf-8"?>',
            '<methodcall>',
            f'<requestid>{request_id}</requestid>',
            '<methodname>connect</methodname>',
            '<username>dummy</username>',
            '<password>dummy</password>',
        ]

        if use_jpeg:
            parts.append('<alwaysstdjpeg>yes</alwaysstdjpeg>')
        else:
            # Explicitly set to 'no' to request raw codec data
            parts.append('<alwaysstdjpeg>no</alwaysstdjpeg>')

        parts.append(f'<connectparam>id={camera_id}&amp;connectiontoken={token}</connectparam>')
        parts.append('</methodcall>')

        connect_xml = ''.join(parts) + "\r\n\r\n"

        logger.info(f"Connect XML:\n{connect_xml}")
        sock.sendall(connect_xml.encode("utf-8"))

        # Receive connect response
        response = recv_until(sock, b"\r\n\r\n")
        logger.info(f"Connect response: {response.decode('utf-8', errors='ignore')}")

        if b'<connected>yes</connected>' not in response.lower():
            logger.error("Failed to connect!")
            return []

        logger.info("Connected successfully!")

        # Use a timestamp from 30 seconds ago
        timestamp_ms = int((datetime.now(timezone.utc) - timedelta(seconds=30)).timestamp() * 1000)

        frames = []

        # Fetch first frame with goto
        request_id += 1
        logger.info(f"\nFetching frame with goto (timestamp: {timestamp_ms})")
        headers, data = fetch_frame(sock, request_id, "goto", time=timestamp_ms)
        if data:
            frames.append((headers, data))
            analyze_frame(headers, data, 1, mode)

        # Fetch 2 more frames with next
        for i in range(2):
            request_id += 1
            logger.info(f"\nFetching frame {i+2} with next")
            headers, data = fetch_frame(sock, request_id, "next")
            if data:
                frames.append((headers, data))
                analyze_frame(headers, data, i + 2, mode)

        return frames

    finally:
        sock.close()


def analyze_frame(headers: dict, data: bytes, frame_num: int, mode: str):
    """Analyze and save a frame."""
    content_type = headers.get("Content-type", "unknown")
    content_length = len(data)
    detected_format = detect_format(data)

    logger.info(f"\n--- Frame {frame_num} Analysis ({mode}) ---")
    logger.info(f"Content-Type: {content_type}")
    logger.info(f"Content-Length: {content_length:,} bytes ({content_length/1024:.1f} KB)")
    logger.info(f"Detected Format: {detected_format}")
    logger.info(f"First 200 bytes hex dump:\n{hex_dump(data, 200)}")

    # Save to file
    suffix = "jpeg" if mode == "JPEG" else "bin"
    filename = OUTPUT_DIR / f"frame_{frame_num}_{mode.lower().replace(' ', '_')}.{suffix}"
    with open(filename, "wb") as f:
        f.write(data)
    logger.info(f"Saved to: {filename}")


def main():
    logger.info("Starting raw codec test")

    # Authenticate
    logger.info("Authenticating with Milestone...")
    client = MilestoneClient()
    client.authenticate()
    logger.info("OAuth authentication successful")

    # Get ImageServer token
    imageserver_token = client.get_imageserver_token()
    logger.info(f"ImageServer token obtained: {imageserver_token[:30]}...")

    # Get first camera
    cameras = client.get_cameras()
    if not cameras:
        logger.error("No cameras found!")
        return

    camera = cameras[0]
    camera_id = camera["id"]
    logger.info(f"Using camera: {camera['name']} ({camera_id})")

    # Get recording server
    host, port = client.get_camera_recording_server(camera_id)
    logger.info(f"Recording server: {host}:{port}")

    # Test with raw codec (alwaysstdjpeg=no)
    raw_frames = test_connection(host, port, camera_id, imageserver_token, use_jpeg=False)

    # Test with JPEG for comparison
    jpeg_frames = test_connection(host, port, camera_id, imageserver_token, use_jpeg=True)

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("SUMMARY")
    logger.info(f"{'='*60}")

    if raw_frames:
        raw_size = sum(len(d) for _, d in raw_frames)
        logger.info(f"Raw codec: {len(raw_frames)} frames, total {raw_size:,} bytes")
    else:
        logger.info("Raw codec: No frames received")

    if jpeg_frames:
        jpeg_size = sum(len(d) for _, d in jpeg_frames)
        logger.info(f"JPEG mode: {len(jpeg_frames)} frames, total {jpeg_size:,} bytes")
    else:
        logger.info("JPEG mode: No frames received")

    if raw_frames and jpeg_frames:
        raw_avg = sum(len(d) for _, d in raw_frames) / len(raw_frames)
        jpeg_avg = sum(len(d) for _, d in jpeg_frames) / len(jpeg_frames)
        ratio = jpeg_avg / raw_avg if raw_avg > 0 else 0
        logger.info(f"\nAverage frame size - Raw: {raw_avg:,.0f} bytes, JPEG: {jpeg_avg:,.0f} bytes")
        logger.info(f"JPEG is {ratio:.1f}x larger than raw codec")

    logger.info(f"\nFrame files saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
