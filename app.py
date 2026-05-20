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
APP_URL = "https://santa-teresa-digital.streamlit.app/"

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
# ESTILOS - VERSIÓN SIMPLE (SIN ERRORES)
# ============================================
st.markdown("""
<style>
.stApp {
    background: linear-gradient(180deg, #FFD700 0%, #00247D 50%, #CF142B 100%);
}
.block-container {
    background-color: rgba(0, 0, 0, 0.85) !important;
    border-radius: 20px !important;
    padding: 20px !important;
}
.main, .main p, .main span, .main div, .main label, .stMarkdown {
    color: #FFFFFF !important;
}
.main h1, .main h2, .main h3, .main h4 {
    color: #FFD700 !important;
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
# BOTONES COMPARTIR (CON INSTAGRAM, WHATSAPP, FACEBOOK Y COPIAR)
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
# PANEL SUPERIOR
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
        else:
            st.info("No hay noticias Nacionales")
    
    with tab_inter:
        noticias_inter = get_noticias(categoria="Internacional")
        if not noticias_inter.empty:
            for _, n in noticias_inter.iterrows():
                with st.expander(f"{n['titulo']} - {n['fecha']}"):
                    if n.get('imagen_url') and n['imagen_url']:
                        st.image(n['imagen_url'], width=300)
                    st.write(n['contenido'])
        else:
            st.info("No hay noticias Internacionales")
    
    with tab_dep:
        noticias_dep = get_noticias(categoria="Deportes")
        if not noticias_dep.empty:
            for _, n in noticias_dep.iterrows():
                with st.expander(f"{n['titulo']} - {n['fecha']}"):
                    if n.get('imagen_url') and n['imagen_url']:
                        st.image(n['imagen_url'], width=300)
                    st.write(n['contenido'])
        else:
            st.info("No hay noticias de Deportes")

# --- TAB 2: DONDE IR - DONDE COMPRAR ---
with menu_tabs[2]:
    st.title("📍 Donde ir - Donde comprar")
    negocios = get_negocios()
    if not negocios.empty:
        for _, n in negocios.iterrows():
            col_a, col_b = st.columns([1, 2])
            with col_a:
                if n.get('imagen_url') and n['imagen_url']:
                    st.image(n['imagen_url'], use_container_width=True)
                else:
                    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Flag_of_Venezuela_%28state%29.svg/1200px-Flag_of_Venezuela_%28state%29.svg.png", use_container_width=True)
            with col_b:
                st.markdown(f"### {n['nombre']}")
                st.caption(n['categoria'])
                st.write(n['resena'])
                if n.get('direccion'):
                    st.write(f"📍 **Dirección:** {n['direccion']}")
                if n.get('telefono'):
                    st.write(f"📞 **Teléfono:** {n['telefono']}")
                if n.get('horario'):
                    st.write(f"⏰ **Horario:** {n['horario']}")
            st.markdown("---")
    else:
        st.info("No hay negocios agregados")

# --- TAB 3: REFLEXIONES ---
with menu_tabs[3]:
    st.title("💭 Reflexiones")
    ref = get_reflexion_activa()
    if ref:
        with st.expander(f"✨ ACTUAL: {ref['titulo']}", expanded=True):
            st.write(ref['contenido'])
            st.caption(f"📖 {ref['versiculo']}")
            st.caption(f"📅 {ref['fecha']}")
    else:
        st.info("No hay reflexión activa")
    
    st.markdown("---")
    st.markdown("### 📜 Reflexiones Anteriores")
    reflexiones = get_reflexiones()
    if not reflexiones.empty:
        for _, r in reflexiones.iterrows():
            if ref is None or r['id'] != ref['id']:
                with st.expander(f"{r['titulo']} - {r['fecha']}"):
                    st.write(r['contenido'])
                    if r.get('versiculo'):
                        st.caption(f"📖 {r['versiculo']}")
    else:
        st.info("No hay reflexiones anteriores")

# --- TAB 4: CRONICAS ---
with menu_tabs[4]:
    st.title("📜 Crónicas")
    estados = ["Todos", "Miranda", "Carabobo", "Distrito Capital", "Zulia", "Lara", "Aragua", "Bolivar", "Anzoategui", "Merida", "Tachira", "Nueva Esparta", "Sucre", "Falcon", "Barinas", "Portuguesa", "Guarico", "Cojedes", "Trujillo", "Yaracuy", "Apure", "Amazonas", "Delta Amacuro", "Vargas"]
    estado_filtro = st.selectbox("Filtrar por estado:", estados)
    cronicas = get_cronicas(estado_filtro if estado_filtro != "Todos" else None)
    if not cronicas.empty:
        for _, c in cronicas.iterrows():
            with st.expander(f"📖 {c['titulo']} - {c['lugar']}, {c['estado']}"):
                st.write(c['contenido'])
                st.caption(f"📅 {c['fecha']}")
    else:
        st.info("No hay crónicas disponibles")

# --- TAB 5: MULTIMEDIA ---
with menu_tabs[5]:
    st.title("🎬 Multimedia")
    tab_vid, tab_mus, tab_rad = st.tabs(["🎥 Videos", "🎵 Música", "📻 Radio"])
    
    with tab_vid:
        videos = get_videos()
        if not videos.empty:
            for _, v in videos.iterrows():
                with st.expander(f"🎬 {v['titulo']}"):
                    mostrar_video_youtube(v['video_url'])
                    st.caption(f"Subido: {v['fecha']}")
        else:
            st.info("No hay videos disponibles")
    
    with tab_mus:
        musicas = get_musicas()
        if not musicas.empty:
            for _, m in musicas.iterrows():
                with st.expander(f"🎵 {m['titulo']}"):
                    mostrar_musica(m['audio_url'])
                    st.caption(f"Agregado: {m['fecha']}")
        else:
            st.info("No hay música disponible")
    
    with tab_rad:
        st.markdown("### 📻 Radio Online")
        st.audio("https://streaming.radiosenlinea.net/9090/stream")

# --- TAB 6: DENUNCIAS ---
with menu_tabs[6]:
    st.title("⚠️ Denuncias Ciudadanas")
    tab_den, tab_ver = st.tabs(["📝 Hacer Denuncia", "👁️ Ver Denuncias"])
    
    with tab_den:
        with st.form("fd"):
            nombre = st.text_input("Nombre (opcional)")
            titulo = st.text_input("Título *")
            desc = st.text_area("Descripción *")
            ubic = st.text_input("Ubicación")
            if st.form_submit_button("Enviar Denuncia"):
                if titulo and desc:
                    add_denuncia(nombre, titulo, desc, ubic)
                    st.success("✅ Denuncia enviada correctamente")
                    st.balloons()
                else:
                    st.error("❌ Título y descripción son obligatorios")
    
    with tab_ver:
        denuncias = get_denuncias()
        if not denuncias.empty:
            for _, d in denuncias.iterrows():
                st.markdown(f"**📌 {d['titulo']}** - `{d['estatus']}`")
                st.caption(f"📍 {d['ubicacion'] if d['ubicacion'] else 'No especificada'}")
                with st.expander("Ver detalles"):
                    st.write(d['descripcion'])
                    st.caption(f"📅 {d['fecha']}")
                st.divider()
        else:
            st.info("No hay denuncias registradas")

# --- TAB 7: OPINIONES ---
with menu_tabs[7]:
    st.title("💬 Opiniones")
    tab_op, tab_ver_op = st.tabs(["✍️ Dar Opinión", "👁️ Ver Opiniones"])
    
    with tab_op:
        with st.form("fo"):
            usuario = st.text_input("Nombre *")
            comentario = st.text_area("Comentario *")
            estrellas = st.slider("Calificación", 1, 5, 5)
            if st.form_submit_button("Enviar Opinión"):
                if usuario and comentario:
                    add_opinion(usuario, comentario, estrellas)
                    st.success("✅ Opinión enviada, será revisada por un administrador")
                    st.balloons()
                else:
                    st.error("❌ Nombre y comentario son obligatorios")
    
    with tab_ver_op:
        opiniones = get_opiniones(aprobadas=True)
        if not opiniones.empty:
            for _, op in opiniones.iterrows():
                stars = "⭐" * int(op['calificacion']) + "☆" * (5 - int(op['calificacion']))
                st.markdown(f"**👤 {op['usuario']}** {stars}")
                st.write(f"\"{op['comentario']}\"")
                st.caption(f"📅 {op['fecha']}")
                st.divider()
        else:
            st.info("No hay opiniones aprobadas")

# --- TAB 8: PERSONAJES QUE HICIERON HISTORIA ---
with menu_tabs[8]:
    st.title("👥 Personajes que hicieron historia")
    
    # Formulario para CREAR
    with st.expander("➕ Agregar nuevo personaje", expanded=True):
        with st.form("fpersonaje_publico"):
            nombre = st.text_input("Nombre del personaje")
            descripcion = st.text_area("Biografía")
            imagen = st.file_uploader("Imagen", type=["jpg", "png", "jpeg"])
            if st.form_submit_button("💾 Guardar Personaje"):
                if nombre and descripcion:
                    add_personaje(nombre, descripcion, imagen, datetime.now().strftime("%d/%m/%Y"))
                    st.success("✅ Personaje guardado")
                    st.rerun()
                else:
                    st.error("❌ Nombre y biografía obligatorios")
    
    st.markdown("---")
    st.markdown("### 📋 Personajes Registrados")
    
    # Lista de personajes
    personajes = get_personajes()
    if not personajes.empty:
        for _, p in personajes.iterrows():
            with st.expander(f"👤 {p['nombre']} - {p['fecha']}"):
                # Validación para evitar error
                if p.get('imagen_url') and p['imagen_url']:
                    st.image(p['imagen_url'], width=200)
                else:
                    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Flag_of_Venezuela_%28state%29.svg/1200px-Flag_of_Venezuela_%28state%29.svg.png", width=200)
                
                st.write(f"**Biografía:** {p['descripcion']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"✏️ Modificar", key=f"edit_pub_{p['id']}"):
                        st.session_state.edit_personaje_publico = p.to_dict()
                        st.rerun()
                with col2:
                    if st.button(f"🗑️ Eliminar", key=f"del_pub_{p['id']}"):
                        delete_personaje(p['id'])
                        st.success(f"✅ {p['nombre']} eliminado")
                        st.rerun()
    else:
        st.info("No hay personajes registrados")
    
    # Formulario para MODIFICAR
    if 'edit_personaje_publico' in st.session_state:
        p = st.session_state.edit_personaje_publico
        st.markdown("---")
        st.subheader(f"✏️ Modificando: {p['nombre']}")
        
        with st.form("edit_personaje_publico_form"):
            nuevo_nombre = st.text_input("Nombre", value=p['nombre'])
            nueva_descripcion = st.text_area("Biografía", value=p['descripcion'])
            nueva_imagen = st.file_uploader("Nueva imagen (opcional)", type=["jpg", "png", "jpeg"])
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("💾 Guardar cambios"):
                    if update_personaje(p['id'], nuevo_nombre, nueva_descripcion, nueva_imagen, p['fecha']):
                        st.success("✅ Personaje actualizado")
                        del st.session_state.edit_personaje_publico
                        st.rerun()
            with col2:
                if st.form_submit_button("❌ Cancelar"):
                    del st.session_state.edit_personaje_publico
                    st.rerun()

# --- TAB 9: EFEMÉRIDES MÉDICAS ---
with menu_tabs[9]:
    st.title("📅 Efemérides Médicas")
    fecha_actual_str = f"{ahora.day} de {meses[ahora.month-1]}"
    st.markdown(f"### 📌 {dias[ahora.weekday()]}, {fecha_actual_str} de {ahora.year}")
    
    col_ven, col_mundo = st.columns(2)
    with col_ven:
        st.markdown("#### 🇻🇪 Venezuela")
        efemerides_venezuela = {
            "24 de Junio": "Día del Médico Venezolano",
            "3 de Diciembre": "Día del Odontólogo Venezolano",
            "13 de Octubre": "Día del Trabajador de la Salud",
            "10 de Diciembre": "Día de la Enfermera Venezolana"
        }
        hoy_ven = None
        for fecha, texto in efemerides_venezuela.items():
            if fecha == fecha_actual_str:
                hoy_ven = texto
                break
        if hoy_ven:
            st.success(f"🎉 **¡HOY!** {fecha_actual_str}: {hoy_ven}")
        else:
            st.info(f"📌 Para hoy ({fecha_actual_str}) no hay efeméride médica registrada")
        st.markdown("**📅 Otras efemérides:**")
        for fecha, texto in efemerides_venezuela.items():
            st.markdown(f"- **{fecha}:** {texto}")
    
    with col_mundo:
        st.markdown("#### 🌎 Mundo")
        efemerides_mundo = {
            "12 de Mayo": "Día Internacional de la Enfermería",
            "7 de Abril": "Día Mundial de la Salud",
            "31 de Mayo": "Día Mundial sin Tabaco",
            "14 de Junio": "Día Mundial del Donante de Sangre",
            "10 de Octubre": "Día Mundial de la Salud Mental",
            "14 de Noviembre": "Día Mundial de la Diabetes"
        }
        hoy_mundo = None
        for fecha, texto in efemerides_mundo.items():
            if fecha == fecha_actual_str:
                hoy_mundo = texto
                break
        if hoy_mundo:
            st.success(f"🎉 **¡HOY!** {fecha_actual_str}: {hoy_mundo}")
        else:
            st.info(f"📌 Para hoy ({fecha_actual_str}) no hay efeméride médica mundial")
        st.markdown("**📅 Otras efemérides:**")
        for fecha, texto in efemerides_mundo.items():
            st.markdown(f"- **{fecha}:** {texto}")

# ============================================
# PANEL ADMIN - CONTENIDO
# ============================================
if st.session_state.get('es_admin', False):
    admin_opt = st.session_state.get('admin_opt', "📰 Noticias")
    st.title("🔧 Panel de Administración")
    
    # --- NOTICIAS ---
    if "📰 Noticias" in admin_opt:
        st.subheader("📰 Gestionar Noticias")
        
        with st.expander("➕ Crear nueva noticia", expanded=True):
            with st.form("fn"):
                titulo = st.text_input("Título")
                categoria = st.selectbox("Categoría", ["Nacional", "Internacional", "Deportes", "Reportajes"])
                contenido = st.text_area("Contenido")
                imagen = st.file_uploader("Imagen", type=["jpg", "png", "jpeg"])
                if st.form_submit_button("📤 Publicar Noticia"):
                    if titulo and contenido:
                        add_noticia(titulo, categoria, contenido, imagen)
                        st.success("✅ Noticia publicada")
                        st.rerun()
                    else:
                        st.error("❌ Título y contenido obligatorios")
        
        st.markdown("---")
        st.markdown("### 📋 Noticias existentes")
        
        for _, n in get_noticias().iterrows():
            with st.expander(f"📰 {n['titulo']} - {n['categoria']} ({n['fecha']})"):
                if n.get('imagen_url') and n['imagen_url']:
                    st.image(n['imagen_url'], width=300)
                st.write(f"**Contenido:** {n['contenido']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"✏️ Modificar", key=f"edit_noti_{n['id']}"):
                        st.session_state.edit_noticia = n.to_dict()
                        st.rerun()
                with col2:
                    if st.button(f"🗑️ Eliminar", key=f"del_noti_{n['id']}"):
                        delete_noticia(n['id'])
                        st.success("✅ Noticia eliminada")
                        st.rerun()
        
        if 'edit_noticia' in st.session_state:
            n = st.session_state.edit_noticia
            st.markdown("---")
            st.subheader(f"✏️ Modificando: {n['titulo']}")
            with st.form("edit_noticia_form"):
                nuevo_titulo = st.text_input("Título", value=n['titulo'])
                nueva_categoria = st.selectbox("Categoría", ["Nacional", "Internacional", "Deportes", "Reportajes"], index=["Nacional", "Internacional", "Deportes", "Reportajes"].index(n['categoria']))
                nuevo_contenido = st.text_area("Contenido", value=n['contenido'])
                nueva_imagen = st.file_uploader("Nueva imagen (opcional)", type=["jpg", "png", "jpeg"])
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Guardar cambios"):
                        if update_noticia(n['id'], nuevo_titulo, nueva_categoria, nuevo_contenido, nueva_imagen):
                            st.success("✅ Noticia actualizada")
                            del st.session_state.edit_noticia
                            st.rerun()
                with col2:
                    if st.form_submit_button("❌ Cancelar"):
                        del st.session_state.edit_noticia
                        st.rerun()
    
    # --- NEGOCIOS ---
    elif "🏪 Negocios" in admin_opt:
        st.subheader("🏪 Gestionar Negocios")
        
        with st.expander("➕ Crear nuevo negocio", expanded=True):
            with st.form("fneg"):
                nombre = st.text_input("Nombre")
                categoria = st.text_input("Categoría")
                resena = st.text_area("Reseña")
                direccion = st.text_input("Dirección")
                telefono = st.text_input("Teléfono")
                horario = st.text_input("Horario")
                imagen = st.file_uploader("Foto", type=["jpg", "png", "jpeg"])
                if st.form_submit_button("➕ Agregar"):
                    if nombre and resena:
                        add_negocio(nombre, categoria, resena, direccion, telefono, horario, imagen)
                        st.success("✅ Negocio agregado")
                        st.rerun()
        
        st.markdown("---")
        st.markdown("### 📋 Negocios existentes")
        
        for _, n in get_negocios().iterrows():
            with st.expander(f"🏪 {n['nombre']} - {n['categoria']}"):
                if n.get('imagen_url') and n['imagen_url']:
                    st.image(n['imagen_url'], width=200)
                st.write(f"**Reseña:** {n['resena']}")
                if n.get('direccion'):
                    st.write(f"📍 {n['direccion']}")
                if n.get('telefono'):
                    st.write(f"📞 {n['telefono']}")
                if n.get('horario'):
                    st.write(f"⏰ {n['horario']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"✏️ Modificar", key=f"edit_neg_{n['id']}"):
                        st.session_state.edit_negocio = n.to_dict()
                        st.rerun()
                with col2:
                    if st.button(f"🗑️ Eliminar", key=f"del_neg_{n['id']}"):
                        delete_negocio(n['id'])
                        st.success("✅ Negocio eliminado")
                        st.rerun()
        
        if 'edit_negocio' in st.session_state:
            n = st.session_state.edit_negocio
            st.markdown("---")
            st.subheader(f"✏️ Modificando: {n['nombre']}")
            with st.form("edit_negocio_form"):
                nuevo_nombre = st.text_input("Nombre", value=n['nombre'])
                nueva_categoria = st.text_input("Categoría", value=n['categoria'])
                nueva_resena = st.text_area("Reseña", value=n['resena'])
                nueva_direccion = st.text_input("Dirección", value=n.get('direccion', ''))
                nuevo_telefono = st.text_input("Teléfono", value=n.get('telefono', ''))
                nuevo_horario = st.text_input("Horario", value=n.get('horario', ''))
                nueva_imagen = st.file_uploader("Nueva imagen (opcional)", type=["jpg", "png", "jpeg"])
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Guardar cambios"):
                        if update_negocio(n['id'], nuevo_nombre, nueva_categoria, nueva_resena, nueva_direccion, nuevo_telefono, nuevo_horario, nueva_imagen):
                            st.success("✅ Negocio actualizado")
                            del st.session_state.edit_negocio
                            st.rerun()
                with col2:
                    if st.form_submit_button("❌ Cancelar"):
                        del st.session_state.edit_negocio
                        st.rerun()
    
    # --- REFLEXIONES ---
    elif "💭 Reflexiones" in admin_opt:
        st.subheader("💭 Gestionar Reflexiones")
        
        with st.expander("➕ Crear nueva reflexión", expanded=True):
            with st.form("fref"):
                titulo = st.text_input("Título")
                versiculo = st.text_input("Versículo")
                contenido = st.text_area("Contenido")
                if st.form_submit_button("💾 Guardar como activa"):
                    if titulo and contenido:
                        add_reflexion(titulo, contenido, versiculo)
                        st.success("✅ Reflexión guardada como activa")
                        st.rerun()
        
        st.markdown("---")
        st.markdown("### 📋 Reflexiones existentes")
        
        for _, r in get_reflexiones().iterrows():
            with st.expander(f"📖 {r['titulo']} - {r['fecha']}"):
                st.write(r['contenido'])
                if r.get('versiculo'):
                    st.caption(f"📖 {r['versiculo']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"✏️ Modificar", key=f"edit_ref_{r['id']}"):
                        st.session_state.edit_reflexion = r.to_dict()
                        st.rerun()
                with col2:
                    if st.button(f"🗑️ Eliminar", key=f"del_ref_{r['id']}"):
                        delete_reflexion(r['id'])
                        st.success("✅ Reflexión eliminada")
                        st.rerun()
        
        if 'edit_reflexion' in st.session_state:
            r = st.session_state.edit_reflexion
            st.markdown("---")
            st.subheader(f"✏️ Modificando: {r['titulo']}")
            with st.form("edit_reflexion_form"):
                nuevo_titulo = st.text_input("Título", value=r['titulo'])
                nuevo_versiculo = st.text_input("Versículo", value=r.get('versiculo', ''))
                nuevo_contenido = st.text_area("Contenido", value=r['contenido'])
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Guardar cambios"):
                        if update_reflexion(r['id'], nuevo_titulo, nuevo_contenido, nuevo_versiculo):
                            st.success("✅ Reflexión actualizada")
                            del st.session_state.edit_reflexion
                            st.rerun()
                with col2:
                    if st.form_submit_button("❌ Cancelar"):
                        del st.session_state.edit_reflexion
                        st.rerun()
    
    # --- CRONICAS ---
    elif "📜 Crónicas" in admin_opt:
        st.subheader("📜 Gestionar Crónicas")
        
        with st.expander("➕ Crear nueva crónica", expanded=True):
            with st.form("fcro"):
                titulo = st.text_input("Título")
                lugar = st.text_input("Lugar")
                estado = st.selectbox("Estado", ["Miranda", "Carabobo", "Distrito Capital", "Zulia", "Lara", "Aragua", "Bolivar", "Anzoategui", "Merida", "Tachira", "Nueva Esparta", "Sucre", "Falcon", "Barinas", "Portuguesa", "Guarico", "Cojedes", "Trujillo", "Yaracuy", "Apure", "Amazonas", "Delta Amacuro", "Vargas"])
                contenido = st.text_area("Contenido")
                if st.form_submit_button("💾 Guardar"):
                    if titulo and contenido:
                        add_cronica(titulo, contenido, lugar, estado)
                        st.success("✅ Crónica guardada")
                        st.rerun()
        
        st.markdown("---")
        st.markdown("### 📋 Crónicas existentes")
        
        for _, c in get_cronicas().iterrows():
            with st.expander(f"📜 {c['titulo']} - {c['lugar']}, {c['estado']}"):
                st.write(c['contenido'])
                st.caption(f"📅 {c['fecha']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"✏️ Modificar", key=f"edit_cron_{c['id']}"):
                        st.session_state.edit_cronica = c.to_dict()
                        st.rerun()
                with col2:
                    if st.button(f"🗑️ Eliminar", key=f"del_cron_{c['id']}"):
                        delete_cronica(c['id'])
                        st.success("✅ Crónica eliminada")
                        st.rerun()
        
        if 'edit_cronica' in st.session_state:
            c = st.session_state.edit_cronica
            st.markdown("---")
            st.subheader(f"✏️ Modificando: {c['titulo']}")
            with st.form("edit_cronica_form"):
                nuevo_titulo = st.text_input("Título", value=c['titulo'])
                nuevo_lugar = st.text_input("Lugar", value=c['lugar'])
                nuevo_estado = st.selectbox("Estado", ["Miranda", "Carabobo", "Distrito Capital", "Zulia", "Lara", "Aragua", "Bolivar", "Anzoategui", "Merida", "Tachira", "Nueva Esparta", "Sucre", "Falcon", "Barinas", "Portuguesa", "Guarico", "Cojedes", "Trujillo", "Yaracuy", "Apure", "Amazonas", "Delta Amacuro", "Vargas"], index=["Miranda", "Carabobo", "Distrito Capital", "Zulia", "Lara", "Aragua", "Bolivar", "Anzoategui", "Merida", "Tachira", "Nueva Esparta", "Sucre", "Falcon", "Barinas", "Portuguesa", "Guarico", "Cojedes", "Trujillo", "Yaracuy", "Apure", "Amazonas", "Delta Amacuro", "Vargas"].index(c['estado']))
                nuevo_contenido = st.text_area("Contenido", value=c['contenido'])
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Guardar cambios"):
                        if update_cronica(c['id'], nuevo_titulo, nuevo_contenido, nuevo_lugar, nuevo_estado):
                            st.success("✅ Crónica actualizada")
                            del st.session_state.edit_cronica
                            st.rerun()
                with col2:
                    if st.form_submit_button("❌ Cancelar"):
                        del st.session_state.edit_cronica
                        st.rerun()
    
    # --- VIDEOS ---
    elif "🎬 Videos" in admin_opt:
        st.subheader("🎬 Gestionar Videos")
        st.info("📌 Sube tu video a YouTube y pega la URL aquí")
        
        with st.expander("➕ Agregar nuevo video", expanded=True):
            with st.form("fvid"):
                titulo = st.text_input("Título del video")
                url_youtube = st.text_input("URL de YouTube", placeholder="https://youtu.be/XXXXX")
                if st.form_submit_button("📤 Agregar Video"):
                    if titulo and url_youtube:
                        add_video(titulo, url_youtube)
                        st.success("✅ Video agregado")
                        st.rerun()
        
        st.markdown("---")
        st.markdown("### 📋 Videos existentes")
        
        for _, v in get_videos().iterrows():
            with st.expander(f"🎬 {v['titulo']}"):
                mostrar_video_youtube(v['video_url'])
                st.caption(f"📅 {v['fecha']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"✏️ Modificar", key=f"edit_vid_{v['id']}"):
                        st.session_state.edit_video = v.to_dict()
                        st.rerun()
                with col2:
                    if st.button(f"🗑️ Eliminar", key=f"del_vid_{v['id']}"):
                        delete_video(v['id'])
                        st.success("✅ Video eliminado")
                        st.rerun()
        
        if 'edit_video' in st.session_state:
            v = st.session_state.edit_video
            st.markdown("---")
            st.subheader(f"✏️ Modificando: {v['titulo']}")
            with st.form("edit_video_form"):
                nuevo_titulo = st.text_input("Título", value=v['titulo'])
                nueva_url = st.text_input("URL de YouTube", value=v['video_url'])
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Guardar cambios"):
                        if update_video(v['id'], nuevo_titulo, nueva_url):
                            st.success("✅ Video actualizado")
                            del st.session_state.edit_video
                            st.rerun()
                with col2:
                    if st.form_submit_button("❌ Cancelar"):
                        del st.session_state.edit_video
                        st.rerun()
    
    # --- MUSICA ---
    elif "🎵 Música" in admin_opt:
        st.subheader("🎵 Gestionar Música")
        
        with st.expander("➕ Agregar nueva canción", expanded=True):
            with st.form("fmus"):
                titulo = st.text_input("Título de la canción")
                url_audio = st.text_input("URL del audio", placeholder="https://ejemplo.com/cancion.mp3")
                if st.form_submit_button("📤 Agregar Música"):
                    if titulo and url_audio:
                        add_musica(titulo, url_audio)
                        st.success("✅ Música agregada")
                        st.rerun()
        
        st.markdown("---")
        st.markdown("### 📋 Canciones existentes")
        
        for _, m in get_musicas().iterrows():
            with st.expander(f"🎵 {m['titulo']}"):
                mostrar_musica(m['audio_url'])
                st.caption(f"📅 {m['fecha']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"✏️ Modificar", key=f"edit_mus_{m['id']}"):
                        st.session_state.edit_musica = m.to_dict()
                        st.rerun()
                with col2:
                    if st.button(f"🗑️ Eliminar", key=f"del_mus_{m['id']}"):
                        delete_musica(m['id'])
                        st.success("✅ Canción eliminada")
                        st.rerun()
        
        if 'edit_musica' in st.session_state:
            m = st.session_state.edit_musica
            st.markdown("---")
            st.subheader(f"✏️ Modificando: {m['titulo']}")
            with st.form("edit_musica_form"):
                nuevo_titulo = st.text_input("Título", value=m['titulo'])
                nueva_url = st.text_input("URL del audio", value=m['audio_url'])
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Guardar cambios"):
                        if update_musica(m['id'], nuevo_titulo, nueva_url):
                            st.success("✅ Canción actualizada")
                            del st.session_state.edit_musica
                            st.rerun()
                with col2:
                    if st.form_submit_button("❌ Cancelar"):
                        del st.session_state.edit_musica
                        st.rerun()
    
    # --- DENUNCIAS ---
    elif "⚠️ Denuncias" in admin_opt:
        st.subheader("⚠️ Gestionar Denuncias")
        
        for _, d in get_denuncias().iterrows():
            with st.expander(f"📌 {d['titulo']} - {d['estatus']}"):
                st.write(f"**Denunciante:** {d['denunciante']}")
                st.write(f"**Descripción:** {d['descripcion']}")
                st.write(f"**Ubicación:** {d['ubicacion'] if d['ubicacion'] else 'No especificada'}")
                st.caption(f"📅 {d['fecha']}")
                
                nuevo_estado = st.selectbox("Cambiar estado:", ["Pendiente", "En revisión", "Resuelta", "Descartada"], 
                                           index=["Pendiente", "En revisión", "Resuelta", "Descartada"].index(d['estatus']),
                                           key=f"est_{d['id']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Actualizar estado", key=f"upd_{d['id']}"):
                        update_denuncia_status(d['id'], nuevo_estado)
                        st.success("✅ Estado actualizado")
                        st.rerun()
                with col2:
                    if st.button("🗑️ Eliminar denuncia", key=f"del_den_{d['id']}"):
                        delete_denuncia(d['id'])
                        st.success("✅ Denuncia eliminada")
                        st.rerun()
    
    # --- OPINIONES ---
    elif "💬 Opiniones" in admin_opt:
        st.subheader("💬 Gestionar Opiniones")
        
        st.markdown("### ⏳ Opiniones pendientes de aprobar")
        opiniones_pendientes = get_opiniones(aprobadas=False)
        if not opiniones_pendientes.empty:
            for _, op in opiniones_pendientes.iterrows():
                if not op['aprobada']:
                    with st.expander(f"👤 {op['usuario']} - {op['calificacion']}⭐"):
                        st.write(f"**Comentario:** {op['comentario']}")
                        st.caption(f"📅 {op['fecha']}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ Aprobar", key=f"aprob_{op['id']}"):
                                approve_opinion(op['id'])
                                st.success("✅ Opinión aprobada")
                                st.rerun()
                        with col2:
                            if st.button("🗑️ Eliminar", key=f"del_op_{op['id']}"):
                                delete_opinion(op['id'])
                                st.success("✅ Opinión eliminada")
                                st.rerun()
        else:
            st.info("No hay opiniones pendientes")
        
        st.markdown("---")
        st.markdown("### ✅ Opiniones aprobadas")
        opiniones_aprobadas = get_opiniones(aprobadas=True)
        if not opiniones_aprobadas.empty:
            for _, op in opiniones_aprobadas.iterrows():
                with st.expander(f"👤 {op['usuario']} - {op['calificacion']}⭐"):
                    st.write(f"**Comentario:** {op['comentario']}")
                    st.caption(f"📅 {op['fecha']}")
                    if st.button("🗑️ Eliminar", key=f"del_op_aprob_{op['id']}"):
                        delete_opinion(op['id'])
                        st.success("✅ Opinión eliminada")
                        st.rerun()
        else:
            st.info("No hay opiniones aprobadas")
    
    # --- PERSONAJES (ADMIN) ---
    elif "👥 Personajes" in admin_opt:
        st.subheader("👥 Gestionar Personajes")
        
        with st.expander("➕ Crear nuevo personaje", expanded=True):
            with st.form("fpersonaje_admin"):
                nombre = st.text_input("Nombre del personaje")
                fecha_personaje = st.date_input("Fecha a mostrar", value=datetime.now().date())
                descripcion = st.text_area("Biografía")
                imagen = st.file_uploader("Imagen", type=["jpg", "png", "jpeg"])
                if st.form_submit_button("💾 Guardar Personaje"):
                    if nombre and descripcion:
                        add_personaje(nombre, descripcion, imagen, fecha_personaje.strftime("%d/%m/%Y"))
                        st.success("✅ Personaje guardado")
                        st.rerun()
                    else:
                        st.error("❌ Nombre y biografía obligatorios")
        
        st.markdown("---")
        st.markdown("### 📋 Personajes Registrados")
        
        personajes = get_personajes()
        if not personajes.empty:
            for _, p in personajes.iterrows():
                with st.expander(f"👤 {p['nombre']} - {p['fecha']}"):
                    if p.get('imagen_url') and p['imagen_url']:
                        st.image(p['imagen_url'], width=150)
                    else:
                        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Flag_of_Venezuela_%28state%29.svg/1200px-Flag_of_Venezuela_%28state%29.svg.png", width=150)
                    
                    st.write(f"**Biografía:** {p['descripcion']}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button(f"✏️ Modificar", key=f"edit_{p['id']}"):
                            st.session_state.edit_personaje = p.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ Eliminar", key=f"del_{p['id']}"):
                            delete_personaje(p['id'])
                            st.success(f"✅ {p['nombre']} eliminado")
                            st.rerun()
                    with col3:
                        if st.button(f"⭐ Destacar hoy", key=f"destacar_{p['id']}"):
                            update_personaje(p['id'], p['nombre'], p['descripcion'], None, datetime.now().strftime("%d/%m/%Y"))
                            st.success(f"✅ {p['nombre']} será el personaje destacado")
                            st.rerun()
        else:
            st.info("No hay personajes registrados")
        
        if 'edit_personaje' in st.session_state:
            p = st.session_state.edit_personaje
            st.markdown("---")
            st.subheader(f"✏️ Modificando: {p['nombre']}")
            with st.form("edit_personaje_form"):
                nuevo_nombre = st.text_input("Nombre", value=p['nombre'])
                try:
                    fecha_default = datetime.strptime(p['fecha'], "%d/%m/%Y").date()
                except:
                    fecha_default = datetime.now().date()
                nueva_fecha = st.date_input("Fecha", value=fecha_default)
                nueva_descripcion = st.text_area("Biografía", value=p['descripcion'])
                nueva_imagen = st.file_uploader("Nueva imagen (opcional)", type=["jpg", "png", "jpeg"])
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Guardar cambios"):
                        if update_personaje(p['id'], nuevo_nombre, nueva_descripcion, nueva_imagen, nueva_fecha.strftime("%d/%m/%Y")):
                            st.success("✅ Personaje actualizado")
                            del st.session_state.edit_personaje
                            st.rerun()
                with col2:
                    if st.form_submit_button("❌ Cancelar"):
                        del st.session_state.edit_personaje
                        st.rerun()
    
    # --- CONFIGURACION ---
    elif "⚙️ Configuración" in admin_opt:
        st.subheader("⚙️ Configuración del Sistema")
        
        st.markdown("### 💵 Tipo de Cambio Dólar BCV")
        dolar_actual = get_dolar()
        st.metric("Valor actual", f"{dolar_actual:.2f} Bs")
        nuevo_dolar = st.number_input("Nuevo valor:", value=float(dolar_actual), step=0.01, format="%.2f")
        
        if st.button("💾 Actualizar Dólar", key="btn_dolar_admin"):
            if actualizar_dolar_manual(nuevo_dolar):
                st.success("✅ Dólar actualizado correctamente")
                st.rerun()
            else:
                st.error("❌ Error al actualizar")
        
        st.markdown("---")
        st.markdown("### 🖼️ Logo de la aplicación")
        if logo:
            st.image(logo, width=150)
        nuevo_logo = st.file_uploader("Subir nuevo logo", type=["png", "jpg", "jpeg"])
        if nuevo_logo and st.button("💾 Guardar Logo", key="btn_logo"):
            url_logo = subir_imagen_storage(nuevo_logo, "logo")
            if url_logo:
                save_logo(url_logo)
                st.success("✅ Logo guardado")
                st.rerun()

# ============================================
# FOOTER
# ============================================
st.markdown("""
<div class="bronze-footer">
    <div style="position: relative;">
        <div style="position: absolute; top: 15px; left: 15px; width: 22px; height: 22px; background: radial-gradient(circle at 30% 30%, #bbb, #444); border-radius: 50%; box-shadow: 2px 2px 6px rgba(0,0,0,0.6); border: 1px solid #d4af37;"></div>
        <div style="position: absolute; top: 15px; right: 15px; width: 22px; height: 22px; background: radial-gradient(circle at 30% 30%, #bbb, #444); border-radius: 50%; box-shadow: 2px 2px 6px rgba(0,0,0,0.6); border: 1px solid #d4af37;"></div>
        <div style="position: absolute; bottom: 15px; left: 15px; width: 22px; height: 22px; background: radial-gradient(circle at 30% 30%, #bbb, #444); border-radius: 50%; box-shadow: 2px 2px 6px rgba(0,0,0,0.6); border: 1px solid #d4af37;"></div>
        <div style="position: absolute; bottom: 15px; right: 15px; width: 22px; height: 22px; background: radial-gradient(circle at 30% 30%, #bbb, #444); border-radius: 50%; box-shadow: 2px 2px 6px rgba(0,0,0,0.6); border: 1px solid #d4af37;"></div>
        <p style="font-size: 1.8em; letter-spacing: 4px; color: #ffd700; font-family: 'Times New Roman', serif; font-weight: bold;">DESARROLLADO POR WILLIAN ALMENAR</p>
        <p style="color: #ffd700; font-family: 'Times New Roman', serif;">Prohibida la reproducción total o parcial</p>
        <p style="color: #ffd700; font-family: 'Times New Roman', serif;">DERECHOS RESERVADOS</p>
        <p style="color: #ffd700; font-family: 'Times New Roman', serif;">Santa Teresa del Tuy, 2026</p>
    </div>
</div>
""", unsafe_allow_html=True)
