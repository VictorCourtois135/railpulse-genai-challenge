import ollama
import pyodbc
import os
import time
import logging
import re
from prompts import SYSTEM_PROMPT , ROUTING_PROMPT
from dotenv import load_dotenv
from groq import Groq
load_dotenv(".env")

def get_db_connection(max_retries=3, base_delay_seconds=10 ):
    
    conn_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER=tcp:{os.environ['AZURE_SQL_SERVER']},1433;"
        f"DATABASE={os.environ['AZURE_SQL_DATABASE']};"
        f"UID={os.environ['AZURE_SQL_CLIENT_ID']};"
        f"PWD={os.environ['AZURE_SQL_CLIENT_SECRET']};"
        "Authentication=ActiveDirectoryServicePrincipal;"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;"
    )

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            return pyodbc.connect(conn_string)
        except pyodbc.Error as e:
            last_error = e
            logging.warning(f"DB connection attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(base_delay_seconds * attempt)  # 5s, then 10s
    
    raise last_error

def call_llm(system_prompt, user_prompt, provider="groq", history = None):
    messages=[{"role":"system","content":system_prompt}]
    if history:
        messages.extend(history)
        
    messages.append({"role": "user", "content": user_prompt})
    
    if provider == "llama":
            response = ollama.chat(model="llama3:8b",messages=messages)
            return response.message.content 
        
    elif provider == "groq":
        client = Groq(api_key=os.environ['GROQ_API_KEY'])
        response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",  
        messages=messages
        )
        return response.choices[0].message.content
    else:
        raise ValueError("No model found")
                


def clean_sql_response(text):
    result = re.search(r"\bSELECT\b", text)
    if result is None:
        raise ValueError("No SQL query found in the model's response")

    sql_part = text[result.start():]

    ending = re.search(r"```", sql_part)
    if ending:
        return sql_part[:ending.start()]
    else:
        return sql_part
    
def validate_query_safety(sql):
    banned_words=["DROP","DELETE","UPDATE","INSERT","ALTER","TRUNCATE","EXEC"]
    for word in banned_words:
        solo_word= rf"\b{word}\b"
        if re.search(solo_word,sql.upper()):
            raise ValueError("Invalid query") 
    return sql

def get_sql_query(prompt, provider="groq", history=None):
    response = call_llm(SYSTEM_PROMPT,prompt,provider,history)
    return clean_sql_response(response)

def detect_delay_unit(sql):
    if re.search(r"/\s*60", sql):
        return "minutes"
    else:
        return "seconds"
    
def is_delay_query(sql):
    return bool(re.search(r"departure_delay|arrival_delay", sql))

def route_question(question, history, provider="llama"):
    decision = call_llm(ROUTING_PROMPT, question, provider, history=history)
    print(f"Routing decision: {decision}")
    return decision.strip()
   
def run_query(sql):
    validate_query_safety(sql)
    conn= get_db_connection()
    cur = conn.cursor()
    cur.execute(sql)
    response = cur.fetchmany(10)
    conn.close()
    return response 


def build_context_note(chat_history, max_turns=3):
    if not chat_history:
        return ""
    user_turns = [m["content"] for m in chat_history if m["role"] == "user"]
    recent = user_turns[-max_turns:]
    if not recent:
        return ""
    context_lines = "\n".join(f"- {t}" for t in recent)
    return (
        f"\n\nAdditional context from earlier in this conversation "
        f"(the user may be referring back to these):\n{context_lines}"
    )