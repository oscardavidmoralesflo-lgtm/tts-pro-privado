import gradio as gr
import edge_tts
import asyncio
import os
import io
import time
import re
import zipfile

# =========================================================
# 1. BASE DE USUARIOS Y CONTROL DE ACCESO
# =========================================================
ADMIN_USERNAMES = ["admin_pro"]

USERS_DATABASE = [
    ("admin_pro", "TTS_MasterKey#2026!"),     # 👑 Acceso Total Ilimitado (Tú)
    ("invitado_vip", "VozStudio2026*Open")     # 👤 Acceso Invitado (Restringido)
]

# LÍMITES PARA CUENTAS DE INVITADOS
GUEST_MAX_CHARS_EDITOR = 2000      # 2.000 caracteres en el editor
GUEST_MAX_WORDS_PODCAST = 1400     # ~10 minutos de audio
GUEST_MAX_CHARS_PODCAST = 8500     # ~10 minutos en caracteres

PRO_UPGRADE_MSG = (
    "🔒 **Función Exclusiva PRO**\n\n"
    "Esta herramienta requiere una suscripción activa a la versión **PRO** sin restricciones.\n\n"
    "👉 **¿Deseas desbloquear acceso ilimitado?** Ponte en contacto directamente con el desarrollador para activar tu cuenta."
)

def check_user_access(request: gr.Request):
    username = getattr(request, "username", "admin_pro")
    is_admin = username in ADMIN_USERNAMES
    badge = "👑 Modo Admin Ilimitado" if is_admin else "👤 Modo Invitado"
    return is_admin, badge, username

def count_words(text: str) -> int:
    return len(text.strip().split()) if text else 0

def render_account_status(request: gr.Request):
    is_admin, _, username = check_user_access(request)
    if is_admin:
        return f"""
        <div class="account-card pro-card">
            <div class="account-badge pro-tag">👑 PRO ILIMITADO</div>
            <div class="account-user">Usuario: <b>{username}</b></div>
            <div class="account-details">Acceso total: 4 Voces, Emociones de Voz, Shadowing, Audiolibros ZIP, Subtítulos .SRT/.VTT y Pack ZIP.</div>
        </div>
        """
    else:
        return f"""
        <div class="account-card guest-card">
            <div class="account-badge guest-tag">👤 INVITADO LIMITADO</div>
            <div class="account-user">Usuario: <b>{username}</b></div>
            <div class="account-details">
                • Editor: máx. 2.000 caracteres<br>
                • Podcast: máx. 10 min<br>
                • Emociones, Libros, Video: Bloqueados (PRO)
            </div>
            <div class="account-upgrade">Para desbloquear todas las funciones, contacta al desarrollador.</div>
        </div>
        """

# =========================================================
# 2. CATÁLOGO DE VOCES Y PARÁMETROS EMOCIONALES
# =========================================================
VOICES = {
    # 🇺🇸 Voces en Inglés Neural HD
    "🇺🇸 Andrew (Podcast / Cálida)": "en-US-AndrewNeural",
    "🇺🇸 Jenny (Conversacional / Expresiva)": "en-US-JennyNeural",
    "🇺🇸 Ava (Joven / Dinámica)": "en-US-AvaNeural",
    "🇺🇸 Brian (Documental / Autoridad)": "en-US-BrianNeural",
    "🇺🇸 Emma (Audiolibros / Suave)": "en-US-EmmaNeural",
    "🇺🇸 Guy (Casual / YouTube)": "en-US-GuyNeural",
    "🇺🇸 Aria (Locución de Estudio)": "en-US-AriaNeural",
    "🇺🇸 Christopher (Profundo / Relato)": "en-US-ChristopherNeural",
    
    # 🇲🇽 🇪🇸 🇨🇴 Voces en Español Neural HD
    "🇲🇽 Dalia (México / Expresiva)": "es-MX-DaliaNeural",
    "🇲🇽 Jorge (México / Radio y Noticias)": "es-MX-JorgeNeural",
    "🇪🇸 Álvaro (España / Corporativo)": "es-ES-AlvaroNeural",
    "🇪🇸 Elvira (España / Narrativa)": "es-ES-ElviraNeural",
    "🇨🇴 Gonzalo (Colombia / Neutro Claro)": "es-CO-GonzaloNeural",
    "🇨🇴 Salomé (Colombia / Amigable)": "es-CO-SalomeNeural"
}

SPEEDS = {
    "0.8x (Lento / Aprendizaje)": -20,
    "1.0x (Normal / Conversacional)": 0,
    "1.2x (Rápido / Dinámico)": 20,
    "1.5x (Ultra Dinámico)": 50
}

# 🎭 Perfiles de Emoción PRO (Modifican Tono, Velocidad y Volumen)
# Formato: "Nombre": (Variación Velocidad, Variación Tono, Variación Volumen)
EMOTIONS = {
    "😐 Neutral (Estándar)": (0, 0, 0),
    "😊 Alegre / Entusiasta": (10, 10, 0),
    "😔 Triste / Melancólico": (-10, -15, -10),
    "😡 Enojado / Firme": (15, -10, 10),
    "🤫 Susurro / Confidencial": (-10, -25, -30),
    "🎤 Épico / Tráiler": (-5, -20, 10),
    "🎙️ Noticiero / Formal": (5, -5, 0)
}

def resolve_voice_id(label_or_id: str, default: str = "en-US-AndrewNeural") -> str:
    if not label_or_id:
        return default
    if label_or_id in VOICES.values():
        return label_or_id
    if label_or_id in VOICES:
        return VOICES[label_or_id]
    
    low = label_or_id.lower()
    if "andrew" in low: return "en-US-AndrewNeural"
    if "jenny" in low: return "en-US-JennyNeural"
    if "ava" in low: return "en-US-AvaNeural"
    if "brian" in low: return "en-US-BrianNeural"
    if "emma" in low: return "en-US-EmmaNeural"
    if "guy" in low: return "en-US-GuyNeural"
    if "aria" in low: return "en-US-AriaNeural"
    if "christopher" in low: return "en-US-ChristopherNeural"
    if "dalia" in low: return "es-MX-DaliaNeural"
    if "jorge" in low: return "es-MX-JorgeNeural"
    if "alvaro" in low or "álvaro" in low: return "es-ES-AlvaroNeural"
    if "elvira" in low: return "es-ES-ElviraNeural"
    if "gonzalo" in low: return "es-CO-GonzaloNeural"
    if "salome" in low or "salomé" in low: return "es-CO-SalomeNeural"
    
    return default

# =========================================================
# MOTOR DE SÍNTESIS ROBUSTO (CON SOPORTE EMOCIONAL)
# =========================================================
async def core_synthesize(text, voice_id, rate_val=0, pitch_val=0, volume_val=0):
    if not text or not text.strip():
        return b""
    
    kwargs = {}
    if rate_val != 0:
        kwargs["rate"] = f"{'+' if rate_val > 0 else ''}{rate_val}%"
    if pitch_val != 0:
        kwargs["pitch"] = f"{'+' if pitch_val > 0 else ''}{pitch_val}Hz"
    if volume_val != 0:
        kwargs["volume"] = f"{'+' if volume_val > 0 else ''}{volume_val}%"
    
    clean_voice = resolve_voice_id(voice_id)
    
    communicator = edge_tts.Communicate(
        text=text.strip(),
        voice=clean_voice,
        **kwargs
    )
    
    buffer = io.BytesIO()
    async for chunk in communicator.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
            
    return buffer.getvalue()

def generate_mp3_silence(seconds: float) -> bytes:
    silence_frame = (
        b'\xff\xfb\x90\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        + b'\x00' * 369
    )
    num_frames = int(max(1, round(seconds * 38.28)))
    return silence_frame * num_frames

# =========================================================
# FUNCIONES DE CADA MÓDULO
# =========================================================

# 1. Editor Principal
async def fn_main_editor(text, voice_label, emotion_label, speed_label, pitch_pref, vol_pref, history, request: gr.Request):
    if not text or not text.strip():
        return None, history, "⚠️ Escribe algún texto en el editor."
    
    is_admin, badge, _ = check_user_access(request)
    char_count = len(text)
    
    # Bloqueo de Límite de Caracteres
    if not is_admin and char_count > GUEST_MAX_CHARS_EDITOR:
        return (None, history, f"⚠️ **[{badge}] Límite superado:** Tu texto contiene **{char_count:,} caracteres** (el límite es {GUEST_MAX_CHARS_EDITOR:,}).")
    
    # Bloqueo de Función PRO (Emociones)
    if not is_admin and emotion_label != "😐 Neutral (Estándar)":
        return None, history, PRO_UPGRADE_MSG
    
    voice_id = resolve_voice_id(voice_label, "en-US-AndrewNeural")
    base_speed = SPEEDS.get(speed_label, 0)
    
    # Aplicar modificadores de emoción
    e_rate, e_pitch, e_vol = EMOTIONS.get(emotion_label, (0, 0, 0))
    final_rate = base_speed + e_rate
    final_pitch = pitch_pref + e_pitch
    final_vol = vol_pref + e_vol
    
    try:
        audio_bytes = await core_synthesize(text, voice_id, final_rate, final_pitch, final_vol)
        if not audio_bytes:
            return None, history, "⚠️ No se pudo procesar el audio. Verifica el texto."
        
        filename = f"audio_script_{int(time.time())}.mp3"
        with open(filename, "wb") as f:
            f.write(audio_bytes)
            
        title = text.strip()[:35].replace("\n", " ") + "..."
        history = history or []
        history.insert(0, [title, voice_label, filename, time.strftime("%H:%M:%S")])
        
        return filename, history, f"✅ [{badge}] Audio generado con éxito ({char_count:,} caracteres)."
    except Exception as e:
        return None, history, f"❌ Error: {str(e)}"

# 2. Muestras de Voz
async def fn_test_voice_sample(voice_label):
    if not voice_label:
        return None, "⚠️ Selecciona una voz del catálogo."
    voice_id = resolve_voice_id(voice_label, "en-US-JennyNeural")
    
    if any(k in voice_id.lower() for k in ["es-", "dalia", "jorge", "alvaro", "elvira", "gonzalo", "salome"]):
        sample_text = "Hola, esta es una prueba de entonación y claridad natural con tecnología neuronal HD."
    else:
        sample_text = "Hello! This is a sample demonstrating the natural inflection and clarity of this neural voice."
    
    try:
        audio_bytes = await core_synthesize(sample_text, voice_id)
        if not audio_bytes:
            return None, "⚠️ No se pudo obtener el audio de muestra."
        filename = f"sample_voice_{int(time.time())}.mp3"
        with open(filename, "wb") as f:
            f.write(audio_bytes)
        return filename, f"✅ Muestra de **{voice_label}** generada con éxito."
    except Exception as e:
        return None, f"❌ Error al generar la muestra: {str(e)}"

# 3. Podcast Studio Dinámico (Con Emociones PRO)
async def fn_podcast_studio(script, num_voices, v1_lbl, v2_lbl, v3_lbl, v4_lbl, emotion_lbl, speed_lbl, request: gr.Request):
    if not script or not script.strip():
        return None, "⚠️ El guión de podcast está vacío."
    
    is_admin, badge, _ = check_user_access(request)
    words = count_words(script)
    chars = len(script)
    
    # Restricción de 10 min para invitados
    if not is_admin and (words > GUEST_MAX_WORDS_PODCAST or chars > GUEST_MAX_CHARS_PODCAST):
        return None, f"⚠️ **[{badge}] Límite de 10 Minutos Alcanzado**.\n\nActualiza a PRO contactando al desarrollador."
    
    # Restricción de Emociones PRO
    if not is_admin and emotion_lbl != "😐 Neutral (Estándar)":
        return None, PRO_UPGRADE_MSG
    
    v1 = resolve_voice_id(v1_lbl, "en-US-AndrewNeural")
    v2 = resolve_voice_id(v2_lbl, "en-US-JennyNeural")
    v3 = resolve_voice_id(v3_lbl, "en-US-BrianNeural")
    v4 = resolve_voice_id(v4_lbl, "en-US-AvaNeural")
    
    base_speed = SPEEDS.get(speed_lbl, 0)
    e_rate, e_pitch, e_vol = EMOTIONS.get(emotion_lbl, (0, 0, 0))
    final_rate = base_speed + e_rate
    
    lines = [l.strip() for l in script.strip().split("\n") if l.strip()]
    if not lines:
        return None, "⚠️ No se detectaron líneas de diálogo válidas."
    
    final_audio = io.BytesIO()
    processed_count = 0
    
    try:
        for line in lines:
            if ":" in line:
                tag, content = line.split(":", 1)
                content = content.strip()
                if not content: continue
                tag_low = tag.lower()
                
                # Asignación de participantes según la cantidad seleccionada
                if "4" in num_voices and any(k in tag_low for k in ["4", "narrador", "voz en off", "narrator", "locutor 4"]):
                    selected_voice = v4
                elif ("3" in num_voices or "4" in num_voices) and any(k in tag_low for k in ["3", "especialista", "guest 2", "invitado 2", "locutor 3"]):
                    selected_voice = v3
                elif any(k in tag_low for k in ["2", "guest", "invitado", "jenny", "locutor 2"]):
                    selected_voice = v2
                else:
                    selected_voice = v1
            else:
                content = line
                selected_voice = v1
                
            chunk = await core_synthesize(content, selected_voice, final_rate, e_pitch, e_vol)
            if chunk:
                final_audio.write(chunk)
                processed_count += 1
            await asyncio.sleep(0.04)
            
        audio_data = final_audio.getvalue()
        if not audio_data:
            return None, "⚠️ No se pudo ensamblar el audio del podcast."
            
        filename = f"podcast_master_{int(time.time())}.mp3"
        with open(filename, "wb") as f:
            f.write(audio_data)
            
        return filename, f"✅ [{badge}] Podcast compilado con éxito ({processed_count} intervenciones / {words:,} palabras)."
    except Exception as e:
        return None, f"❌ Error durante la compilación: {str(e)}"

# 4. Shadowing & Pronunciation Trainer (PRO)
async def fn_shadowing_trainer(script, voice_label, speed_label, pause_mode, request: gr.Request):
    if not script or not script.strip(): return None, None, "⚠️ Ingresa las frases."
    is_admin, badge, _ = check_user_access(request)
    if not is_admin: return None, None, PRO_UPGRADE_MSG
    
    voice_id = resolve_voice_id(voice_label, "en-US-AndrewNeural")
    speed_val = SPEEDS.get(speed_label, 0)
    
    sentences = [s.strip() for s in script.strip().split("\n") if s.strip()]
    if not sentences: return None, None, "⚠️ No hay oraciones válidas."
    
    master_audio = io.BytesIO()
    zip_buffer = io.BytesIO()
    
    try:
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, sentence in enumerate(sentences, 1):
                chunk = await core_synthesize(sentence, voice_id, speed_val)
                if not chunk: continue
                duration_sec = max(2.5, len(sentence.split()) * 0.45)
                pause_sec = duration_sec * 1.3
                
                master_audio.write(chunk)
                master_audio.write(generate_mp3_silence(pause_sec))
                
                if "Doble" in pause_mode:
                    master_audio.write(chunk)
                    master_audio.write(generate_mp3_silence(2.0))
                
                safe_name = re.sub(r'[^a-zA-Z0-9]', '_', sentence[:25])
                zf.writestr(f"{i:02d}_{safe_name}.mp3", chunk)
                await asyncio.sleep(0.04)
        
        master_file = f"shadowing_master_{int(time.time())}.mp3"
        with open(master_file, "wb") as f: f.write(master_audio.getvalue())
        zip_file = f"shadowing_pack_{int(time.time())}.zip"
        with open(zip_file, "wb") as f: f.write(zip_buffer.getvalue())
        return master_file, zip_file, f"✅ [{badge}] Sesión generada ({len(sentences)} unidades)."
    except Exception as e:
        return None, None, f"❌ Error: {str(e)}"

# 5. Audiolibros Masivos en ZIP (PRO)
async def fn_book_narration_zip(book_text, voice_label, speed_label, request: gr.Request):
    if not book_text or not book_text.strip(): return None, None, "⚠️ Pega el contenido."
    is_admin, badge, _ = check_user_access(request)
    if not is_admin: return None, None, PRO_UPGRADE_MSG
    
    voice_id = resolve_voice_id(voice_label, "es-ES-ElviraNeural")
    speed_val = SPEEDS.get(speed_label, 0)
    
    raw_chapters = re.split(r'(?i)(?:^|\n)(?=###|\bcap[ií]tulo\b|\bchapter\b)', book_text.strip())
    chapters = [c.strip() for c in raw_chapters if c.strip()]
    if not chapters: chapters = [book_text.strip()]
        
    master_audio = io.BytesIO()
    zip_buffer = io.BytesIO()
    index_text = "ÍNDICE DE CONTENIDOS\n====================\n\n"
    
    try:
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, chap in enumerate(chapters, 1):
                title = chap.split("\n")[0][:40].replace("#", "").strip() or f"Capitulo_{i}"
                index_text += f"{i:02d}. {title} ({count_words(chap):,} palabras)\n"
                chunk = await core_synthesize(chap, voice_id, speed_val)
                if chunk:
                    master_audio.write(chunk)
                    master_audio.write(generate_mp3_silence(2.5))
                    safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
                    zf.writestr(f"{i:02d}_{safe_title}.mp3", chunk)
                await asyncio.sleep(0.04)
            zf.writestr("Indice.txt", index_text)
            
        master_file = f"audiolibro_{int(time.time())}.mp3"
        with open(master_file, "wb") as f: f.write(master_audio.getvalue())
        zip_file = f"audiolibro_{int(time.time())}.zip"
        with open(zip_file, "wb") as f: f.write(zip_buffer.getvalue())
        return master_file, zip_file, f"✅ [{badge}] Audiolibro compilado ({len(chapters)} capítulos)."
    except Exception as e:
        return None, None, f"❌ Error: {str(e)}"

# 6. Locución para Video con Subtítulos .SRT y .VTT (PRO)
async def fn_video_voiceover(text, voice_label, style_speed, request: gr.Request):
    if not text or not text.strip(): return None, None, None, "⚠️ Ingresa el guión."
    is_admin, badge, _ = check_user_access(request)
    if not is_admin: return None, None, None, PRO_UPGRADE_MSG
    
    speed_mapping = {"⚡ Dinámico (+15%)": 15, "🗣️ Estándar (0%)": 0, "🎬 Pausado (-10%)": -10}
    speed_val = speed_mapping.get(style_speed, 0)
    voice_id = resolve_voice_id(voice_label, "en-US-GuyNeural")
    
    try:
        audio_bytes = await core_synthesize(text, voice_id, speed_val)
        mp3_file = f"locucion_video_{int(time.time())}.mp3"
        with open(mp3_file, "wb") as f: f.write(audio_bytes)
            
        sentences = [s.strip() for s in re.split(r'(?<=[.?!])\s+', text) if s.strip()]
        srt_content, vtt_content = "", "WEBVTT\n\n"
        start_sec = 0.0
        
        for i, s in enumerate(sentences, 1):
            duration = max(2.2, len(s) * 0.062)
            end_sec = start_sec + duration
            
            def fmt_srt(t): return f"{int(t//3600):02}:{int((t%3600)//60):02}:{int(t%60):02},{int((t-int(t))*1000):03}"
            def fmt_vtt(t): return f"{int(t//3600):02}:{int((t%3600)//60):02}:{int(t%60):02}.{int((t-int(t))*1000):03}"
                
            srt_content += f"{i}\n{fmt_srt(start_sec)} --> {fmt_srt(end_sec)}\n{s}\n\n"
            vtt_content += f"{i}\n{fmt_vtt(start_sec)} --> {fmt_vtt(end_sec)}\n{s}\n\n"
            start_sec = end_sec
            
        srt_file, vtt_file = f"sub_{int(time.time())}.srt", f"sub_{int(time.time())}.vtt"
        with open(srt_file, "w", encoding="utf-8") as f: f.write(srt_content)
        with open(vtt_file, "w", encoding="utf-8") as f: f.write(vtt_content)
        return mp3_file, srt_file, vtt_file, f"✅ [{badge}] Subtítulos generados."
    except Exception as e:
        return None, None, None, f"❌ Error: {str(e)}"

# 7. Centro de Descargas & Exportación Masiva en ZIP
def get_all_media_files(request: gr.Request):
    is_admin, _, _ = check_user_access(request)
    files = [f for f in os.listdir(".") if f.endswith(".mp3") or f.endswith(".srt") or f.endswith(".vtt") or f.endswith(".zip")]
    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    if not is_admin: return files[:3], None, "ℹ️ *Modo Invitado: Mostrando últimos 3 archivos.*"
    return files, None, "✅ *Historial completo.*"

def download_all_as_zip(request: gr.Request):
    is_admin, badge, _ = check_user_access(request)
    if not is_admin: return None, PRO_UPGRADE_MSG
    files = [f for f in os.listdir(".") if f.endswith((".mp3", ".srt", ".vtt"))]
    if not files: return None, "⚠️ No hay archivos."
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files: zf.write(f, arcname=f)
    zip_name = f"Pack_Completo_{int(time.time())}.zip"
    with open(zip_name, "wb") as f: f.write(zip_buffer.getvalue())
    return zip_name, f"✅ [{badge}] Pack generado."

def clear_all_media_files(request: gr.Request):
    is_admin, _, _ = check_user_access(request)
    if not is_admin: return [], None, "⚠️ Solo PRO puede purgar.", []
    count = 0
    for f in os.listdir("."):
        if f.endswith((".mp3", ".srt", ".vtt", ".zip")) and not f.startswith("sample_"):
            try: os.remove(f); count += 1
            except: pass
    return [], None, f"🧹 Eliminados {count} archivos temporales.", []

# =========================================================
# DISEÑO VISUAL PROFESIONAL
# =========================================================
custom_css = """
:root, html, body, .dark, .gradio-container, .gradio-container * { color-scheme: light !important; }
body, .gradio-container { background-color: #f8fafc !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important; padding: 0 !important; margin: 0 !important; max-width: 100% !important; }
footer { visibility: hidden !important; }
.app-layout { display: flex; min-height: 100vh; background-color: #f8fafc !important; }
.sidebar-panel { width: 275px; background-color: #ffffff !important; border-right: 1px solid #e2e8f0 !important; padding: 24px 16px; flex-shrink: 0; display: flex; flex-direction: column; justify-content: space-between; }
.brand-header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; padding-left: 4px; }
.brand-icon { width: 36px; height: 36px; background: linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%); border-radius: 10px; display: flex; align-items: center; justify-content: center; color: #ffffff; font-weight: 800; font-size: 16px; box-shadow: 0 4px 12px rgba(79, 70, 229, 0.25); }
.brand-title { font-size: 17px; font-weight: 800; color: #0f172a !important; letter-spacing: -0.5px; }
.brand-title span { color: #4f46e5 !important; }
.account-card { border-radius: 12px; padding: 12px; margin-bottom: 16px; font-size: 12px; line-height: 1.4; }
.pro-card { background: linear-gradient(145deg, #f5f3ff 0%, #ede9fe 100%); border: 1px solid #ddd6fe; color: #4c1d95; }
.pro-tag { background: #7c3aed; color: #ffffff; font-weight: 800; font-size: 10px; display: inline-block; padding: 2px 8px; border-radius: 6px; margin-bottom: 6px; letter-spacing: 0.5px; }
.guest-card { background: linear-gradient(145deg, #fffbeb 0%, #fef3c7 100%); border: 1px solid #fde68a; color: #92400e; }
.guest-tag { background: #d97706; color: #ffffff; font-weight: 800; font-size: 10px; display: inline-block; padding: 2px 8px; border-radius: 6px; margin-bottom: 6px; letter-spacing: 0.5px; }
.account-user { font-size: 13px; margin-bottom: 4px; }
.account-details { font-size: 11px; opacity: 0.9; margin-bottom: 4px; }
.account-upgrade { font-size: 10.5px; font-weight: 700; color: #b45309; margin-top: 6px; padding-top: 4px; border-top: 1px dashed #fcd34d; }
.menu-section { font-size: 11px; font-weight: 700; color: #94a3b8 !important; text-transform: uppercase; letter-spacing: 0.6px; margin: 14px 0 6px 10px; }
.nav-btn { width: 100% !important; text-align: left !important; justify-content: flex-start !important; background: #ffffff !important; border: 1px solid transparent !important; color: #475569 !important; font-size: 13px !important; font-weight: 600 !important; padding: 9px 12px !important; border-radius: 10px !important; margin-bottom: 2px !important; box-shadow: none !important; transition: all 0.15s ease !important; }
.nav-btn:hover { background: #f1f5f9 !important; color: #0f172a !important; }
.logout-btn { background-color: #fef2f2 !important; color: #ef4444 !important; border: 1px solid #fee2e2 !important; margin-top: 12px !important; }
.logout-btn:hover { background-color: #fee2e2 !important; color: #dc2626 !important; }
.content-area { flex-grow: 1; display: flex; flex-direction: column; padding: 24px 32px; background-color: #f8fafc !important; }
.card-box { background-color: #ffffff !important; border: 1px solid #e2e8f0 !important; border-radius: 20px; box-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.04) !important; padding: 28px 32px; max-width: 960px; margin: 0 auto; width: 100%; }
.top-bar-controls { display: flex; align-items: center; justify-content: center; gap: 16px; margin-bottom: 16px; padding-bottom: 16px; border-bottom: 1px solid #f1f5f9; }
.btn-play-hero { background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%) !important; border-radius: 50% !important; width: 42px !important; height: 42px !important; min-width: 42px !important; max-width: 42px !important; aspect-ratio: 1 / 1 !important; padding: 0 !important; color: #ffffff !important; border: none !important; box-shadow: 0 4px 14px rgba(79, 70, 229, 0.3) !important; font-size: 15px !important; display: flex !important; align-items: center !important; justify-content: center !important; cursor: pointer !important; flex-shrink: 0 !important; }
.custom-audio-player { background-color: #ffffff !important; border: 1px solid #e2e8f0 !important; border-radius: 14px !important; margin-top: 14px !important; }
.clean-editor textarea { border: 1px solid #e2e8f0 !important; border-radius: 14px !important; background-color: #ffffff !important; font-size: 15px !important; line-height: 1.6 !important; color: #0f172a !important; padding: 16px !important; }
.template-pill { border: 1px solid #e2e8f0 !important; background-color: #f8fafc !important; border-radius: 20px !important; padding: 6px 14px !important; font-size: 12px !important; font-weight: 600 !important; color: #475569 !important; }
.pro-badge { background: #fef3c7; color: #d97706; font-size: 11px; font-weight: 800; padding: 3px 8px; border-radius: 6px; margin-left: 6px; text-transform: uppercase; }
"""

# =========================================================
# INTERFAZ GRADIO
# =========================================================
with gr.Blocks(title="Text to Speech Pro Studio", css=custom_css) as demo:
    
    project_history = gr.State([])
    pref_pitch = gr.State(0)
    pref_volume = gr.State(0)
    
    with gr.Row(elem_classes=["app-layout"]):
        
        # BARRA LATERAL
        with gr.Column(elem_classes=["sidebar-panel"], scale=0, min_width=270):
            with gr.Column():
                gr.HTML("""
                    <div class="brand-header">
                        <div class="brand-icon">⚡</div>
                        <div class="brand-title">Text to Speech <span>Pro</span></div>
                    </div>
                """)
                
                account_status_view = gr.HTML()
                
                gr.HTML('<div class="menu-section">Creación & Estudio</div>')
                btn_nav_editor = gr.Button("📝 Nuevo Guión", elem_classes=["nav-btn"])
                btn_nav_podcast = gr.Button("🎧 Podcast Studio Multi-Voz", elem_classes=["nav-btn"])
                btn_nav_shadowing = gr.Button("🗣️ Shadowing Trainer (PRO)", elem_classes=["nav-btn"])
                btn_nav_book = gr.Button("📖 Audiolibros en ZIP (PRO)", elem_classes=["nav-btn"])
                btn_nav_video = gr.Button("🎬 Locución Video & SRT (PRO)", elem_classes=["nav-btn"])
                
                gr.HTML('<div class="menu-section">Recursos & Proyectos</div>')
                btn_nav_projects = gr.Button("📂 Mis Proyectos", elem_classes=["nav-btn"])
                btn_nav_voices = gr.Button("🎙️ Catálogo de Voces HD", elem_classes=["nav-btn"])
                
                gr.HTML('<div class="menu-section">Exportación & Ajustes</div>')
                btn_nav_downloads = gr.Button("📥 Centro de Descargas", elem_classes=["nav-btn"])
                btn_nav_settings = gr.Button("⚙️ Preferencias & Calidad", elem_classes=["nav-btn"])

            with gr.Column():
                btn_logout = gr.Button("🚪 Cerrar Sesión", elem_classes=["nav-btn", "logout-btn"])

        # CONTENIDO PRINCIPAL
        with gr.Column(elem_classes=["content-area"]):
            
            # 1. Editor Principal
            with gr.Column(visible=True, elem_classes=["card-box"]) as view_editor:
                gr.Markdown("### 📝 Editor de Guión *(Gratis hasta 2.000 caracteres / Ilimitado PRO)*")
                with gr.Row(elem_classes=["top-bar-controls"]):
                    main_voice = gr.Dropdown(choices=list(VOICES.keys()), value="🇺🇸 Andrew (Podcast / Cálida)", show_label=False, scale=3)
                    main_emotion = gr.Dropdown(choices=list(EMOTIONS.keys()), value="😐 Neutral (Estándar)", label="🎭 Emoción (Solo PRO)", scale=2)
                    main_speed = gr.Dropdown(choices=list(SPEEDS.keys()), value="1.0x (Normal / Conversacional)", show_label=False, scale=2)
                    main_play_btn = gr.Button("▶", elem_classes=["btn-play-hero"])
                
                main_audio = gr.Audio(show_label=False, elem_classes=["custom-audio-player"])
                main_status = gr.Markdown("")
                
                main_text = gr.Textbox(
                    placeholder="Escribe o pega aquí tu guión...",
                    show_label=False,
                    lines=8,
                    value="Welcome to Text to Speech Pro Studio. Convert your scripts into ultra-realistic, studio-quality speech using advanced deep learning models. Click Play and experience true human cadence.",
                    elem_classes=["clean-editor"]
                )
                
                with gr.Row():
                    t1 = gr.Button("📖 Historia en Inglés", elem_classes=["template-pill"])
                    t2 = gr.Button("🎙️ Intro Podcast", elem_classes=["template-pill"])
                    t3 = gr.Button("🇲🇽 Narración Español", elem_classes=["template-pill"])

            # 2. Podcast Studio (Adaptable 2, 3 o 4 Voces)
            with gr.Column(visible=False, elem_classes=["card-box"]) as view_podcast:
                gr.Markdown("### 🎧 Podcast Studio Multi-Voz")
                
                # Botón de selección de participantes
                pod_num_voices = gr.Radio(choices=["2 Voces (Conversación)", "3 Voces (Panel)", "4 Voces (Debate)"], value="2 Voces (Conversación)", label="Cantidad de Locutores / Personajes")
                
                with gr.Row():
                    pod_v1 = gr.Dropdown(choices=list(VOICES.keys()), value="🇺🇸 Andrew (Podcast / Cálida)", label="Locutor 1 (Host)")
                    pod_v2 = gr.Dropdown(choices=list(VOICES.keys()), value="🇺🇸 Jenny (Conversacional / Expresiva)", label="Locutor 2 (Invitado 1)")
                with gr.Row() as pod_extra_row:
                    pod_v3 = gr.Dropdown(choices=list(VOICES.keys()), value="🇺🇸 Brian (Documental / Autoridad)", label="Locutor 3 (Especialista)", visible=False)
                    pod_v4 = gr.Dropdown(choices=list(VOICES.keys()), value="🇺🇸 Ava (Joven / Dinámica)", label="Locutor 4 (Narrador)", visible=False)
                with gr.Row():
                    pod_emotion = gr.Dropdown(choices=list(EMOTIONS.keys()), value="😐 Neutral (Estándar)", label="🎭 Actitud Global (PRO)")
                    pod_spd = gr.Dropdown(choices=list(SPEEDS.keys()), value="1.0x (Normal / Conversacional)", label="Velocidad")
                
                pod_text = gr.Textbox(
                    label="Guión de Podcast (Ejemplo: 'Locutor 1: Hola!', 'Locutor 2: Qué tal!')",
                    lines=8,
                    value="Locutor 1: Welcome everyone to today's roundtable podcast!\nLocutor 2: Thanks Andrew, excited to be here!\nLocutor 3: Glad to join the discussion as well.\nLocutor 4: Stay tuned, this episode is brought to you by Text to Speech Pro."
                )
                
                with gr.Row():
                    btn_pod_sample_en = gr.Button("🇬🇧 Cargar Diálogo de Prueba", elem_classes=["template-pill"])
                
                btn_gen_podcast = gr.Button("✨ Compilar Podcast", variant="primary")
                pod_status = gr.Markdown("")
                pod_audio = gr.Audio(label="Audio del Podcast Completo", show_label=True, elem_classes=["custom-audio-player"])

            # 3. Shadowing & Pronunciation Trainer (PRO)
            with gr.Column(visible=False, elem_classes=["card-box"]) as view_shadowing:
                gr.Markdown("### 🗣️ Shadowing & Pronunciation Trainer <span class='pro-badge'>PRO</span>")
                gr.Markdown("Crea sesiones de práctica con pausas inteligentes para que los estudiantes repitan en voz alta.")
                with gr.Row():
                    shad_voice = gr.Dropdown(choices=list(VOICES.keys()), value="🇺🇸 Andrew (Podcast / Cálida)", label="Voz de Entrenamiento", scale=2)
                    shad_speed = gr.Dropdown(choices=list(SPEEDS.keys()), value="0.8x (Lento / Aprendizaje)", label="Velocidad de Dicción", scale=1)
                    shad_mode = gr.Dropdown(choices=["Repetición Simple (Frase + Silencio)", "Doble Escucha (Frase + Silencio + Repetición)"], value="Repetición Simple (Frase + Silencio)", label="Modo de Práctica", scale=1)
                
                shad_text = gr.Textbox(
                    label="Frases de Práctica (Una oración por línea)",
                    lines=7,
                    value="Connected speech makes your English flow naturally.\nPay attention to the musicality and melody of the phrase.\nConsistent shadowing builds unstoppable speaking confidence."
                )
                btn_gen_shadowing = gr.Button("🎯 Generar Sesión de Shadowing & Pack ZIP", variant="primary")
                shad_status = gr.Markdown("")
                with gr.Row():
                    shad_audio = gr.Audio(label="Audio Master con Pausas", show_label=True)
                    shad_zip = gr.File(label="Pistas Individuales (.ZIP)")

            # 4. Audiolibros Masivos en ZIP (PRO)
            with gr.Column(visible=False, elem_classes=["card-box"]) as view_book:
                gr.Markdown("### 📖 Generador de Audiolibros por Capítulos en ZIP <span class='pro-badge'>PRO</span>")
                with gr.Row():
                    book_voice = gr.Dropdown(choices=list(VOICES.keys()), value="🇪🇸 Elvira (España / Narrativa)", label="Voz de Narrador")
                    book_speed = gr.Dropdown(choices=list(SPEEDS.keys()), value="1.0x (Normal / Conversacional)", label="Velocidad")
                
                book_text = gr.Textbox(
                    label="Contenido del Libro (Usa '### Capítulo 1', 'Capítulo 2' para separar automáticamente)",
                    lines=8,
                    placeholder="### Capítulo 1: El Despertar\nHabía una vez en un valle lejano...\n\n### Capítulo 2: El Sendero\nAl día siguiente comenzó el gran viaje..."
                )
                btn_gen_book = gr.Button("📚 Generar Audiolibro Completo & Pack ZIP", variant="primary")
                book_status = gr.Markdown("")
                with gr.Row():
                    book_audio = gr.Audio(label="Audiolibro Unificado", show_label=True)
                    book_zip = gr.File(label="Capítulos Separados (.ZIP)")

            # 5. Locución para Video con Subtítulos .SRT y .VTT (PRO)
            with gr.Column(visible=False, elem_classes=["card-box"]) as view_video:
                gr.Markdown("### 🎬 Locución para Video & Creadores <span class='pro-badge'>PRO</span>")
                with gr.Row():
                    vid_voice = gr.Dropdown(choices=list(VOICES.keys()), value="🇺🇸 Guy (Casual / YouTube)", label="Voz de Locución")
                    vid_style = gr.Dropdown(choices=["⚡ Dinámico (+15%)", "🗣️ Estándar (0%)", "🎬 Pausado (-10%)"], value="⚡ Dinámico (+15%)", label="Estilo de Locución")
                
                vid_text = gr.Textbox(label="Guión del Video", lines=5, value="In this video, I will show you how to generate realistic neural voiceovers in seconds. Make sure to hit that subscribe button!")
                btn_gen_video = gr.Button("🎬 Generar Locución y Subtítulos (.SRT + .VTT)", variant="primary")
                vid_status = gr.Markdown("")
                with gr.Row():
                    vid_audio = gr.Audio(label="Audio MP3", show_label=True)
                    vid_srt = gr.File(label="Subtítulos .SRT (Editores)")
                    vid_vtt = gr.File(label="Subtítulos .VTT (YouTube)")

            # 6. Proyectos Guardados
            with gr.Column(visible=False, elem_classes=["card-box"]) as view_projects:
                gr.Markdown("### 📂 Mis Proyectos Guardados")
                projects_list = gr.Dataframe(
                    headers=["Título / Resumen", "Voz Utilizada", "Archivo MP3", "Hora"],
                    datatype=["str", "str", "str", "str"],
                    interactive=False
                )
                btn_refresh_projects = gr.Button("🔄 Actualizar Tabla de Proyectos", variant="secondary")

            # 7. Catálogo de Voces HD
            with gr.Column(visible=False, elem_classes=["card-box"]) as view_voices:
                gr.Markdown("### 🎙️ Catálogo de Voces Neuronales HD")
                with gr.Row():
                    sample_voice = gr.Dropdown(choices=list(VOICES.keys()), value="🇺🇸 Jenny (Conversacional / Expresiva)", label="Voz Neuronal", scale=3)
                    btn_test_voice = gr.Button("🔊 Escuchar Muestra", variant="primary", scale=1)
                sample_status = gr.Markdown("")
                sample_audio = gr.Audio(label="Reproductor de Muestra", show_label=True, elem_classes=["custom-audio-player"])

            # 8. Centro de Descargas
            with gr.Column(visible=False, elem_classes=["card-box"]) as view_downloads:
                gr.Markdown("### 📥 Centro de Exportación y Descargas")
                dl_status = gr.Markdown("Archivos disponibles en la sesión actual:")
                dl_files = gr.File(label="Archivos Disponibles", file_count="multiple", interactive=False)
                with gr.Row():
                    btn_refresh_dl = gr.Button("🔄 Actualizar Archivos", variant="secondary")
                    btn_zip_all = gr.Button("📦 Descargar Todo en un solo ZIP (PRO)", variant="primary")
                    btn_clean_dl = gr.Button("🗑️ Purgar Temporales (PRO)", variant="stop")
                dl_zip_file = gr.File(label="Pack ZIP Generado", visible=True)

            # 9. Preferencias & Calidad
            with gr.Column(visible=False, elem_classes=["card-box"]) as view_settings:
                gr.Markdown("### ⚙️ Preferencias y Modulación de Voz")
                set_pitch = gr.Slider(minimum=-30, maximum=30, value=0, step=2, label="Modulación Global de Tono (Hz)")
                set_volume = gr.Slider(minimum=-50, maximum=50, value=0, step=5, label="Ganancia Global de Volumen (%)")
                btn_save_settings = gr.Button("💾 Guardar Preferencias", variant="primary")
                set_status = gr.Markdown("")

    # LÓGICA DE INTERFAZ: Mostrar/Ocultar Locutores en Podcast
    def update_podcast_ui(choice):
        if "2" in choice:
            return gr.update(visible=False), gr.update(visible=False)
        elif "3" in choice:
            return gr.update(visible=True), gr.update(visible=False)
        else:
            return gr.update(visible=True), gr.update(visible=True)
            
    pod_num_voices.change(fn=update_podcast_ui, inputs=pod_num_voices, outputs=[pod_v3, pod_v4])

    # NAVEGACIÓN ENTRE PESTAÑAS
    all_views = [view_editor, view_podcast, view_shadowing, view_book, view_video, view_projects, view_voices, view_downloads, view_settings]
    
    def switch_tab(target_idx):
        return [gr.update(visible=(i == target_idx)) for i in range(len(all_views))]
    
    btn_nav_editor.click(fn=lambda: switch_tab(0), outputs=all_views)
    btn_nav_podcast.click(fn=lambda: switch_tab(1), outputs=all_views)
    btn_nav_shadowing.click(fn=lambda: switch_tab(2), outputs=all_views)
    btn_nav_book.click(fn=lambda: switch_tab(3), outputs=all_views)
    btn_nav_video.click(fn=lambda: switch_tab(4), outputs=all_views)
    btn_nav_projects.click(fn=lambda: switch_tab(5), outputs=all_views)
    btn_nav_voices.click(fn=lambda: switch_tab(6), outputs=all_views)
    btn_nav_downloads.click(fn=lambda: switch_tab(7), outputs=all_views)
    btn_nav_settings.click(fn=lambda: switch_tab(8), outputs=all_views)

    # EVENTO CERRAR SESIÓN
    btn_logout.click(fn=None, js="() => { window.location.href = '/logout'; }")

    # CARGA AUTOMÁTICA DEL ESTADO DE CUENTA
    demo.load(fn=render_account_status, inputs=None, outputs=account_status_view)

    # EVENTOS PRINCIPALES
    main_play_btn.click(
        fn=fn_main_editor,
        inputs=[main_text, main_voice, main_emotion, main_speed, pref_pitch, pref_volume, project_history],
        outputs=[main_audio, project_history, main_status]
    )
    t1.click(fn=lambda: "The ancient lighthouse stood firm against the midnight storm, its radiant beam piercing the dense ocean fog to guide ships safely to harbor.", outputs=main_text)
    t2.click(fn=lambda: "Hey everyone, welcome back to the channel! Today we are exploring the future of generative AI and neural voice synthesis.", outputs=main_text)
    t3.click(fn=lambda: "Bienvenidos a Text to Speech Pro. Transforma cualquier texto en locuciones claras y fluidas con entonación humana natural.", outputs=main_text)

    btn_refresh_projects.click(fn=lambda h: h or [], inputs=[project_history], outputs=projects_list)

    btn_test_voice.click(
        fn=fn_test_voice_sample,
        inputs=sample_voice,
        outputs=[sample_audio, sample_status]
    )

    btn_gen_podcast.click(
        fn=fn_podcast_studio,
        inputs=[pod_text, pod_num_voices, pod_v1, pod_v2, pod_v3, pod_v4, pod_emotion, pod_spd],
        outputs=[pod_audio, pod_status]
    )
    btn_pod_sample_en.click(
        fn=lambda: "Locutor 1: Welcome back to The Sound Wave podcast! I am Andrew, and today we are diving into connected speech.\nLocutor 2: Thanks for having me Andrew! In natural conversation, native speakers blend and link sounds smoothly.\nLocutor 3: Exactly, and shadowing is the best way to develop that muscle memory.\nLocutor 4: Stay tuned for our next episode!",
        outputs=pod_text
    )

    btn_gen_shadowing.click(
        fn=fn_shadowing_trainer,
        inputs=[shad_text, shad_voice, shad_speed, shad_mode],
        outputs=[shad_audio, shad_zip, shad_status]
    )

    btn_gen_book.click(
        fn=fn_book_narration_zip,
        inputs=[book_text, book_voice, book_speed],
        outputs=[book_audio, book_zip, book_status]
    )

    btn_gen_video.click(
        fn=fn_video_voiceover,
        inputs=[vid_text, vid_voice, vid_style],
        outputs=[vid_audio, vid_srt, vid_vtt, vid_status]
    )

    btn_refresh_dl.click(fn=get_all_media_files, outputs=[dl_files, dl_zip_file, dl_status])
    btn_zip_all.click(fn=download_all_as_zip, outputs=[dl_zip_file, dl_status])
    btn_clean_dl.click(fn=clear_all_media_files, outputs=[dl_files, dl_zip_file, dl_status, project_history])

    btn_save_settings.click(
        fn=lambda p, v: (p, v, "✅ Preferencias guardadas correctamente y aplicadas a todos los módulos."),
        inputs=[set_pitch, set_volume],
        outputs=[pref_pitch, pref_volume, set_status]
    )

# =========================================================
# LANZAMIENTO DEL SERVIDOR
# =========================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        auth=USERS_DATABASE,
        auth_message="🔒 Acceso Privado - Text to Speech Pro Studio"
    )
