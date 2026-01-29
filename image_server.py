"""ImageServer TCP protocol client for retrieving video frames from Milestone Recording Server."""

import socket
from typing import Optional


class ImageServerClient:
    """Client for Milestone ImageServer protocol (TCP port 7563)."""

    def __init__(self):
        self.sock: Optional[socket.socket] = None
        self.request_id = 0
        self.connected = False

    def _next_request_id(self) -> int:
        """Increment and return request ID."""
        self.request_id += 1
        return self.request_id

    def _send_xml(self, xml: str) -> None:
        """Send XML message terminated with \\r\\n\\r\\n."""
        message = xml.strip() + "\r\n\r\n"
        self.sock.sendall(message.encode("utf-8"))

    def _recv_until(self, delimiter: bytes) -> bytes:
        """Receive data until delimiter is found."""
        data = b""
        while delimiter not in data:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Connection closed by server")
            data += chunk
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

    def connect(self, host: str, port: int, camera_id: str, token: str) -> dict:
        """
        Open socket and send connect XML to establish session.

        Args:
            host: Recording server hostname
            port: ImageServer port (typically 7563)
            camera_id: Camera GUID
            token: OAuth access token

        Returns:
            Response headers from server
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(30)
        self.sock.connect((host, port))

        # Build connect XML
        # Note: username/password are dummy - actual auth is via connectiontoken
        connect_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<methodcall>
  <requestid>{self._next_request_id()}</requestid>
  <methodname>connect</methodname>
  <username>dummy</username>
  <password>dummy</password>
  <connectparam>id={camera_id}&amp;connectiontoken={token}</connectparam>
</methodcall>"""

        self._send_xml(connect_xml)

        # Receive response
        response = self._recv_until(b"\r\n\r\n")
        headers = self._parse_headers(response)

        if headers.get("connected", "").lower() != "yes":
            error = headers.get("errorreason", "Unknown error")
            raise ConnectionError(f"Failed to connect to ImageServer: {error}")

        self.connected = True
        return headers

    def goto(self, timestamp_ms: int) -> dict:
        """
        Seek to a specific timestamp.

        Args:
            timestamp_ms: Unix timestamp in milliseconds

        Returns:
            Response headers from server
        """
        if not self.connected:
            raise RuntimeError("Not connected. Call connect() first.")

        goto_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<methodcall>
  <requestid>{self._next_request_id()}</requestid>
  <methodname>goto</methodname>
  <time>{timestamp_ms}</time>
</methodcall>"""

        self._send_xml(goto_xml)

        # Receive response headers
        response = self._recv_until(b"\r\n\r\n")
        headers = self._parse_headers(response)

        return headers

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

        # Request next frame
        next_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<methodcall>
  <requestid>{self._next_request_id()}</requestid>
  <methodname>next</methodname>
</methodcall>"""

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
