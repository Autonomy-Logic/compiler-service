from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import subprocess
import os
import shutil
from typing import Dict

app = FastAPI(title="OpenPLC Compiler Service")

ALLOWED_ORIGINS = [
    "https://autonomy-edge.com",
    "https://www.autonomy-edge.com",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
    max_age=86400,  # Cache preflight requests for 24 hours
)


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
    # Parse and validate JSON body
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON.")

    plc_xml_text = data.get("plc_xml")
    if not isinstance(plc_xml_text, str) or not plc_xml_text.strip():
        raise HTTPException(status_code=422, detail="Missing or invalid 'plc_xml' field in request body.")

    # Create a unique temporary directory
    temp_dir = tempfile.mkdtemp(prefix="xml2st_")
    xml_path = os.path.join(temp_dir, "plc.xml")
    st_path = os.path.join(temp_dir, "program.st")

    try:
        # Save XML text to file
        with open(xml_path, "w") as f:
            f.write(plc_xml_text)

        # Run xml2st command
        result = subprocess.run(
            ["/usr/bin/xml2st", "--generate-st", xml_path],
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
            "output_stdout": result.stdout,
            "output_stderr": (result.stderr if result.stderr else ""),
            "exit_code": result.returncode,
            "program_st": program_st
        }
        return JSONResponse(content=response)

    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)


"""
Compile Structured Text (ST) code into C files using iec2c.
The endpoint accepts a JSON payload with a "program_st" field containing the ST code.
It returns all generated C files, command output, and exit code.

To test:
curl -X POST http://localhost:8000/compile-st \
  -H "Content-Type: application/json" \
  -d "{\"program_st\": \"$(cat program.st | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])')\"}"
"""
@app.post("/compile-st", response_class=JSONResponse)
async def compile_st(request: Request):
    # Parse and validate JSON body
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON.")

    program_st_text = data.get("program_st")
    if not isinstance(program_st_text, str) or not program_st_text.strip():
        raise HTTPException(status_code=422, detail="Missing or invalid 'program_st' field in request body.")

    # Create a unique temporary directory
    temp_dir = tempfile.mkdtemp(prefix="iec2c_")
    st_path = os.path.join(temp_dir, "program.st")
    lib_path = os.path.join(temp_dir, "lib")

    try:
        # Save ST text to file
        with open(st_path, "w") as f:
            f.write(program_st_text)


        result = subprocess.run(
            ["/usr/bin/iec2c", "-f", "-p", "-i", "-l", "program.st"],
            cwd=temp_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        generated_files: Dict[str, str] = {}
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            if os.path.isfile(file_path) and filename != "program.st":
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        generated_files[filename] = f.read()
                except Exception as e:
                    generated_files[filename] = f"Error reading file: {str(e)}"

        response = {
            "output_stdout": result.stdout,
            "output_stderr": (result.stderr if result.stderr else ""),
            "exit_code": result.returncode,
            "files": generated_files
        }
        return JSONResponse(content=response)

    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)


"""
Generate debug.c and append debug strings to program.st using xml2st --generate-debug.
The endpoint accepts a JSON payload with "program_st" and "variables_csv" fields.
It returns the updated program.st with debug strings and the generated debug.c file.

Note: The variables_csv should be obtained from a prior /compile-st call.

To test:
curl -X POST http://localhost:8000/generate-debug \
  -H "Content-Type: application/json" \
  -d "{\"program_st\": \"...\", \"variables_csv\": \"...\"}"
"""
@app.post("/generate-debug", response_class=JSONResponse)
async def generate_debug(request: Request):
    # Parse and validate JSON body
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON.")

    program_st_text = data.get("program_st")
    variables_csv_text = data.get("variables_csv")
    
    if not isinstance(program_st_text, str) or not program_st_text.strip():
        raise HTTPException(status_code=422, detail="Missing or invalid 'program_st' field in request body.")
    
    if not isinstance(variables_csv_text, str) or not variables_csv_text.strip():
        raise HTTPException(status_code=422, detail="Missing or invalid 'variables_csv' field in request body.")

    # Create a unique temporary directory
    temp_dir = tempfile.mkdtemp(prefix="xml2st_debug_")
    st_path = os.path.join(temp_dir, "program.st")
    csv_path = os.path.join(temp_dir, "VARIABLES.csv")
    debug_c_path = os.path.join(temp_dir, "debug.c")

    try:
        # Save ST and CSV text to files
        with open(st_path, "w") as f:
            f.write(program_st_text)
        
        with open(csv_path, "w") as f:
            f.write(variables_csv_text)

        # Run xml2st --generate-debug command
        result = subprocess.run(
            ["/usr/bin/xml2st", "--generate-debug", "program.st", "VARIABLES.csv"],
            cwd=temp_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        program_st_with_debug = None
        if os.path.exists(st_path):
            with open(st_path, "r") as f:
                program_st_with_debug = f.read()

        # Read debug.c if generated
        debug_c = None
        if os.path.exists(debug_c_path):
            with open(debug_c_path, "r") as f:
                debug_c = f.read()

        response = {
            "output_stdout": result.stdout,
            "output_stderr": (result.stderr if result.stderr else ""),
            "exit_code": result.returncode,
            "program_st": program_st_with_debug,
            "debug_c": debug_c
        }
        return JSONResponse(content=response)

    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)


"""
Generate glueVars.c from LOCATED_VARIABLES.h using xml2st --generate-gluevars.
The endpoint accepts a JSON payload with "located_variables_h" field.
It returns the generated glueVars.c file.

Note: The located_variables_h should be obtained from a prior /compile-st call.

To test:
curl -X POST http://localhost:8000/generate-gluevars \
  -H "Content-Type: application/json" \
  -d "{\"located_variables_h\": \"...\"}"
"""
@app.post("/generate-gluevars", response_class=JSONResponse)
async def generate_gluevars(request: Request):
    # Parse and validate JSON body
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON.")

    located_vars_text = data.get("located_variables_h")
    
    if not isinstance(located_vars_text, str):
        raise HTTPException(status_code=422, detail="Missing or invalid 'located_variables_h' field in request body.")

    # Create a unique temporary directory
    temp_dir = tempfile.mkdtemp(prefix="xml2st_glue_")
    located_vars_path = os.path.join(temp_dir, "LOCATED_VARIABLES.h")
    glue_vars_path = os.path.join(temp_dir, "glueVars.c")

    try:
        # Save LOCATED_VARIABLES.h text to file
        with open(located_vars_path, "w") as f:
            f.write(located_vars_text)

        # Run xml2st --generate-gluevars command
        result = subprocess.run(
            ["/usr/bin/xml2st", "--generate-gluevars", "LOCATED_VARIABLES.h"],
            cwd=temp_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Read glueVars.c if generated
        glue_vars_c = None
        if os.path.exists(glue_vars_path):
            with open(glue_vars_path, "r") as f:
                glue_vars_c = f.read()

        response = {
            "output_stdout": result.stdout,
            "output_stderr": (result.stderr if result.stderr else ""),
            "exit_code": result.returncode,
            "glue_vars_c": glue_vars_c
        }
        return JSONResponse(content=response)

    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)
