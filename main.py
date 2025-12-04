from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import logging

# Importaciones de Presidio y Spacy
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

# --- 1. CONFIGURACIÓN DEL MOTOR (SOLUCIÓN DEFINITIVA ESPAÑOL) ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("secure-chat-api")

# Configuración de Spacy en Español
nlp_config = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "es", "model_name": "es_core_news_sm"}],
}
provider = NlpEngineProvider(nlp_configuration=nlp_config)

# INICIALIZACIÓN DEL ANALYZER CON SOPORTE EXPLÍCITO DE IDIOMA
# Esto corrige el error de "Language not supported"
analyzer = AnalyzerEngine(
    nlp_engine=provider.create_engine(), 
    supported_languages=["es"]
)

anonymizer = AnonymizerEngine()

# --- 2. AGREGANDO REGLAS PERSONALIZADAS (RegEx) ---
# Estas son las reglas que probamos en Colab para detectar Emails, Teléfonos y Bancos

# Regla: Email
email_pattern = Pattern(name="email_pattern", regex=r"\b[\w\.-]+@[\w\.-]+\.\w{2,4}\b", score=1.0)
email_recognizer = PatternRecognizer(
    supported_entity="EMAIL_CUSTOM", 
    patterns=[email_pattern], 
    supported_language="es"
)
analyzer.registry.add_recognizer(email_recognizer)

# Regla: Teléfono (Formatos varios)
phone_pattern = Pattern(name="phone_pattern", regex=r"\b(?:\+?\d{1,3}[- ]?)?\(?\d{2,4}\)?[- ]?\d{3,4}[- ]?\d{3,4}\b", score=0.8)
phone_recognizer = PatternRecognizer(
    supported_entity="PHONE_CUSTOM", 
    patterns=[phone_pattern], 
    supported_language="es"
)
analyzer.registry.add_recognizer(phone_recognizer)

# Regla: Cuentas Bancarias / CBU / IBAN
bank_pattern = Pattern(name="bank_pattern", regex=r"\b[A-Z0-9]{15,30}\b|(?:\d[ -]*?){10,22}", score=0.6)
bank_recognizer = PatternRecognizer(
    supported_entity="BANK_ACCOUNT", 
    patterns=[bank_pattern], 
    supported_language="es"
)
analyzer.registry.add_recognizer(bank_recognizer)

# --- 3. DEFINICIÓN DE LA API (FastAPI) ---

app = FastAPI(title="Privacy Firewall API", version="1.0.0")

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
    return {"status": "online", "engine": "Presidio Spanish Optimized"}

@app.post("/chat/secure", response_model=SecureChatResponse)
async def secure_chat(request: SecureChatRequest):
    logger.info(f"Procesando solicitud para usuario: {request.user_id}")
    try:
        # PASO A: ANÁLISIS
        results = analyzer.analyze(text=request.prompt, language='es')
        
        # PASO B: ANONIMIZACIÓN
        anonymized_result = anonymizer.anonymize(
            text=request.prompt,
            analyzer_results=results
        )
        
        prompt_seguro = anonymized_result.text
        
        # PASO C: SIMULACIÓN DE RESPUESTA IA (Aquí conectaríamos OpenAI más adelante)
        ai_simulation = f"He recibido tu mensaje seguro. El contenido procesado es: '{prompt_seguro}'. No tengo acceso a tus datos reales."
        
        # PASO D: REPORTE
        detected_types = list(set([res.entity_type for res in results]))
        
        return SecureChatResponse(
            ai_response=ai_simulation,
            safety_report=SafetyReport(
                detected_items=detected_types,
                sanitized_prompt=prompt_seguro
            )
        )

    except Exception as e:
        logger.error(f"Error procesando solicitud: {str(e)}")

        raise HTTPException(status_code=500, detail=str(e))

