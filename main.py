from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import logging
import os

from openai import OpenAI
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

# --- 1. CONFIGURACIÓN ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("secure-chat-api")

nlp_config = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "es", "model_name": "es_core_news_sm"}],
}
provider = NlpEngineProvider(nlp_configuration=nlp_config)
analyzer = AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["es"])
anonymizer = AnonymizerEngine()

# --- 2. REGLAS PERSONALIZADAS (DNI, Plata, etc.) ---

# A. EMAIL
email_pattern = Pattern(name="email_pattern", regex=r"\b[\w\.-]+@[\w\.-]+\.\w{2,4}\b", score=1.0)
email_recognizer = PatternRecognizer(supported_entity="EMAIL_CUSTOM", patterns=[email_pattern], supported_language="es")
analyzer.registry.add_recognizer(email_recognizer)

# B. TELÉFONO
phone_pattern = Pattern(name="phone_pattern", regex=r"\b(?:\+?\d{1,3}[- ]?)?\(?\d{2,4}\)?[- ]?\d{3,4}[- ]?\d{3,4}\b", score=0.8)
phone_recognizer = PatternRecognizer(supported_entity="PHONE_CUSTOM", patterns=[phone_pattern], supported_language="es")
analyzer.registry.add_recognizer(phone_recognizer)

# C. CUENTA BANCARIA
bank_pattern = Pattern(name="bank_pattern", regex=r"\b[A-Z0-9]{15,30}\b|(?:\d[ -]*?){10,22}", score=0.6)
bank_recognizer = PatternRecognizer(supported_entity="BANK_ACCOUNT", patterns=[bank_pattern], supported_language="es")
analyzer.registry.add_recognizer(bank_recognizer)

# D. DNI ARGENTINO (NUEVO)
# Busca números de 7 a 8 dígitos, opcionalmente con puntos de miles
dni_pattern = Pattern(name="dni_pattern", regex=r"\b\d{1,2}\.?\d{3}\.?\d{3}\b", score=0.85)
dni_recognizer = PatternRecognizer(supported_entity="DNI_ARG", patterns=[dni_pattern], supported_language="es")
analyzer.registry.add_recognizer(dni_recognizer)

# E. DINERO / MONTOS (NUEVO)
# Busca símbolos $ o palabras 'pesos', 'dólares', 'usd' cerca de números
money_pattern = Pattern(name="money_pattern", regex=r"(?:\$|USD|EUR)\s?[\d.,]+|[\d.,]+\s?(?:pesos|dólares|usd|eur|us\$)", score=0.8)
money_recognizer = PatternRecognizer(supported_entity="MONEY_AMOUNT", patterns=[money_pattern], supported_language="es")
analyzer.registry.add_recognizer(money_recognizer)


# --- 3. CLIENTE OPENAI ---
api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# --- 4. API FASTAPI ---
app = FastAPI(title="Privacy Firewall API", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SecureChatRequest(BaseModel):
    prompt: str
    user_id: str = "guest"

class SafetyReport(BaseModel):
    detected_items: List[str]
    sanitized_prompt: str

class SecureChatResponse(BaseModel):
    ai_response: str
    safety_report: SafetyReport

@app.get("/")
def health_check():
    return {"status": "online", "mode": "OpenAI Connected" if api_key else "Simulation Mode"}

@app.post("/chat/secure", response_model=SecureChatResponse)
async def secure_chat(request: SecureChatRequest):
    try:
        # A. ANALIZAR
        results = analyzer.analyze(text=request.prompt, language='es')
        
        # B. ANONIMIZAR
        anonymized_result = anonymizer.anonymize(text=request.prompt, analyzer_results=results)
        prompt_seguro = anonymized_result.text
        
        detected_types = list(set([res.entity_type for res in results]))

        # C. LLAMAR A OPENAI
        if not api_key:
            ai_response = f"[SIMULACIÓN] Prompt seguro: {prompt_seguro}"
        else:
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un asistente legal útil. El usuario te enviará textos con datos sensibles ocultos (ej: <DNI_ARG>, <MONEY_AMOUNT>). Redacta o responde manteniendo esos placeholders en su lugar para que luego puedan ser rellenados."},
                    {"role": "user", "content": prompt_seguro}
                ]
            )
            ai_response = completion.choices[0].message.content

        return SecureChatResponse(
            ai_response=ai_response,
            safety_report=SafetyReport(
                detected_items=detected_types,
                sanitized_prompt=prompt_seguro
            )
        )

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
