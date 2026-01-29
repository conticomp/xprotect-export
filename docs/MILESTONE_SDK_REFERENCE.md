# Milestone XProtect VMS SDK Reference

> **Purpose**: Comprehensive reference for developing integrations with Milestone XProtect VMS, including browser-based applications, REST APIs, and video export functionality.

---

## Table of Contents

1. [What is Milestone XProtect?](#what-is-milestone-xprotect)
2. [System Architecture](#system-architecture)
3. [Prerequisites for Development](#prerequisites-for-development)
4. [Authentication](#authentication)
5. [Available APIs and Protocols](#available-apis-and-protocols)
6. [Configuration REST API](#configuration-rest-api)
7. [ImageServer Protocol](#imageserver-protocol)
8. [WebRTC for Browser Streaming](#webrtc-for-browser-streaming)
9. [Video Export Approaches](#video-export-approaches)
10. [Building Browser-Based Applications](#building-browser-based-applications)
11. [Quick Reference](#quick-reference)
12. [Code Examples](#code-examples)

---

## What is Milestone XProtect?

Milestone XProtect is an enterprise Video Management System (VMS) that:
- Manages IP cameras, encoders, and other video devices
- Records and stores video from multiple sources
- Provides live viewing and playback capabilities
- Offers extensive integration APIs for third-party development

### Product Versions
- XProtect Essential+ (free, limited cameras)
- XProtect Express+
- XProtect Professional+
- XProtect Expert
- XProtect Corporate (enterprise, unlimited)

All versions share the same core SDK/API capabilities.

---

## System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         XProtect VMS Architecture                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────────┐     ┌────────────────────┐     ┌─────────────────┐ │
│  │  Management Server │     │   API Gateway      │     │ Identity        │ │
│  │  (Port 80/443)     │◄───►│   (Port 443)       │◄───►│ Provider (IDP)  │ │
│  │                    │     │                    │     │                 │ │
│  │  • Configuration   │     │  • REST APIs       │     │ • OAuth 2.0     │ │
│  │  • User mgmt       │     │  • WebSocket APIs  │     │ • Token mgmt    │ │
│  │  • Licensing       │     │  • WebRTC          │     │                 │ │
│  └────────────────────┘     └────────────────────┘     └─────────────────┘ │
│           │                          │                                      │
│           │                          │                                      │
│           ▼                          ▼                                      │
│  ┌────────────────────┐     ┌────────────────────┐     ┌─────────────────┐ │
│  │  Recording Server  │     │   Event Server     │     │  Mobile Server  │ │
│  │  (Port 7563)       │     │   (Port 22331)     │     │  (Optional)     │ │
│  │                    │     │                    │     │                 │ │
│  │  • Video storage   │     │  • Alarms          │     │                 │ │
│  │  • ImageServer     │     │  • Events          │     │                 │ │
│  │  • SOAP services   │     │  • Notifications   │     │                 │ │
│  └────────────────────┘     └────────────────────┘     └─────────────────┘ │
│           │                                                                 │
│           ▼                                                                 │
│  ┌────────────────────┐                                                    │
│  │   IP Cameras /     │                                                    │
│  │   Video Devices    │                                                    │
│  └────────────────────┘                                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Purpose | Default Port |
|-----------|---------|--------------|
| **Management Server** | Central configuration, authentication, licensing | 80 (HTTP), 443 (HTTPS) |
| **Recording Server** | Video recording, storage, retrieval | 7563 |
| **API Gateway** | Single entry point for all REST/WebSocket APIs | 443 |
| **Identity Provider (IDP)** | OAuth 2.0/OpenID Connect authentication | 443 (via API Gateway) |
| **Event Server** | Alarm management, event processing | 22331 |

### Data Flow for Video Export

```
1. Client authenticates → IDP → receives Bearer token
2. Client queries cameras → API Gateway → Management Server
3. Client requests video → API Gateway → Recording Server
4. Recording Server returns video data → Client
5. Client processes/converts video (e.g., MKV → MP4)
```

---

## Prerequisites for Development

### System Requirements

1. **XProtect VMS Installation**
   - Version 2021 R2 or later (for REST APIs)
   - Version 2022 R1 or later (for API Gateway included by default)
   - Version 2023 R3 or later (API Gateway mandatory)

2. **User Account**
   - XProtect Basic user with appropriate roles, OR
   - Windows/AD user with XProtect permissions

3. **Network Access**
   - HTTPS access to Management Server (port 443)
   - TCP access to Recording Server (port 7563) for ImageServer protocol

### Development Environment

**For REST API Development (Recommended for Browser Apps)**:
- Any language with HTTP client (Python, JavaScript, C#, etc.)
- No special SDK required

**For .NET SDK Development**:
- .NET Framework 4.8+ or .NET 6+
- MIP SDK NuGet packages
- Windows OS (for full SDK features)

**For Protocol-Level Development**:
- SOAP client library (for ServerCommandService)
- TCP socket support (for ImageServer protocol)
- XML parsing capabilities

### Recommended Python Dependencies

```
requests>=2.32.0        # HTTP client
requests-ntlm>=1.3.0    # Windows auth (optional)
websockets>=12.0        # WebSocket support
ffmpeg-python>=0.2.0    # Video conversion
```

### Recommended Node.js Dependencies

```json
{
  "axios": "^1.6.0",
  "ws": "^8.0.0",
  "fluent-ffmpeg": "^2.1.0"
}
```

---

## Authentication

### Overview

XProtect supports three authentication methods:

| Method | Use Case | Endpoint |
|--------|----------|----------|
| **OAuth 2.0 / OpenID Connect** | Browser apps, REST APIs | `/API/IDP/connect/token` |
| **HTTP Basic Auth** | Simple integrations | Management Server HTTPS |
| **Windows Auth (NTLM/Kerberos)** | Domain environments | Management Server HTTP |

### OAuth 2.0 Authentication (Recommended)

This is the recommended method for browser-based and modern applications.

#### Step 1: Discover Endpoints

```http
GET /api/.well-known/uris
```

Response:
```json
{
  "ProductVersion": "24.2.12065.1",
  "IdentityProvider": "https://server.example.com/IDP",
  "ApiGateways": ["https://server.example.com/API/"]
}
```

#### Step 2: Request Access Token

```http
POST /API/IDP/connect/token
Content-Type: application/x-www-form-urlencoded

grant_type=password
&username=myuser
&password=mypassword
&client_id=GrantValidatorClient
```

Response:
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsImtpZCI...",
  "expires_in": 3600,
  "token_type": "Bearer",
  "scope": "managementserver"
}
```

#### Step 3: Use Token in Requests

```http
GET /api/rest/v1/cameras
Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI...
```

#### Token Refresh

Tokens expire (default: 1 hour). Refresh before expiration:

```http
POST /API/IDP/connect/token
Content-Type: application/x-www-form-urlencoded

grant_type=password
&username=myuser
&password=mypassword
&client_id=GrantValidatorClient
```

### HTTP Basic Authentication

For simple server-to-server integrations:

```http
GET /api/rest/v1/cameras
Authorization: Basic base64(username:password)
```

**Note**: Only works over HTTPS (port 443).

### Windows Authentication (NTLM)

For domain-joined environments:

```python
from requests_ntlm import HttpNtlmAuth

response = requests.get(
    'http://server/ManagementServer/ServerCommandService.svc',
    auth=HttpNtlmAuth('DOMAIN\\username', 'password')
)
```

### Two-Token Authentication (ImageServer Protocol)

> **IMPORTANT**: The ImageServer TCP protocol requires a DIFFERENT token than the OAuth access token used for REST APIs.

XProtect uses two distinct tokens:

| Token Type | Purpose | How to Obtain | Used For |
|------------|---------|---------------|----------|
| **OAuth Access Token** | REST API authentication | `/API/IDP/connect/token` | REST APIs, WebRTC, WebSocket |
| **ImageServer Token** | TCP protocol authentication | SOAP `Login()` call | ImageServer TCP connections |

**Authentication Flow for ImageServer:**

```
1. Get OAuth token from IDP (as usual)
2. Call SOAP Login() with OAuth token in header
3. SOAP returns ImageServer session token
4. Use ImageServer token for TCP connections
```

**SOAP Login Request:**

```http
POST /ManagementServer/ServerCommandServiceOAuth.svc HTTP/1.1
Content-Type: text/xml; charset=utf-8
SOAPAction: http://videoos.net/2/XProtectCSServerCommand/IServerCommandService/Login
Authorization: Bearer {oauth_access_token}

<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsc="http://videoos.net/2/XProtectCSServerCommand">
  <soap:Body>
    <xsc:Login>
      <xsc:instanceId>{new-guid}</xsc:instanceId>
      <xsc:currentToken></xsc:currentToken>
    </xsc:Login>
  </soap:Body>
</soap:Envelope>
```

**SOAP Login Response:**

```xml
<LoginResult>
  <Token>IMAGESERVER_SESSION_TOKEN_HERE</Token>
  <RegistrationTime>2024-01-15T12:00:00Z</RegistrationTime>
  <TimeToLive>
    <MicroSeconds>3600000000</MicroSeconds>
  </TimeToLive>
</LoginResult>
```

**Python Example:**

```python
import uuid
import re
import requests

def get_imageserver_token(base_url, oauth_token):
    """Get ImageServer token via SOAP Login."""
    url = f"{base_url}/ManagementServer/ServerCommandServiceOAuth.svc"
    instance_id = str(uuid.uuid4())

    soap_envelope = f'''<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsc="http://videoos.net/2/XProtectCSServerCommand">
  <soap:Body>
    <xsc:Login>
      <xsc:instanceId>{instance_id}</xsc:instanceId>
      <xsc:currentToken></xsc:currentToken>
    </xsc:Login>
  </soap:Body>
</soap:Envelope>'''

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": "http://videoos.net/2/XProtectCSServerCommand/IServerCommandService/Login",
        "Authorization": f"Bearer {oauth_token}"
    }

    response = requests.post(url, data=soap_envelope, headers=headers, verify=False)
    response.raise_for_status()

    # Parse token from response
    token_match = re.search(r'<(?:a:)?Token>([^<]+)</(?:a:)?Token>', response.text)
    if not token_match:
        raise RuntimeError("Failed to parse token from SOAP response")

    return token_match.group(1)
```

---

## Available APIs and Protocols

### Modern APIs (via API Gateway)

| API | Purpose | Type |
|-----|---------|------|
| **Configuration API** | CRUD operations on VMS objects | REST |
| **Events API** | Query and trigger events | REST |
| **Alarms API** | Manage alarms | REST |
| **Bookmarks API** | Manage video bookmarks | REST |
| **Evidence Locks API** | Protect video from deletion | REST |
| **Event & State API** | Real-time event subscriptions | WebSocket |
| **Messages API** | Pub/sub messaging | WebSocket |
| **WebRTC Signaling** | Browser video streaming | REST/WebSocket |

### Legacy Protocols

| Protocol | Purpose | Port |
|----------|---------|------|
| **ServerCommandService** | Authentication, configuration | 80/443 |
| **RecorderCommandService** | PTZ, JPEG retrieval | 7563 |
| **ImageServer Protocol** | Video streaming, export | 7563 |

### API Base URLs

```
Discovery:     https://{host}/api/.well-known/uris
REST APIs:     https://{host}/api/rest/v1/
WebSocket:     wss://{host}/api/ws/events/v1
               wss://{host}/api/ws/messages/v1
WebRTC:        https://{host}/api/rest/v1/webRTC/
```

---

## Configuration REST API

### Base URL
```
https://{host}/api/rest/v1
```

### Common Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sites` | GET | Get VMS site information |
| `/cameras` | GET | List all cameras |
| `/cameras/{id}` | GET | Get specific camera |
| `/cameras/{id}?tasks` | GET | List available tasks for camera |
| `/cameras/{id}?task=GetSequences` | POST | Get recorded video sequences |
| `/cameras/{id}/streams` | GET | Get camera streams |
| `/recordingServers` | GET | List recording servers |
| `/recordingServers/{id}` | GET | Get specific recording server |
| `/hardware` | GET | List all hardware devices |

### Query Parameters

| Parameter | Description |
|-----------|-------------|
| `?disabled` | Include disabled items |
| `?tasks` | List available tasks |
| `?task={taskId}` | Execute a task |
| `?resources` | List child resources |
| `?definitions` | Get property definitions |
| `?page=N&size=M` | Pagination |

### Camera Object Schema

```json
{
  "data": {
    "id": "638bc8f1-cf28-4329-b8e6-5bba37bdb48f",
    "name": "Front Door Camera",
    "displayName": "Front Door Camera",
    "enabled": true,
    "channel": 0,
    "recordingEnabled": true,
    "recordingFramerate": 15.0,
    "prebufferEnabled": true,
    "prebufferSeconds": 3,
    "ptzEnabled": false,
    "edgeStorageEnabled": false,
    "gisPoint": "POINT (12.377 55.658)",
    "recordingStorage": {
      "type": "storages",
      "id": "storage-guid"
    },
    "relations": {
      "self": {
        "type": "cameras",
        "id": "638bc8f1-cf28-4329-b8e6-5bba37bdb48f"
      },
      "parent": {
        "type": "hardware",
        "id": "hardware-guid"
      }
    }
  }
}
```

### Recording Server Object Schema

```json
{
  "data": {
    "id": "9f21d63b-6693-4dfc-ad0c-829f27ef9315",
    "name": "Recording Server 1",
    "displayName": "Recording Server 1",
    "enabled": true,
    "hostName": "recorder.example.com",
    "portNumber": 7563,
    "webServerUri": "https://recorder.example.com:7563/",
    "version": "24.2.12065.1",
    "timeZoneName": "Eastern Standard Time"
  }
}
```

### GetSequences Task (Query Recorded Video)

Get information about recorded video for a camera:

```http
POST /api/rest/v1/cameras/{cameraId}?task=GetSequences
Authorization: Bearer {token}
Content-Type: application/json

{
  "sequenceType": "RecordingSequence",
  "time": "2024-01-15T12:00:00.000Z",
  "timeBefore": "1.00:00:00",
  "timeAfter": "1.00:00:00",
  "maxCountBefore": 100,
  "maxCountAfter": 100
}
```

Parameters:
- `sequenceType`: `RecordingSequence` | `MotionSequence` | `RecordingWithTriggerSequence`
- `time`: Center time for lookup (ISO 8601)
- `timeBefore`/`timeAfter`: Time span in format `ddd.HH:mm:ss`
- `maxCountBefore`/`maxCountAfter`: Maximum sequences to return

### JpegGetLive Task (Get Single Frame)

```http
POST /api/rest/v1/cameras/{cameraId}?task=JpegGetLive
Authorization: Bearer {token}
```

Returns a single JPEG frame from live video.

---

## ImageServer Protocol

The ImageServer Protocol is a TCP-based protocol for retrieving video from Recording Servers. It's required for frame-by-frame video retrieval and export.

### Connection Details

- **Transport**: TCP socket
- **Port**: 7563 (default)
- **Message Format**: XML
- **Message Terminator**: `\r\n\r\n` (CR-LF-CR-LF, bytes: 13-10-13-10)

### Connection Flow

```
1. Open TCP socket to Recording Server:7563
2. Send connect request with token
3. Receive connect response
4. Send video commands (goto, next, live, etc.)
5. Receive video frames
6. Periodically send connectupdate to refresh token
```

### Connect Request

> **IMPORTANT**: The `connectiontoken` must be an ImageServer token obtained via SOAP `Login()`, NOT the OAuth JWT token. See [Two-Token Authentication](#two-token-authentication-imageserver-protocol) for details.

```xml
<?xml version="1.0" encoding="utf-8"?>
<methodcall>
  <requestid>1</requestid>
  <methodname>connect</methodname>
  <username>dummy</username>
  <password>dummy</password>
  <alwaysstdjpeg>yes</alwaysstdjpeg>
  <connectparam>id={cameraGuid}&amp;connectiontoken={imageserver_token}</connectparam>
</methodcall>
```

**Required Elements**:
- `<alwaysstdjpeg>yes</alwaysstdjpeg>` - Request JPEG format. Without this, the server returns raw codec data (`application/x-genericbytedata-octet-stream`) which is typically H.264 NAL units, not displayable images.

**Optional Parameters in connectparam**:
- `streamid={streamGuid}` - For multi-stream cameras
- `compressionrate=100` - Quality (1-100, 100=original)
- `sendinitialimage=yes` - Receive image on connect

### Video Retrieval Commands

| Command | Purpose | Parameters |
|---------|---------|------------|
| `connect` | Establish connection | camera ID, token |
| `connectupdate` | Refresh token | new token |
| `goto` | Seek to timestamp | time (ms since Unix epoch) |
| `next` | Next frame | - |
| `previous` | Previous frame | - |
| `nextsequence` | Jump to next sequence | - |
| `previoussequence` | Jump to previous sequence | - |
| `begin` | First recorded frame | - |
| `end` | Last recorded frame | - |
| `live` | Start live streaming | - |
| `alarms` | Query sequences | starttime, endtime |

### Goto Command (Recorded Video)

```xml
<?xml version="1.0" encoding="utf-8"?>
<methodcall>
  <requestid>2</requestid>
  <methodname>goto</methodname>
  <time>1705320000000</time>
</methodcall>
```

**Note**: Time is milliseconds since Unix epoch (1970-01-01 00:00:00 UTC).

### Response Format

**XML Response** (for metadata):
```xml
<?xml version="1.0" encoding="utf-8"?>
<methodresponse>
  <requestid>2</requestid>
  <status>success</status>
</methodresponse>
```

**Image Response** (HTTP-style headers + binary):
```
ImageResponse
Content-type: image/jpeg
Content-length: 45678
Current: 1705320000500
Prev: 1705320000000
Next: 1705320001000
RequestId: 2
\r\n\r\n
[Binary JPEG data - exactly Content-length bytes]
\r\n\r\n
```

> **CRITICAL Implementation Detail**: After reading the binary data (exactly `Content-length` bytes), there is a trailing `\r\n\r\n` terminator that MUST be consumed before sending the next request. Failure to consume this terminator will cause the next `_recv_until(\r\n\r\n)` call to return immediately with empty data, breaking the frame retrieval loop.

### Query Recording Sequences

```xml
<?xml version="1.0" encoding="utf-8"?>
<methodcall>
  <requestid>3</requestid>
  <methodname>alarms</methodname>
  <starttime>1705233600000</starttime>
  <endtime>1705320000000</endtime>
</methodcall>
```

### Raw Codec Mode vs JPEG Mode

The ImageServer can return video data in two formats controlled by the `<alwaysstdjpeg>` element:

| Mode | Setting | Content-Type | Use Case |
|------|---------|--------------|----------|
| **JPEG** | `<alwaysstdjpeg>yes</alwaysstdjpeg>` | `image/jpeg` | Simple display, frame-by-frame viewing |
| **Raw Codec** | `<alwaysstdjpeg>no</alwaysstdjpeg>` | `application/x-genericbytedata-octet-stream` | High-performance export |

#### Performance Comparison

| Metric | JPEG Mode | Raw Codec Mode |
|--------|-----------|----------------|
| Frame size (4K) | ~5.3 MB | ~1.3 MB |
| Server CPU | High (transcode) | Low (passthrough) |
| Network transfer (2 min @ 15fps) | ~9.5 GB | ~2.5 GB |
| FFmpeg work | Decode JPEG + encode H.264 | Mux only (`-c:v copy`) |

**Recommendation**: Use raw codec mode (`alwaysstdjpeg=no`) for video export to reduce transfer size by ~75% and eliminate transcoding overhead.

> **Note**: Some camera/server configurations may still return JPEG even with `alwaysstdjpeg=no`. Always detect the actual format from the first frame and fall back to JPEG processing if needed. Check for JPEG signature (`FF D8 FF`) at the start of frame data.

### Raw Codec Data Format (Milestone Proprietary Header)

When using `<alwaysstdjpeg>no</alwaysstdjpeg>`, Milestone wraps the raw H.264 data in a 36-byte proprietary header:

```
Offset  Size  Description
------  ----  -----------
0-1     2     Codec type (big-endian): 0x000A = H.264/AVC
2-7     6     Reserved/unknown
8-11    4     Payload length
12-19   8     Timestamps
20-35   16    Reserved/metadata
36+     N     H.264 NAL units (Annex B format with 00 00 00 01 start codes)
```

#### Codec Type Values

| Value | Codec |
|-------|-------|
| 0x0001 | MJPEG |
| 0x000A | H.264/AVC |
| 0x000E | H.265/HEVC |
| 0x000F | AV1 |

#### Extracting Raw H.264

To get raw H.264 NAL units from Milestone's response:

```python
MILESTONE_HEADER_SIZE = 36
H264_CODEC_ID = 0x000A

def strip_milestone_header(data: bytes) -> bytes:
    """Strip 36-byte Milestone header to get raw H.264 NAL units."""
    if len(data) <= MILESTONE_HEADER_SIZE:
        return data

    # Verify codec type (big-endian)
    import struct
    codec_id = struct.unpack('>H', data[0:2])[0]
    if codec_id != H264_CODEC_ID:
        raise ValueError(f"Unexpected codec: 0x{codec_id:04X}")

    return data[MILESTONE_HEADER_SIZE:]
```

#### FFmpeg Integration (No Transcoding)

Feed the stripped H.264 data directly to FFmpeg for muxing without re-encoding:

```bash
# Mux raw H.264 to MP4 (no transcoding)
ffmpeg -f h264 -i - -c:v copy -movflags +faststart output.mp4
```

Python example:

```python
import subprocess

# Start FFmpeg in raw H.264 mode
ffmpeg_cmd = [
    "ffmpeg", "-y",
    "-f", "h264",           # Input is raw H.264 Annex B
    "-i", "-",              # Read from stdin
    "-c:v", "copy",         # No transcoding - just mux
    "-movflags", "+faststart",
    "output.mp4"
]

proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

# For each frame from ImageServer (raw codec mode)
for headers, raw_data in image_client.fetch_frames():
    h264_data = strip_milestone_header(raw_data)
    proc.stdin.write(h264_data)

proc.stdin.close()
proc.wait()
```

---

## WebRTC for Browser Streaming

WebRTC enables direct browser-based video streaming without plugins.

### Prerequisites

- XProtect 2022 R3+ (WebRTC support)
- Camera streaming H.264, H.265, or MJPEG
- No privacy masking enabled on camera

### Signaling Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/webRTC/session` | POST | Create session |
| `/webRTC/session/{id}` | PATCH | Update session |
| `/webRTC/iceCandidates/{id}` | GET/POST | Exchange ICE candidates |

### Create WebRTC Session

```http
POST /api/rest/v1/webRTC/session
Authorization: Bearer {token}
Content-Type: application/json

{
  "deviceId": "638bc8f1-cf28-4329-b8e6-5bba37bdb48f",
  "offerSDP": "v=0\r\no=- 123456...",
  "streamId": "stream-guid",
  "includeAudio": true,
  "iceServers": [
    {"url": "stun:stun.example.com:3478"}
  ]
}
```

### Playback (Recorded Video)

Add `playbackTimeNode` for recorded video:

```json
{
  "deviceId": "camera-guid",
  "offerSDP": "...",
  "playbackTimeNode": {
    "playbackTime": "2024-01-15T12:00:00Z",
    "speed": 1.0,
    "skipGaps": true
  }
}
```

### Browser Implementation Flow

```javascript
// 1. Create RTCPeerConnection
const pc = new RTCPeerConnection({
  iceServers: [{ urls: 'stun:stun.example.com:3478' }]
});

// 2. Create offer
const offer = await pc.createOffer();
await pc.setLocalDescription(offer);

// 3. Send to Milestone server
const response = await fetch('/api/rest/v1/webRTC/session', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    deviceId: cameraId,
    offerSDP: offer.sdp
  })
});

const { answerSDP, sessionId } = await response.json();

// 4. Set remote description
await pc.setRemoteDescription({ type: 'answer', sdp: answerSDP });

// 5. Handle video track
pc.ontrack = (event) => {
  document.getElementById('video').srcObject = event.streams[0];
};
```

---

## Video Export Approaches

### Approach 1: WebRTC + MediaRecorder (Browser-Based)

**Pros**: Pure browser, no backend needed for capture
**Cons**: Real-time only, can't export faster than playback

```javascript
const mediaRecorder = new MediaRecorder(stream, { mimeType: 'video/webm' });
mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
mediaRecorder.start();
// ... playback duration ...
mediaRecorder.stop();
// Convert chunks to file
```

### Approach 2: ImageServer Protocol + FFmpeg (Backend)

**Pros**: Full control, faster-than-realtime export
**Cons**: Requires backend service

```
1. Connect to ImageServer via TCP
2. Use goto/next to retrieve all frames
3. Pipe frames to FFmpeg
4. Output MKV/MP4
```

### Approach 3: MIP SDK MKVExporter (.NET)

**Pros**: Official, well-supported, handles all codecs
**Cons**: Requires Windows/.NET

```csharp
var exporter = new MKVExporter {
    CameraDeviceId = cameraGuid,
    StartTime = startDateTime,
    EndTime = endDateTime,
    OutputPath = "export.mkv"
};
exporter.Export();
```

### Approach 4: Hybrid (WebRTC Preview + Backend Export)

**Best for browser apps**:
- Use WebRTC for live preview and time selection
- Use backend service for actual export
- Convert MKV → MP4 with FFmpeg

### FFmpeg Conversion Commands

```bash
# Fast stream copy (no re-encoding)
ffmpeg -i input.mkv -c copy output.mp4

# Re-encode with H.264 (if needed)
ffmpeg -i input.mkv -c:v libx264 -c:a aac output.mp4

# Extract time range
ffmpeg -i input.mkv -ss 00:01:00 -to 00:02:00 -c copy output.mp4
```

---

## Building Browser-Based Applications

### Architecture for Browser App with REST API

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          Your Application                                   │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌──────────────────┐         ┌──────────────────┐                        │
│  │   Browser UI     │◄───────►│  Your Backend    │                        │
│  │   (React/Vue)    │  REST   │  API Server      │                        │
│  │                  │         │                  │                        │
│  │  • Camera list   │         │  • Auth proxy    │                        │
│  │  • Time picker   │         │  • Export jobs   │                        │
│  │  • WebRTC view   │         │  • File storage  │                        │
│  │  • Download      │         │  • FFmpeg        │                        │
│  └──────────────────┘         └────────┬─────────┘                        │
│                                        │                                   │
└────────────────────────────────────────┼───────────────────────────────────┘
                                         │
                      ┌──────────────────┼──────────────────┐
                      │    XProtect VMS  │                  │
                      │                  ▼                  │
                      │  ┌──────────────────────────────┐   │
                      │  │       API Gateway            │   │
                      │  │   (REST, WebSocket, WebRTC)  │   │
                      │  └──────────────────────────────┘   │
                      │                  │                  │
                      │  ┌───────────────┴───────────────┐  │
                      │  │                               │  │
                      │  ▼                               ▼  │
                      │  ┌─────────────┐   ┌─────────────┐  │
                      │  │ Management  │   │  Recording  │  │
                      │  │   Server    │   │   Server    │  │
                      │  └─────────────┘   └─────────────┘  │
                      │                                     │
                      └─────────────────────────────────────┘
```

### Your REST API Design

```yaml
# Authentication
POST /api/auth/login
  Request: { server, username, password }
  Response: { token, expiresIn, refreshToken }

POST /api/auth/refresh
  Request: { refreshToken }
  Response: { token, expiresIn }

# Cameras
GET /api/cameras
  Headers: Authorization: Bearer {token}
  Query: ?server={serverUrl}
  Response: [{ id, name, enabled, hasRecording }]

GET /api/cameras/{id}
  Response: { id, name, streams[], recordingServer }

# Recording Info
GET /api/cameras/{id}/sequences
  Query: ?start={ISO8601}&end={ISO8601}
  Response: [{ startTime, endTime, hasGaps }]

# Export
POST /api/export
  Request: {
    cameraId: "guid",
    startTime: "ISO8601",
    endTime: "ISO8601",
    format: "mp4"
  }
  Response: { jobId, status: "queued" }

GET /api/export/{jobId}
  Response: { status, progress, error?, downloadUrl? }

GET /api/export/{jobId}/download
  Response: Binary video file

DELETE /api/export/{jobId}
  Response: { success: true }
```

### CORS Configuration

For browser access, configure API Gateway CORS in `appsettings.Production.json`:

```json
{
  "CORS": {
    "Enabled": true,
    "Access-Control-Allow-Origin": "https://your-app.example.com",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Allow-Methods": "*"
  }
}
```

### Export Job Flow

```
1. Browser: User selects camera, start/end time
2. Browser: POST /api/export → Backend
3. Backend: Queue export job, return jobId
4. Background Worker:
   a. Authenticate to XProtect
   b. Connect to ImageServer on Recording Server
   c. Request frames for time range
   d. Write to MKV file
   e. Convert MKV → MP4 with FFmpeg
   f. Store in download directory
5. Browser: Poll GET /api/export/{jobId} for status
6. Browser: Download completed file
```

---

## Quick Reference

### Timestamp Formats

| Context | Format | Example |
|---------|--------|---------|
| REST API | ISO 8601 | `2024-01-15T12:00:00.000Z` |
| ImageServer | Unix ms | `1705320000000` |
| GetSequences timespan | `ddd.HH:mm:ss` | `1.00:00:00` (1 day) |

### Conversion Helpers

```javascript
// ISO 8601 to Unix milliseconds
const unixMs = new Date('2024-01-15T12:00:00Z').getTime();
// → 1705320000000

// Unix milliseconds to ISO 8601
const iso = new Date(1705320000000).toISOString();
// → "2024-01-15T12:00:00.000Z"
```

### Common Ports

| Service | Port | Protocol |
|---------|------|----------|
| Management Server (HTTP) | 80 | TCP |
| Management Server (HTTPS) | 443 | TCP |
| API Gateway | 443 | TCP |
| Recording Server | 7563 | TCP |
| Event Server | 22331 | TCP |

### GUIDs

All XProtect objects are identified by GUIDs:
```
Camera:     638bc8f1-cf28-4329-b8e6-5bba37bdb48f
Server:     9f21d63b-6693-4dfc-ad0c-829f27ef9315
```

### Video Codecs Supported

| Codec | ID | Common Use |
|-------|-----|------------|
| MJPEG | 0x0001 | Older cameras |
| H.264/AVC | 0x000A | Most common |
| H.265/HEVC | 0x000E | High efficiency |
| AV1 | 0x000F | Newest |

---

## Code Examples

### Python: Complete Authentication and Camera List

```python
import requests
from urllib.parse import urljoin

class MilestoneClient:
    def __init__(self, server_url, username, password):
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.password = password
        self.token = None
        self.session = requests.Session()
        self.session.verify = False  # For self-signed certs

    def authenticate(self):
        """Get OAuth token from IDP."""
        url = f"{self.server_url}/API/IDP/connect/token"
        data = {
            'grant_type': 'password',
            'username': self.username,
            'password': self.password,
            'client_id': 'GrantValidatorClient'
        }
        response = self.session.post(url, data=data)
        response.raise_for_status()
        result = response.json()
        self.token = result['access_token']
        self.session.headers['Authorization'] = f"Bearer {self.token}"
        return result

    def get_cameras(self, include_disabled=False):
        """Get list of all cameras."""
        url = f"{self.server_url}/api/rest/v1/cameras"
        if include_disabled:
            url += "?disabled"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get('array', [])

    def get_camera(self, camera_id):
        """Get specific camera details."""
        url = f"{self.server_url}/api/rest/v1/cameras/{camera_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get('data')

    def get_recording_servers(self):
        """Get list of recording servers."""
        url = f"{self.server_url}/api/rest/v1/recordingServers"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get('array', [])

    def get_sequences(self, camera_id, center_time, hours_before=24, hours_after=24):
        """Query recorded video sequences for a camera."""
        url = f"{self.server_url}/api/rest/v1/cameras/{camera_id}?task=GetSequences"
        data = {
            'sequenceType': 'RecordingSequence',
            'time': center_time,
            'timeBefore': f'{hours_before}:00:00',
            'timeAfter': f'{hours_after}:00:00',
            'maxCountBefore': 1000,
            'maxCountAfter': 1000
        }
        response = self.session.post(url, json=data)
        response.raise_for_status()
        return response.json()

# Usage
client = MilestoneClient('https://milestone-server.local', 'admin', 'password')
client.authenticate()
cameras = client.get_cameras()
for cam in cameras:
    print(f"{cam['name']} ({cam['id']})")
```

### Python: ImageServer Connection

> **Note**: This example requires TWO tokens - see [Two-Token Authentication](#two-token-authentication-imageserver-protocol).

```python
import socket
import re
import uuid
import requests
from datetime import datetime

class MilestoneAuth:
    """Handle both OAuth and ImageServer authentication."""

    def __init__(self, server_url, username, password):
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.password = password
        self.oauth_token = None
        self.imageserver_token = None
        self.instance_id = str(uuid.uuid4())

    def authenticate(self):
        """Get OAuth token from IDP."""
        url = f"{self.server_url}/API/IDP/connect/token"
        data = {
            'grant_type': 'password',
            'username': self.username,
            'password': self.password,
            'client_id': 'GrantValidatorClient'
        }
        response = requests.post(url, data=data, verify=False)
        response.raise_for_status()
        self.oauth_token = response.json()['access_token']
        return self.oauth_token

    def get_imageserver_token(self):
        """Get ImageServer token via SOAP Login."""
        if not self.oauth_token:
            raise RuntimeError("Must call authenticate() first")

        url = f"{self.server_url}/ManagementServer/ServerCommandServiceOAuth.svc"
        soap_envelope = f'''<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsc="http://videoos.net/2/XProtectCSServerCommand">
  <soap:Body>
    <xsc:Login>
      <xsc:instanceId>{self.instance_id}</xsc:instanceId>
      <xsc:currentToken></xsc:currentToken>
    </xsc:Login>
  </soap:Body>
</soap:Envelope>'''

        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "http://videoos.net/2/XProtectCSServerCommand/IServerCommandService/Login",
            "Authorization": f"Bearer {self.oauth_token}"
        }

        response = requests.post(url, data=soap_envelope, headers=headers, verify=False)
        response.raise_for_status()

        token_match = re.search(r'<(?:a:)?Token>([^<]+)</(?:a:)?Token>', response.text)
        if not token_match:
            raise RuntimeError("Failed to parse token from SOAP response")

        self.imageserver_token = token_match.group(1)
        return self.imageserver_token


class ImageServerClient:
    """TCP client for ImageServer protocol."""

    def __init__(self, host, port=7563):
        self.host = host
        self.port = port
        self.sock = None
        self.request_id = 0

    def connect(self, camera_id, imageserver_token):
        """Connect to ImageServer.

        Args:
            camera_id: Camera GUID
            imageserver_token: Token from SOAP Login (NOT OAuth token!)
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))

        self.request_id += 1
        # Single-line XML per Milestone docs
        request = (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<methodcall>'
            f'<requestid>{self.request_id}</requestid>'
            f'<methodname>connect</methodname>'
            f'<username>dummy</username>'
            f'<password>dummy</password>'
            f'<connectparam>id={camera_id}&amp;connectiontoken={imageserver_token}</connectparam>'
            f'</methodcall>\r\n\r\n'
        )

        self.sock.send(request.encode('utf-8'))
        return self._receive_response()

    def goto(self, timestamp_ms):
        """Seek to specific time."""
        self.request_id += 1
        request = (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<methodcall>'
            f'<requestid>{self.request_id}</requestid>'
            f'<methodname>goto</methodname>'
            f'<time>{timestamp_ms}</time>'
            f'</methodcall>\r\n\r\n'
        )

        self.sock.send(request.encode('utf-8'))
        return self._receive_image()

    def next_frame(self):
        """Get next frame."""
        self.request_id += 1
        request = (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<methodcall>'
            f'<requestid>{self.request_id}</requestid>'
            f'<methodname>next</methodname>'
            f'</methodcall>\r\n\r\n'
        )

        self.sock.send(request.encode('utf-8'))
        return self._receive_image()

    def _receive_response(self):
        """Receive XML response."""
        data = b''
        while not data.endswith(b'\r\n\r\n'):
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            data += chunk
        return data.decode('utf-8')

    def _receive_image(self):
        """Receive image with headers."""
        headers = {}
        header_data = b''
        while b'\r\n\r\n' not in header_data:
            header_data += self.sock.recv(1)

        for line in header_data.decode('utf-8').split('\r\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip()] = value.strip()

        content_length = int(headers.get('Content-length', 0))
        image_data = b''
        while len(image_data) < content_length:
            image_data += self.sock.recv(min(4096, content_length - len(image_data)))

        return headers, image_data

    def close(self):
        if self.sock:
            self.sock.close()


# Usage
auth = MilestoneAuth('https://milestone-server.local', 'admin', 'password')
auth.authenticate()  # Get OAuth token
imageserver_token = auth.get_imageserver_token()  # Get ImageServer token via SOAP

img_client = ImageServerClient('recorder.example.com')
img_client.connect(camera_guid, imageserver_token)  # Use ImageServer token!

# Get frame at specific time
timestamp_ms = int(datetime(2024, 1, 15, 12, 0, 0).timestamp() * 1000)
headers, image_data = img_client.goto(timestamp_ms)

# Save frame
with open('frame.jpg', 'wb') as f:
    f.write(image_data)

# Get next frames
for i in range(100):
    headers, image_data = img_client.next_frame()
    with open(f'frame_{i:04d}.jpg', 'wb') as f:
        f.write(image_data)
```

### JavaScript: Browser WebRTC Viewer

```javascript
class MilestoneWebRTC {
  constructor(serverUrl, token) {
    this.serverUrl = serverUrl;
    this.token = token;
    this.pc = null;
    this.sessionId = null;
  }

  async connect(cameraId, videoElement, options = {}) {
    // Create peer connection
    this.pc = new RTCPeerConnection({
      iceServers: options.iceServers || []
    });

    // Handle incoming video
    this.pc.ontrack = (event) => {
      videoElement.srcObject = event.streams[0];
    };

    // Create offer
    this.pc.addTransceiver('video', { direction: 'recvonly' });
    if (options.includeAudio) {
      this.pc.addTransceiver('audio', { direction: 'recvonly' });
    }

    const offer = await this.pc.createOffer();
    await this.pc.setLocalDescription(offer);

    // Send to server
    const body = {
      deviceId: cameraId,
      offerSDP: offer.sdp,
      includeAudio: options.includeAudio || false
    };

    // Add playback options for recorded video
    if (options.playbackTime) {
      body.playbackTimeNode = {
        playbackTime: options.playbackTime,
        speed: options.speed || 1.0,
        skipGaps: options.skipGaps || true
      };
    }

    const response = await fetch(`${this.serverUrl}/api/rest/v1/webRTC/session`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    });

    const result = await response.json();
    this.sessionId = result.sessionId;

    // Set remote description
    await this.pc.setRemoteDescription({
      type: 'answer',
      sdp: result.answerSDP
    });

    return this.sessionId;
  }

  disconnect() {
    if (this.pc) {
      this.pc.close();
      this.pc = null;
    }
  }
}

// Usage
const viewer = new MilestoneWebRTC('https://milestone-server.local', token);

// Live view
await viewer.connect(cameraId, document.getElementById('video'));

// Playback
await viewer.connect(cameraId, document.getElementById('video'), {
  playbackTime: '2024-01-15T12:00:00Z',
  speed: 1.0,
  skipGaps: true
});
```

---

## References

### Official Documentation
- [MIP VMS API Overview](https://doc.developer.milestonesys.com/mipvmsapi/api-overview/)
- [Configuration REST API](https://doc.developer.milestonesys.com/mipvmsapi/api/config-rest/v1/)
- [WebRTC Signaling API](https://doc.developer.milestonesys.com/mipvmsapi/api/webrtc-rest/v1/)
- [ImageServer Protocol](https://doc.developer.milestonesys.com/mipsdk/reference/protocols/imageserver_request_response.html)
- [Authentication Protocol](https://doc.developer.milestonesys.com/mipsdk/reference/protocols/protocol_authenticate.html)

### Sample Code
- [RestfulCommunicationPython](https://github.com/milestonesys/mipsdk-samples-protocol/tree/main/RestfulCommunicationPython)
- [WebRTC JavaScript](https://github.com/milestonesys/mipsdk-samples-protocol/tree/main/WebRTC_JavaScript)
- [ExportSample (.NET)](https://github.com/milestonesys/mipsdk-samples-component/tree/main/ExportSample)
- [ConfigApiClient (.NET)](https://github.com/milestonesys/mipsdk-samples-component/tree/main/ConfigApiClient)

### Developer Resources
- [Milestone Developer Forum](https://developer.milestonesys.com/s/)
- [OpenAPI Spec Download](https://doc.developer.milestonesys.com/mipvmsapi/api/config-rest/v1/openapi.yaml)
