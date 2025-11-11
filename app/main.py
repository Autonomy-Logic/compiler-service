from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import tempfile
import subprocess
import os
import shutil

app = FastAPI(title="OpenPLC Compiler Service")


"""
Generate Structured Text (ST) code from PLC XML.
The endpoint accepts a JSON payload with a "plc_xml" field containing the XML text.
It returns the generated ST code, command output, and exit code.

To test:
curl -X POST http://localhost:8000/generate-st \
  -H "Content-Type: application/json" \
  -d "{\"plc_xml\": \"$(cat input.xml | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])')\"}"
"""
@app.post("/generate-st", response_class=JSONResponse)
async def generate_st(request: Request):
    # Parse JSON body
    data = await request.json()
    plc_xml_text = data.get("plc_xml")
    if not plc_xml_text:
        raise HTTPException(status_code=422, detail="Missing 'plc_xml' field in request body")

    # Create a unique temporary directory
    temp_dir = tempfile.mkdtemp(prefix="xml2st_")
    xml_path = os.path.join(temp_dir, "input.xml")
    st_path = os.path.join(temp_dir, "program.st")

    try:
        # Save XML text to file
        with open(xml_path, "w") as f:
            f.write(plc_xml_text)

        # Run xml2st command
        result = subprocess.run(
            ["xml2st", "--generate-st", xml_path],
            cwd=temp_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Read program.st if generated
        program_st = None
        if os.path.exists(st_path):
            with open(st_path, "r") as f:
                program_st = f.read()

        response = {
            "output": result.stdout + ("\n" + result.stderr if result.stderr else ""),
            "exit_code": result.returncode,
            "program_st": program_st
        }
        return JSONResponse(content=response)

    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)
