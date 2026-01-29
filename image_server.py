"""ImageServer TCP protocol client for retrieving video frames from Milestone Recording Server."""

import logging
import re
import socket
from typing import Optional

logger = logging.getLogger(__name__)


class ImageServerClient:
    """Client for Milestone ImageServer protocol (TCP port 7563)."""

    def __init__(self):
        self.sock: Optional[socket.socket] = None
        self.request_id = 0
        self.connected = False

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
        logger.debug("Connecting to ImageServer: host=%s, port=%d, camera_id=%s, token=%s...",
                     host, port, camera_id, token[:20] if len(token) > 20 else token)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(30)
        self.sock.connect((host, port))

        # Build connect XML (single-line per Milestone docs)
        # Note: username/password are dummy - actual auth is via connectiontoken
        # Request JPEG format with alwaysstdjpeg=yes
        connect_xml = self._build_xml(
            'connect',
            username='dummy',
            password='dummy',
            alwaysstdjpeg='yes',
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
            Tuple of (headers, jpeg_data)
            - headers includes 'Current' (timestamp) and 'Content-length'
            - jpeg_data is the raw JPEG bytes
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

        # Read the JPEG data
        jpeg_data = extra_data
        while len(jpeg_data) < content_length:
            remaining = content_length - len(jpeg_data)
            chunk = self.sock.recv(min(remaining, 65536))
            if not chunk:
                raise ConnectionError("Connection closed while reading frame data")
            jpeg_data += chunk

        # Consume trailing terminator if present (ImageServer sends \r\n\r\n after data)
        self.sock.setblocking(False)
        try:
            trailing = self.sock.recv(4)
            logger.debug("Consumed trailing data: %r", trailing)
        except BlockingIOError:
            pass  # No trailing data available
        finally:
            self.sock.setblocking(True)

        return headers, jpeg_data[:content_length]

    def get_frame_timestamp(self, headers: dict) -> Optional[int]:
        """Extract frame timestamp from headers."""
        current = headers.get("Current")
        if current:
            try:
                return int(current)
            except ValueError:
                pass
        return None

    def close(self) -> None:
        """Close the socket connection."""
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        self.connected = False
