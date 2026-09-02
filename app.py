import os
import re
import gc
import urllib.request
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from kokoro_onnx import Kokoro

# =========================================================
# DESCARGA AUTOMÁTICA Y GESTIÓN DE MEMORIA
# =========================================================
MODEL_FILE = "kokoro-v1.0.int8.onnx"
VOICES_FILE = "voices-v1.0.bin"

class TTSState:
    pipeline: Kokoro = None

state = TTSState()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Descargar solo si no existen
    if not os.path.exists(MODEL_FILE):
        urllib.request.urlretrieve("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx", MODEL_FILE)
    if not os.path.exists(VOICES_FILE):
        urllib.request.urlretrieve("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin", VOICES_FILE)
    
    # Cargar el modelo
    state.pipeline = Kokoro(MODEL_FILE, VOICES_FILE)
    yield
    state.pipeline = None
    gc.collect() # Forzar limpieza de RAM al apagar

app = FastAPI(title="SonicReader API", lifespan=lifespan)

# =========================================================
# ENDPOINT DE STREAMING (CERO LATENCIA)
# =========================================================
class TTSRequest(BaseModel):
    text: str
    voice: str = "af_heart"
    speed: float = 1.0

@app.post("/api/tts/stream")
def stream_tts(request: TTSRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text is empty")

    def audio_generator():
        try:
            # Dividir en oraciones para streaming instantáneo
            parts = re.split(r'(?<=[.,!?])\s+', " ".join(request.text.split()))
            sentences = [s.strip() for s in parts if s.strip()]

            for sentence in sentences:
                samples, _ = state.pipeline.create(sentence, voice=request.voice, speed=request.speed, lang="en-us")
                if samples is not None and len(samples) > 0:
                    # Empaquetado binario: 4 bytes de longitud + bytes crudos PCM
                    audio_bytes = samples.tobytes()
                    chunk = len(audio_bytes).to_bytes(4, byteorder='little') + audio_bytes
                    yield chunk
                    
            # Forzar liberación de RAM de las variables locales
            del samples, audio_bytes, chunk
            gc.collect()

        except Exception as e:
            error_msg = f"ERROR: {str(e)}".encode('utf-8')
            yield len(error_msg).to_bytes(4, byteorder='little') + error_msg

    return StreamingResponse(audio_generator(), media_type="application/octet-stream")

# Montar el Frontend
if os.path.exists("public"):
    app.mount("/", StaticFiles(directory="public", html=True), name="public")
