from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
import openai
from fpdf import FPDF
import datetime
import shutil
from pypdf import PdfReader

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create folders if they don't exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("reports", exist_ok=True)

# Serve the frontend files for the PDF link
app.mount("/reports", StaticFiles(directory="reports"), name="reports")

# --- 1. THE FRONT DOOR ---
@app.get("/")
async def read_root():
    return FileResponse('frontend/index.html')

# --- 2. THE AI BRAIN ---
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
    {text[:10000]}
    """
    
    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a strict compliance auditor."},
                      {"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI Analysis Failed: {str(e)}"

# --- 3. THE PDF PRINTER (With Watermark & Signature) ---
def create_pdf(analysis_text, filename="audit_report.pdf"):
    pdf = FPDF()
    pdf.add_page()
    
    # --- A. THE WATERMARK (TRIAL MODE) ---
    # We print this FIRST so it sits "behind" or at the top of everything
    pdf.set_font("Arial", "B", 40)
    pdf.set_text_color(220, 220, 220) # Light Grey
    pdf.cell(0, 20, "TRIAL MODE - DRAFT", 0, 1, 'C') # Top Watermark
    
    # Reset color for normal text
    pdf.set_text_color(0, 0, 0) 

    # --- B. Header ---
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "COMPLIANCE AI | AUDIT REPORT", 0, 1, 'C')
    pdf.line(10, 35, 200, 35) # Draw a line (moved down slightly)
    pdf.ln(10)

    # --- C. Body (Cleaned) ---
    pdf.set_font("Arial", "", 12)
    # 1. Clean the robot text (** and ###)
    clean_text = analysis_text.replace("**", "").replace("### ", "").replace("## ", "")
    # 2. Handle special characters
    safe_text = clean_text.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 7, safe_text)
    
    # --- D. Signature Block ---
    pdf.ln(20)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "_" * 60, 0, 1, 'C')
    pdf.cell(0, 10, "OFFICIAL DIGITAL AUDIT RECORD", 0, 1, 'C')
    
    pdf.set_font("Arial", "I", 10)
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    pdf.cell(0, 8, f"Timestamp: {current_time}", 0, 1, 'C')
    pdf.cell(0, 8, "Auditor ID: AI-NIST-VERIFIER-001", 0, 1, 'C')
    
    # --- E. The Upsell Warning ---
    pdf.ln(5)
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(255, 0, 0) # Red
    pdf.cell(0, 10, "UNVERIFIED DRAFT - UPGRADE TO REMOVE WATERMARK", 0, 1, 'C')
    
    # Save
    report_filename = f"Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    file_path = f"reports/{report_filename}"
    pdf.output(file_path)
    return report_filename

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), standard: str = Form(...)):
    print(f"Processing {file.filename} for {standard}...")
    
    # 1. Save File
    file_location = f"uploads/{file.filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 2. Extract Text
    try:
        reader = PdfReader(file_location)
        text = ""
        for page in reader.pages[:10]: 
            text += page.extract_text()
    except:
        text = "Error reading PDF text."

    # 3. Analyze
    analysis = analyze_policy(text, standard)
    
    # 4. Print PDF
    pdf_filename = create_pdf(analysis)
    
    return {"report": analysis, "pdf_url": f"/reports/{pdf_filename}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)