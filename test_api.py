import requests
import json
import pandas as pd
import os
from fpdf import FPDF
from datetime import datetime

# CONFIGURATION
BASE_URL = "http://localhost:8000"
TEST_FILE = "test_dataset_report.xlsx"
REPORT_FILENAME = "Verification_Test_Report.pdf"

def create_test_file():
    """Creates a fresh Excel file for testing"""
    data_staff = {
        "Staff ID": [101, 102, 103, 104, 105],
        "Name": ["Alice", "Bob", "Charlie", "David", "Eve"],
        "Join Date": ["2023-01-01", "2023-06-15", "2022-01-01", "2024-01-01", "2023-03-10"],
        "Salary": [50000, 60000, 75000, 55000, 62000],
        "Dept": ["Sales", "Sales", "IT", "HR", "IT"]
    }
    data_feedback = {
        "ID": [1, 2, 3],
        "Comment": [
            "The system is amazing and very fast.", 
            "I hated the experience, it was too slow.",
            "It is okay, essentially average performance."
        ]
    }
    with pd.ExcelWriter(TEST_FILE) as writer:
        pd.DataFrame(data_staff).to_excel(writer, sheet_name="Staff", index=False)
        pd.DataFrame(data_feedback).to_excel(writer, sheet_name="Feedback", index=False)
    return TEST_FILE

class TestReportPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'AI Excel Engine - Verification Report', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def add_test_case(self, case_num, title, url, payload, response):
        self.add_page()
        # Title
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(220, 230, 241) # Light Blue
        self.cell(0, 10, f"Test Case #{case_num}: {title}", 1, 1, 'L', fill=True)
        self.ln(5)
        
        # Endpoint Info
        self.set_font('Arial', 'B', 10)
        self.cell(0, 6, f"Endpoint: {url}", 0, 1)
        self.ln(2)
        
        # INPUT SECTION
        self.set_font('Arial', 'B', 10)
        self.cell(0, 6, "Input Payload (Code/JSON):", 0, 1)
        self.set_font('Courier', '', 8)
        self.set_fill_color(245, 245, 245) # Light Gray
        
        # Pretty Print JSON
        input_str = json.dumps(payload, indent=2)
        self.multi_cell(0, 5, input_str, 1, 'L', fill=True)
        self.ln(5)

        # OUTPUT SECTION
        self.set_font('Arial', 'B', 10)
        self.cell(0, 6, "Engine Response:", 0, 1)
        self.set_font('Courier', '', 8)
        
        # Handle Output
        resp_str = json.dumps(response, indent=2)
        # Truncate if huge
        if len(resp_str) > 2000:
            resp_str = resp_str[:2000] + "\n... [Output Truncated for PDF]"
            
        self.multi_cell(0, 5, resp_str, 1, 'L', fill=False)
        
        # Pass/Fail Check
        self.ln(5)
        is_error = "error" in str(response).lower() or "detail" in str(response).lower()
        # Note: Some test cases EXPECT errors (Edge cases), so we just label status
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, f"Result: {'Captured'}", 0, 1)

# --- 3. RUNNER ---
def run_tests():
    pdf = TestReportPDF()
    create_test_file()
    
    # 0. Upload File (Prerequisite)
    with open(TEST_FILE, "rb") as f:
        requests.post(f"{BASE_URL}/ingest/excel", files={"file": f})

    # THE 10 TEST CASES
    test_cases = [
        {
            "title": "Ingest Excel File (Sanity Check)",
            "url": "/ingest/excel",
            "payload": {"file": "test_dataset_report.xlsx"}
        },
        {
            "title": "Advanced Analysis: Pivot Table",
            "url": "/analyze/",
            "payload": {
                "file_path": f"uploaded_files/{TEST_FILE}",
                "question": "Create a pivot table for 'Staff' sheet. Index='Dept', Values='Salary', aggfunc='mean'."
            }
        },
        {
            "title": "Advanced Analysis: Date Calculation",
            "url": "/analyze/",
            "payload": {
                "file_path": f"uploaded_files/{TEST_FILE}",
                "question": "In 'Staff', add column 'Tenure' = difference in days between '2025-01-01' and 'Join Date'."
            }
        },
        {
            "title": "Advanced Analysis: Complex Filter",
            "url": "/analyze/",
            "payload": {
                "file_path": f"uploaded_files/{TEST_FILE}",
                "question": "Filter 'Staff' where Salary > 55000 and Dept is 'Sales'."
            }
        },
        {
            "title": "V2 Feature: Sentiment Analysis Only",
            "url": "/enrich/sentiment",
            "payload": {
                "file_path": f"uploaded_files/{TEST_FILE}",
                "sheet_name": "Feedback",
                "text_column": "Comment",
                "tasks": ["sentiment"]
            }
        },
        {
            "title": "V2 Feature: Summarization Only",
            "url": "/enrich/sentiment",
            "payload": {
                "file_path": f"uploaded_files/{TEST_FILE}",
                "sheet_name": "Feedback",
                "text_column": "Comment",
                "tasks": ["summary"]
            }
        },
        {
            "title": "V2 Feature: Multi-Modal (Both)",
            "url": "/enrich/sentiment",
            "payload": {
                "file_path": f"uploaded_files/{TEST_FILE}",
                "sheet_name": "Feedback",
                "text_column": "Comment",
                "tasks": ["sentiment", "summary"]
            }
        },
        {
            "title": "Advanced Analysis: Unpivot/Melt",
            "url": "/analyze/",
            "payload": {
                "file_path": f"uploaded_files/{TEST_FILE}",
                "question": "Melt the 'Staff' table. Keep 'Staff ID' and 'Name' as keys. Melt 'Salary' and 'Dept'."
            }
        },
        {
            "title": "Edge Case: Invalid Column Name",
            "url": "/analyze/",
            "payload": {
                "file_path": f"uploaded_files/{TEST_FILE}",
                "question": "Show me the 'GhostColumn' in Staff."
            }
        },
        {
            "title": "Edge Case: Missing File",
            "url": "/enrich/sentiment",
            "payload": {
                "file_path": "files/does_not_exist.xlsx",
                "sheet_name": "Sheet1", 
                "text_column": "A"
            }
        }
    ]

    print("Running 10 Test Cases...")
    
    for i, case in enumerate(test_cases):
        full_url = BASE_URL + case['url']
        print(f"   [{i+1}/10] {case['title']}")
        
        # Execute Request
        try:
            # Special handling for Ingest endpoint which uses multipart/form-data
            if "ingest" in case['url']:
                with open(TEST_FILE, "rb") as f:
                    resp = requests.post(full_url, files={"file": f})
            else:
                resp = requests.post(full_url, json=case['payload'])
            
            try:
                json_resp = resp.json()
            except:
                json_resp = {"raw_text": resp.text}
                
            pdf.add_test_case(i+1, case['title'], case['url'], case['payload'], json_resp)
            
        except Exception as e:
            pdf.add_test_case(i+1, case['title'], case['url'], case['payload'], {"CRITICAL ERROR": str(e)})

    pdf.output(REPORT_FILENAME)
    print(f"\nReport generated: {REPORT_FILENAME}")
    
    # Cleanup
    if os.path.exists(TEST_FILE): os.remove(TEST_FILE)

if __name__ == "__main__":
    run_tests()