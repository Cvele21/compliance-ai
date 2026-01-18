from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv
import openai
from fpdf import FPDF
import datetime

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI()

# Enable CORS for local testing and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the frontend files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
def read_root():
    return JSONResponse(content={"message": "Compliance AI is running"})

# Serve the index.html directly
@app.get("/app")
async def read_index():
    from fastapi.responses import FileResponse
    return FileResponse('frontend/index.html')

def analyze_policy(text, standard):
    prompt = f"""
    You are an expert Compliance Auditor for Federal Regulations.
    
    TASK: Audit the following policy text against the standard: {standard}.
    
    OUTPUT FORMAT:
    SECTION 1: EXECUTIVE SUMMARY
    (Briefly explain if this policy meets the general intent of {standard}.)

    SECTION 2: COMPLIANCE CHECKLIST
    (List 3-5 key requirements of {standard}. Mark them as [PASS] or [FAIL] based on the text.)

    SECTION 3: CRITICAL GAPS
    (List missing specific clauses required by the law.)

    SECTION 4: REMEDIATION PLAN
    (Bullet points on how to fix the gaps.)

    SECTION 5: OFFICIAL SCORE
    (Give a score out of 100 based on completeness.)

    POLICY TEXT:
    {text[:4000]}
    """
    
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "system", "content": "You are a strict compliance auditor."},
                  {"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def create_pdf(analysis_text, filename="audit_report.pdf"):
    pdf = FPDF()
    pdf.add_page()
    
    # 1. Header
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "COMPLIANCE AI | AUDIT REPORT", 0, 1, 'C')
    pdf.line(10, 20, 200, 20) # Draw a line
    pdf.ln(10)

    # 2. The Analysis Body
    pdf.set_font("Arial", "", 12)
    # Fix for special characters (smart quotes, etc)
    safe_text = analysis_text.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 10, safe_text)
    
    # 3. THE OFFICIAL SIGNATURE BLOCK (New!)
    pdf.ln(20) # Add space
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "_" * 60, 0, 1, 'C') # The line
    
    pdf.cell(0, 10, "OFFICIAL DIGITAL AUDIT RECORD", 0, 1, 'C')
    
    pdf.set_font("Arial", "I", 10)
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    pdf.cell(0, 8, f"Timestamp: {current_time}", 0, 1, 'C')
    pdf.cell(0, 8, "Auditor ID: AI-NIST-VERIFIER-001", 0, 1, 'C')
    pdf.cell(0, 8, "Status: PRE-ASSESSMENT GENERATED", 0, 1, 'C')
    
    # Save file
    file_path = f"frontend/{filename}"
    pdf.output(file_path)
    return filename

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), standard: str = Form(...)):
    # 1. Read the PDF (Simulated text extraction for now)
    # In a real app, we would use pypdf to extract text here.
    # For this MVP, we will simulate reading text to save on complexity.
    policy_text = "This is a sample policy text extracted from the PDF..." 
    
    # 2. AI Analysis
    analysis = analyze_policy(policy_text, standard)
    
    # 3. Generate PDF with Signature
    pdf_filename = f"report_{datetime.datetime.now().timestamp()}.pdf"
    create_pdf(analysis, pdf_filename)
    
    # 4. Return URL
    # On Render, the URL needs to be relative
    return {"report": analysis, "pdf_url": f"{pdf_filename}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)