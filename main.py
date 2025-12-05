from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import logging
import os # <--- Para leer la API Key secreta

# Librerías de IA
from openai import OpenAI # <--- El cliente oficial
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

# --- 1. CONFIGURACIÓN ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("secure-chat-api")

# Configuración Spacy (Modelo Ligero para Render)
nlp_config = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "es", "model_name": "es_core_news_sm"}],
}
provider = NlpEngineProvider(nlp_configuration=nlp_config)
analyzer = AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["es"])
anonymizer = AnonymizerEngine()

# --- 2. REGLAS PERSONALIZADAS (Email, Teléfono, Banco) ---
# (Las mismas que ya tenías, las mantengo igual)
email_pattern = Pattern(name="email_pattern", regex=r"\b[\w\.-]+@[\w\.-]+\.\w{2,4}\b", score=1.0)
email_recognizer = PatternRecognizer(supported_entity="EMAIL_CUSTOM", patterns=[email_pattern], supported_language="es")
analyzer.registry.add_recognizer(email_recognizer)

phone_pattern = Pattern(name="phone_pattern", regex=r"\b(?:\+?\d{1,3}[- ]?)?\(?\d{2,4}\)?[- ]?\d{3,4}[- ]?\d{3,4}\b", score=0.8)
phone_recognizer = PatternRecognizer(supported_entity="PHONE_CUSTOM", patterns=[phone_pattern], supported_language="es")
analyzer.registry.add_recognizer(phone_recognizer)

bank_pattern = Pattern(name="bank_pattern", regex=r"\b[A-Z0-9]{15,30}\b|(?:\d[ -]*?){10,22}", score=0.6)
bank_recognizer = PatternRecognizer(supported_entity="BANK_ACCOUNT", patterns=[bank_pattern], supported_language="es")
analyzer.registry.add_recognizer(bank_recognizer)

# --- 3. CLIENTE OPENAI ---
# Intentamos conectar. Si no hay key, avisaremos en los logs.
api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# --- 4. API FASTAPI ---
app = FastAPI(title="Privacy Firewall API", version="2.0.0")

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
    return {"status": "online", "mode": "OpenAI Connected" if api_key else "Simulation Mode (No Key)"}

@app.post("/chat/secure", response_model=SecureChatResponse)
async def secure_chat(request: SecureChatRequest):
    try:
        # A. ANALIZAR Y ANONIMIZAR
        results = analyzer.analyze(text=request.prompt, language='es')
        anonymized_result = anonymizer.anonymize(text=request.prompt, analyzer_results=results)
        prompt_seguro = anonymized_result.text
        
        detected_types = list(set([res.entity_type for res in results]))

        # B. LLAMAR A OPENAI (¡La parte nueva!)
        if not api_key:
            ai_response = f"[MODO SIMULACIÓN] OpenAI no configurado. Prompt seguro: {prompt_seguro}"
        else:
            # Creamos el contexto para que GPT entienda qué hacer con los <TAGS>
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo", # Usamos este que es rápido y barato
                messages=[
                    {"role": "system", "content": "Eres un asistente útil. El usuario te enviará texto con datos sensibles ocultos (ej: <PERSON>, <EMAIL>). Responde a la consulta normalmente, refiriéndote a las personas u objetos por sus etiquetas genéricas si es necesario."},
                    {"role": "user", "content": prompt_seguro}
                ]
            )
            ai_response = completion.choices[0].message.content

        # C. RESPONDER
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
