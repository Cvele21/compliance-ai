from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import shutil
import os
from pypdf import PdfReader
from dotenv import load_dotenv
from openai import OpenAI
from fpdf import FPDF
import datetime

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)
os.makedirs("reports", exist_ok=True)
app.mount("/reports", StaticFiles(directory="reports"), name="reports")

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
INDEX_FILE = FRONTEND_DIR / "index.html"


@app.get("/")
def root():
    return FileResponse(INDEX_FILE)


@app.get("/health")
def health():
    return {"status": "active"}

# --- PRO PDF GENERATOR ---
class AuditPDF(FPDF):
    def header(self):
        # Draw a "Shield" Icon using lines
        self.set_draw_color(37, 99, 235) # Blue
        self.set_line_width(1)
        # Shield shape
        self.line(15, 15, 15, 25)
        self.line(15, 25, 20, 30)
        self.line(20, 30, 25, 25)
        self.line(25, 25, 25, 15)
        self.line(25, 15, 15, 15)
        
        # Company Name
        self.set_font('Arial', 'B', 12)
        self.set_text_color(15, 23, 42) # Dark Navy
        self.cell(20) # Move right
        self.cell(0, 10, 'COMPLIANCE AI', ln=0)
        
        # Date on right
        self.set_font('Arial', '', 10)
        self.set_text_color(100, 116, 139) # Grey
        self.cell(0, 10, f'Date: {datetime.date.today()}', ln=1, align='R')
        
        # Line break
        self.ln(10)
        self.set_draw_color(200, 200, 200)
        self.line(10, 35, 200, 35) # Horizontal line
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def create_pdf_report(audit_text, original_filename, standard_name):
    pdf = AuditPDF()
    pdf.add_page()
    
    # 1. REPORT TITLE
    pdf.set_font("Arial", "B", 24)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 15, f"AUDIT CERTIFICATE", ln=True, align="L")
    
    # 2. SUBTITLE (The Standard)
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(37, 99, 235) # Bright Blue
    pdf.cell(0, 10, f"STANDARD: {standard_name.upper()}", ln=True, align="L")
    
    # 3. FILE INFO
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(100)
    pdf.cell(0, 10, f"Source File: {original_filename}", ln=True)
    pdf.ln(5)
    
    # 4. THE CONTENT
    pdf.set_font("Courier", size=10) # Monospace looks more "technical"
    pdf.set_text_color(0)
    
    # Clean text
    clean_text = audit_text.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 6, clean_text)
    
    # 5. SIGNATURE LINE
    pdf.ln(20)
    pdf.set_draw_color(0)
    pdf.line(10, pdf.get_y(), 80, pdf.get_y())
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 5, "Authorized Signature", ln=True)
    
    filename = f"Audit_{standard_name.replace(' ', '_')}.pdf"
    pdf.output(f"reports/{filename}")
    return filename

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), standard: str = Form(...)):
    print(f"\n📂 PROCESSING: {file.filename} [{standard}]")
    file_location = f"uploads/{file.filename}"
    
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        reader = PdfReader(file_location)
        text = ""
        for i, page in enumerate(reader.pages):
            if i > 20: break 
            text += page.extract_text()
            
        print("🧠 RUNNING STRICT AI AUDIT...")
        
        # --- THE AGGRESSIVE PROMPT ---
        system_prompt = f"""
        You are a FEDERAL AUDITOR specializing in {standard}. 
        Your tone is STRICT, FORMAL, and DIRECT.
        
        Task: Audit this policy text against {standard}.
        
        Output Format:
        
        SECTION 1: EXECUTIVE SUMMARY
        [Write a 2-sentence summary of the document's relevance]
        
        SECTION 2: COMPLIANCE CHECKLIST
        [List 3-4 key requirements of {standard}. Mark them as [PASS] or [FAIL] based on the text.]
        
        SECTION 3: CRITICAL GAPS (Citations Required)
        [List failures. You MUST cite specific codes/sections of {standard} (e.g., 'CFR 164.312' or 'NIST 3.1.1').]
        
        SECTION 4: REMEDIATION PLAN
        [Bullet points on how to fix the gaps.]
        
        SECTION 5: OFFICIAL SCORE
        [0-100]
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Audit this:\n\n{text[:15000]}"}
            ]
        )
        audit_result = response.choices[0].message.content
        
        print("🖨️  PRINTING OFFICIAL CERTIFICATE...")
        pdf_name = create_pdf_report(audit_result, file.filename, standard)
        pdf_url = f"http://127.0.0.1:8000/reports/{pdf_name}"

        return {
            "status": "success", 
            "report": audit_result,
            "pdf_url": pdf_url
        }

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    print("🚀 BRANDED COMPLIANCE ENGINE READY")
    uvicorn.run(app, host="0.0.0.0", port=8000)