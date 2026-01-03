import time
import json
import os
import shutil
import re
import ast
import traceback
import pandas as pd
import logging
from typing import List, Literal, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

#LLMs
import google.generativeai as genai
from openai import OpenAI

#Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

#Setup
load_dotenv()
app = FastAPI(title="AI Excel Analyst")

UPLOAD_FOLDER = "uploaded_files"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

#Configuration
if os.getenv("GEMINI_API_KEY"):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

groq_client = None
if os.getenv("GROQ_API_KEY"):
    groq_client = OpenAI(
        api_key=os.getenv("GROQ_API_KEY"), 
        base_url="https://api.groq.com/openai/v1"
    )

#Models
class QueryRequest(BaseModel):
    file_path: str
    question: str

class SentimentRequest(BaseModel):
    file_path: str
    sheet_name: str
    text_column: str

    tasks: List[Literal["sentiment", "summary"]] = ["sentiment"]
    sentiment_col_name: str = "Sentiment_Analysis"
    summary_col_name: str = "Content_Summary"

def call_llm(prompt: str):
    provider = os.getenv("DEFAULT_PROVIDER", "gemini").lower()
    model_name = os.getenv("DEFAULT_MODEL", "gemini-1.5-flash")
    
    print(f"CALLING {provider.upper()} (Model: {model_name})")

    try:
        if provider == "gemini":
            model = genai.GenerativeModel(model_name)
            return model.generate_content(prompt).text
            
        elif provider == "groq":
            if not groq_client: return "Error: GROQ_API_KEY missing"
            response = groq_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        return "Error: Invalid Provider"
    except Exception as e:
        return f"Error: {str(e)}"

#Endpoints
#Data Ingestion
@app.post("/ingest/excel")
def ingest_spreadsheet(file: UploadFile = File(...)):
    if not file.filename.endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="Invalid File")
    
    path = f"{UPLOAD_FOLDER}/{file.filename}"
    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    df = pd.read_excel(path, sheet_name=0)
    logger.info(f"File Saved: {path} | Columns detected: {len(df.columns)}")
    return {"status": "Ready", "file_path": path, "columns": list(df.columns)}

#Analysis
@app.post("/analyze/")
def analyze_data(request: QueryRequest):
    logger.info(f"User Query: {request.question}")

    if not os.path.exists(request.file_path): 
        raise HTTPException(404, "File not found")

    try:
        # Load all sheets
        dfs = pd.read_excel(request.file_path, sheet_name=None)
        
        # Schema Summary
        schema_info = []
        for name, df in dfs.items():
            cols_and_types = [f"{col} ({dtype})" for col, dtype in df.dtypes.items()]
            schema_info.append(f"Sheet '{name}': {cols_and_types}")
        info = "\n".join(schema_info)
        
        # --- STRICT PROMPT ---
        prompt = f"""
        You are a Pandas Code Generator.
        
        CONTEXT:
        - 'pd' is already imported.
        - 'dfs' is a dictionary of DataFrames loaded from Excel.
        - Keys in dfs: {list(dfs.keys())}
        - Schema: {info}
        
        USER REQUEST: "{request.question}"
        
        STRICT RULES:
        1. DO NOT import pandas. DO NOT read_excel. Use 'dfs' and 'pd' directly.
        2. Assign the FINAL OUTPUT to a variable named 'result'.
        3. If doing Date Math: ALWAYS convert to datetime first using pd.to_datetime(col, errors='coerce').
        4. If Pivot/Melt: 'result' must be a DataFrame.
        
        OUTPUT FORMAT:
        Write ONLY valid Python code inside markdown blocks. NO EXPLANATION.
        Example:
        ```python
        df = dfs['Staff']
        df['Days'] = (pd.to_datetime('2025-01-01') - pd.to_datetime(df['DateOfJoining'])).dt.days
        result = df
        ```
        """
        
        response = call_llm(prompt)
        
        # --- ROBUST EXTRACTION ---
        # Find code between ```python and ```
        match = re.search(r"```python(.*?)```", response, re.DOTALL)
        if match:
            code = match.group(1).strip()
        else:
            # Fallback: Just strip generic markdown if no block found
            code = response.replace("```python", "").replace("```", "").strip()
            
        logger.info(f"Generated Code:\n{code}")
        
        # Execute
        local_vars = {"pd": pd, "dfs": dfs}
        exec(code, {}, local_vars)
        result = local_vars.get("result")
        
        if result is None:
            return {"error": "AI executed code but 'result' variable was missing."}

        # --- SAVE & RETURN ---
        response_payload = {"type": "value", "data": str(result)}
        
        if isinstance(result, pd.DataFrame):
            # Save File
            out_filename = "analysis_result.xlsx"
            out_path = f"{UPLOAD_FOLDER}/{out_filename}"
            result.to_excel(out_path, index=False)
            
            # JSON Preview
            result_clean = result.where(pd.notnull(result), None)
            if len(result_clean) > 100: result_clean = result_clean.head(100)
            
            response_payload = {
                "type": "dataframe",
                "download_link": out_path,
                "data": result_clean.to_dict(orient="records")
            }
            
        elif isinstance(result, pd.Series):
             response_payload = {"type": "series", "data": result.to_dict()}

        return response_payload

    except Exception as e:
        logger.exception("Analysis Failed")
        return {"error": str(e), "failed_code": locals().get("code", "")}

#Sentiment and Summary
@app.post("/enrich/sentiment")
def analyze_sentiment(request: SentimentRequest):
    if not os.path.exists(request.file_path): raise HTTPException(404, "File not found")

    batch_size = int(os.getenv("DEFAULT_BATCH_SIZE", 10))
    row_limit = int(os.getenv("DEFAULT_LIMIT_ROWS", 50))
    provider = os.getenv("DEFAULT_PROVIDER", "gemini").lower()

    try:
        xls = pd.ExcelFile(request.file_path)
        sheet_dict = pd.read_excel(xls, sheet_name=None)
        df = sheet_dict[request.sheet_name]
        
        df_subset = df.head(row_limit).copy() if row_limit > 0 else df.copy()
        logger.info(f"Analysis (Tasks: {request.tasks}) on {len(df_subset)} rows")

        #PROMPT
        def build_prompt(texts):
            base = f"Analyze these {len(texts)} texts. Texts: {json.dumps(texts)}\n"
            
            if "sentiment" in request.tasks and "summary" in request.tasks:
                return base + """
                Return a valid JSON List of Objects.
                Each object MUST have exactly these keys: "sentiment", "summary".
                - "sentiment": 'Positive', 'Negative', or 'Neutral'.
                - "summary": A short 1-sentence summary.
                Example: [{"sentiment": "Positive", "summary": "Good service"}, ...]
                RETURN ONLY THE JSON LIST. NO MARKDOWN.
                """
            elif "sentiment" in request.tasks:
                return base + """
                Return a valid JSON List of strings.
                Values: 'Positive', 'Negative', 'Neutral'.
                Example: ["Positive", "Negative"]
                RETURN ONLY THE JSON LIST.
                """
            else:
                return base + """
                Return a valid JSON List of strings (Summaries).
                Example: ["User liked it", "Service bad"]
                RETURN ONLY THE JSON LIST.
                """

        def get_batch(texts):
            prompt = build_prompt(texts)
            res = call_llm(prompt)
            
            try:
                clean = res.replace("```json", "").replace("```", "").strip()
                
                #boundaries
                start = clean.find("[")
                end = clean.rfind("]")
                
                if start == -1 or end == -1:
                    logger.error(f"JSON Parse Failed (No brackets): {clean[:100]}...")
                    return None

                json_str = clean[start:end+1]
                
                #Parse
                try: data = json.loads(json_str)
                except: data = ast.literal_eval(json_str)
                
                if isinstance(data, list) and len(data) == len(texts):
                    return data
                
                logger.error(f"Mismatch: Expected {len(texts)} items, got {len(data) if isinstance(data, list) else 'Not List'}")
                return None
                
            except Exception as e:
                logger.error(f"Batch Failed: {str(e)} | Raw: {res[:50]}...")
                return None

        results_sentiment = []
        results_summary = []
        comments = df_subset[request.text_column].tolist()
        
        for i in range(0, len(comments), batch_size):
            batch = comments[i:i+batch_size]
            logger.info(f"Processing Batch {i} to {i+batch_size}...")
            
            batch_data = get_batch(batch)
            
            if batch_data is None:
                if "sentiment" in request.tasks: results_sentiment.extend(["Error"] * len(batch))
                if "summary" in request.tasks: results_summary.extend(["Error"] * len(batch))
            else:
                if "sentiment" in request.tasks and "summary" in request.tasks:
                    for item in batch_data:
                        sent = item.get("sentiment") or item.get("Sentiment") or "Neutral"
                        summ = item.get("summary") or item.get("Summary") or "No Summary"
                        results_sentiment.append(sent)
                        results_summary.append(summ)
                        
                elif "sentiment" in request.tasks:
                    results_sentiment.extend(batch_data)
                else:
                    results_summary.extend(batch_data)

            if provider == "gemini": time.sleep(2)

        pad = len(df_subset)
        
        if "sentiment" in request.tasks:
            while len(results_sentiment) < pad: results_sentiment.append("Error")
            results_sentiment = [str(x).title() if x != "Error" else x for x in results_sentiment]
            
            df_subset[request.sentiment_col_name] = results_sentiment
            df.loc[df_subset.index, request.sentiment_col_name] = df_subset[request.sentiment_col_name]

        if "summary" in request.tasks:
            while len(results_summary) < pad: results_summary.append("Error")
            df_subset[request.summary_col_name] = results_summary
            df.loc[df_subset.index, request.summary_col_name] = df_subset[request.summary_col_name]

        sheet_dict[request.sheet_name] = df
        out_path = f"{UPLOAD_FOLDER}/dataset_updated.xlsx"
        with pd.ExcelWriter(out_path) as writer:
            for name, data in sheet_dict.items(): data.to_excel(writer, sheet_name=name, index=False)
                
        logger.info("Analysis Completed")
        return {"status": "Success", "rows_processed": len(df_subset), "download_link": out_path}

    except Exception as e:
        logger.exception("Analysis Failed")
        raise HTTPException(status_code=500, detail=str(e))