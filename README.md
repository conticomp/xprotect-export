# XProtect Video Export

A web-based application for exporting video from Milestone XProtect VMS to MP4 format.

## Status

**Work in Progress** - The ImageServer connection is not yet working. See [Issues](#known-issues) below.

## Features

- OAuth authentication with XProtect API Gateway
- Camera listing via REST API
- Browser-based UI for selecting camera and time range
- Video export to MP4 (when ImageServer connection is resolved)

## Requirements

- Python 3.10+
- FFmpeg
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
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 in your browser.

## Architecture

- `main.py` - FastAPI application with REST endpoints
- `milestone_client.py` - REST API client for authentication and camera listing
- `image_server.py` - ImageServer protocol client for video frame retrieval
- `config.py` - Environment variable configuration
- `static/index.html` - Browser UI

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serve web UI |
| GET | `/api/cameras` | List available cameras |
| POST | `/api/export` | Start video export |
| GET | `/api/export/{filename}/download` | Download exported MP4 |

## Known Issues

### ImageServer Connection Returns 403 Forbidden

When attempting to connect to the ImageServer endpoint on port 7563, all requests return 403 Forbidden despite valid authentication tokens. This occurs even though:

- OAuth authentication works (REST API calls succeed)
- SOAP authentication works (corporate token obtained)
- Smart Client connects successfully through the same network path

We are working with Milestone support to resolve this issue.

## References

- [Milestone Developer Documentation](https://doc.developer.milestonesys.com/)
- [MIP SDK Samples](https://github.com/milestonesys/mipsdk-samples-protocol)

## License

MIT
