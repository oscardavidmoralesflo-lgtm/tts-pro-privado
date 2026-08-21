import gradio as gr
import edge_tts
import asyncio
import os
import io
import time
import re
import zipfile

# =========================================================
# 1. BASE DE USUARIOS Y ACCESO (100% ILIMITADO)
# =========================================================
USERS_DATABASE = [
    ("admin_pro", "TTS_MasterKey#2026!"),
    ("invitado_vip", "VozStudio2026*Open")
]

# Reglas del Diccionario Fonético Iniciales
DEFAULT_PRONUNCIATION_RULES = """WhatsApp = Uasap
ChatGPT = Chat Yipití
AI = Ei Ai
Wi-Fi = Guai Fai
YouTube = Yutub
TikTok = Tik Tok
Python = Paiton
Online = Onlain"""

def count_words(text: str) -> int:
    return len(text.strip().split()) if text else 0

def apply_pronunciation_rules(text: str, rules_raw: str) -> str:
    """Aplica las reglas de reemplazo del diccionario fonético."""
    if not text or not rules_raw:
        return text
    modified_text = text
    for line in rules_raw.strip().split("\n"):
        if "=" in line:
            parts = line.split("=", 1)
            original = parts[0].strip()
            replacement = parts[1].strip()
            if original and replacement:
                pattern = re.compile(r'\b' + re.escape(original) + r'\b', re.IGNORECASE)
                modified_text = pattern.sub(replacement, modified_text)
    return modified_text

def render_account_status(request: gr.Request):
    """Muestra la tarjeta de Suite PRO Ilimitada en la barra lateral."""
    username = getattr(request, "username", "admin_pro")
    return f"""
    <div class="account-card pro-card">
        <div class="account-badge pro-tag">👑 SUITE PRO MASTER</div>
        <div class="account-user">Usuario: <b>{username}</b></div>
        <div class="account-details">
            ✨ <b>Acceso Total e Ilimitado:</b><br>
            • Sin límites de caracteres ni tiempo<br>
            • Podcast 4 Voces & Emociones<br>
            • Shadowing & Audiolibros ZIP<br>
            • Subtítulos .SRT/.VTT & ID3 Portadas<br>
            • Diccionario Fonético & Asistente IA
        </div>
    </div>
    """

# =========================================================
# 2. CATÁLOGO DE VOCES NEURONALES HD & EMOCIONES
# =========================================================
VOICES = {
    # 🇺🇸 Inglés Neural HD
    "🇺🇸 Andrew (Podcast / Cálida)": "en-US-AndrewNeural",
    "🇺🇸 Jenny (Conversacional / Expresiva)": "en-US-JennyNeural",
    "🇺🇸 Ava (Joven / Dinámica)": "en-US-AvaNeural",
    "🇺🇸 Brian (Documental / Autoridad)": "en-US-BrianNeural",
    "🇺🇸 Emma (Audiolibros / Suave)": "en-US-EmmaNeural",
    "🇺🇸 Guy (Casual / YouTube)": "en-US-GuyNeural",
    "🇺🇸 Aria (Locución de Estudio)": "en-US-AriaNeural",
    "🇺🇸 Christopher (Profundo / Relato)": "en-US-ChristopherNeural",
    
    # 🇲🇽 🇪🇸 🇨🇴 Español Neural HD
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
    if not label_or_id: return default
    if label_or_id in VOICES.values(): return label_or_id
    if label_or_id in VOICES: return VOICES[label_or_id]
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
# MOTOR DE SÍNTESIS CORE
# =========================================================
async def core_synthesize(text, voice_id, rate_val=0, pitch_val=0, volume_val=0):
    if not text or not text.strip():
        return b""
    kwargs = {}
    if rate_val != 0: kwargs["rate"] = f"{'+' if rate_val > 0 else ''}{rate_val}%"
    if pitch_val != 0: kwargs["pitch"] = f"{'+' if pitch_val > 0 else ''}{pitch_val}Hz"
    if volume_val != 0: kwargs["volume"] = f"{'+' if volume_val > 0 else ''}{volume_val}%"
    
    clean_voice = resolve_voice_id(voice_id)
    communicator = edge_tts.Communicate(text=text.strip(), voice=clean_voice, **kwargs)
    buffer = io.BytesIO()
    async for chunk in communicator.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
    return buffer.getvalue()

def generate_mp3_silence(seconds: float) -> bytes:
    """Genera silencios digitales limpios en formato MP3 puro."""
    silence_frame = (
        b'\xff\xfb\x90\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        + b'\x00' * 369
    )
    num_frames = int(max(1, round(seconds * 38.28)))
    return silence_frame * num_frames

def parse_tagged_speech(text: str):
    """Parsea el texto dividiendo por pausas y cambios emocionales."""
    tag_pattern = r'(\[(?:Pausa\s+\d+(?:\.\d+)?s|Susurro|Alegre|Triste|Épico|Epico|Firme|Normal)\])'
    tokens = re.split(tag_pattern, text, flags=re.IGNORECASE)
    segments = []
    current_emotion = "😐 Neutral (Estándar)"
    emotion_map = {
        "[susurro]": "🤫 Susurro / Confidencial",
        "[alegre]": "😊 Alegre / Entusiasta",
        "[triste]": "😔 Triste / Melancólico",
        "[épico]": "🎤 Épico / Tráiler",
        "[epico]": "🎤 Épico / Tráiler",
        "[firme]": "😡 Enojado / Firme",
        "[normal]": "😐 Neutral (Estándar)"
    }
    for token in tokens:
        if not token: continue
        t_strip = token.strip()
        t_low = t_strip.lower()
        if t_low.startswith("[pausa") and t_low.endswith("s]"):
            match = re.search(r'\d+(?:\.\d+)?', t_low)
            if match:
                segments.append({"type": "pause", "duration": float(match.group(0))})
        elif t_low in emotion_map:
            current_emotion = emotion_map[t_low]
        else:
            if t_strip:
                segments.append({"type": "text", "content": t_strip, "emotion": current_emotion})
    return segments

def embed_id3_metadata(mp3_bytes: bytes, title: str = "", artist: str = "", album: str = "", cover_bytes: bytes = None) -> bytes:
    """Incrusta metadatos ID3v2.3 y portada de imagen en el archivo MP3."""
    def make_frame(frame_id, text):
        encoded = b'\x03' + text.encode('utf-8')
        size = len(encoded)
        header = frame_id.encode('ascii') + size.to_bytes(4, 'big') + b'\x00\x00'
        return header + encoded

    frames = b''
    if title: frames += make_frame('TIT2', title)
    if artist: frames += make_frame('TPE1', artist)
    if album: frames += make_frame('TALB', album)
    if cover_bytes:
        mime = b'image/jpeg\x00' if cover_bytes[:2] == b'\xff\xd8' else b'image/png\x00'
        pic_type = b'\x03'
        desc = b'\x00'
        apic_data = b'\x00' + mime + pic_type + desc + cover_bytes
        header = b'APIC' + len(apic_data).to_bytes(4, 'big') + b'\x00\x00'
        frames += header + apic_data

    tag_size = len(frames)
    if tag_size == 0:
        return mp3_bytes
        
    b0 = (tag_size >> 21) & 0x7F
    b1 = (tag_size >> 14) & 0x7F
    b2 = (tag_size >> 7) & 0x7F
    b3 = tag_size & 0x7F
    id3_header = b'ID3\x03\x00\x00' + bytes([b0, b1, b2, b3])
    return id3_header + frames + mp3_bytes

# =========================================================
# FUNCIONES DE CADA MÓDULO
# =========================================================

# 1. Editor Inteligente (Tags & Pausas)
async def fn_main_editor(text, voice_label, default_emotion, speed_label, pitch_pref, vol_pref, rules_raw, history):
    if not text or not text.strip():
        return None, history, "⚠️ Escribe algún texto en el editor."
    
    # Aplicar diccionario fonético
    processed_text = apply_pronunciation_rules(text, rules_raw)
    voice_id = resolve_voice_id(voice_label, "en-US-AndrewNeural")
    base_speed = SPEEDS.get(speed_label, 0)
    
    segments = parse_tagged_speech(processed_text)
    if not segments:
        return None, history, "⚠️ No hay contenido para procesar."
        
    final_audio = io.BytesIO()
    
    try:
        for seg in segments:
            if seg["type"] == "pause":
                final_audio.write(generate_mp3_silence(seg["duration"]))
            else:
                emotion_to_use = seg["emotion"] if seg["emotion"] != "😐 Neutral (Estándar)" else default_emotion
                e_rate, e_pitch, e_vol = EMOTIONS.get(emotion_to_use, (0, 0, 0))
                
                final_rate = base_speed + e_rate
                final_pitch = pitch_pref + e_pitch
                final_vol = vol_pref + e_vol
                
                chunk = await core_synthesize(seg["content"], voice_id, final_rate, final_pitch, final_vol)
                if chunk:
                    final_audio.write(chunk)
                await asyncio.sleep(0.03)
                
        audio_data = final_audio.getvalue()
        if not audio_data:
            return None, history, "⚠️ No se pudo generar el audio."
            
        filename = f"audio_script_{int(time.time())}.mp3"
        with open(filename, "wb") as f:
            f.write(audio_data)
            
        title = text.strip()[:35].replace("\n", " ") + "..."
        history = history or []
        history.insert(0, [title, voice_label, filename, time.strftime("%H:%M:%S")])
        
        return filename, history, f"✅ Audio generado con éxito ({count_words(text):,} palabras / {len(text):,} caracteres)."
    except Exception as e:
        return None, history, f"❌ Error: {str(e)}"

# 2. Muestras de Voz (Catálogo)
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

# 3. Podcast Studio (2, 3 o 4 Voces)
async def fn_podcast_studio(script, num_voices, v1_lbl, v2_lbl, v3_lbl, v4_lbl, emotion_lbl, speed_lbl, rules_raw):
    if not script or not script.strip():
        return None, "⚠️ El guión de podcast está vacío."
    
    processed_script = apply_pronunciation_rules(script, rules_raw)
    v1 = resolve_voice_id(v1_lbl, "en-US-AndrewNeural")
    v2 = resolve_voice_id(v2_lbl, "en-US-JennyNeural")
    v3 = resolve_voice_id(v3_lbl, "en-US-BrianNeural")
    v4 = resolve_voice_id(v4_lbl, "en-US-AvaNeural")
    
    base_speed = SPEEDS.get(speed_lbl, 0)
    e_rate, e_pitch, e_vol = EMOTIONS.get(emotion_lbl, (0, 0, 0))
    final_rate = base_speed + e_rate
    
    lines = [l.strip() for l in processed_script.strip().split("\n") if l.strip()]
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
            
        return filename, f"✅ Podcast compilado con éxito ({processed_count} intervenciones / {count_words(script):,} palabras)."
    except Exception as e:
        return None, f"❌ Error durante la compilación: {str(e)}"

# 4. Shadowing & Fonética Trainer
async def fn_shadowing_trainer(script, voice_label, speed_label, pause_mode, rules_raw):
    if not script or not script.strip():
        return None, None, "⚠️ Ingresa las frases para la sesión de shadowing."
    
    processed_script = apply_pronunciation_rules(script, rules_raw)
    voice_id = resolve_voice_id(voice_label, "en-US-AndrewNeural")
    speed_val = SPEEDS.get(speed_label, 0)
    
    sentences = [s.strip() for s in processed_script.strip().split("\n") if s.strip()]
    if not sentences:
        return None, None, "⚠️ No hay oraciones válidas para entrenar."
    
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
        with open(master_file, "wb") as f:
            f.write(master_audio.getvalue())
            
        zip_file = f"shadowing_pack_{int(time.time())}.zip"
        with open(zip_file, "wb") as f:
            f.write(zip_buffer.getvalue())
            
        return master_file, zip_file, f"✅ Sesión de Shadowing generada ({len(sentences)} unidades de práctica + Pack ZIP)."
    except Exception as e:
        return None, None, f"❌ Error: {str(e)}"

# 5. Audiolibros por Capítulos en ZIP
async def fn_book_narration_zip(book_text, voice_label, speed_label, rules_raw):
    if not book_text or not book_text.strip():
        return None, None, "⚠️ Pega el contenido del manuscrito o audiolibro."
    
    processed_book = apply_pronunciation_rules(book_text, rules_raw)
    voice_id = resolve_voice_id(voice_label, "es-ES-ElviraNeural")
    speed_val = SPEEDS.get(speed_label, 0)
    
    raw_chapters = re.split(r'(?i)(?:^|\n)(?=###|\bcap[ií]tulo\b|\bchapter\b)', processed_book.strip())
    chapters = [c.strip() for c in raw_chapters if c.strip()]
    if not chapters:
        chapters = [processed_book.strip()]
        
    master_audio = io.BytesIO()
    zip_buffer = io.BytesIO()
    index_text = "ÍNDICE DE CONTENIDOS DEL AUDIOLIBRO\n===================================\n\n"
    
    try:
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, chap in enumerate(chapters, 1):
                first_line = chap.split("\n")[0][:40].replace("#", "").strip()
                title = first_line if first_line else f"Capitulo_{i}"
                index_text += f"{i:02d}. {title} ({count_words(chap):,} palabras)\n"
                
                chunk = await core_synthesize(chap, voice_id, speed_val)
                if chunk:
                    master_audio.write(chunk)
                    master_audio.write(generate_mp3_silence(2.5))
                    
                    safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
                    zf.writestr(f"{i:02d}_{safe_title}.mp3", chunk)
                await asyncio.sleep(0.04)
                
            zf.writestr("Indice_Capitulos.txt", index_text)
            
        master_file = f"audiolibro_completo_{int(time.time())}.mp3"
        with open(master_file, "wb") as f:
            f.write(master_audio.getvalue())
            
        zip_file = f"audiolibro_capitulos_{int(time.time())}.zip"
        with open(zip_file, "wb") as f:
            f.write(zip_buffer.getvalue())
            
        return master_file, zip_file, f"✅ Audiolibro compilado ({len(chapters)} capítulos empaquetados en ZIP)."
    except Exception as e:
        return None, None, f"❌ Error: {str(e)}"

# 6. Locución para Video con Subtítulos .SRT y .VTT
async def fn_video_voiceover(text, voice_label, style_speed, rules_raw):
    if not text or not text.strip():
        return None, None, None, "⚠️ Ingresa el guión para el video."
    
    processed_text = apply_pronunciation_rules(text, rules_raw)
    speed_mapping = {
        "⚡ Dinámico / YouTube (+15%)": 15,
        "🗣️ Comercial / Estándar (0%)": 0,
        "🎬 Documental / Pausado (-10%)": -10
    }
    speed_val = speed_mapping.get(style_speed, 0)
    voice_id = resolve_voice_id(voice_label, "en-US-GuyNeural")
    
    try:
        audio_bytes = await core_synthesize(processed_text, voice_id, speed_val)
        mp3_file = f"locucion_video_{int(time.time())}.mp3"
        with open(mp3_file, "wb") as f:
            f.write(audio_bytes)
            
        sentences = [s.strip() for s in re.split(r'(?<=[.?!])\s+', processed_text) if s.strip()]
        
        srt_content = ""
        vtt_content = "WEBVTT\n\n"
        start_sec = 0.0
        
        for i, s in enumerate(sentences, 1):
            duration = max(2.2, len(s) * 0.062)
            end_sec = start_sec + duration
            
            def fmt_srt(t):
                h, m, sec, ms = int(t // 3600), int((t % 3600) // 60), int(t % 60), int((t - int(t)) * 1000)
                return f"{h:02}:{m:02}:{sec:02},{ms:03}"
                
            def fmt_vtt(t):
                h, m, sec, ms = int(t // 3600), int((t % 3600) // 60), int(t % 60), int((t - int(t)) * 1000)
                return f"{h:02}:{m:02}:{sec:02}.{ms:03}"
                
            srt_content += f"{i}\n{fmt_srt(start_sec)} --> {fmt_srt(end_sec)}\n{s}\n\n"
            vtt_content += f"{i}\n{fmt_vtt(start_sec)} --> {fmt_vtt(end_sec)}\n{s}\n\n"
            start_sec = end_sec
            
        srt_file = f"subtitulos_{int(time.time())}.srt"
        with open(srt_file, "w", encoding="utf-8") as f:
            f.write(srt_content)
            
        vtt_file = f"subtitulos_{int(time.time())}.vtt"
        with open(vtt_file, "w", encoding="utf-8") as f:
            f.write(vtt_content)
            
        return mp3_file, srt_file, vtt_file, f"✅ Locución y subtítulos (.SRT + .VTT) generados con éxito."
    except Exception as e:
        return None, None, None, f"❌ Error: {str(e)}"

# 7. Asistente de Guiones con IA
def fn_generate_script_assistant(template_type, topic):
    t = topic.strip() if topic and topic.strip() else "el poder de la consistencia"
    
    if "TikTok" in template_type:
        return f"""[Alegre] ¿Sabías que el 90% de las personas comete este error al hablar sobre {t}?
[Pausa 0.8s]
[Susurro] Te voy a revelar el secreto exacto que nadie te cuenta.
[Pausa 1.0s]
[Normal] La clave no es la perfección, sino el ritmo y la confianza.
[Pausa 0.5s]
[Épico] Si quieres dominarlo hoy mismo, guarda este video y sígueme para más."""
    
    elif "Podcast" in template_type:
        return f"""Locutor 1: ¡Hola a todos y bienvenidos a este nuevo episodio donde exploramos {t}!
Locutor 2: ¡Hola Andrew! Es un tema fascinante y que genera muchísimo debate hoy en día.
Locutor 3: Totalmente de acuerdo. Cuando analizamos los datos a fondo, vemos oportunidades increíbles.
Locutor 4: Quédense con nosotros hasta el final para descubrir las conclusiones más reveladoras."""
    
    elif "Shadowing" in template_type:
        return f"""Connected speech makes your speaking flow naturally.
Focus on the musicality and rhythm of every single word.
Mastering {t} requires daily, deliberate shadowing practice.
Listen carefully, imitate the melody, and build permanent muscle memory."""
    
    elif "Audiolibro" in template_type:
        return f"""### Capítulo 1: El Comienzo
[Pausa 1.0s]
El viaje hacia {t} comenzó en una mañana despejada de otoño. Las decisiones que se tomaron aquel día cambiarían el rumbo de la historia para siempre.
[Pausa 1.5s]

### Capítulo 2: La Transformación
[Pausa 1.0s]
Con cada obstáculo superado, la visión se hacía más clara. No había marcha atrás."""
    
    else: # Comercial
        return f"""[Épico] ¿Buscas llevar tus resultados al siguiente nivel con {t}?
[Pausa 0.8s]
[Alegre] Descubre la plataforma diseñada para creadores y profesionales exigentes.
[Pausa 0.5s]
[Firme] Calidad de estudio, rapidez instantánea y control total.
[Pausa 0.5s]
[Susurro] Pruébalo hoy mismo y siente la diferencia."""

# 8. Editor de Metadatos ID3 & Portada
def fn_embed_metadata(source_audio, title, artist, album, cover_image):
    if not source_audio:
        return None, "⚠️ Selecciona o genera un archivo de audio primero."
    
    try:
        with open(source_audio, "rb") as f:
            raw_mp3 = f.read()
            
        cover_bytes = None
        if cover_image:
            with open(cover_image, "rb") as img_f:
                cover_bytes = img_f.read()
                
        tagged_mp3 = embed_id3_metadata(raw_mp3, title, artist, album, cover_bytes)
        
        out_name = f"master_id3_{int(time.time())}.mp3"
        with open(out_name, "wb") as out_f:
            out_f.write(tagged_mp3)
            
        return out_name, f"✅ Metadatos ID3 y portada incrustados correctamente en **{out_name}**."
    except Exception as e:
        return None, f"❌ Error al incrustar metadatos: {str(e)}"

# 9. Centro de Descargas & Exportación Masiva en ZIP
def get_all_media_files():
    files = [f for f in os.listdir(".") if f.endswith(".mp3") or f.endswith(".srt") or f.endswith(".vtt") or f.endswith(".zip")]
    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return files, None, "✅ Historial completo de archivos disponibles."

def download_all_as_zip():
    files = [f for f in os.listdir(".") if f.endswith((".mp3", ".srt", ".vtt"))]
    if not files:
        return None, "⚠️ No hay archivos para empaquetar."
        
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            if os.path.exists(f):
                zf.write(f, arcname=f)
                
    zip_name = f"Pack_Completo_Audios_{int(time.time())}.zip"
    with open(zip_name, "wb") as f:
        f.write(zip_buffer.getvalue())
        
    return zip_name, f"✅ Pack ZIP generado con {len(files)} archivos listos para descargar."

def clear_all_media_files():
    count = 0
    for f in os.listdir("."):
        if (f.endswith(".mp3") or f.endswith(".srt") or f.endswith(".vtt") or f.endswith(".zip")) and not f.startswith("sample_"):
            try:
                os.remove(f)
                count += 1
            except:
                pass
    return [], None, f"🧹 Se eliminaron {count} archivos temporales.", []

# =========================================================
# DISEÑO VISUAL PROFESIONAL
# =========================================================
custom_css = """
:root, html, body, .dark, .gradio-container, .gradio-container * {
    color-scheme: light !important;
}

body, .gradio-container {
    background-color: #f8fafc !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    padding: 0 !important;
    margin: 0 !important;
    max-width: 100% !important;
}

footer { visibility: hidden !important; }

.app-layout {
    display: flex;
    min-height: 100vh;
    background-color: #f8fafc !important;
}

.sidebar-panel {
    width: 275px;
    background-color: #ffffff !important;
    border-right: 1px solid #e2e8f0 !important;
    padding: 24px 16px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.brand-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    padding-left: 4px;
}

.brand-icon {
    width: 36px;
    height: 36px;
    background: linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #ffffff;
    font-weight: 800;
    font-size: 16px;
    box-shadow: 0 4px 12px rgba(79, 70, 229, 0.25);
}

.brand-title {
    font-size: 17px;
    font-weight: 800;
    color: #0f172a !important;
    letter-spacing: -0.5px;
}

.brand-title span {
    color: #4f46e5 !important;
}

.account-card {
    border-radius: 12px;
    padding: 12px;
    margin-bottom: 16px;
    font-size: 12px;
    line-height: 1.4;
}

.pro-card {
    background: linear-gradient(145deg, #f5f3ff 0%, #ede9fe 100%);
    border: 1px solid #ddd6fe;
    color: #4c1d95;
}

.pro-tag {
    background: #7c3aed;
    color: #ffffff;
    font-weight: 800;
    font-size: 10px;
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
    margin-bottom: 6px;
    letter-spacing: 0.5px;
}

.account-user {
    font-size: 13px;
    margin-bottom: 4px;
}

.account-details {
    font-size: 11px;
    opacity: 0.9;
    margin-bottom: 4px;
}

.menu-section {
    font-size: 11px;
    font-weight: 700;
    color: #94a3b8 !important;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin: 14px 0 6px 10px;
}

.nav-btn {
    width: 100% !important;
    text-align: left !important;
    justify-content: flex-start !important;
    background: #ffffff !important;
    border: 1px solid transparent !important;
    color: #475569 !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    padding: 9px 12px !important;
    border-radius: 10px !important;
    margin-bottom: 2px !important;
    box-shadow: none !important;
    transition: all 0.15s ease !important;
}

.nav-btn:hover {
    background: #f1f5f9 !important;
    color: #0f172a !important;
}

.logout-btn {
    background-color: #fef2f2 !important;
    color: #ef4444 !important;
    border: 1px solid #fee2e2 !important;
    margin-top: 12px !important;
}

.logout-btn:hover {
    background-color: #fee2e2 !important;
    color: #dc2626 !important;
}

.content-area {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    padding: 24px 32px;
    background-color: #f8fafc !important;
}

.card-box {
    background-color: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 20px;
    box-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.04) !important;
    padding: 28px 32px;
    max-width: 960px;
    margin: 0 auto;
    width: 100%;
}

.top-bar-controls {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    margin-bottom: 16px;
    padding-bottom: 16px;
    border-bottom: 1px solid #f1f5f9;
}

.btn-play-hero {
    background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%) !important;
    border-radius: 50% !important;
    width: 42px !important;
    height: 42px !important;
    min-width: 42px !important;
    max-width: 42px !important;
    aspect-ratio: 1 / 1 !important;
    padding: 0 !important;
    color: #ffffff !important;
    border: none !important;
    box-shadow: 0 4px 14px rgba(79, 70, 229, 0.3) !important;
    font-size: 15px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    cursor: pointer !important;
    flex-shrink: 0 !important;
}

.custom-audio-player {
    background-color: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 14px !important;
    margin-top: 14px !important;
}

.clean-editor textarea {
    border: 1px solid #e2e8f0 !important;
    border-radius: 14px !important;
    background-color: #ffffff !important;
    font-size: 15px !important;
    line-height: 1.6 !important;
    color: #0f172a !important;
    padding: 16px !important;
}

.template-pill {
    border: 1px solid #e2e8f0 !important;
    background-color: #f8fafc !important;
    border-radius: 20px !important;
    padding: 6px 14px !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    color: #475569 !important;
}

.tag-btn {
    border: 1px solid #cbd5e1 !important;
    background-color: #ffffff !important;
    border-radius: 8px !important;
    padding: 4px 10px !important;
    font-size: 11.5px !important;
    font-weight: 600 !important;
    color: #334155 !important;
}

.tag-btn:hover {
    background-color: #f1f5f9 !important;
    border-color: #94a3b8 !important;
}
"""

# =========================================================
# INTERFAZ GRADIO
# =========================================================
with gr.Blocks(title="Text to Speech Pro Studio", css=custom_css) as demo:
    
    project_history = gr.State([])
    pref_pitch = gr.State(0)
    pref_volume = gr.State(0)
    rules_state = gr.State(DEFAULT_PRONUNCIATION_RULES)
    
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
                btn_nav_editor = gr.Button("📝 Editor Inteligente (Tags)", elem_classes=["nav-btn"])
                btn_nav_podcast = gr.Button("🎧 Podcast Studio 4 Voces", elem_classes=["nav-btn"])
                btn_nav_shadowing = gr.Button("🗣️ Shadowing & Fonética", elem_classes=["nav-btn"])
                btn_nav_book = gr.Button("📖 Audiolibros en ZIP", elem_classes=["nav-btn"])
                btn_nav_video = gr.Button("🎬 Locución Video (.SRT/.VTT)", elem_classes=["nav-btn"])
                
                gr.HTML('<div class="menu-section">Herramientas Pro</div>')
                btn_nav_assistant = gr.Button("🪄 Asistente de Guiones con IA", elem_classes=["nav-btn"])
                btn_nav_dictionary = gr.Button("📖 Diccionario Fonético", elem_classes=["nav-btn"])
                btn_nav_metadata = gr.Button("🏷️ Metadatos ID3 & Portada", elem_classes=["nav-btn"])
                
                gr.HTML('<div class="menu-section">Exportación & Ajustes</div>')
                btn_nav_projects = gr.Button("📂 Mis Proyectos", elem_classes=["nav-btn"])
                btn_nav_voices = gr.Button("🎙️ Catálogo de Voces HD", elem_classes=["nav-btn"])
                btn_nav_downloads = gr.Button("📥 Centro de Descargas (ZIP)", elem_classes=["nav-btn"])
                btn_nav_settings = gr.Button("⚙️ Preferencias & Calidad", elem_classes=["nav-btn"])

            with gr.Column():
                btn_logout = gr.Button("🚪 Cerrar Sesión", elem_classes=["nav-btn", "logout-btn"])

        # CONTENIDO PRINCIPAL
        with gr.Column(elem_classes=["content-area"]):
            
            # 1. Editor Inteligente
            with gr.Column(visible=True, elem_classes=["card-box"]) as view_editor:
                gr.Markdown("### 📝 Editor Inteligente con Expresiones y Pausas")
                with gr.Row(elem_classes=["top-bar-controls"]):
                    main_voice = gr.Dropdown(choices=list(VOICES.keys()), value="🇺🇸 Andrew (Podcast / Cálida)", show_label=False, scale=3)
                    main_emotion = gr.Dropdown(choices=list(EMOTIONS.keys()), value="😐 Neutral (Estándar)", label="🎭 Emoción Base", scale=2)
                    main_speed = gr.Dropdown(choices=list(SPEEDS.keys()), value="1.0x (Normal / Conversacional)", show_label=False, scale=2)
                    main_play_btn = gr.Button("▶", elem_classes=["btn-play-hero"])
                
                main_audio = gr.Audio(show_label=False, elem_classes=["custom-audio-player"])
                main_status = gr.Markdown("")
                
                # Barra de Botones Táctiles para Pausas y Emociones
                gr.Markdown("##### ⏱️ Insertar Pausas y Actitudes en el Cursor:")
                with gr.Row():
                    btn_tag_p05 = gr.Button("⏱️ +Pausa 0.5s", elem_classes=["tag-btn"])
                    btn_tag_p10 = gr.Button("⏱️ +Pausa 1.0s", elem_classes=["tag-btn"])
                    btn_tag_p20 = gr.Button("⏱️ +Pausa 2.0s", elem_classes=["tag-btn"])
                    btn_tag_alegre = gr.Button("😊 [Alegre]", elem_classes=["tag-btn"])
                    btn_tag_susurro = gr.Button("🤫 [Susurro]", elem_classes=["tag-btn"])
                    btn_tag_triste = gr.Button("😔 [Triste]", elem_classes=["tag-btn"])
                    btn_tag_epico = gr.Button("🎤 [Épico]", elem_classes=["tag-btn"])
                    btn_tag_normal = gr.Button("😐 [Normal]", elem_classes=["tag-btn"])
                
                main_text = gr.Textbox(
                    placeholder="Escribe tu guión. Puedes usar tags como [Pausa 1s] o [Susurro]...",
                    show_label=False,
                    lines=8,
                    value="Welcome to Text to Speech Pro Studio. [Pausa 1.0s] [Alegre] Convert your scripts into ultra-realistic speech using neural deep learning models! [Pausa 0.8s] [Susurro] Experience true human inflection like never before.",
                    elem_classes=["clean-editor"]
                )
                
                with gr.Row():
                    t1 = gr.Button("📖 Historia en Inglés", elem_classes=["template-pill"])
                    t2 = gr.Button("🎙️ Intro Podcast", elem_classes=["template-pill"])
                    t3 = gr.Button("🇲🇽 Narración Español", elem_classes=["template-pill"])

            # 2. Podcast Studio (Adaptable 2, 3 o 4 Voces)
            with gr.Column(visible=False, elem_classes=["card-box"]) as view_podcast:
                gr.Markdown("### 🎧 Podcast Studio Multi-Voz")
                pod_num_voices = gr.Radio(choices=["2 Voces (Conversación)", "3 Voces (Panel)", "4 Voces (Debate Completo)"], value="2 Voces (Conversación)", label="Cantidad de Participantes")
                
                with gr.Row():
                    pod_v1 = gr.Dropdown(choices=list(VOICES.keys()), value="🇺🇸 Andrew (Podcast / Cálida)", label="Locutor 1 (Host)")
                    pod_v2 = gr.Dropdown(choices=list(VOICES.keys()), value="🇺🇸 Jenny (Conversacional / Expresiva)", label="Locutor 2 (Invitado 1)")
                with gr.Row() as pod_extra_row:
                    pod_v3 = gr.Dropdown(choices=list(VOICES.keys()), value="🇺🇸 Brian (Documental / Autoridad)", label="Locutor 3 (Especialista)", visible=False)
                    pod_v4 = gr.Dropdown(choices=list(VOICES.keys()), value="🇺🇸 Ava (Joven / Dinámica)", label="Locutor 4 (Narrador)", visible=False)
                with gr.Row():
                    pod_emotion = gr.Dropdown(choices=list(EMOTIONS.keys()), value="😐 Neutral (Estándar)", label="🎭 Actitud Global")
                    pod_spd = gr.Dropdown(choices=list(SPEEDS.keys()), value="1.0x (Normal / Conversacional)", label="Velocidad")
                
                pod_text = gr.Textbox(
                    label="Guión de Podcast (Usa 'Locutor 1:', 'Locutor 2:', 'Locutor 3:' o 'Locutor 4:')",
                    lines=8,
                    value="Locutor 1: Welcome everyone to today's roundtable podcast!\nLocutor 2: Thanks Andrew, excited to be here!\nLocutor 3: Glad to join the discussion as well.\nLocutor 4: Stay tuned, this episode is brought to you by Text to Speech Pro."
                )
                
                with gr.Row():
                    btn_pod_sample_en = gr.Button("🇬🇧 Cargar Diálogo Inglés", elem_classes=["template-pill"])
                    btn_pod_sample_es = gr.Button("🇲🇽 Cargar Diálogo Español", elem_classes=["template-pill"])
                
                btn_gen_podcast = gr.Button("✨ Compilar Podcast Multi-Voz", variant="primary")
                pod_status = gr.Markdown("")
                pod_audio = gr.Audio(label="Audio del Podcast Completo", show_label=True, elem_classes=["custom-audio-player"])

            # 3. Shadowing & Fonética Trainer
            with gr.Column(visible=False, elem_classes=["card-box"]) as view_shadowing:
                gr.Markdown("### 🗣️ Shadowing & Fonética Trainer")
                gr.Markdown("Crea sesiones de práctica con pausas inteligentes para repetición guiada y exporta las pistas en ZIP.")
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

            # 4. Audiolibros Masivos en ZIP
            with gr.Column(visible=False, elem_classes=["card-box"]) as view_book:
                gr.Markdown("### 📖 Generador de Audiolibros por Capítulos en ZIP")
                with gr.Row():
                    book_voice = gr.Dropdown(choices=list(VOICES.keys()), value="🇪🇸 Elvira (España / Narrativa)", label="Voz de Narrador")
                    book_speed = gr.Dropdown(choices=list(SPEEDS.keys()), value="1.0x (Normal / Conversacional)", label="Velocidad")
                
                book_text = gr.Textbox(
                    label="Contenido del Libro (Usa '### Capítulo 1', 'Capítulo 2' para separar automáticamente)",
                    lines=8,
                    value="### Capítulo 1: El Despertar\nHabía una vez en un valle lejano, un pueblo que custodiaba un antiguo secreto...\n\n### Capítulo 2: El Sendero\nAl día siguiente comenzó la travesía hacia lo desconocido..."
                )
                btn_gen_book = gr.Button("📚 Generar Audiolibro Completo & Pack ZIP", variant="primary")
                book_status = gr.Markdown("")
                with gr.Row():
                    book_audio = gr.Audio(label="Audiolibro Unificado", show_label=True)
                    book_zip = gr.File(label="Capítulos Separados (.ZIP)")

            # 5. Locución para Video con Subtítulos .SRT y .VTT
            with gr.Column(visible=False, elem_classes=["card-box"]) as view_video:
                gr.Markdown("### 🎬 Locución para Video & Creadores")
                with gr.Row():
                    vid_voice = gr.Dropdown(choices=list(VOICES.keys()), value="🇺🇸 Guy (Casual / YouTube)", label="Voz de Locución")
                    vid_style = gr.Dropdown(choices=["⚡ Dinámico / YouTube (+15%)", "🗣️ Comercial / Estándar (0%)", "🎬 Documental / Pausado (-10%)"], value="⚡ Dinámico / YouTube (+15%)", label="Estilo de Locución")
                
                vid_text = gr.Textbox(label="Guión del Video", lines=5, value="In this video, I will show you how to generate realistic neural voiceovers in seconds. Make sure to hit that subscribe button!")
                btn_gen_video = gr.Button("🎬 Generar Locución y Subtítulos (.SRT + .VTT)", variant="primary")
                vid_status = gr.Markdown("")
                with gr.Row():
                    vid_audio = gr.Audio(label="Audio MP3", show_label=True)
                    vid_srt = gr.File(label="Subtítulos .SRT (Editores)")
                    vid_vtt = gr.File(label="Subtítulos .VTT (YouTube)")

            # 6. Asistente de Guiones con IA
            with gr.Column(visible=False, elem_classes=["card-box"]) as view_assistant:
                gr.Markdown("### 🪄 Asistente de Guiones con IA")
                gr.Markdown("Escribe una idea o tema para generar un guión optimizado con pausas y entonación:")
                with gr.Row():
                    ast_type = gr.Dropdown(choices=["🚀 Hook Viral para TikTok/Shorts", "🎙️ Podcast Conversacional", "🗣️ Sesión de Shadowing", "📖 Capítulo de Audiolibro", "🎬 Anuncio Comercial"], value="🚀 Hook Viral para TikTok/Shorts", label="Tipo de Guión")
                    ast_topic = gr.Textbox(label="Tema / Idea Principal", placeholder="Ej: La importancia del ritmo al hablar inglés", value="La importancia del ritmo al hablar inglés")
                btn_make_script = gr.Button("✨ Generar Estructura de Guión", variant="primary")
                ast_result = gr.Textbox(label="Guión Generado con Marcas de Expresión", lines=8)
                btn_copy_to_editor = gr.Button("📋 Enviar este Guión al Editor Principal", variant="secondary")

            # 7. Diccionario Fonético
            with gr.Column(visible=False, elem_classes=["card-box"]) as view_dictionary:
                gr.Markdown("### 📖 Diccionario Fonético & Reglas de Reemplazo")
                gr.Markdown("Define cómo deben pronunciarse términos especiales, acrónimos o marcas (Formato: `Palabra = Pronunciación`):")
                dict_rules_input = gr.Textbox(label="Reglas de Reemplazo (Una por línea)", lines=9, value=DEFAULT_PRONUNCIATION_RULES)
                btn_save_rules = gr.Button("💾 Guardar y Aplicar Reglas Fonéticas", variant="primary")
                dict_status = gr.Markdown("")

            # 8. Metadatos ID3 & Portada
            with gr.Column(visible=False, elem_classes=["card-box"]) as view_metadata:
                gr.Markdown("### 🏷️ Editor de Metadatos ID3 & Portada")
                gr.Markdown("Incrusta título, artista, álbum y portada en cualquier archivo de audio generado:")
                with gr.Row():
                    meta_audio = gr.File(label="Seleccionar Archivo MP3")
                    meta_cover = gr.Image(label="Imagen de Portada (JPG/PNG)", type="filepath")
                with gr.Row():
                    meta_title = gr.Textbox(label="Título de la Pista / Episodio", value="Episodio 1: Master Class")
                    meta_artist = gr.Textbox(label="Artista / Locutor", value="Text to Speech Pro")
                    meta_album = gr.Textbox(label="Nombre del Álbum / Podcast", value="Neural Studio Sessions")
                btn_apply_meta = gr.Button("🏷️ Incrustar Metadatos en MP3", variant="primary")
                meta_status = gr.Markdown("")
                meta_out = gr.File(label="Archivo MP3 Final con Metadatos")

            # 9. Proyectos Guardados
            with gr.Column(visible=False, elem_classes=["card-box"]) as view_projects:
                gr.Markdown("### 📂 Mis Proyectos Guardados")
                projects_list = gr.Dataframe(
                    headers=["Título / Resumen", "Voz Utilizada", "Archivo MP3", "Hora"],
                    datatype=["str", "str", "str", "str"],
                    interactive=False
                )
                btn_refresh_projects = gr.Button("🔄 Actualizar Tabla de Proyectos", variant="secondary")

            # 10. Catálogo de Voces HD
            with gr.Column(visible=False, elem_classes=["card-box"]) as view_voices:
                gr.Markdown("### 🎙️ Catálogo de Voces Neuronales HD")
                with gr.Row():
                    sample_voice = gr.Dropdown(choices=list(VOICES.keys()), value="🇺🇸 Jenny (Conversacional / Expresiva)", label="Voz Neuronal", scale=3)
                    btn_test_voice = gr.Button("🔊 Escuchar Muestra", variant="primary", scale=1)
                sample_status = gr.Markdown("")
                sample_audio = gr.Audio(label="Reproductor de Muestra", show_label=True, elem_classes=["custom-audio-player"])

            # 11. Centro de Descargas
            with gr.Column(visible=False, elem_classes=["card-box"]) as view_downloads:
                gr.Markdown("### 📥 Centro de Exportación y Descargas")
                dl_status = gr.Markdown("Archivos listos para su descarga:")
                dl_files = gr.File(label="Archivos Disponibles", file_count="multiple", interactive=False)
                with gr.Row():
                    btn_refresh_dl = gr.Button("🔄 Actualizar Archivos", variant="secondary")
                    btn_zip_all = gr.Button("📦 Descargar Todo en un solo ZIP", variant="primary")
                    btn_clean_dl = gr.Button("🗑️ Limpiar Archivos Temporales", variant="stop")
                dl_zip_file = gr.File(label="Pack ZIP Generado", visible=True)

            # 12. Preferencias & Calidad
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
    all_views = [view_editor, view_podcast, view_shadowing, view_book, view_video, view_assistant, view_dictionary, view_metadata, view_projects, view_voices, view_downloads, view_settings]
    
    def switch_tab(target_idx):
        return [gr.update(visible=(i == target_idx)) for i in range(len(all_views))]
    
    btn_nav_editor.click(fn=lambda: switch_tab(0), outputs=all_views)
    btn_nav_podcast.click(fn=lambda: switch_tab(1), outputs=all_views)
    btn_nav_shadowing.click(fn=lambda: switch_tab(2), outputs=all_views)
    btn_nav_book.click(fn=lambda: switch_tab(3), outputs=all_views)
    btn_nav_video.click(fn=lambda: switch_tab(4), outputs=all_views)
    btn_nav_assistant.click(fn=lambda: switch_tab(5), outputs=all_views)
    btn_nav_dictionary.click(fn=lambda: switch_tab(6), outputs=all_views)
    btn_nav_metadata.click(fn=lambda: switch_tab(7), outputs=all_views)
    btn_nav_projects.click(fn=lambda: switch_tab(8), outputs=all_views)
    btn_nav_voices.click(fn=lambda: switch_tab(9), outputs=all_views)
    btn_nav_downloads.click(fn=lambda: switch_tab(10), outputs=all_views)
    btn_nav_settings.click(fn=lambda: switch_tab(11), outputs=all_views)

    # EVENTO CERRAR SESIÓN
    btn_logout.click(fn=None, js="() => { window.location.href = '/logout'; }")

    # CARGA AUTOMÁTICA DEL ESTADO DE CUENTA
    demo.load(fn=render_account_status, inputs=None, outputs=account_status_view)

    # BOTONES TÁCTILES DE TAGS PARA EL EDITOR
    def append_tag(current_text, tag):
        return (current_text or "") + f" {tag} "
        
    btn_tag_p05.click(fn=lambda t: append_tag(t, "[Pausa 0.5s]"), inputs=main_text, outputs=main_text)
    btn_tag_p10.click(fn=lambda t: append_tag(t, "[Pausa 1.0s]"), inputs=main_text, outputs=main_text)
    btn_tag_p20.click(fn=lambda t: append_tag(t, "[Pausa 2.0s]"), inputs=main_text, outputs=main_text)
    btn_tag_alegre.click(fn=lambda t: append_tag(t, "[Alegre]"), inputs=main_text, outputs=main_text)
    btn_tag_susurro.click(fn=lambda t: append_tag(t, "[Susurro]"), inputs=main_text, outputs=main_text)
    btn_tag_triste.click(fn=lambda t: append_tag(t, "[Triste]"), inputs=main_text, outputs=main_text)
    btn_tag_epico.click(fn=lambda t: append_tag(t, "[Épico]"), inputs=main_text, outputs=main_text)
    btn_tag_normal.click(fn=lambda t: append_tag(t, "[Normal]"), inputs=main_text, outputs=main_text)

    # EVENTOS PRINCIPALES
    main_play_btn.click(
        fn=fn_main_editor,
        inputs=[main_text, main_voice, main_emotion, main_speed, pref_pitch, pref_volume, rules_state, project_history],
        outputs=[main_audio, project_history, main_status]
    )
    t1.click(fn=lambda: "The ancient lighthouse stood firm against the midnight storm, its radiant beam piercing the dense ocean fog to guide ships safely to harbor.", outputs=main_text)
    t2.click(fn=lambda: "Hey everyone, welcome back to the channel! [Pausa 0.8s] [Alegre] Today we are exploring the future of generative AI and neural voice synthesis.", outputs=main_text)
    t3.click(fn=lambda: "Bienvenidos a Text to Speech Pro. [Pausa 0.5s] Transforma cualquier texto en locuciones claras y fluidas con entonación humana natural.", outputs=main_text)

    btn_refresh_projects.click(fn=lambda h: h or [], inputs=[project_history], outputs=projects_list)

    btn_test_voice.click(
        fn=fn_test_voice_sample,
        inputs=sample_voice,
        outputs=[sample_audio, sample_status]
    )

    btn_gen_podcast.click(
        fn=fn_podcast_studio,
        inputs=[pod_text, pod_num_voices, pod_v1, pod_v2, pod_v3, pod_v4, pod_emotion, pod_spd, rules_state],
        outputs=[pod_audio, pod_status]
    )
    btn_pod_sample_en.click(
        fn=lambda: "Locutor 1: Welcome back to The Sound Wave podcast! I am Andrew, and today we are diving into connected speech.\nLocutor 2: Thanks for having me Andrew! In natural conversation, native speakers blend and link sounds smoothly.\nLocutor 3: Exactly, and shadowing is the best way to develop that muscle memory.\nLocutor 4: Stay tuned for our next episode!",
        outputs=pod_text
    )
    btn_pod_sample_es.click(
        fn=lambda: "Locutor 1: ¡Hola a todos y bienvenidos al podcast! Hoy exploramos los avances en síntesis de voz neuronal.\nLocutor 2: ¡Hola Andrew! Es increíble la naturalidad y calidez que se logra hoy en día sin equipos profesionales.\nLocutor 3: Totalmente de acuerdo, la tecnología abre puertas increíbles para creadores de contenido.\nLocutor 4: Gracias por escuchar este episodio especial.",
        outputs=pod_text
    )

    btn_gen_shadowing.click(
        fn=fn_shadowing_trainer,
        inputs=[shad_text, shad_voice, shad_speed, shad_mode, rules_state],
        outputs=[shad_audio, shad_zip, shad_status]
    )

    btn_gen_book.click(
        fn=fn_book_narration_zip,
        inputs=[book_text, book_voice, book_speed, rules_state],
        outputs=[book_audio, book_zip, book_status]
    )

    btn_gen_video.click(
        fn=fn_video_voiceover,
        inputs=[vid_text, vid_voice, vid_style, rules_state],
        outputs=[vid_audio, vid_srt, vid_vtt, vid_status]
    )

    btn_make_script.click(
        fn=fn_generate_script_assistant,
        inputs=[ast_type, ast_topic],
        outputs=ast_result
    )
    btn_copy_to_editor.click(
        fn=lambda s: (s, *switch_tab(0)),
        inputs=ast_result,
        outputs=[main_text, *all_views]
    )

    btn_save_rules.click(
        fn=lambda r: (r, "✅ Reglas fonéticas guardadas y sincronizadas con todos los módulos."),
        inputs=dict_rules_input,
        outputs=[rules_state, dict_status]
    )

    btn_apply_meta.click(
        fn=fn_embed_metadata,
        inputs=[meta_audio, meta_title, meta_artist, meta_album, meta_cover],
        outputs=[meta_out, meta_status]
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
