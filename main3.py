import time
import json
import os
import shutil
import re
import ast
import traceback
import pandas as pd
import logging
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
        logger.error(f"File not found at {request.file_path}")
        raise HTTPException(404, "File not found")

    try:
        dfs = pd.read_excel(request.file_path, sheet_name=None)
        info = "\n".join([f"- Sheet '{n}' cols: {list(d.columns)}" for n, d in dfs.items()])
        
        prompt = f"""
        You are a Pandas Expert. Data Structure: {info}
        User Question: "{request.question}"
        Task: Write a SINGLE LINE of Python code to assign the answer to variable 'result'.
        RULES: Use Pandas filtering. No loops. Access sheets via 'dfs'.
        Example: result = dfs['Sheet1'][dfs['Sheet1']['City'] == 'Paris']
        RETURN ONLY CODE.
        """
        
        response = call_llm(prompt)
        if response.startswith("Error"): return {"error": "AI Failed", "details": response}

        clean = response.replace("```python", "").replace("```", "").strip()
        match = re.search(r"(result\s*=.*)", clean, re.DOTALL)
        code = match.group(1).strip() if match else clean

        logger.info(f"Generated Code: {code}")
        
        print(f"Executing: {code}")
        
        local_vars = {"pd": pd, "dfs": dfs}
        exec(code, {}, local_vars)
        result = local_vars.get("result")

        logger.info("Analysis Execution Successful")
        
        if isinstance(result, pd.DataFrame):
            if len(result) > 100: result = result.head(100)
            return {"type": "dataframe", "data": result.where(pd.notnull(result), None).to_dict(orient="records")}
        elif isinstance(result, pd.Series):
            if len(result) > 100: result = result.head(100)
            return {"type": "series", "data": result.where(pd.notnull(result), None).to_dict()}
        return {"type": "value", "data": str(result)}

    except Exception as e:
        logger.exception("Analysis Failed")
        traceback.print_exc()
        return {"error": str(e), "failed_code": locals().get("code", "")}

#Sentiment Analysis
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
        logger.info(f"Starting Sentiment Analysis on {len(df_subset)} rows (Batch: {batch_size})")

        def normalize_result(raw_list):
            clean_list = []
            valid_labels = ["Positive", "Negative", "Neutral"]
            
            for item in raw_list:
                item_str = str(item).title() # Convert "positive" -> "Positive"
                
                #Exact Match
                if item_str in valid_labels:
                    clean_list.append(item_str)
                    continue
                
                #Fuzzy Match
                found = False
                for label in valid_labels:
                    if label in item_str:
                        clean_list.append(label)
                        found = True
                        break
                
                if not found:
                    clean_list.append("Neutral") # Default
            return clean_list

        def get_batch(texts):
            prompt = f"""
            Analyze sentiment for these {len(texts)} texts.
            Texts: {json.dumps(texts)}
            
            Format: Return ONLY a Python list of strings.
            Allowed values: 'Positive', 'Negative', 'Neutral'.
            Example: ['Positive', 'Negative', 'Neutral']
            NO EXPLANATION. ONLY THE LIST.
            """
            res = call_llm(prompt)
            
            try:
                match = re.search(r'\[.*\]', res, re.DOTALL)
                if not match: return ["Error"] * len(texts)
                
                raw_text = match.group(0)
                try: 
                    # Try parsing
                    parsed_list = json.loads(raw_text)
                except: 
                    # Fallback to AST
                    parsed_list = ast.literal_eval(raw_text)
                
                if isinstance(parsed_list, list) and len(parsed_list) == len(texts):
                    return normalize_result(parsed_list) 
                else:
                    return ["Error"] * len(texts)
                    
            except: 
                return ["Error"] * len(texts)

        all_sentiments = []
        comments = df_subset[request.text_column].tolist()
        
        for i in range(0, len(comments), batch_size):
            logger.info(f"Processing Batch {i} to {i+batch_size}...")
            all_sentiments.extend(get_batch(comments[i:i+batch_size]))
            if provider == "gemini": time.sleep(2)
            
        if len(all_sentiments) < len(df_subset):
            all_sentiments.extend(["Error"] * (len(df_subset) - len(all_sentiments)))
            
        df_subset['Sentiment_Analysis'] = all_sentiments[:len(df_subset)]
        df.loc[df_subset.index, 'Sentiment_Analysis'] = df_subset['Sentiment_Analysis']
        sheet_dict[request.sheet_name] = df
        
        out_path = f"{UPLOAD_FOLDER}/dataset_updated.xlsx"
        with pd.ExcelWriter(out_path) as writer:
            for name, data in sheet_dict.items(): data.to_excel(writer, sheet_name=name, index=False)
                
        logger.info("Sentiment Analysis Completed Successfully")
        return {"status": "Success", "rows_processed": len(df_subset), "download_link": out_path}

    except Exception as e:
        logger.exception("Sentiment Analysis Failed")
        raise HTTPException(status_code=500, detail=str(e))