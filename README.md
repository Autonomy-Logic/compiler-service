# OpenPLC Compiler Service

HTTP API for OpenPLC Runtime v4 compilation pipeline: XML → ST → C → Debug files.

## Overview

The OpenPLC Compiler Service is a lightweight FastAPI microservice that provides an HTTP interface to the OpenPLC compilation toolchain (xml2st and iec2c). It supports the complete compilation pipeline for OpenPLC Runtime v4, from PLCopen XML to debuggable C code.

**Key Features:**
- Complete compilation pipeline with 4 endpoints
- Isolated compilation using temporary directories
- Returns compilation output, exit codes, and all generated files
- Automatic cleanup of temporary files
- Production-ready with Gunicorn + Uvicorn workers

**Use Cases:**
- OpenPLC IDE and development tools
- Automated build and test pipelines
- Web-based PLC programming interfaces
- Integration with third-party automation systems

## How It Works

The service follows a simple workflow:

1. Receives POST request with PLCopen XML in JSON body
2. Creates a unique temporary directory for isolation
3. Writes the XML to `plc.xml` in the temp directory
4. Executes `/usr/bin/xml2st --generate-st plc.xml`
5. Reads the generated `program.st` file (if compilation succeeded)
6. Returns JSON response with output, exit code, and ST code
7. Cleans up the temporary directory

Each request is isolated in its own temporary directory, preventing interference between concurrent compilation requests.

## Prerequisites

### Required Dependencies

- **Python 3.10+** - The service is developed and tested with Python 3.10
- **xml2st binary** - Must be installed at `/usr/bin/xml2st`
- **iec2c binary** - Must be installed at `/usr/bin/iec2c`

### Verifying Binary Installation

Check if the required binaries are installed:

```bash
ls -l /usr/bin/xml2st /usr/bin/iec2c
```

If the binaries are installed elsewhere, create symlinks:

```bash
sudo ln -s /path/to/xml2st /usr/bin/xml2st
sudo ln -s /path/to/iec2c /usr/bin/iec2c
```

**Note:** Both xml2st and iec2c are external dependencies not provided by this repository. Consult your OpenPLC documentation for installation instructions.

### Platform Support

The production installation script (`install.sh`) is designed for Amazon Linux and uses `yum` for package management. For other distributions, you'll need to adapt the installation commands accordingly.

## Quick Start (Local Development)

### 1. Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Start the Service

```bash
./start_local.sh
```

The service will start on `http://localhost:8000`.

### 3. Test the API

**Interactive Documentation:**

Open `http://localhost:8000/docs` in your browser to access the auto-generated Swagger UI.

**Simple curl Example:**

```bash
curl -X POST http://localhost:8000/generate-st \
  -H "Content-Type: application/json" \
  -d '{"plc_xml": "<?xml version=\"1.0\"?><project></project>"}'
```

**From File (with proper escaping):**

```bash
curl -X POST http://localhost:8000/generate-st \
  -H "Content-Type: application/json" \
  -d "{\"plc_xml\": \"$(cat input.xml | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])')\"}"
```

**Python Example:**

```python
import requests

# Read XML from file
with open("plc_program.xml", "r") as f:
    plc_xml = f.read()

# Send compilation request
response = requests.post(
    "http://localhost:8000/generate-st",
    json={"plc_xml": plc_xml}
)

result = response.json()

# Check compilation result
if result["exit_code"] == 0:
    print("Compilation successful!")
    if result["program_st"]:
        print(f"Generated ST code:\n{result['program_st']}")
else:
    print(f"Compilation failed with exit code {result['exit_code']}")
    print(f"Output:\n{result['output']}")
```

## API Reference

### POST /generate-st

Compiles PLCopen XML to Structured Text (Step 1 of the compilation pipeline).

**Request Body:**

```json
{
  "plc_xml": "string (required, non-empty)"
}
```

**Response (200 OK):**

```json
{
  "output": "string - Combined stdout and stderr from xml2st",
  "exit_code": "integer - Process exit code (0 = success)",
  "program_st": "string or null - Generated ST code if compilation succeeded"
}
```

**Error Responses:**

- **400 Bad Request** - Invalid JSON in request body
- **422 Unprocessable Entity** - Missing or invalid `plc_xml` field

---

### POST /compile-st

Compiles Structured Text to C files using iec2c (Step 2 of the compilation pipeline).

**Request Body:**

```json
{
  "program_st": "string (required, non-empty)"
}
```

**Response (200 OK):**

```json
{
  "output": "string - Combined stdout and stderr from iec2c",
  "exit_code": "integer - Process exit code (0 = success)",
  "files": {
    "POUS.c": "string - Generated C code for POUs",
    "POUS.h": "string - Header file for POUs",
    "VARIABLES.csv": "string - Variable definitions for debugger",
    "LOCATED_VARIABLES.h": "string - Located variable declarations",
    "config.c": "string - Configuration C code",
    "config.h": "string - Configuration header",
    "resource1.c": "string - Resource-specific C code (name varies)"
  }
}
```

**Error Responses:**

- **400 Bad Request** - Invalid JSON in request body
- **422 Unprocessable Entity** - Missing or invalid `program_st` field

**Note:** The exact set of generated files depends on the input ST program. All files generated by iec2c (except the input program.st) are returned in the `files` object.

---

### POST /generate-debug

Generates debug.c and appends debug strings to program.st (Step 3 of the compilation pipeline).

**Request Body:**

```json
{
  "program_st": "string (required, non-empty)",
  "variables_csv": "string (required, non-empty)"
}
```

**Response (200 OK):**

```json
{
  "output": "string - Combined stdout and stderr from xml2st",
  "exit_code": "integer - Process exit code (0 = success)",
  "program_st": "string or null - Updated program.st with debug strings appended",
  "debug_c": "string or null - Generated debug.c file"
}
```

**Error Responses:**

- **400 Bad Request** - Invalid JSON in request body
- **422 Unprocessable Entity** - Missing or invalid `program_st` or `variables_csv` field

**Note:** The `variables_csv` should be obtained from a prior `/compile-st` call. This endpoint modifies program.st in place by appending debug information as IEC comments.

---

### POST /generate-gluevars

Generates glueVars.c from LOCATED_VARIABLES.h (Step 4 of the compilation pipeline).

**Request Body:**

```json
{
  "located_variables_h": "string (required)"
}
```

**Response (200 OK):**

```json
{
  "output": "string - Combined stdout and stderr from xml2st",
  "exit_code": "integer - Process exit code (0 = success)",
  "glue_vars_c": "string or null - Generated glueVars.c file"
}
```

**Error Responses:**

- **400 Bad Request** - Invalid JSON in request body
- **422 Unprocessable Entity** - Missing or invalid `located_variables_h` field

**Note:** The `located_variables_h` should be obtained from a prior `/compile-st` call. This generates I/O glue code for mapping PLC variables to hardware.

---

**Important Design Note:**

All endpoints return HTTP 200 even when compilation fails. Always check the `exit_code` field in the response to determine success or failure. A non-zero exit code indicates compilation errors, with details in the `output` field.

## Production Deployment

### Installation (Amazon Linux)

Run the installation script as root:

```bash
sudo ./install.sh
```

This script will:
- Create a Python virtual environment
- Install pip and all dependencies
- Install and enable Nginx

### Running with Gunicorn

Start the service with multiple worker processes:

```bash
source venv/bin/activate
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000
```

**Worker Count Recommendations:**
- Start with `2-4 × CPU cores`
- Adjust based on xml2st compilation time and load patterns
- Each worker can handle one compilation at a time (subprocess.run blocks)

### Nginx Configuration

The `install.sh` script installs Nginx but does not configure it as a reverse proxy. Add the following to your Nginx configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Increase timeout for long compilations
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }
}
```

Reload Nginx after configuration:

```bash
sudo systemctl reload nginx
```

### Systemd Service (Optional)

Create `/etc/systemd/system/compiler-service.service`:

```ini
[Unit]
Description=OpenPLC Compiler Service
After=network.target

[Service]
Type=notify
User=ubuntu
Group=ubuntu
WorkingDirectory=/path/to/compiler-service
Environment="PATH=/path/to/compiler-service/venv/bin"
ExecStart=/path/to/compiler-service/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable compiler-service
sudo systemctl start compiler-service
```

## Configuration

### Current Configuration Options

The service currently has minimal configuration:

- **xml2st path:** Hard-coded to `/usr/bin/xml2st`
- **Port:** Specified via uvicorn/gunicorn command-line arguments
- **Workers:** Specified via gunicorn `-w` flag

**No environment variables or configuration files are currently supported.**

### Development Mode Options

When running locally, you can enable auto-reload for development:

```bash
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Repository Structure

```
compiler-service/
├── app/
│   └── main.py              # FastAPI application and endpoint logic
├── venv/                    # Python virtual environment (created by install.sh)
├── requirements.txt         # Python dependencies
├── install.sh               # Production installation script (Amazon Linux)
├── start_local.sh           # Local development startup script
└── README.md                # This file
```

## Security and Operational Considerations

### Security Warnings

⚠️ **No Authentication:** This service does not implement authentication or authorization. Do not expose it directly to the public internet.

**Recommendations:**
- Deploy behind an API gateway with authentication
- Use private network or VPN access only
- Implement rate limiting at the gateway level
- Consider adding API key authentication for production use

### Resource Considerations

⚠️ **No Timeouts:** The service does not enforce timeouts on xml2st execution. A malicious or malformed input could cause a worker to hang indefinitely.

⚠️ **No Input Size Limits:** Large XML inputs are not restricted and could consume excessive resources.

**Recommendations:**
- Implement request timeouts at the Nginx/gateway level
- Add input size limits in your API gateway
- Monitor worker processes for hung compilations
- Consider adding timeout parameter to subprocess.run() in production

### Operational Notes

- Each compilation request creates and cleans up a temporary directory
- Temporary directories use the prefix `xml2st_` for easy identification
- Cleanup occurs even if compilation fails (via `finally` block)
- Concurrent requests are isolated and do not interfere with each other

## Troubleshooting

### "xml2st not found" or Command Fails

**Problem:** The service cannot find the xml2st binary.

**Solution:**
```bash
# Verify xml2st exists
which xml2st

# Create symlink if needed
sudo ln -s /actual/path/to/xml2st /usr/bin/xml2st

# Verify permissions
ls -l /usr/bin/xml2st
```

### program_st is null in Response

**Problem:** Compilation completed but no ST code was generated.

**Solution:**
- Check the `exit_code` field (non-zero indicates failure)
- Review the `output` field for compiler error messages
- Verify your PLCopen XML is valid
- Test xml2st directly: `/usr/bin/xml2st --generate-st your-file.xml`

### 400 or 422 Errors

**Problem:** Request validation failed.

**Solutions:**
- **400 Bad Request:** Ensure request body is valid JSON
- **422 Unprocessable Entity:** Ensure `plc_xml` field exists and is a non-empty string

Example of valid request:
```json
{
  "plc_xml": "<?xml version=\"1.0\"?><project>...</project>"
}
```

### Long or Stuck Requests

**Problem:** Compilation requests take a very long time or hang.

**Explanation:** The service has no built-in timeout mechanism. Complex or malformed XML can cause xml2st to run indefinitely.

**Solutions:**
- Implement timeouts at the Nginx/gateway level
- Monitor and restart hung worker processes
- Consider modifying `app/main.py` to add timeout parameter to subprocess.run()

### Port Already in Use

**Problem:** Cannot start service because port 8000 is in use.

**Solution:**
```bash
# Find process using port 8000
sudo lsof -i :8000

# Kill the process or use a different port
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## Development Notes

### Dependencies Explained

- **fastapi** - Modern async web framework for building APIs
- **uvicorn** - ASGI server for running FastAPI applications
- **gunicorn** - Process manager for production (manages multiple Uvicorn workers)
- **python-multipart** - Enables form-data parsing (included for potential future file upload support)

### Running Tests

Currently, this repository does not include automated tests. Consider adding:
- Unit tests for the endpoint logic
- Integration tests with sample PLC XML files
- Error handling tests

### Code Style

The codebase follows standard Python conventions. When contributing:
- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Keep the service simple and focused on its single responsibility

## Future Enhancements

Potential improvements for future versions:

- **Health Check Endpoint:** Add `/health` endpoint for monitoring
- **Authentication:** Implement API key or OAuth2 authentication
- **Request Timeouts:** Add configurable timeout for xml2st execution
- **Input Validation:** Add size limits and XML schema validation
- **Logging:** Structured logging with request IDs for debugging
- **Metrics:** Prometheus metrics for monitoring compilation times and success rates
- **Dockerization:** Container image for easier deployment
- **Configuration File:** Support for environment variables or config files
- **File Upload:** Direct file upload support (python-multipart is already included)

## License

Please refer to the repository license file for licensing information.

## Acknowledgements

This service is part of the OpenPLC project ecosystem and relies on the xml2st compiler for PLC program compilation.
