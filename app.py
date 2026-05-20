import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
from supabase import create_client, Client
from PIL import Image
import io
import tempfile
import os
import uuid
import re

# ============================================
# CONFIGURACION DE SUPABASE
# ============================================
def init_supabase():
    try:
        supabase_url = st.secrets["SUPABASE_URL"]
        supabase_key = st.secrets["SUPABASE_KEY"]
        supabase: Client = create_client(supabase_url, supabase_key)
        return supabase
    except Exception as e:
        st.error(f"Error de conexión con Supabase: {str(e)}")
        st.stop()

supabase = init_supabase()

# ============================================
# FUNCIÓN PARA DÓLAR - MANUAL
# ============================================
def get_dolar():
    try:
        response = supabase.table("configuracion").select("dolar").eq("id", 1).execute()
        if response.data and response.data[0].get("dolar"):
            return float(response.data[0]["dolar"])
        return 55.0
    except Exception:
        return 55.0

def actualizar_dolar_manual(nuevo_valor):
    try:
        supabase.table("configuracion").update({"dolar": nuevo_valor}).eq("id", 1).execute()
        return True
    except Exception:
        return False

# ============================================
# FUNCIÓN DE OPTIMIZACIÓN DE IMÁGENES
# ============================================
def optimizar_imagen(file, max_width=1024, quality=75):
    try:
        if file is None:
            return None
        
        img = Image.open(file)
        
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        if img.width > max_width:
            ratio = max_width / img.width
            nuevo_alto = int(img.height * ratio)
            img = img.resize((max_width, nuevo_alto), Image.Resampling.LANCZOS)
        
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        buffer.seek(0)
        
        class OptimizedFile:
            def __init__(self, buffer, original_name):
                self.buffer = buffer
                self.name = original_name.rsplit('.', 1)[0] + '.jpg'
                self.type = "image/jpeg"
                self.size = len(buffer.getvalue())
            
            def getvalue(self):
                return self.buffer.getvalue()
        
        return OptimizedFile(buffer, file.name)
    except Exception:
        return file

# ============================================
# FUNCIONES DE SUBIDA A STORAGE
# ============================================
def subir_imagen_storage(file, carpeta="imagenes"):
    try:
        if file is None:
            return None
        
        archivo_optimizado = optimizar_imagen(file)
        if archivo_optimizado is None:
            return None
        
        nombre_archivo = f"{carpeta}/{uuid.uuid4()}.jpg"
        
        supabase.storage.from_("imagenes").upload(
            nombre_archivo,
            archivo_optimizado.getvalue(),
            {"content-type": "image/jpeg"}
        )
        
        url = supabase.storage.from_("imagenes").get_public_url(nombre_archivo)
        return url
    except Exception:
        return None

def extraer_video_id(url_youtube):
    if "youtu.be" in url_youtube:
        return url_youtube.split("/")[-1].split("?")[0]
    elif "watch?v=" in url_youtube:
        return url_youtube.split("v=")[1].split("&")[0]
    return url_youtube

def mostrar_video_youtube(url_youtube):
    video_id = extraer_video_id(url_youtube)
    if video_id:
        st.video(f"https://www.youtube.com/embed/{video_id}")
    else:
        st.error("URL de YouTube no válida")

def mostrar_musica(url_audio):
    html = f"""
    <audio controls style="width: 100%;">
        <source src="{url_audio}" type="audio/mpeg">
    </audio>
    """
    st.markdown(html, unsafe_allow_html=True)

# ============================================
# DETECTAR DISPOSITIVO MOVIL
# ============================================
def is_mobile():
    try:
        user_agent = st.context.headers.get('User-Agent', '').lower()
        mobile_keywords = ['android', 'iphone', 'ipad', 'mobile']
        return any(k in user_agent for k in mobile_keywords)
    except:
        return False

es_movil = is_mobile()

# ============================================
# OCULTAR ELEMENTOS DE DESARROLLO
# ============================================
st.markdown("""
<style>
#MainMenu {visibility: hidden !important;}
footer {visibility: hidden !important;}
.stDeployButton {display: none !important;}
header {visibility: hidden !important;}
[data-testid="stToolbar"] {display: none !important;}
</style>
""", unsafe_allow_html=True)

# ============================================
# URL DE LA APP
# ============================================
APP_URL = "https://santateresaldia.streamlit.app/"

# ============================================
# CONFIGURACION DE PAGINA
# ============================================
st.set_page_config(
    page_title="Santa Teresa al Dia",
    page_icon="🇻🇪",
    layout="wide"
)

# ============================================
# ZONA HORARIA
# ============================================
CARACAS_TZ = pytz.timezone('America/Caracas')

def get_fecha_hora_venezuela():
    ahora_utc = datetime.now(pytz.UTC)
    ahora_caracas = ahora_utc.astimezone(CARACAS_TZ)
    return ahora_caracas

# ============================================
# FUNCIONES DE ACCESO A DATOS
# ============================================

# --- NOTICIAS ---
def add_noticia(titulo, categoria, contenido, imagen):
    try:
        ahora = get_fecha_hora_venezuela()
        img_url = subir_imagen_storage(imagen, "noticias") if imagen else None
        data = {
            "titulo": titulo,
            "categoria": categoria,
            "contenido": contenido,
            "imagen_url": img_url,
            "fecha": ahora.strftime("%d/%m/%Y"),
            "autor": "Admin"
        }
        supabase.table("noticias").insert(data).execute()
        return True
    except Exception:
        return False

def update_noticia(id_, titulo, categoria, contenido, imagen):
    try:
        img_url = None
        if imagen:
            img_url = subir_imagen_storage(imagen, "noticias")
        else:
            existing = supabase.table("noticias").select("imagen_url").eq("id", id_).execute()
            if existing.data:
                img_url = existing.data[0].get("imagen_url")
        
        data = {
            "titulo": titulo,
            "categoria": categoria,
            "contenido": contenido,
            "imagen_url": img_url
        }
        supabase.table("noticias").update(data).eq("id", id_).execute()
        return True
    except Exception:
        return False

def get_noticias(categoria=None):
    try:
        if categoria and categoria != "Todas":
            response = supabase.table("noticias").select("*").eq("categoria", categoria).order("id", desc=True).execute()
        else:
            response = supabase.table("noticias").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data)
    except Exception:
        return pd.DataFrame()

def delete_noticia(id_):
    try:
        supabase.table("noticias").delete().eq("id", id_).execute()
        return True
    except Exception:
        return False

# --- NEGOCIOS ---
def add_negocio(nombre, categoria, resena, direccion, telefono, horario, imagen):
    try:
        ahora = get_fecha_hora_venezuela()
        img_url = subir_imagen_storage(imagen, "negocios") if imagen else None
        data = {
            "nombre": nombre,
            "categoria": categoria,
            "resena": resena,
            "imagen_url": img_url,
            "direccion": direccion,
            "telefono": telefono,
            "horario": horario,
            "fecha": ahora.strftime("%d/%m/%Y")
        }
        supabase.table("negocios").insert(data).execute()
        return True
    except Exception:
        return False

def update_negocio(id_, nombre, categoria, resena, direccion, telefono, horario, imagen):
    try:
        img_url = None
        if imagen:
            img_url = subir_imagen_storage(imagen, "negocios")
        else:
            existing = supabase.table("negocios").select("imagen_url").eq("id", id_).execute()
            if existing.data:
                img_url = existing.data[0].get("imagen_url")
        
        data = {
            "nombre": nombre,
            "categoria": categoria,
            "resena": resena,
            "imagen_url": img_url,
            "direccion": direccion,
            "telefono": telefono,
            "horario": horario
        }
        supabase.table("negocios").update(data).eq("id", id_).execute()
        return True
    except Exception:
        return False

def get_negocios():
    try:
        response = supabase.table("negocios").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data)
    except Exception:
        return pd.DataFrame()

def delete_negocio(id_):
    try:
        supabase.table("negocios").delete().eq("id", id_).execute()
        return True
    except Exception:
        return False

# --- REFLEXIONES ---
def add_reflexion(titulo, contenido, versiculo):
    try:
        ahora = get_fecha_hora_venezuela()
        supabase.table("reflexiones").update({"activo": False}).execute()
        data = {
            "titulo": titulo,
            "contenido": contenido,
            "versiculo": versiculo,
            "autor": "Admin",
            "fecha": ahora.strftime("%d/%m/%Y"),
            "activo": True
        }
        supabase.table("reflexiones").insert(data).execute()
        return True
    except Exception:
        return False

def update_reflexion(id_, titulo, contenido, versiculo):
    try:
        data = {
            "titulo": titulo,
            "contenido": contenido,
            "versiculo": versiculo
        }
        supabase.table("reflexiones").update(data).eq("id", id_).execute()
        return True
    except Exception:
        return False

def get_reflexion_activa():
    try:
        response = supabase.table("reflexiones").select("*").eq("activo", True).limit(1).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception:
        return None

def get_reflexiones():
    try:
        response = supabase.table("reflexiones").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data)
    except Exception:
        return pd.DataFrame()

def delete_reflexion(id_):
    try:
        supabase.table("reflexiones").delete().eq("id", id_).execute()
        return True
    except Exception:
        return False

# --- CRONICAS ---
def add_cronica(titulo, contenido, lugar, estado):
    try:
        ahora = get_fecha_hora_venezuela()
        data = {
            "titulo": titulo,
            "contenido": contenido,
            "autor": "Admin",
            "fecha": ahora.strftime("%d/%m/%Y"),
            "lugar": lugar,
            "estado": estado
        }
        supabase.table("cronicas").insert(data).execute()
        return True
    except Exception:
        return False

def update_cronica(id_, titulo, contenido, lugar, estado):
    try:
        data = {
            "titulo": titulo,
            "contenido": contenido,
            "lugar": lugar,
            "estado": estado
        }
        supabase.table("cronicas").update(data).eq("id", id_).execute()
        return True
    except Exception:
        return False

def get_cronicas(estado=None):
    try:
        if estado and estado != "Todos":
            response = supabase.table("cronicas").select("*").eq("estado", estado).order("id", desc=True).execute()
        else:
            response = supabase.table("cronicas").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data)
    except Exception:
        return pd.DataFrame()

def delete_cronica(id_):
    try:
        supabase.table("cronicas").delete().eq("id", id_).execute()
        return True
    except Exception:
        return False

# --- VIDEOS ---
def add_video(titulo, url_youtube):
    try:
        ahora = get_fecha_hora_venezuela()
        data = {
            "titulo": titulo,
            "video_url": url_youtube,
            "formato": "youtube",
            "fecha": ahora.strftime("%d/%m/%Y")
        }
        supabase.table("videos").insert(data).execute()
        return True
    except Exception:
        return False

def update_video(id_, titulo, url_youtube):
    try:
        data = {
            "titulo": titulo,
            "video_url": url_youtube
        }
        supabase.table("videos").update(data).eq("id", id_).execute()
        return True
    except Exception:
        return False

def get_videos():
    try:
        response = supabase.table("videos").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data)
    except Exception:
        return pd.DataFrame()

def delete_video(id_):
    try:
        supabase.table("videos").delete().eq("id", id_).execute()
        return True
    except Exception:
        return False

# --- MUSICA ---
def add_musica(titulo, url_audio):
    try:
        ahora = get_fecha_hora_venezuela()
        data = {
            "titulo": titulo,
            "audio_url": url_audio,
            "formato": "externo",
            "fecha": ahora.strftime("%d/%m/%Y")
        }
        supabase.table("musicas").insert(data).execute()
        return True
    except Exception:
        return False

def update_musica(id_, titulo, url_audio):
    try:
        data = {
            "titulo": titulo,
            "audio_url": url_audio
        }
        supabase.table("musicas").update(data).eq("id", id_).execute()
        return True
    except Exception:
        return False

def get_musicas():
    try:
        response = supabase.table("musicas").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data)
    except Exception:
        return pd.DataFrame()

def delete_musica(id_):
    try:
        supabase.table("musicas").delete().eq("id", id_).execute()
        return True
    except Exception:
        return False

# --- DENUNCIAS ---
def add_denuncia(denunciante, titulo, descripcion, ubicacion):
    try:
        ahora = get_fecha_hora_venezuela()
        data = {
            "denunciante": denunciante or "Anonimo",
            "titulo": titulo,
            "descripcion": descripcion,
            "ubicacion": ubicacion,
            "fecha": ahora.strftime("%d/%m/%Y"),
            "estatus": "Pendiente"
        }
        supabase.table("denuncias").insert(data).execute()
        return True
    except Exception:
        return False

def get_denuncias():
    try:
        response = supabase.table("denuncias").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data)
    except Exception:
        return pd.DataFrame()

def update_denuncia_status(id_, status):
    try:
        supabase.table("denuncias").update({"estatus": status}).eq("id", id_).execute()
        return True
    except Exception:
        return False

def delete_denuncia(id_):
    try:
        supabase.table("denuncias").delete().eq("id", id_).execute()
        return True
    except Exception:
        return False

# --- OPINIONES ---
def add_opinion(usuario, comentario, calificacion):
    try:
        ahora = get_fecha_hora_venezuela()
        data = {
            "usuario": usuario,
            "comentario": comentario,
            "calificacion": calificacion,
            "fecha": ahora.strftime("%d/%m/%Y %H:%M"),
            "aprobada": False
        }
        supabase.table("opiniones").insert(data).execute()
        return True
    except Exception:
        return False

def get_opiniones(aprobadas=True):
    try:
        if aprobadas:
            response = supabase.table("opiniones").select("*").eq("aprobada", True).order("id", desc=True).execute()
        else:
            response = supabase.table("opiniones").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data)
    except Exception:
        return pd.DataFrame()

def approve_opinion(id_):
    try:
        supabase.table("opiniones").update({"aprobada": True}).eq("id", id_).execute()
        return True
    except Exception:
        return False

def delete_opinion(id_):
    try:
        supabase.table("opiniones").delete().eq("id", id_).execute()
        return True
    except Exception:
        return False

# --- PERSONAJES ---
def add_personaje(nombre, descripcion, imagen, fecha):
    try:
        img_url = subir_imagen_storage(imagen, "personajes") if imagen else None
        data = {
            "nombre": nombre,
            "descripcion": descripcion,
            "imagen_url": img_url,
            "fecha": fecha,
            "activo": True
        }
        existing = supabase.table("personajes").select("*").eq("fecha", fecha).eq("activo", True).execute()
        if existing.data:
            for p in existing.data:
                supabase.table("personajes").update({"activo": False}).eq("id", p["id"]).execute()
        supabase.table("personajes").insert(data).execute()
        return True
    except Exception:
        return False

def update_personaje(id_, nombre, descripcion, imagen, fecha):
    try:
        img_url = None
        if imagen:
            img_url = subir_imagen_storage(imagen, "personajes")
        else:
            existing = supabase.table("personajes").select("imagen_url").eq("id", id_).execute()
            if existing.data:
                img_url = existing.data[0].get("imagen_url")
        
        data = {
            "nombre": nombre,
            "descripcion": descripcion,
            "imagen_url": img_url,
            "fecha": fecha,
            "activo": True
        }
        supabase.table("personajes").update(data).eq("id", id_).execute()
        return True
    except Exception:
        return False

def get_personajes():
    try:
        response = supabase.table("personajes").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data)
    except Exception:
        return pd.DataFrame()

def delete_personaje(id_):
    try:
        supabase.table("personajes").delete().eq("id", id_).execute()
        return True
    except Exception:
        return False

# --- CONFIGURACION ---
def get_portada_url():
    return "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Flag_of_Venezuela_%28state%29.svg/1200px-Flag_of_Venezuela_%28state%29.svg.png"

def actualizar_visitas():
    try:
        response = supabase.table("visitas").select("conteo").eq("id", 1).execute()
        if response.data:
            conteo_actual = response.data[0]["conteo"]
            supabase.table("visitas").update({"conteo": conteo_actual + 1}).eq("id", 1).execute()
        else:
            supabase.table("visitas").insert({"id": 1, "conteo": 1531}).execute()
    except Exception:
        pass

def get_visitas():
    try:
        response = supabase.table("visitas").select("conteo").eq("id", 1).execute()
        if response.data:
            return int(response.data[0]["conteo"])
        return 1530
    except Exception:
        return 1530

def get_logo():
    try:
        response = supabase.table("configuracion").select("logo_url").eq("id", 1).execute()
        if response.data and response.data[0].get("logo_url"):
            return response.data[0]["logo_url"]
        return None
    except Exception:
        return None

def save_logo(url):
    try:
        supabase.table("configuracion").update({"logo_url": url}).eq("id", 1).execute()
        return True
    except Exception:
        return False

# ============================================
# INICIALIZAR
# ============================================
def inicializar_configuracion():
    try:
        response = supabase.table("configuracion").select("*").eq("id", 1).execute()
        if not response.data:
            supabase.table("configuracion").insert({"id": 1, "logo_url": None, "dolar": 55.0}).execute()
    except Exception:
        pass

inicializar_configuracion()

if 'visitante_contado' not in st.session_state:
    actualizar_visitas()
    st.session_state.visitante_contado = True

# ============================================
# ESTILOS
# ============================================
st.markdown("""
<style>
.stApp {
    background: linear-gradient(180deg, #FFD700 0%, #00247D 50%, #CF142B 100%);
}
.stApp::before {
    content: "★ ★ ★ ★ ★ ★ ★ ★";
    position: fixed;
    top: 50%;
    left: 0;
    right: 0;
    transform: translateY(-50%);
    text-align: center;
    font-size: 120px;
    color: rgba(255, 255, 255, 0.08);
    pointer-events: none;
    z-index: 0;
    letter-spacing: 30px;
    white-space: nowrap;
}
.block-container {
    background-color: rgba(0, 0, 0, 0.85) !important;
    border-radius: 20px !important;
    padding: 20px !important;
    z-index: 1 !important;
}
.main, .main p, .main span, .main div, .main label, .stMarkdown {
    color: #FFFFFF !important;
    font-weight: 500 !important;
}
.main h1, .main h2, .main h3, .main h4 {
    color: #FFD700 !important;
    font-weight: bold !important;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 8px !important;
    background-color: #1a1a1a !important;
    border-radius: 15px !important;
    padding: 8px !important;
}
.stTabs [data-baseweb="tab"] {
    background-color: #2a2a2a !important;
    border-radius: 12px !important;
    color: #FFD700 !important;
    font-weight: bold !important;
    padding: 10px 20px !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #FFD700, #CF142B) !important;
    color: white !important;
}
.streamlit-expanderHeader {
    background-color: #1a1a1a !important;
    border-radius: 10px !important;
    border-left: 4px solid #FFD700 !important;
    color: #FFD700 !important;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #87CEEB 0%, #4682B4 100%) !important;
    border-right: 3px solid #FFD700 !important;
}
[data-testid="stSidebar"] * {
    color: #1a1a2e !important;
}
input, textarea, .stSelectbox > div > div {
    background-color: #f0f0f0 !important;
    color: #000000 !important;
    border-radius: 12px !important;
    border: 2px solid #FFD700 !important;
}
.stButton > button {
    background: linear-gradient(135deg, #FFD700, #CF142B) !important;
    color: white !important;
    border: none !important;
    font-weight: bold !important;
    border-radius: 25px !important;
}
.stats-panel {
    background: rgba(0,0,0,0.8) !important;
    padding: 15px !important;
    border-radius: 20px !important;
    border: 2px solid #FFD700 !important;
    text-align: center !important;
    margin-bottom: 20px !important;
}
.bronze-footer {
    background: linear-gradient(145deg, #8c6a31, #5d431a) !important;
    border: 5px solid #d4af37 !important;
    padding: 35px 25px !important;
    border-radius: 20px !important;
    text-align: center !important;
    margin-top: 50px !important;
}
.bronze-footer p {
    color: #ffd700 !important;
}
</style>
""", unsafe_allow_html=True)

# ============================================
# ENCABEZADO
# ============================================
portada_url = get_portada_url()

st.markdown(f"""
<div style="text-align: center; margin-bottom: 20px;">
    <div style="background: linear-gradient(rgba(0,0,0,0.55), rgba(0,0,0,0.55)), 
                url('{portada_url}');
                background-size: cover;
                background-position: center;
                border-radius: 20px;
                padding: 80px 20px;
                border: 3px solid #FFD700;">
        <h1 style="color: #FFD700; text-shadow: 3px 3px 8px black; font-size: 2.5em;">Santa Teresa al Dia</h1>
        <p style="color: #FFFFFF; text-shadow: 2px 2px 5px black; font-size: 1.3em;">Informacion, Cultura y Fe de nuestro pueblo</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================
# FECHA Y HORA
# ============================================
ahora = get_fecha_hora_venezuela()
dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

visitas = get_visitas()
dolar = get_dolar()

# ============================================
# LOGO
# ============================================
logo = get_logo()
if logo:
    st.markdown(f'<div style="text-align: center;"><img src="{logo}" style="max-width: 200px;"></div>', unsafe_allow_html=True)

# ============================================
# BOTONES COMPARTIR
# ============================================
st.markdown(f"""
<div style="display: flex; justify-content: center; gap: 15px; flex-wrap: wrap; margin: 15px 0;">
    <a href="https://api.whatsapp.com/send?text=Santa Teresa al Dia - {APP_URL}" target="_blank" style="display: inline-block; padding: 10px 25px; border-radius: 25px; text-decoration: none; font-weight: bold; color: white; background: #25D366;">📱 WhatsApp</a>
    <a href="https://www.facebook.com/sharer/sharer.php?u={APP_URL}" target="_blank" style="display: inline-block; padding: 10px 25px; border-radius: 25px; text-decoration: none; font-weight: bold; color: white; background: #1877F2;">📘 Facebook</a>
    <a href="https://www.instagram.com/" target="_blank" style="display: inline-block; padding: 10px 25px; border-radius: 25px; text-decoration: none; font-weight: bold; color: white; background: linear-gradient(45deg, #f09433, #d62976);">📸 Instagram</a>
    <button onclick="copyToClipboard('{APP_URL}')" style="display: inline-block; padding: 10px 25px; border-radius: 25px; text-decoration: none; font-weight: bold; color: white; background: #3498db; border: none; cursor: pointer;">📋 Copiar</button>
</div>
<script>
function copyToClipboard(text) {{
    navigator.clipboard.writeText(text);
    alert("Enlace copiado!");
}}
</script>
""", unsafe_allow_html=True)

st.markdown("---")

# ============================================
# PANEL SUPERIOR (CON DÓLAR MODIFICABLE)
# ============================================
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.markdown(f"""
    <div class="stats-panel">
        <span style="color:#FFD700;">⭐ {dias[ahora.weekday()]}, {ahora.day} de {meses[ahora.month-1]} de {ahora.year} ⭐</span><br>
        <span style="color:white; font-size:1.5em;">{ahora.strftime("%I:%M %p")}</span><br>
        <span style="color:#FFD700;">👥 Visitantes: {visitas:,}</span>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="stats-panel">
        <span style="color:#FFD700;">💵 Dólar BCV</span><br>
        <span style="color:white; font-size:1.5em;">{dolar:.2f} Bs</span>
    </div>
    """, unsafe_allow_html=True)

with col3:
    with st.expander("✏️ Cambiar Dólar"):
        nuevo_dolar = st.number_input("Nuevo valor:", value=float(dolar), step=0.01, format="%.2f", key="dolar_rapido")
        if st.button("💾 Actualizar", key="btn_dolar_rapido"):
            if actualizar_dolar_manual(nuevo_dolar):
                st.success("✅ Dólar actualizado")
                st.rerun()
            else:
                st.error("❌ Error")

# ============================================
# SIDEBAR ADMIN
# ============================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Flag_of_Venezuela_%28state%29.svg/1200px-Flag_of_Venezuela_%28state%29.svg.png", width=150)
    st.markdown("---")
    
    st.markdown("### 🔐 Administración")
    clave = st.text_input("Clave de acceso:", type="password", key="admin_pass")
    
    es_admin = False
    if clave == "Juan*316*" or clave == "1966":
        es_admin = True
        st.success("✅ Acceso concedido")
    elif clave:
        st.error("❌ Clave incorrecta")
    
    if es_admin:
        st.markdown("---")
        st.markdown("### 📋 Panel de Control")
        admin_opt = st.radio("Seleccionar módulo:", [
            "📰 Noticias", "🏪 Negocios", "💭 Reflexiones", "📜 Crónicas",
            "🎬 Videos", "🎵 Música", "⚠️ Denuncias", "💬 Opiniones", 
            "👥 Personajes", "⚙️ Configuración"
        ])
        st.session_state.admin_opt = admin_opt
        st.session_state.es_admin = True
    else:
        st.session_state.es_admin = False

# ============================================
# MENU PRINCIPAL (TABS)
# ============================================
menu_tabs = st.tabs(["🏠 Portada", "📰 Noticias", "📍 Donde ir - Donde comprar", "💭 Reflexiones", "📜 Crónicas", "🎬 Multimedia", "⚠️ Denuncias", "💬 Opiniones", "👥 Personajes que hicieron historia", "📅 Efemérides Médicas"])

# --- TAB 0: PORTADA ---
with menu_tabs[0]:
    st.title("Santa Teresa al Dia")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📰 Últimas Noticias")
        noticias = get_noticias()
        if not noticias.empty:
            for _, n in noticias.head(5).iterrows():
                with st.expander(f"{n['titulo']} - {n['categoria']} ({n['fecha']})"):
                    if n.get('imagen_url') and n['imagen_url']:
                        st.image(n['imagen_url'], width=300)
                    st.write(n['contenido'])
        else:
            st.info("No hay noticias")
    
    with col2:
        st.markdown("### ✝️ Reflexión del Día")
        ref = get_reflexion_activa()
        if ref:
            with st.expander(f"{ref['titulo']}", expanded=True):
                st.write(ref['contenido'])
                st.caption(f"📖 {ref['versiculo']}")
        else:
            st.info("No hay reflexión activa")
    
    # Sección "⭐ Recomendados" ELIMINADA para evitar errores

# --- TAB 1: NOTICIAS ---
with menu_tabs[1]:
    st.title("📰 Noticias")
    tab_nac, tab_inter, tab_dep = st.tabs(["🇻🇪 Nacionales", "🌎 Internacionales", "⚽ Deportes"])
    
    with tab_nac:
        noticias_nac = get_noticias(categoria="Nacional")
        if not noticias_nac.empty:
            for _, n in noticias_nac.iterrows():
                with st.expander(f"{n['titulo']} - {n['fecha']}"):
                    if n.get('imagen_url') and n['imagen_url']:
                        st.image(n['imagen_url'], width=300)
                    st.write(n['contenido'])
        else
