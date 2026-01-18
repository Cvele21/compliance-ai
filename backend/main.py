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
import uuid

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- 🔐 THE SECRET PASSWORD ---
PRO_ACCESS_CODE = "PRO-2026" 

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)
os.makedirs("reports", exist_ok=True)
app.mount("/reports", StaticFiles(directory="reports"), name="reports")

@app.get("/")
async def read_root():
    return FileResponse('frontend/index.html')

def analyze_policy(text, standard):
    prompt = f"""
    You are an expert Compliance Auditor. Audit this text against {standard}.
    
    OUTPUT FORMAT:
    SECTION 1: EXECUTIVE SUMMARY
    SECTION 2: COMPLIANCE CHECKLIST (Pass/Fail)
    SECTION 3: CRITICAL GAPS (Cite specific codes)
    SECTION 4: REMEDIATION PLAN
    SECTION 5: OFFICIAL SCORE (0-100)

    TEXT: {text[:10000]}
    """
    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Strict auditor."}, {"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

# --- PDF GENERATOR (Smart Mode) ---
def create_pdf(analysis_text, is_pro_user=False):
    pdf = FPDF()
    pdf.add_page()
    
    # 1. TRIAL WATERMARK (Only if NOT Pro)
    if not is_pro_user:
        pdf.set_font("Arial", "B", 40)
        pdf.set_text_color(220, 220, 220)
        pdf.cell(0, 20, "TRIAL MODE - DRAFT", 0, 1, 'C')
        pdf.set_text_color(0, 0, 0) # Reset color

    # 2. Header
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "COMPLIANCE CORE | AUDIT REPORT", 0, 1, 'C')
    pdf.line(10, 35, 200, 35)
    pdf.ln(10)

    # 3. Body
    pdf.set_font("Arial", "", 12)
    clean_text = analysis_text.replace("**", "").replace("### ", "").replace("## ", "")
    safe_text = clean_text.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 7, safe_text)
    
    # 4. Signature Block (ONLY for Pro Users)
    if is_pro_user:
        pdf.ln(20)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "_" * 60, 0, 1, 'C')
        pdf.cell(0, 10, "OFFICIAL DIGITAL AUDIT RECORD", 0, 1, 'C')
        
        pdf.set_font("Arial", "I", 10)
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # GENERATE UNIQUE HASH
        unique_hash = str(uuid.uuid4())[:8].upper()
        
        pdf.cell(0, 8, f"Timestamp: {current_time}", 0, 1, 'C')
        pdf.cell(0, 8, f"Validation Hash: {unique_hash}", 0, 1, 'C')
        pdf.cell(0, 8, "Engine: Compliance Core AI v1.0", 0, 1, 'C')
    else:
        # Warning for free users
        pdf.ln(20)
        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(255, 0, 0)
        pdf.cell(0, 10, "UNVERIFIED DRAFT - UPGRADE TO REMOVE WATERMARK", 0, 1, 'C')
    
    filename = f"Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(f"reports/{filename}")
    return filename

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), standard: str = Form(...), access_code: str = Form("")):
    
    # CHECK PASSWORD
    is_pro = False
    if access_code == PRO_ACCESS_CODE:
        print("🔓 PRO CODE ACCEPTED!")
        is_pro = True
    else:
        print("🔒 No valid code. Running Trial Mode.")

    # Save
    file_location = f"uploads/{file.filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Read
    try:
        reader = PdfReader(file_location)
        text = ""
        for page in reader.pages[:10]: text += page.extract_text()
    except: text = "Error"

    # Analyze
    analysis = analyze_policy(text, standard)
    
        # Print PDF (Pass the Pro Flag)
    pdf_filename = create_pdf(analysis, is_pro)
    
    # --- SECURITY CLEANUP ---
    # Delete the uploaded user file immediately
    if os.path.exists(file_location):
        os.remove(file_location)
        print(f"Deleted sensitive file: {file_location}")
    
    return {"report": analysis, "pdf_url": f"/reports/{pdf_filename}", "is_pro": is_pro}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)