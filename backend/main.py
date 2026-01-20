import magic # Security library for file types
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

app = FastAPI()

# --- 1. CONFIGURATION & CORS ---
# Allow the frontend to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, change this to ["https://compliance-core.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. VISITOR TRACKER (LOGGING) ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Logs every visitor's IP and Browser to the console.
    Ignores 'UptimeRobot' so logs stay clean.
    """
    # Get the real IP address (handling Render's proxy)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0]
    else:
        client_ip = request.client.host

    user_agent = request.headers.get("user-agent", "Unknown")

    # Only print if it's NOT the robot
    if "UptimeRobot" not in user_agent:
        print(f"👀 VISITOR: IP={client_ip} | Browser={user_agent} | Path={request.url.path}")

    response = await call_next(request)
    return response

# --- 3. SECURITY CHECK FUNCTION ---
def validate_pdf(file_content: bytes):
    """
    Uses 'Magic Bytes' to verify the file is actually a PDF.
    Prevents hackers from uploading .exe files renamed as .pdf.
    """
    try:
        # Create a magic object to detect mime type
        mime = magic.Magic(mime=True)
        file_type = mime.from_buffer(file_content)
        
        # If the file signature isn't 'application/pdf', reject it
        if file_type != 'application/pdf':
            print(f"🚨 SECURITY ALERT: Invalid file type detected: {file_type}")
            raise HTTPException(status_code=400, detail="Security Alert: Invalid file format. Only true PDFs accepted.")
            
    except Exception as e:
        # Fallback if magic fails (rare), but keeps system safe
        print(f"⚠️ Magic check warning: {e}")
        pass

# --- 4. MAIN UPLOAD ENDPOINT ---
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    standard: str = Form(...),
    access_code: str = Form(None)
):
    print(f"📥 RECEIVED: {file.filename} checking against {standard}")

    # 1. READ FILE
    content = await file.read()
    
    # 2. RUN SECURITY CHECK
    validate_pdf(content)

    # 3. CHECK ACCESS CODE (Simple logic for now)
    is_pro = False
    if access_code and access_code.strip() == "USCG2026": # Example 'Pro' code
        is_pro = True

    # 4. GENERATE REPORT (This simulates the AI Analysis)
    # In the future, this is where you connect the LLM
    
    report_text = f"""
    COMPLIANCE AUDIT REPORT
    -----------------------
    FILE: {file.filename}
    STANDARD: {standard}
    STATUS: ⚠️ GAP ANALYSIS COMPLETE
    
    EXECUTIVE SUMMARY:
    The document was scanned for {standard} compliance keywords.
    
    1. [MISSING] Incident Response Plan (IR-3.1)
       - The phrase 'report to DoD within 72 hours' was not found.
       
    2. [DETECTED] Access Control (AC-1.1)
       - 'Least Privilege' policy detected in section 4.
       
    3. [WARNING] Media Protection (MP-3)
       - No mention of 'FIPS 140-2' encryption found.
    
    RECOMMENDATION:
    Update the Incident Response section to include DIBNet reporting requirements.
    """

    # 5. RETURN RESPONSE TO FRONTEND
    return {
        "filename": file.filename,
        "status": "success",
        "report": report_text,
        "pdf_url": "#", # Placeholder for the generated PDF link
        "is_pro": is_pro
    }

# --- 5. HEALTH CHECK (For UptimeRobot) ---
@app.get("/")
def home():
    return {"status": "System Online", "version": "1.0.2"}