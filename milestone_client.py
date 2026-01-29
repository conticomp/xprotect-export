"""Milestone XProtect REST API client for authentication and camera listing."""

import requests
import urllib3
from typing import Optional
from config import MILESTONE_SERVER_URL, MILESTONE_USERNAME, MILESTONE_PASSWORD

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class MilestoneClient:
    def __init__(self):
        self.base_url = MILESTONE_SERVER_URL
        self.username = MILESTONE_USERNAME
        self.password = MILESTONE_PASSWORD
        self.access_token: Optional[str] = None
        self.token_type: str = "Bearer"

    def authenticate(self) -> bool:
        """Authenticate via OAuth and store access token."""
        url = f"{self.base_url}/API/IDP/connect/token"
        data = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
            "client_id": "GrantValidatorClient"
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(url, data=data, headers=headers, verify=False)
        response.raise_for_status()

        token_data = response.json()
        self.access_token = token_data["access_token"]
        self.token_type = token_data.get("token_type", "Bearer")
        return True

    def _auth_headers(self) -> dict:
        """Return authorization headers for API requests."""
        if not self.access_token:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        return {"Authorization": f"{self.token_type} {self.access_token}"}

    def get_cameras(self) -> list[dict]:
        """Get list of all cameras with their IDs and names."""
        url = f"{self.base_url}/api/rest/v1/cameras"
        response = requests.get(url, headers=self._auth_headers(), verify=False)
        response.raise_for_status()

        data = response.json()
        cameras = []
        for cam in data.get("array", []):
            cameras.append({
                "id": cam.get("id"),
                "name": cam.get("name"),
                "displayName": cam.get("displayName", cam.get("name")),
                "enabled": cam.get("enabled", True)
            })
        return cameras

    def get_camera_details(self, camera_id: str) -> dict:
        """Get detailed camera information including hardware reference."""
        url = f"{self.base_url}/api/rest/v1/cameras/{camera_id}"
        response = requests.get(url, headers=self._auth_headers(), verify=False)
        response.raise_for_status()
        return response.json().get("data", {})

    def get_hardware(self, hardware_id: str) -> dict:
        """Get hardware information including recording server reference."""
        url = f"{self.base_url}/api/rest/v1/hardware/{hardware_id}"
        response = requests.get(url, headers=self._auth_headers(), verify=False)
        response.raise_for_status()
        return response.json().get("data", {})

    def get_recording_server(self, recording_server_id: str) -> dict:
        """Get recording server information including hostname."""
        url = f"{self.base_url}/api/rest/v1/recordingServers/{recording_server_id}"
        response = requests.get(url, headers=self._auth_headers(), verify=False)
        response.raise_for_status()
        return response.json().get("data", {})

    def get_camera_recording_server(self, camera_id: str) -> tuple[str, int]:
        """
        Traverse camera → hardware → recordingServer to get the host and port
        for the ImageServer connection.

        Returns: (hostname, port) tuple
        """
        # Get camera details to find hardware
        camera = self.get_camera_details(camera_id)

        # Extract hardware ID from relations.parent (type: hardware)
        parent = camera.get("relations", {}).get("parent", {})
        if isinstance(parent, dict) and parent.get("type") == "hardware":
            hardware_id = parent.get("id")
        else:
            hardware_id = None

        if not hardware_id:
            raise ValueError(f"Could not find hardware for camera {camera_id}")

        # Get hardware to find recording server
        hardware = self.get_hardware(hardware_id)

        # Extract recording server ID from relations.parent (type: recordingServers)
        parent = hardware.get("relations", {}).get("parent", {})
        if isinstance(parent, dict) and parent.get("type") == "recordingServers":
            rs_id = parent.get("id")
        else:
            rs_id = None

        if not rs_id:
            raise ValueError(f"Could not find recording server for hardware {hardware_id}")

        # Get recording server details
        recording_server = self.get_recording_server(rs_id)

        # Use the configured server URL hostname instead of the recording server's
        # internal hostname (needed for Tailscale/VPN access)
        from urllib.parse import urlparse
        parsed = urlparse(self.base_url)
        hostname = parsed.hostname

        if not hostname:
            # Fall back to recording server's hostname
            hostname = recording_server.get("hostName", "")

        if not hostname:
            raise ValueError(f"Could not determine hostname for recording server {rs_id}")

        # ImageServer port is typically 7563
        port = 7563

        return hostname, port

    def get_token(self) -> str:
        """Return the current access token for ImageServer authentication."""
        if not self.access_token:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        return self.access_token
