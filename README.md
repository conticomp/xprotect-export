# XProtect Video Export

A web-based application for exporting video from Milestone XProtect VMS to MP4 format.

## Disclaimer

**This software is provided as a reference implementation only.**

- PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED
- NO SUPPORT IS PROVIDED - This is not a supported product
- USE AT YOUR OWN RISK - The authors are not responsible for any damages or data loss
- NOT AFFILIATED WITH MILESTONE SYSTEMS - This is an independent implementation

This code is intended as a starting point for developers integrating with Milestone XProtect. You are responsible for testing, securing, and maintaining any derivative works for your own use cases.

## Security Considerations

**IMPORTANT:** This application handles sensitive credentials. Before deploying:

- **Never commit `.env` files** - They contain plaintext credentials. The `.gitignore` should exclude them.
- **Use HTTPS in production** - The default configuration disables SSL verification (`verify=False`) for development convenience. Enable proper SSL certificate validation in production.
- **Restrict network access** - The web server binds to `0.0.0.0` by default. Consider binding to `127.0.0.1` or using a reverse proxy with authentication.
- **Use least-privilege accounts** - Create a dedicated Milestone user with only the permissions needed for video export.
- **Secure exported files** - Video exports may contain sensitive content. Implement appropriate access controls.

## Features

- OAuth authentication with XProtect API Gateway
- Two-token authentication flow (OAuth + SOAP Login for ImageServer)
- Camera listing via REST API
- Browser-based UI for selecting camera and time range
- **Raw H.264 export** - Near-instant exports using native codec passthrough (~3.8x smaller than JPEG)
- Request pipelining for high-throughput frame retrieval
- Auto-detection of codec format with JPEG fallback

## Requirements

- Python 3.10+
- FFmpeg (must be in PATH)
- Milestone XProtect 2021 R1 or later (with API Gateway)

## Installation

```bash
# Clone the repository
git clone https://github.com/conticomp/xprotect-export.git
cd xprotect-export

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your Milestone server details
```

## Configuration

Edit `.env` with your Milestone server details:

```
MILESTONE_SERVER_URL=https://your-milestone-server
MILESTONE_USERNAME=your_username
MILESTONE_PASSWORD=your_password
```

**Note:** Use a Basic user account, not a Windows/AD account, for OAuth authentication.

## Usage

```bash
# Start the server
python main.py
# Or with auto-reload for development:
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 in your browser.

1. Select a camera from the dropdown
2. Choose start and end times (max 10 minutes)
3. Click "Export Video"
4. Wait for processing (progress shown)
5. Download the MP4 file

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Browser UI     │────▶│  FastAPI Server  │────▶│  XProtect VMS   │
│  (static/*)     │     │  (main.py)       │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │                        │
                               ▼                        ▼
                        ┌──────────────┐         ┌─────────────┐
                        │ milestone_   │────────▶│ REST API    │
                        │ client.py    │         │ (OAuth)     │
                        └──────────────┘         └─────────────┘
                               │                        │
                               ▼                        ▼
                        ┌──────────────┐         ┌─────────────┐
                        │ image_       │────────▶│ ImageServer │
                        │ server.py    │  TCP    │ (Port 7563) │
                        │ (pipelined)  │ raw H264│             │
                        └──────────────┘         └─────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │   FFmpeg     │────▶ MP4 file
                        │  (-c:v copy) │  (no transcode)
                        └──────────────┘
```

### Key Files

| File | Purpose |
|------|---------|
| `main.py` | FastAPI application with REST endpoints |
| `milestone_client.py` | REST API + SOAP client for authentication |
| `image_server.py` | ImageServer TCP protocol client (raw H.264 + pipelining) |
| `config.py` | Environment variable configuration |
| `static/index.html` | Browser UI |
| `scripts/` | Test and utility scripts |
| `docs/MILESTONE_SDK_REFERENCE.md` | Comprehensive SDK documentation |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serve web UI |
| GET | `/api/cameras` | List available cameras |
| POST | `/api/export` | Start video export |
| GET | `/api/export/{filename}/download` | Download exported MP4 |

### Export Request

```json
POST /api/export
{
  "camera_id": "570b267f-ddc1-445c-a998-563437cdd3c0",
  "start_time": "2026-01-29T12:35:00-08:00",
  "end_time": "2026-01-29T12:37:00-08:00"
}
```

## Authentication Flow

XProtect requires **two different tokens** for full functionality:

1. **OAuth Token** (from `/API/IDP/connect/token`)
   - Used for REST API calls (cameras, configuration)
   - Standard JWT format

2. **ImageServer Token** (from SOAP `Login()`)
   - Used for TCP connections to ImageServer
   - Format: `TOKEN#guid#hostname//ServerConnector#...`
   - Obtained by calling `/ManagementServer/ServerCommandServiceOAuth.svc`

See `docs/MILESTONE_SDK_REFERENCE.md` for detailed documentation.

## Testing

```bash
# Test raw codec mode (verifies H.264 vs JPEG detection)
python scripts/test_raw_codec.py

# Test ImageServer connection
python scripts/test_imageserver.py
```

## Troubleshooting

### "Security token invalid" error
You're using the OAuth token instead of the ImageServer token. The ImageServer requires a token obtained via SOAP Login, not the OAuth JWT.

### No video data / empty frames
Check that the camera has recorded video at the requested time range. Use the XProtect Smart Client to verify recordings exist.

### Export produces corrupt video
The application auto-detects whether the server returns raw H.264 or JPEG. If detection fails, check the server logs for "Unknown frame format" warnings. Some older cameras may not support raw codec output.

### Frames work once then stop
The ImageServer sends a trailing `\r\n\r\n` after each frame's binary data. This must be consumed before sending the next request.

### Slow exports
Ensure raw H.264 mode is active (check logs for "Detected video format: h264"). JPEG mode requires transcoding and is significantly slower. Raw H.264 exports should be near-instant.

## References

- [Milestone Developer Documentation](https://doc.developer.milestonesys.com/)
- [MIP SDK Protocol Samples](https://github.com/milestonesys/mipsdk-samples-protocol)
- [ImageServer Protocol Reference](https://doc.developer.milestonesys.com/mipsdk/reference/protocols/imageserver_request_response.html)
- [Authentication Protocol](https://doc.developer.milestonesys.com/mipsdk/reference/protocols/protocol_authenticate.html)

## License

MIT License

Copyright (c) 2026 Continental Computers

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
