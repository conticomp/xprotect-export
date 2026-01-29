"""ImageServer TCP protocol client for retrieving video frames from Milestone Recording Server."""

import logging
import re
import socket
import struct
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

# Milestone wraps raw H.264 in a 36-byte proprietary header
MILESTONE_HEADER_SIZE = 36

# H.264 codec ID in Milestone header
H264_CODEC_ID = 0x000A


class ImageServerClient:
    """Client for Milestone ImageServer protocol (TCP port 7563)."""

    def __init__(self, force_jpeg: bool = True):
        """
        Initialize ImageServer client.

        Args:
            force_jpeg: If True, request JPEG transcoding (alwaysstdjpeg=yes).
                       If False, request raw codec data for better performance.
        """
        self.sock: Optional[socket.socket] = None
        self.request_id = 0
        self.connected = False
        self.force_jpeg = force_jpeg

    def _build_xml(self, method: str, **elements) -> str:
        """
        Build single-line XML for ImageServer protocol.

        Milestone docs state: "Requests should be sent without linebreaks within the XML"
        """
        request_id = self._next_request_id()
        parts = [
            '<?xml version="1.0" encoding="utf-8"?>',
            '<methodcall>',
            f'<requestid>{request_id}</requestid>',
            f'<methodname>{method}</methodname>',
        ]
        for key, value in elements.items():
            parts.append(f'<{key}>{value}</{key}>')
        parts.append('</methodcall>')
        return ''.join(parts)

    def _next_request_id(self) -> int:
        """Increment and return request ID."""
        self.request_id += 1
        return self.request_id

    def _send_xml(self, xml: str) -> None:
        """Send XML message terminated with \\r\\n\\r\\n."""
        message = xml.strip() + "\r\n\r\n"
        logger.debug("Sending XML: %r", message)
        self.sock.sendall(message.encode("utf-8"))

    def _recv_until(self, delimiter: bytes) -> bytes:
        """Receive data until delimiter is found."""
        data = b""
        while delimiter not in data:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Connection closed by server")
            data += chunk
        # Only log first 200 bytes to avoid huge binary dumps
        logger.debug("Received response: %r", data[:200])
        return data

    def _parse_headers(self, header_block: bytes) -> dict:
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

    def _parse_xml_response(self, xml_data: bytes) -> dict:
        """Parse XML response from ImageServer into a dictionary."""
        text = xml_data.decode("utf-8", errors="ignore")
        result = {}

        # Extract common XML elements using regex
        patterns = [
            (r'<connected>([^<]+)</connected>', 'connected'),
            (r'<errorreason>([^<]+)</errorreason>', 'errorreason'),
            (r'<requestid>([^<]+)</requestid>', 'requestid'),
            (r'<methodname>([^<]+)</methodname>', 'methodname'),
        ]

        for pattern, key in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result[key] = match.group(1)

        return result

    def strip_milestone_header(self, data: bytes) -> tuple[bytes, str]:
        """
        Strip Milestone proprietary header if present to get raw codec data.

        Milestone wraps raw codec data in a 36-byte header with structure:
        - Bytes 0-1: Codec type as big-endian (0x000A = H.264)
        - Bytes 8-11: Payload length
        - Bytes 12-19: Timestamps
        - Byte 36+: H.264 NAL units with Annex B start codes (00 00 00 01)

        However, some configurations still return JPEG even with alwaysstdjpeg=no.
        This method detects the actual format and returns it appropriately.

        Args:
            data: Raw frame data from ImageServer

        Returns:
            Tuple of (processed_data, format) where format is 'h264' or 'jpeg'
        """
        if len(data) < 4:
            logger.warning("Frame data too short: %d bytes", len(data))
            return data, 'unknown'

        # Check for JPEG signature (FFD8FF)
        if data[:3] == b'\xff\xd8\xff':
            return data, 'jpeg'

        # Check for H.264 Annex B start code at beginning (raw H.264 without wrapper)
        if data[:4] == b'\x00\x00\x00\x01' or data[:3] == b'\x00\x00\x01':
            return data, 'h264'

        # Check for Milestone proprietary header with codec ID
        # Codec ID is stored as big-endian in first 2 bytes
        if len(data) > MILESTONE_HEADER_SIZE:
            codec_id = struct.unpack('>H', data[0:2])[0]  # Big-endian!
            logger.debug("Detected codec ID: 0x%04X", codec_id)

            if codec_id == H264_CODEC_ID:
                # Strip header and return H.264 payload
                payload = data[MILESTONE_HEADER_SIZE:]
                logger.debug("Stripped Milestone header, payload starts with: %s", payload[:8].hex() if len(payload) >= 8 else payload.hex())
                # H.264 payload - may or may not have visible start codes
                # Some encoders use Annex B (00 00 00 01), others use length-prefixed
                return payload, 'h264'

            # MJPEG wrapped in generic byte data container
            if codec_id == 0x0001:
                payload = data[MILESTONE_HEADER_SIZE:]
                if payload[:3] == b'\xff\xd8\xff':
                    return payload, 'jpeg'
                return payload, 'jpeg'  # Assume MJPEG even without signature

        # Unknown format - check if it might be JPEG anywhere in first 100 bytes
        jpeg_marker = data.find(b'\xff\xd8\xff')
        if jpeg_marker != -1 and jpeg_marker < 100:
            return data[jpeg_marker:], 'jpeg'

        logger.warning("Unknown frame format, first bytes: %s", data[:20].hex())
        return data, 'unknown'

    def is_h264_available(self, data: bytes) -> bool:
        """
        Check if frame data contains actual H.264 (not JPEG).

        Args:
            data: Raw frame data from ImageServer

        Returns:
            True if data contains H.264, False if JPEG or unknown
        """
        _, fmt = self.strip_milestone_header(data)
        return fmt == 'h264'

    def is_raw_mode(self) -> bool:
        """Return True if client is in raw codec mode (not JPEG)."""
        return not self.force_jpeg

    def connect(self, host: str, port: int, camera_id: str, token: str) -> dict:
        """
        Open socket and send connect XML to establish session.

        Args:
            host: Recording server hostname
            port: ImageServer port (typically 7563)
            camera_id: Camera GUID
            token: ImageServer token from SOAP Login (NOT the OAuth JWT token).
                   Obtain via MilestoneClient.get_imageserver_token()

        Returns:
            Response headers from server
        """
        mode = "JPEG" if self.force_jpeg else "raw codec"
        logger.debug("Connecting to ImageServer: host=%s, port=%d, camera_id=%s, mode=%s, token=%s...",
                     host, port, camera_id, mode, token[:20] if len(token) > 20 else token)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(30)
        self.sock.connect((host, port))

        # Build connect XML (single-line per Milestone docs)
        # Note: username/password are dummy - actual auth is via connectiontoken
        # alwaysstdjpeg=yes requests JPEG transcoding
        # alwaysstdjpeg=no requests raw codec data (H.264)
        jpeg_setting = 'yes' if self.force_jpeg else 'no'
        connect_xml = self._build_xml(
            'connect',
            username='dummy',
            password='dummy',
            alwaysstdjpeg=jpeg_setting,
            connectparam=f'id={camera_id}&amp;connectiontoken={token}'
        )

        self._send_xml(connect_xml)

        # Receive response (XML format)
        response = self._recv_until(b"\r\n\r\n")
        result = self._parse_xml_response(response)

        if result.get("connected", "").lower() != "yes":
            error = result.get("errorreason", "Unknown error")
            raise ConnectionError(f"Failed to connect to ImageServer: {error}")

        self.connected = True
        return result

    def goto(self, timestamp_ms: int) -> tuple[dict, bytes]:
        """
        Seek to a specific timestamp and retrieve the frame at that time.

        Args:
            timestamp_ms: Unix timestamp in milliseconds

        Returns:
            Tuple of (headers, image_data)
            - headers includes 'Current' (timestamp) and 'Content-length'
            - image_data is the raw frame bytes
        """
        if not self.connected:
            raise RuntimeError("Not connected. Call connect() first.")

        # Build single-line XML per Milestone docs
        goto_xml = self._build_xml('goto', time=timestamp_ms)

        self._send_xml(goto_xml)

        # Receive headers (goto returns image data like next_frame)
        response = self._recv_until(b"\r\n\r\n")

        # Split at delimiter to separate headers from any data that came with it
        header_end = response.find(b"\r\n\r\n")
        header_block = response[:header_end]
        extra_data = response[header_end + 4:]

        headers = self._parse_headers(header_block)

        # Check for end of stream or error
        if "Content-length" not in headers:
            return headers, b""

        content_length = int(headers["Content-length"])

        if content_length == 0:
            return headers, b""

        # Read the image data
        image_data = extra_data
        while len(image_data) < content_length:
            remaining = content_length - len(image_data)
            chunk = self.sock.recv(min(remaining, 65536))
            if not chunk:
                raise ConnectionError("Connection closed while reading frame data")
            image_data += chunk

        # Consume trailing terminator if present (ImageServer sends \r\n\r\n after data)
        # Read any remaining data that might include the terminator
        self.sock.setblocking(False)
        try:
            trailing = self.sock.recv(4)
            logger.debug("Consumed trailing data: %r", trailing)
        except BlockingIOError:
            pass  # No trailing data available
        finally:
            self.sock.setblocking(True)

        return headers, image_data[:content_length]

    def next_frame(self) -> tuple[dict, bytes]:
        """
        Request and receive the next frame.

        Returns:
            Tuple of (headers, frame_data)
            - headers includes 'Current' (timestamp) and 'Content-length'
            - frame_data is JPEG bytes (if force_jpeg=True) or raw codec with
              Milestone header (if force_jpeg=False). Use strip_milestone_header()
              to extract raw H.264 NAL units from raw codec data.
        """
        if not self.connected:
            raise RuntimeError("Not connected. Call connect() first.")

        # Request next frame (single-line XML per Milestone docs)
        next_xml = self._build_xml('next')

        self._send_xml(next_xml)

        # Receive headers
        response = self._recv_until(b"\r\n\r\n")

        # Split at delimiter to separate headers from any data that came with it
        header_end = response.find(b"\r\n\r\n")
        header_block = response[:header_end]
        extra_data = response[header_end + 4:]

        headers = self._parse_headers(header_block)

        # Check for end of stream or error
        if "Content-length" not in headers:
            # No frame available
            return headers, b""

        content_length = int(headers["Content-length"])

        if content_length == 0:
            return headers, b""

        # Read the frame data
        frame_data = extra_data
        while len(frame_data) < content_length:
            remaining = content_length - len(frame_data)
            chunk = self.sock.recv(min(remaining, 65536))
            if not chunk:
                raise ConnectionError("Connection closed while reading frame data")
            frame_data += chunk

        # Consume trailing terminator if present (ImageServer sends \r\n\r\n after data)
        self.sock.setblocking(False)
        try:
            trailing = self.sock.recv(4)
            logger.debug("Consumed trailing data: %r", trailing)
        except BlockingIOError:
            pass  # No trailing data available
        finally:
            self.sock.setblocking(True)

        return headers, frame_data[:content_length]

    def get_frame_timestamp(self, headers: dict) -> Optional[int]:
        """Extract frame timestamp from headers."""
        current = headers.get("Current")
        if current:
            try:
                return int(current)
            except ValueError:
                pass
        return None

    def _send_next_request(self) -> None:
        """Send a 'next' frame request without waiting for response."""
        next_xml = self._build_xml('next')
        self._send_xml(next_xml)

    def _receive_frame_response(self) -> tuple[dict, bytes]:
        """
        Receive a single frame response.

        Returns:
            Tuple of (headers, frame_data)
        """
        # Receive headers
        response = self._recv_until(b"\r\n\r\n")

        # Split at delimiter to separate headers from any data that came with it
        header_end = response.find(b"\r\n\r\n")
        header_block = response[:header_end]
        extra_data = response[header_end + 4:]

        headers = self._parse_headers(header_block)

        # Check for end of stream or error
        if "Content-length" not in headers:
            return headers, b""

        content_length = int(headers["Content-length"])

        if content_length == 0:
            return headers, b""

        # Read the frame data
        frame_data = extra_data
        while len(frame_data) < content_length:
            remaining = content_length - len(frame_data)
            chunk = self.sock.recv(min(remaining, 65536))
            if not chunk:
                raise ConnectionError("Connection closed while reading frame data")
            frame_data += chunk

        # Consume trailing terminator if present
        self.sock.setblocking(False)
        try:
            trailing = self.sock.recv(4)
            logger.debug("Consumed trailing data: %r", trailing)
        except BlockingIOError:
            pass
        finally:
            self.sock.setblocking(True)

        return headers, frame_data[:content_length]

    def fetch_frames_pipelined(
        self,
        end_timestamp_ms: int,
        pipeline_depth: int = 5
    ) -> Iterator[tuple[dict, bytes]]:
        """
        Fetch multiple frames with request pipelining for improved throughput.

        Sends multiple 'next' requests before waiting for responses to reduce
        round-trip latency overhead. This dramatically improves export speed
        for high-latency connections.

        Args:
            end_timestamp_ms: Stop fetching when frame timestamp exceeds this value
            pipeline_depth: Number of requests to keep in flight (default 5)

        Yields:
            Tuple of (headers, frame_data) for each frame
            - frame_data is raw codec with Milestone header when force_jpeg=False
            - Use strip_milestone_header() to extract H.264 NAL units
        """
        if not self.connected:
            raise RuntimeError("Not connected. Call connect() first.")

        # Send initial batch of requests to fill the pipeline
        pending_requests = 0
        for _ in range(pipeline_depth):
            self._send_next_request()
            pending_requests += 1

        while pending_requests > 0:
            # Receive one response
            headers, frame_data = self._receive_frame_response()
            pending_requests -= 1

            if not frame_data:
                # No more frames available
                logger.debug("No frame data received, ending pipeline")
                break

            # Check timestamp
            frame_timestamp = self.get_frame_timestamp(headers)
            if frame_timestamp is None:
                continue

            if frame_timestamp >= end_timestamp_ms:
                logger.debug("Reached end timestamp, stopping pipeline")
                break

            # Yield this frame
            yield headers, frame_data

            # Send another request to keep pipeline filled
            self._send_next_request()
            pending_requests += 1

    def close(self) -> None:
        """Close the socket connection."""
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        self.connected = False
