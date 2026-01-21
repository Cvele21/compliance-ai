from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import io

app = FastAPI()

# --- CONFIGURATION ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- VISITOR TRACKER ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    user_agent = request.headers.get("user-agent", "Unknown")
    if "UptimeRobot" not in user_agent:
        forwarded = request.headers.get("x-forwarded-for")
        ip = forwarded.split(",")[0] if forwarded else request.client.host
        print(f"👀 VISITOR: IP={ip} | Path={request.url.path}")
    return await call_next(request)

# --- 🔒 SECURITY: MANUAL BYTE CHECK ---
def is_secure_pdf(file_content: bytes) -> bool:
    # PDF files ALWAYS start with these bytes: %PDF (Hex: 25 50 44 46)
    # We check the first 4 bytes.
    header = file_content[:4]
    if header == b'%PDF':
        return True
    return False

# --- UPLOAD ENDPOINT ---
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    standard: str = Form(...),
    access_code: str = Form(None)
):
    print(f"📥 ANALYZING: {file.filename} for {standard}")

    # 1. READ FILE
    content = await file.read()
    
    # 2. 🛡️ SECURITY CHECK (The Fix)
    if not is_secure_pdf(content):
        print(f"🚨 BLOCKED: {file.filename} is not a PDF.")
        # This 400 error will trigger the 'Catch' block in Frontend
        raise HTTPException(status_code=400, detail="INVALID FILE: Please upload a valid PDF.")

    # 3. GENERATE REPORT TEXT
    report_text = f"""
    COMPLIANCE CORE AUDIT REPORT
    ============================
    DATE: 2026-01-21
    FILE: {file.filename}
    STANDARD: {standard}
    STATUS: PRELIMINARY SCAN COMPLETE

    [1] EXECUTIVE SUMMARY
    The system scanned the document against {standard} controls.
    
    [2] DETECTED GAPS (SIMULATED)
    - Control 3.1.1 (Access Control): 'Least Privilege' keyword found.
    - Control 3.5.2 (Identification): MFA requirements not detected.
    - Control 3.8.3 (Media Protection): No mention of FIPS 140-2.

    [3] RECOMMENDATION
    Review Section 4 of your policy. Ensure reporting guidelines are included.
    
    -- END OF REPORT --
    """

    # 4. RETURN DATA
    return {
        "status": "success",
        "report": report_text,
        "filename": f"Audit_Report_{file.filename}.txt"
    }

# --- NEW: DOWNLOAD ENDPOINT ---
@app.post("/download_report")
async def download_report(report_content: str = Form(...)):
    # Converts the text string back into a downloadable file
    stream = io.BytesIO(report_content.encode())
    return StreamingResponse(
        stream, 
        media_type="text/plain", 
        headers={"Content-Disposition": "attachment; filename=Audit_Report.txt"}
    )

# --- SERVE FRONTEND ---
@app.get("/", response_class=HTMLResponse)
async def serve_home():
    try:
        with open("frontend/index.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return "Error: frontend/index.html not found."