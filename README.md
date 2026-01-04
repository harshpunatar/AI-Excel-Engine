# 📊 AI Excel Analyst

**AI Excel Analyst** is an intelligent data processing engine that allows users to interact with Excel datasets using natural language.

Instead of writing complex SQL queries or Python scripts manually, users can simply ask *"Show me the average salary by Department"* or *"Analyze the sentiment of these customer reviews"*. The engine dynamically generates Pandas code or orchestrates LLM calls to deliver accurate, downloadable results.

## 🚀 Key Features

* **Natural Language Querying:** Converts English questions into executable Pandas code (Filter, GroupBy, Pivot, Join).
* **Automated Enrichment:** Performs Sentiment Analysis and Text Summarization on unstructured data columns.
* **Multi-Sheet Support:** Handles complex `.xlsx` files with foreign key relationships (e.g., Joining 'Staff' with 'Divisions').
* **Sandboxed Execution:** Runs dynamic code execution within an isolated Docker environment for security.
* **Idempotent Testing Suite:** Includes an automated runner that generates a PDF verification report.

---

## 📂 Project Structure

```text
├── main.py                 # Core FastAPI application & AI Agent logic
├── generate_dataset.py     # Script to create synthetic dummy data (Faker)
├── test_api.py             # Automated testing suite (creates PDF report)
├── Dockerfile              # Container configuration (Python 3.9 Slim)
├── requirements.txt        # Project dependencies
├── .env                    # API Keys (Not included in repo)
└── README.md               # Documentation
```

---

## 🛠️ Prerequisites

* **Docker Desktop** (Recommended for safe execution)
* **API Key:** An API Key from **Google Gemini** (Free Tier) or **Groq**.
* **Python 3.9+** (If running locally without Docker)

---

## Quick Start (Docker)

This is the recommended way to run the application to ensure environment consistency and security isolation.

### 1. Setup Environment Variables
Create a file named `.env` in the root directory and add your keys:

```ini
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
DEFAULT_PROVIDER=gemini
DEFAULT_MODEL=gemini-1.5-flash
```

### 2. Build the Image
```bash
docker build -t ai-excel-engine .
```

### 3. Run the Container
We use a **Volume Mount** to ensure logs and generated reports appear instantly on your host machine.

```bash
docker run -p 8000:8000 --env-file .env -v $(pwd):/app ai-excel-engine
```

The API is now live at: `http://localhost:8000/docs`

---

## How to Test

We strictly follow **Test-Driven Development (TDD)** principles. Do not test manually.

I have included an automated test suite (`test_api.py`) that acts as a robot user. It will:
1.  Generate a fresh, random Excel dataset (ensuring **idempotency**).
2.  Send 10 distinct test scenarios to the running Docker container.
3.  Test Happy Paths (Pivot tables, Sentiment) and Edge Cases (Missing files, 404s).
4.  Compile the results into a professional **PDF Report**.

**To run the test:**
*(Ensure the Docker container is running first!)*

```bash
# In a new terminal window
pip install requests fpdf pandas openpyxl  # Install test dependencies
python test_api.py
```

**Output:** A file named `Verification_Test_Report.pdf` will be generated in your project folder.

---

## API Endpoints

### 1. Ingest Data
* **POST** `/ingest/excel`
* **Input:** Upload an `.xlsx` file.
* **Output:** Saves file and returns schema/column info.

### 2. Data Analysis (Code Interpreter)
* **POST** `/analyze/`
* **Input:** `{"question": "Filter for IT Dept and calculate average Age"}`
* **Logic:** Uses LLM to write Pandas code -> Executes in Sandbox -> Returns Result.

### 3. AI Enrichment
* **POST** `/enrich/sentiment`
* **Input:** `{"sheet_name": "Feedback", "tasks": ["sentiment", "summary"]}`
* **Logic:** Batches text rows -> Sends to LLM -> Appends new columns to Excel.

---

## Architecture & Design Decisions

### 1. Why Docker?
The application uses Python's `exec()` function to run AI-generated code. This allows for powerful queries but poses a Remote Code Execution (RCE) risk. Running inside **Docker** isolates this risk—if the AI accidentally deletes files, it only affects the disposable container, not the host server.

### 2. Batch Processing
For the `/enrich/` endpoint, we process rows in **batches of 10**. This optimizes API token usage and prevents HTTP Timeouts that occur when processing large files row-by-row.

### 3. Security (Docker Hub)
This image is designed to be **built locally**. It is not pushed to public registries (like Docker Hub) to prevent any accidental leakage of API keys or environment variables embedded during the build context.

---

## Tech Stack

* **Framework:** FastAPI (Python)
* **Data Manipulation:** Pandas, OpenPyXL
* **AI/LLM:** Google Gemini (via `google-generativeai`), OpenAI Client (for Groq)
* **Infrastructure:** Docker
* **Testing:** FPDF, Requests
