from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.responses import PlainTextResponse
import tempfile
import subprocess
import os
import shutil

app = FastAPI(title="OpenPLC Compiler Service")

@app.post("/generate-st", response_class=PlainTextResponse)
async def generate_st(plc_xml: UploadFile):
    # Create a unique temporary directory
    temp_dir = tempfile.mkdtemp(prefix="xml2st_")
    xml_path = os.path.join(temp_dir, plc_xml.filename)
    st_path = os.path.join(temp_dir, "program.st")

    try:
        # Save uploaded XML file
        with open(xml_path, "wb") as f:
            f.write(await plc_xml.read())

        # Run xml2st command
        result = subprocess.run(
            ["xml2st", "--generate-st", xml_path],
            cwd=temp_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=f"xml2st failed:\n{result.stderr}")

        # Ensure output exists
        if not os.path.exists(st_path):
            raise HTTPException(status_code=500, detail="program.st not generated")

        # Read program.st and return content
        with open(st_path, "r") as f:
            content = f.read()

        return content

    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)
