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
import hashlib
import time

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
# FUNCIÓN PARA DÓLAR
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
# FUNCIONES DE ME GUSTA
# ============================================
def agregar_like(usuario_id, usuario_nombre, usuario_telefono):
    try:
        existing = supabase.table("likes").select("*").eq("usuario_id", usuario_id).execute()
        
        if existing.data:
            supabase.table("likes").update({
                "activo": True,
                "fecha": datetime.now(pytz.UTC).isoformat()
            }).eq("usuario_id", usuario_id).execute()
            return True
        else:
            data = {
                "usuario_id": usuario_id,
                "usuario_nombre": usuario_nombre if usuario_nombre else "Anónimo",
                "usuario_telefono": usuario_telefono if usuario_telefono else None,
                "fecha": datetime.now(pytz.UTC).isoformat(),
                "activo": True
            }
            supabase.table("likes").insert(data).execute()
            return True
    except Exception as e:
        st.error(f"Error al agregar like: {str(e)}")
        return False

def obtener_total_likes():
    try:
        response = supabase.table("likes").select("*", count="exact").eq("activo", True).execute()
        return response.count if response.count else 0
    except Exception:
        return 0

def obtener_lista_likes():
    try:
        response = supabase.table("likes").select("*").eq("activo", True).order("fecha", desc=True).execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

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
    except Exception as e:
        st.error(f"Error al subir imagen: {str(e)}")
        return None

def subir_multiples_imagenes(files, carpeta):
    urls = []
    if files:
        for file in files:
            url = subir_imagen_storage(file, carpeta)
            if url:
                urls.append(url)
    return urls

def subir_audio_storage(file):
    try:
        if file is None:
            return None
        
        nombre_archivo = f"audio_{uuid.uuid4()}.mp3"
        
        supabase.storage.from_("imagenes").upload(
            nombre_archivo,
            file.getvalue(),
            {"content-type": "audio/mpeg"}
        )
        
        url = supabase.storage.from_("imagenes").get_public_url(nombre_archivo)
        return url
    except Exception as e:
        st.error(f"Error al subir audio: {str(e)}")
        return None

def extraer_video_id(url_youtube):
    if not url_youtube:
        return None
    
    url_youtube = url_youtube.strip()
    
    patterns = [
        r'(?:youtube\.com\/watch\?v=)([\w-]+)',
        r'(?:youtu\.be\/)([\w-]+)',
        r'(?:youtube\.com\/embed\/)([\w-]+)',
        r'(?:youtube\.com\/v\/)([\w-]+)',
        r'(?:youtube\.com\/shorts\/)([\w-]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url_youtube)
        if match:
            return match.group(1)
    
    if re.match(r'^[\w-]+$', url_youtube):
        return url_youtube
    
    return None

def mostrar_video_youtube(url_youtube, width_percent=25):
    video_id = extraer_video_id(url_youtube)
    if video_id:
        html = f"""
        <div style="width: {width_percent}%; margin: 0 auto;">
            <iframe 
                width="100%" 
                height="200" 
                src="https://www.youtube.com/embed/{video_id}" 
                frameborder="0" 
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                allowfullscreen>
            </iframe>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.error("URL de YouTube no válida")

def mostrar_musica(url_audio):
    if url_audio:
        html = f"""
        <audio controls style="width: 100%; border-radius: 30px;">
            <source src="{url_audio}" type="audio/mpeg">
            Tu navegador no soporta el elemento de audio.
        </audio>
        """
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.warning("No hay URL de audio disponible")

# ============================================
# FUNCIONES DE TIKTOK
# ============================================
def extraer_tiktok_id(url_tiktok):
    if not url_tiktok:
        return None
    
    url_tiktok = url_tiktok.strip()
    
    patterns = [
        r'tiktok\.com/(?:@[\w.-]+/video/|v/|embed/)(\d+)',
        r'tiktok\.com/t/([\w-]+)',
        r'vm\.tiktok\.com/([\w-]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url_tiktok)
        if match:
            return match.group(1)
    
    return None

def mostrar_tiktok(url_tiktok, width_percent=25):
    tiktok_id = extraer_tiktok_id(url_tiktok)
    
    if tiktok_id:
        html = f"""
        <div style="width: {width_percent}%; margin: 0 auto;">
            <blockquote 
                class="tiktok-embed" 
                cite="{url_tiktok}" 
                data-video-id="{tiktok_id}"
                style="max-width: 100%; width: 100%;">
                <section>
                    <a target="_blank" href="{url_tiktok}">Ver en TikTok</a>
                </section>
            </blockquote>
            <script async src="https://www.tiktok.com/embed.js"></script>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.markdown(f"📱 [Ver video en TikTok]({url_tiktok})")

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
    except Exception as e:
        st.error(f"Error al agregar noticia: {str(e)}")
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
    except Exception as e:
        st.error(f"Error al actualizar noticia: {str(e)}")
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
def add_negocio(nombre, resena, google_maps_url, imagenes):
    try:
        ahora = get_fecha_hora_venezuela()
        imagenes_urls = subir_multiples_imagenes(imagenes, "negocios") if imagenes else []
        data = {
            "nombre": nombre,
            "resena": resena,
            "google_maps_url": google_maps_url if google_maps_url else None,
            "imagenes_url": imagenes_urls,
            "fecha": ahora.strftime("%d/%m/%Y")
        }
        result = supabase.table("negocios").insert(data).execute()
        return True if result.data else False
    except Exception as e:
        st.error(f"Error al agregar negocio: {str(e)}")
        return False

def update_negocio(id_, nombre, resena, google_maps_url, imagenes):
    try:
        imagenes_urls = None
        if imagenes:
            imagenes_urls = subir_multiples_imagenes(imagenes, "negocios")
        else:
            existing = supabase.table("negocios").select("imagenes_url").eq("id", id_).execute()
            if existing.data:
                imagenes_urls = existing.data[0].get("imagenes_url")
        
        data = {
            "nombre": nombre,
            "resena": resena,
            "google_maps_url": google_maps_url if google_maps_url else None,
            "imagenes_url": imagenes_urls if imagenes_urls else []
        }
        supabase.table("negocios").update(data).eq("id", id_).execute()
        return True
    except Exception:
        return False

def get_negocios():
    try:
        response = supabase.table("negocios").select("*").order("id", desc=True).execute()
        if response.data:
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al obtener negocios: {str(e)}")
        return pd.DataFrame()

def delete_negocio(id_):
    try:
        supabase.table("negocios").delete().eq("id", id_).execute()
        return True
    except Exception:
        return False

# --- OPINIONES DE NEGOCIOS ---
def add_opinion_negocio(negocio_id, usuario, comentario, calificacion):
    try:
        ahora = get_fecha_hora_venezuela()
        data = {
            "negocio_id": negocio_id,
            "usuario": usuario,
            "comentario": comentario,
            "calificacion": calificacion,
            "fecha": ahora.strftime("%d/%m/%Y %H:%M"),
            "aprobada": True
        }
        supabase.table("opiniones_negocios").insert(data).execute()
        return True
    except Exception:
        return False

def get_opiniones_negocio(negocio_id):
    try:
        response = supabase.table("opiniones_negocios").select("*").eq("negocio_id", negocio_id).order("id", desc=True).execute()
        return pd.DataFrame(response.data)
    except Exception:
        return pd.DataFrame()

def delete_opinion_negocio(id_):
    try:
        supabase.table("opiniones_negocios").delete().eq("id", id_).execute()
        return True
    except Exception:
        return False

# --- REFLEXIONES ---
def add_reflexion(titulo, contenido, versiculo):
    try:
        ahora = get_fecha_hora_venezuela()
        
        try:
            supabase.table("reflexiones").update({"activo": False}).execute()
        except:
            pass
        
        data = {
            "titulo": titulo,
            "contenido": contenido,
            "versiculo": versiculo if versiculo else None,
            "autor": "Admin",
            "fecha": ahora.strftime("%d/%m/%Y"),
            "activo": True
        }
        
        result = supabase.table("reflexiones").insert(data).execute()
        return True if result.data else False
    except Exception as e:
        st.error(f"Error al guardar reflexión: {str(e)}")
        return False

def update_reflexion(id_, titulo, contenido, versiculo):
    try:
        data = {
            "titulo": titulo,
            "contenido": contenido,
            "versiculo": versiculo if versiculo else None
        }
        supabase.table("reflexiones").update(data).eq("id", id_).execute()
        return True
    except Exception as e:
        st.error(f"Error al actualizar reflexión: {str(e)}")
        return False

def get_reflexion_activa():
    try:
        response = supabase.table("reflexiones").select("*").eq("activo", True).limit(1).execute()
        if response.data:
            return response.data[0]
        
        response = supabase.table("reflexiones").select("*").order("id", desc=True).limit(1).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception:
        try:
            response = supabase.table("reflexiones").select("*").order("id", desc=True).limit(1).execute()
            if response.data:
                return response.data[0]
        except:
            pass
        return None

def get_reflexiones():
    try:
        response = supabase.table("reflexiones").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error al obtener reflexiones: {str(e)}")
        return pd.DataFrame()

def delete_reflexion(id_):
    try:
        supabase.table("reflexiones").delete().eq("id", id_).execute()
        return True
    except Exception as e:
        st.error(f"Error al eliminar reflexión: {str(e)}")
        return False

# --- CRONICAS ---
def add_cronica(titulo, contenido, lugar, estado, imagenes):
    try:
        ahora = get_fecha_hora_venezuela()
        imagenes_urls = subir_multiples_imagenes(imagenes, "cronicas") if imagenes else []
        data = {
            "titulo": titulo,
            "contenido": contenido,
            "autor": "Admin",
            "fecha": ahora.strftime("%d/%m/%Y"),
            "lugar": lugar,
            "estado": estado,
            "imagenes_url": imagenes_urls
        }
        supabase.table("cronicas").insert(data).execute()
        return True
    except Exception:
        return False

def update_cronica(id_, titulo, contenido, lugar, estado, imagenes):
    try:
        imagenes_urls = None
        if imagenes:
            imagenes_urls = subir_multiples_imagenes(imagenes, "cronicas")
        else:
            existing = supabase.table("cronicas").select("imagenes_url").eq("id", id_).execute()
            if existing.data:
                imagenes_urls = existing.data[0].get("imagenes_url")
        
        data = {
            "titulo": titulo,
            "contenido": contenido,
            "lugar": lugar,
            "estado": estado,
            "imagenes_url": imagenes_urls
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
        if not url_youtube or url_youtube.strip() == "":
            st.error("❌ La URL del video es obligatoria")
            return False
        
        video_id = extraer_video_id(url_youtube)
        if not video_id:
            st.error("❌ URL de YouTube no válida")
            return False
        
        ahora = get_fecha_hora_venezuela()
        video_url_limpia = f"https://www.youtube.com/watch?v={video_id}"
        
        data = {
            "titulo": titulo,
            "video_url": video_url_limpia,
            "formato": "youtube",
            "fecha": ahora.strftime("%d/%m/%Y")
        }
        
        result = supabase.table("videos").insert(data).execute()
        
        if result.data:
            st.success("✅ Video agregado correctamente")
            return True
        else:
            st.error("❌ Error: No se pudo guardar el video")
            return False
            
    except Exception as e:
        st.error(f"❌ Error al agregar video: {str(e)}")
        return False

def update_video(id_, titulo, url_youtube):
    try:
        if not url_youtube or url_youtube.strip() == "":
            st.error("❌ La URL del video es obligatoria")
            return False
        
        video_id = extraer_video_id(url_youtube)
        if not video_id:
            st.error("❌ URL de YouTube no válida")
            return False
        
        video_url_limpia = f"https://www.youtube.com/watch?v={video_id}"
        
        data = {
            "titulo": titulo,
            "video_url": video_url_limpia
        }
        supabase.table("videos").update(data).eq("id", id_).execute()
        return True
    except Exception as e:
        st.error(f"Error al actualizar video: {str(e)}")
        return False

def get_videos():
    try:
        response = supabase.table("videos").select("*").order("id", desc=True).execute()
        if response.data:
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al obtener videos: {str(e)}")
        return pd.DataFrame()

def delete_video(id_):
    try:
        supabase.table("videos").delete().eq("id", id_).execute()
        return True
    except Exception as e:
        st.error(f"Error al eliminar video: {str(e)}")
        return False

# --- TIKTOK ---
def add_tiktok(titulo, url_tiktok):
    try:
        if not titulo or titulo.strip() == "":
            st.error("❌ El título es obligatorio")
            return False
        
        if not url_tiktok or url_tiktok.strip() == "":
            st.error("❌ La URL de TikTok es obligatoria")
            return False
        
        ahora = get_fecha_hora_venezuela()
        
        data = {
            "titulo": titulo,
            "tiktok_url": url_tiktok,
            "fecha": ahora.strftime("%d/%m/%Y")
        }
        
        result = supabase.table("tiktoks").insert(data).execute()
        
        if result.data:
            st.success(f"✅ Video de TikTok agregado correctamente")
            return True
        else:
            st.error("❌ Error al guardar en la base de datos")
            return False
            
    except Exception as e:
        st.error(f"❌ Error al agregar TikTok: {str(e)}")
        return False

def get_tiktoks():
    try:
        response = supabase.table("tiktoks").select("*").order("id", desc=True).execute()
        if response.data:
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al obtener TikToks: {str(e)}")
        return pd.DataFrame()

def delete_tiktok(id_):
    try:
        supabase.table("tiktoks").delete().eq("id", id_).execute()
        return True
    except Exception as e:
        st.error(f"Error al eliminar TikTok: {str(e)}")
        return False

# --- MUSICA ---
def add_musica(titulo, audio_file):
    try:
        if not titulo or titulo.strip() == "":
            st.error("❌ El título es obligatorio")
            return False
        
        if not audio_file:
            st.error("❌ Debes seleccionar un archivo de audio")
            return False
        
        if not audio_file.name.lower().endswith('.mp3'):
            st.error("❌ Solo se permiten archivos MP3")
            return False
        
        ahora = get_fecha_hora_venezuela()
        
        audio_url = subir_audio_storage(audio_file)
        
        if not audio_url:
            st.error("❌ Error al subir el archivo de audio")
            return False
        
        data = {
            "titulo": titulo,
            "audio_url": audio_url,
            "fecha": ahora.strftime("%d/%m/%Y")
        }
        
        result = supabase.table("musicas").insert(data).execute()
        
        if result.data:
            st.success(f"✅ Música '{titulo}' agregada correctamente")
            return True
        else:
            st.error("❌ Error al guardar en la base de datos")
            return False
            
    except Exception as e:
        st.error(f"❌ Error al agregar música: {str(e)}")
        return False

def get_musicas():
    try:
        response = supabase.table("musicas").select("*").order("id", desc=True).execute()
        if response.data:
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al obtener música: {str(e)}")
        return pd.DataFrame()

def delete_musica(id_):
    try:
        supabase.table("musicas").delete().eq("id", id_).execute()
        return True
    except Exception as e:
        st.error(f"Error al eliminar música: {str(e)}")
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

# --- OPINIONES GENERALES ---
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
# INICIALIZAR CONFIGURACION
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
# ESTILOS - TODAS LAS LETRAS EN BLANCO NEGRITA
# ============================================
st.markdown("""
<style>
/* Fondo tricolor venezolano */
.stApp {
    background: linear-gradient(180deg, #FFD700 0%, #00247D 50%, #CF142B 100%);
}

/* Contenido principal con fondo oscuro */
.block-container {
    background-color: rgba(0, 0, 0, 0.85) !important;
    border-radius: 20px !important;
    padding: 20px !important;
}

/* TODAS LAS LETRAS EN BLANCO NEGRITA */
* {
    color: #FFFFFF !important;
    font-weight: bold !important;
}

.main, .main p, .main span, .main div, .main label, .stMarkdown {
    color: #FFFFFF !important;
    font-weight: bold !important;
}

/* Títulos en dorado (ligeramente más claro) */
.main h1, .main h2, .main h3, .main h4 {
    color: #FFD700 !important;
    font-weight: bold !important;
}

/* Enlaces */
a {
    color: #FFD700 !important;
    font-weight: bold !important;
    text-decoration: underline !important;
}

/* Pestañas (TABS) */
div[data-testid="stTabs"] {
    background-color: transparent !important;
}

div[data-testid="stTabs"] button {
    background-color: #1a1a1a !important;
    border-radius: 12px !important;
    color: #FFFFFF !important;
    font-weight: bold !important;
    font-size: 14px !important;
    padding: 8px 16px !important;
    margin: 0 4px !important;
    border: 1px solid #FFD700 !important;
    cursor: pointer !important;
    transition: all 0.3s ease !important;
}

div[data-testid="stTabs"] button:hover {
    background-color: #FFD700 !important;
    color: #000000 !important;
    border-color: #FFFFFF !important;
}

div[data-testid="stTabs"] button p {
    color: inherit !important;
    font-weight: bold !important;
}

/* Expanders */
.streamlit-expanderHeader {
    background-color: #1a1a1a !important;
    border-radius: 10px !important;
    border-left: 4px solid #FFD700 !important;
    color: #FFD700 !important;
    font-weight: bold !important;
}

.streamlit-expanderContent {
    background-color: #1a1a1a !important;
    border-radius: 10px !important;
    padding: 15px !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #87CEEB 0%, #4682B4 100%) !important;
    border-right: 3px solid #FFD700 !important;
}

[data-testid="stSidebar"] * {
    color: #1a1a2e !important;
    font-weight: bold !important;
}

/* Inputs */
input, textarea, .stSelectbox > div > div {
    background-color: #f0f0f0 !important;
    color: #000000 !important;
    font-weight: normal !important;
    border-radius: 12px !important;
    border: 2px solid #FFD700 !important;
}

input::placeholder, textarea::placeholder {
    color: #666666 !important;
    font-weight: normal !important;
}

/* Botones */
.stButton > button {
    background: linear-gradient(135deg, #FFD700, #CF142B) !important;
    color: white !important;
    border: none !important;
    font-weight: bold !important;
    border-radius: 25px !important;
}

/* Footer */
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
    font-weight: bold !important;
}

/* Mensajes */
.stInfo, .stSuccess, .stWarning, .stError {
    background-color: rgba(0,0,0,0.8) !important;
    color: white !important;
    font-weight: bold !important;
}

/* Reproductor de audio */
audio {
    width: 100%;
    border-radius: 30px;
}

/* Métricas */
[data-testid="stMetricValue"] {
    color: #FFD700 !important;
    font-weight: bold !important;
    font-size: 1.5rem !important;
}

[data-testid="stMetricLabel"] {
    color: #FFFFFF !important;
    font-weight: bold !important;
}

/* Inputs pequeños para like */
.stTextInput > div > div > input {
    padding: 4px 8px !important;
    font-size: 12px !important;
}
</style>
""", unsafe_allow_html=True)

# ============================================
# LOGO
# ============================================
logo = get_logo()
if logo:
    st.markdown(f'<div style="text-align: center;"><img src="{logo}" style="max-width: 200px;"></div>', unsafe_allow_html=True)

# ============================================
# BOTONES DE COMPARTIR
# ============================================
st.markdown(f"""
<div style="display: flex; justify-content: center; gap: 15px; flex-wrap: wrap; margin: 15px 0;">
    <a href="https://api.whatsapp.com/send?text=Santa Teresa al Dia - {APP_URL}" target="_blank" style="display: inline-block; padding: 10px 25px; border-radius: 25px; text-decoration: none; font-weight: bold; color: white; background: #25D366;">📱 WhatsApp</a>
    <a href="https://www.facebook.com/sharer/sharer.php?u={APP_URL}" target="_blank" style="display: inline-block; padding: 10px 25px; border-radius: 25px; text-decoration: none; font-weight: bold; color: white; background: #1877F2;">📘 Facebook</a>
    <a href="https://www.instagram.com/" target="_blank" style="display: inline-block; padding: 10px 25px; border-radius: 25px; text-decoration: none; font-weight: bold; color: white; background: linear-gradient(45deg, #f09433, #d62976);">📸 Instagram</a>
    <button id="copyButton" style="display: inline-block; padding: 10px 25px; border-radius: 25px; text-decoration: none; font-weight: bold; color: white; background: #3498db; border: none; cursor: pointer;">📋 Copiar</button>
</div>
<script>
document.getElementById('copyButton').addEventListener('click', function() {{
    var dummy = document.createElement('textarea');
    document.body.appendChild(dummy);
    dummy.value = '{APP_URL}';
    dummy.select();
    document.execCommand('copy');
    document.body.removeChild(dummy);
    alert('Enlace copiado: {APP_URL}');
}});
</script>
""", unsafe_allow_html=True)

st.markdown("---")

# ============================================
# ENCABEZADO PRINCIPAL
# ============================================
ahora = get_fecha_hora_venezuela()
dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
visitas = get_visitas()
dolar = get_dolar()
portada_url = get_portada_url()

st.markdown(f"""
<div style="text-align: center; margin-bottom: 20px;">
    <div style="background: linear-gradient(rgba(0,0,0,0.55), rgba(0,0,0,0.55)), 
                url('{portada_url}');
                background-size: cover;
                background-position: center;
                border-radius: 20px;
                padding: 60px 20px 40px 20px;
                border: 3px solid #FFD700;">
        <h1 style="color: #FFD700; text-shadow: 3px 3px 8px black; font-size: 2.5em; font-weight: bold;">Santa Teresa al Dia</h1>
        <p style="color: #FFFFFF; text-shadow: 2px 2px 5px black; font-size: 1.3em; font-weight: bold;">Informacion, Cultura y Fe de nuestro pueblo</p>
        <div style="margin-top: 25px; padding-top: 10px; border-top: 1px solid rgba(255, 215, 0, 0.5);">
            <p style="color: #FFD700; font-size: 0.9em; margin: 0; font-weight: bold;">⭐ {dias[ahora.weekday()]}, {ahora.day} de {meses[ahora.month-1]} de {ahora.year} ⭐</p>
            <p style="color: white; font-size: 1em; margin: 5px 0; font-weight: bold;">{ahora.strftime("%I:%M %p")}</p>
            <p style="color: #FFD700; font-size: 0.9em; margin: 0; font-weight: bold;">👥 Visitantes: {visitas:,} | 💵 Dólar BCV: {dolar:.2f} Bs</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

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
        st.caption(f"💵 Dólar actual: {dolar:.2f} Bs")
    elif clave:
        st.error("❌ Clave incorrecta")
    
    if es_admin:
        st.markdown("---")
        st.markdown("### 📋 Panel de Control")
        admin_opt = st.radio("Seleccionar módulo:", [
            "📰 Noticias", "🏪 Negocios", "💭 Reflexiones", "📜 Crónicas",
            "🎬 Videos", "📱 TikTok", "🎵 Música", "⚠️ Denuncias", 
            "💬 Opiniones", "👥 Personajes", "⚙️ Configuración"
        ])
        st.session_state.admin_opt = admin_opt
        st.session_state.es_admin = True
        
        # Mostrar estadísticas rápidas en sidebar (solo admin)
        st.markdown("---")
        st.markdown("### 📊 Estadísticas Rápidas")
        total_likes_sidebar = obtener_total_likes()
        st.metric("👍 Me gusta", total_likes_sidebar)
    else:
        st.session_state.es_admin = False

# ============================================
# FUNCIÓN SEGURA PARA MOSTRAR IMÁGENES
# ============================================
def mostrar_imagen_segura(url, width=300, use_container_width=False):
    if url and isinstance(url, str) and url.startswith(('http://', 'https://', 'data:image')):
        if use_container_width:
            st.image(url, use_container_width=True)
        else:
            st.image(url, width=width)
        return True
    return False

# ============================================
# MENU PRINCIPAL (TABS)
# ============================================
menu_tabs = st.tabs(["🏠 Portada", "📰 Noticias", "📍 Donde ir - Donde comprar", "💭 Reflexiones", "📜 Crónicas", "🎬 Multimedia", "⚠️ Denuncias", "💬 Opiniones", "👥 Personajes que hicieron historia", "📅 Efemérides Médicas"])

# --- TAB 0: PORTADA ---
with menu_tabs[0]:
    st.title("Santa Teresa al Dia")
    
    # Generar ID único para el usuario
    if 'usuario_id' not in st.session_state:
        session_id = str(time.time()) + str(st.session_state.get('admin_pass', ''))
        st.session_state.usuario_id = hashlib.md5(session_id.encode()).hexdigest()
    
    # Botón de Me gusta - HORIZONTAL Y MÁS PEQUEÑO
    st.markdown("### 👍 Apoya nuestra página")
    
    with st.form("form_like"):
        # Tres columnas para nombre, teléfono y botón
        col_nom, col_tel, col_btn = st.columns([2, 2, 1])
        
        with col_nom:
            nombre_like = st.text_input("Tu nombre", placeholder="Ej: María González", key="like_nombre", label_visibility="collapsed")
        
        with col_tel:
            telefono_like = st.text_input("WhatsApp", placeholder="0412 1234567", key="like_tel", label_visibility="collapsed")
        
        with col_btn:
            if st.form_submit_button("👍 Me gusta", use_container_width=True):
                if agregar_like(st.session_state.usuario_id, nombre_like if nombre_like else "Anónimo", telefono_like):
                    st.success("✅ Gracias por tu like!")
                    st.balloons()
                    st.rerun()
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📰 Últimas Noticias")
        noticias = get_noticias()
        if not noticias.empty:
            for _, n in noticias.head(5).iterrows():
                with st.expander(f"📰 {n['titulo']} - {n['categoria']} ({n['fecha']})"):
                    mostrar_imagen_segura(n.get('imagen_url'), 300)
                    st.write(n['contenido'])
        else:
            st.info("No hay noticias disponibles")
    
    with col2:
        st.markdown("### ✝️ Reflexión del Día")
        ref = get_reflexion_activa()
        if ref:
            with st.expander(f"✨ {ref['titulo']}", expanded=True):
                st.write(ref['contenido'])
                if ref.get('versiculo'):
                    st.caption(f"📖 {ref['versiculo']}")
        else:
            st.info("No hay reflexión activa")

# --- TAB 1: NOTICIAS ---
with menu_tabs[1]:
    st.title("📰 Noticias")
    tab_nac, tab_inter, tab_dep, tab_suc, tab_far = st.tabs(["🇻🇪 Nacionales", "🌎 Internacionales", "⚽ Deportes", "🚨 Sucesos", "🎭 Farándula"])
    
    with tab_nac:
        noticias_nac = get_noticias(categoria="Nacional")
        if not noticias_nac.empty:
            for _, n in noticias_nac.iterrows():
                with st.expander(f"📰 {n['titulo']} - {n['fecha']}"):
                    mostrar_imagen_segura(n.get('imagen_url'), 300)
                    st.write(n['contenido'])
        else:
            st.info("No hay noticias Nacionales")
    
    with tab_inter:
        noticias_inter = get_noticias(categoria="Internacional")
        if not noticias_inter.empty:
            for _, n in noticias_inter.iterrows():
                with st.expander(f"📰 {n['titulo']} - {n['fecha']}"):
                    mostrar_imagen_segura(n.get('imagen_url'), 300)
                    st.write(n['contenido'])
        else:
            st.info("No hay noticias Internacionales")
    
    with tab_dep:
        noticias_dep = get_noticias(categoria="Deportes")
        if not noticias_dep.empty:
            for _, n in noticias_dep.iterrows():
                with st.expander(f"📰 {n['titulo']} - {n['fecha']}"):
                    mostrar_imagen_segura(n.get('imagen_url'), 300)
                    st.write(n['contenido'])
        else:
            st.info("No hay noticias de Deportes")
    
    with tab_suc:
        noticias_suc = get_noticias(categoria="Sucesos")
        if not noticias_suc.empty:
            for _, n in noticias_suc.iterrows():
                with st.expander(f"📰 {n['titulo']} - {n['fecha']}"):
                    mostrar_imagen_segura(n.get('imagen_url'), 300)
                    st.write(n['contenido'])
        else:
            st.info("No hay noticias de Sucesos")
    
    with tab_far:
        noticias_far = get_noticias(categoria="Farándula")
        if not noticias_far.empty:
            for _, n in noticias_far.iterrows():
                with st.expander(f"📰 {n['titulo']} - {n['fecha']}"):
                    mostrar_imagen_segura(n.get('imagen_url'), 300)
                    st.write(n['contenido'])
        else:
            st.info("No hay noticias de Farándula")

# --- TAB 2: NEGOCIOS ---
with menu_tabs[2]:
    st.title("📍 Donde ir - Donde comprar")
    
    negocios = get_negocios()
    
    if not negocios.empty:
        for _, n in negocios.iterrows():
            with st.expander(f"🏪 {n['nombre']}"):
                if n.get('imagenes_url') and n['imagenes_url']:
                    if isinstance(n['imagenes_url'], list):
                        for img_url in n['imagenes_url'][:2]:
                            mostrar_imagen_segura(img_url, 200)
                    elif isinstance(n['imagenes_url'], str):
                        mostrar_imagen_segura(n['imagenes_url'], 200)
                else:
                    st.caption("📷 Sin imágenes")
                
                st.write(f"**Reseña:** {n['resena']}")
                if n.get('google_maps_url') and n['google_maps_url']:
                    st.markdown(f"📍 [Ver ubicación en Google Maps]({n['google_maps_url']})")
                
                st.markdown("---")
                st.markdown("### 💬 Opiniones de este negocio")
                
                with st.form(f"opinion_form_{n['id']}"):
                    st.markdown("#### Deja tu opinión")
                    nombre_usuario = st.text_input("Tu nombre", key=f"nombre_{n['id']}")
                    comentario = st.text_area("Comentario", key=f"comentario_{n['id']}")
                    calificacion = st.slider("Calificación", 1, 5, 5, key=f"calif_{n['id']}")
                    if st.form_submit_button("Enviar Opinión"):
                        if nombre_usuario and comentario:
                            if add_opinion_negocio(n['id'], nombre_usuario, comentario, calificacion):
                                st.success("✅ Opinión enviada")
                                st.rerun()
                            else:
                                st.error("❌ Error al enviar opinión")
                        else:
                            st.error("❌ Nombre y comentario son obligatorios")
                
                opiniones = get_opiniones_negocio(n['id'])
                if not opiniones.empty:
                    for _, op in opiniones.iterrows():
                        stars = "⭐" * int(op['calificacion']) + "☆" * (5 - int(op['calificacion']))
                        st.markdown(f"**👤 {op['usuario']}** {stars}")
                        st.write(f"\"{op['comentario']}\"")
                        st.caption(f"📅 {op['fecha']}")
                        st.divider()
                else:
                    st.info("No hay opiniones para este negocio")
    else:
        st.info("No hay negocios agregados aún")

# --- TAB 3: REFLEXIONES ---
with menu_tabs[3]:
    st.title("💭 Reflexiones")
    ref = get_reflexion_activa()
    if ref:
        with st.expander(f"✨ ACTUAL: {ref['titulo']}", expanded=True):
            st.write(ref['contenido'])
            if ref.get('versiculo'):
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
                with st.expander(f"📖 {r['titulo']} - {r['fecha']}"):
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
                if c.get('imagenes_url') and c['imagenes_url']:
                    if isinstance(c['imagenes_url'], list):
                        for img_url in c['imagenes_url']:
                            mostrar_imagen_segura(img_url, 200)
                    elif isinstance(c['imagenes_url'], str):
                        mostrar_imagen_segura(c['imagenes_url'], 200)
                st.write(c['contenido'])
                st.caption(f"📅 {c['fecha']}")
    else:
        st.info("No hay crónicas disponibles")

# --- TAB 5: MULTIMEDIA ---
with menu_tabs[5]:
    st.title("🎬 Multimedia")
    tab_vid, tab_tik, tab_mus, tab_rad = st.tabs(["🎥 YouTube", "📱 TikTok", "🎵 Música", "📻 Radio"])
    
    with tab_vid:
        st.markdown("### 🎥 Videos de YouTube al 25% de tamaño")
        videos = get_videos()
        if not videos.empty:
            for _, v in videos.iterrows():
                with st.expander(f"🎬 {v['titulo']}"):
                    mostrar_video_youtube(v['video_url'], width_percent=25)
                    st.caption(f"📅 {v['fecha']}")
        else:
            st.info("No hay videos disponibles")
    
    with tab_tik:
        st.markdown("### 📱 Videos de TikTok al 25% de tamaño")
        tiktoks = get_tiktoks()
        if not tiktoks.empty:
            for _, t in tiktoks.iterrows():
                with st.expander(f"📱 {t['titulo']}"):
                    mostrar_tiktok(t['tiktok_url'], width_percent=25)
                    st.caption(f"📅 {t['fecha']}")
        else:
            st.info("No hay videos de TikTok disponibles")
        
        if es_admin:
            st.markdown("---")
            st.markdown("#### ➕ Agregar nuevo TikTok")
            with st.form("add_tiktok_form"):
                titulo_tik = st.text_input("Título del video")
                url_tik = st.text_input("URL de TikTok", placeholder="https://www.tiktok.com/@usuario/video/123456789")
                if st.form_submit_button("📤 Agregar TikTok"):
                    if titulo_tik and url_tik:
                        if add_tiktok(titulo_tik, url_tik):
                            st.rerun()
                    else:
                        st.error("❌ Título y URL son obligatorios")
    
    with tab_mus:
        st.markdown("### 🎵 Lista de Música")
        musicas = get_musicas()
        if not musicas.empty:
            for _, m in musicas.iterrows():
                with st.expander(f"🎵 {m['titulo']}"):
                    if m.get('audio_url') and m['audio_url']:
                        mostrar_musica(m['audio_url'])
                        st.caption(f"📅 {m['fecha']}")
                    else:
                        st.warning("No hay URL de audio disponible")
        else:
            st.info("No hay música disponible")
    
    with tab_rad:
        st.markdown("### 📻 Love Songs Radio")
        radio_iframe = """
        <iframe src="https://hearme.fm/embed/love-songs" 
                width="100%" 
                height="200" 
                frameborder="0" 
                allowtransparency 
                allow="autoplay">
        </iframe>
        """
        st.markdown(radio_iframe, unsafe_allow_html=True)
        st.caption("🎶 Música romántica las 24 horas")

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
                    if add_denuncia(nombre, titulo, desc, ubic):
                        st.success("✅ Denuncia enviada correctamente")
                        st.balloons()
                    else:
                        st.error("❌ Error al enviar denuncia")
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
                    if add_opinion(usuario, comentario, estrellas):
                        st.success("✅ Opinión enviada, será revisada por un administrador")
                        st.balloons()
                    else:
                        st.error("❌ Error al enviar opinión")
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

# --- TAB 8: PERSONAJES ---
with menu_tabs[8]:
    st.title("👥 Personajes que hicieron historia")
    
    st.markdown("### 📋 Personajes Registrados")
    
    personajes = get_personajes()
    if not personajes.empty:
        for _, p in personajes.iterrows():
            with st.expander(f"👤 {p['nombre']} - {p['fecha']}"):
                mostrar_imagen_segura(p.get('imagen_url'), 200)
                st.write(f"**Biografía:** {p['descripcion']}")
    else:
        st.info("No hay personajes registrados")

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
# PANEL ADMIN
# ============================================
if st.session_state.get('es_admin', False):
    admin_opt = st.session_state.get('admin_opt', "📰 Noticias")
    st.title("🔧 Panel de Administración")
    
    # --- NOTICIAS ---
    if "📰 Noticias" in admin_opt:
        st.subheader("📰 Gestionar Noticias")
        
        with st.expander("➕ CREAR nueva noticia", expanded=True):
            with st.form("fn"):
                titulo = st.text_input("Título *")
                categoria = st.selectbox("Categoría", ["Nacional", "Internacional", "Deportes", "Sucesos", "Farándula", "Reportajes"])
                contenido = st.text_area("Contenido *")
                imagen = st.file_uploader("Imagen (opcional)", type=["jpg", "png", "jpeg"])
                if st.form_submit_button("📤 Publicar Noticia"):
                    if titulo and contenido:
                        if add_noticia(titulo, categoria, contenido, imagen):
                            st.success("✅ Noticia guardada")
                            st.rerun()
                        else:
                            st.error("❌ Error al guardar noticia")
                    else:
                        st.error("❌ Título y contenido son obligatorios")
        
        st.markdown("---")
        st.markdown("### 📋 Noticias existentes")
        
        noticias = get_noticias()
        if not noticias.empty:
            for _, n in noticias.iterrows():
                with st.expander(f"📰 {n['titulo']} - {n['categoria']} ({n['fecha']})"):
                    mostrar_imagen_segura(n.get('imagen_url'), 300)
                    st.write(f"**Contenido:** {n['contenido']}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✏️ MODIFICAR", key=f"edit_noti_{n['id']}"):
                            st.session_state.edit_noticia = n.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR", key=f"del_noti_{n['id']}"):
                            if delete_noticia(n['id']):
                                st.success("✅ Noticia eliminada")
                                st.rerun()
        else:
            st.info("No hay noticias registradas")
        
        if 'edit_noticia' in st.session_state:
            n = st.session_state.edit_noticia
            st.markdown("---")
            st.subheader(f"✏️ Modificando: {n['titulo']}")
            with st.form("edit_noticia_form"):
                nuevo_titulo = st.text_input("Título", value=n['titulo'])
                nueva_categoria = st.selectbox("Categoría", ["Nacional", "Internacional", "Deportes", "Sucesos", "Farándula", "Reportajes"], index=["Nacional", "Internacional", "Deportes", "Sucesos", "Farándula", "Reportajes"].index(n['categoria']))
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
        
        with st.expander("➕ CREAR nuevo negocio", expanded=True):
            with st.form("fneg"):
                nombre = st.text_input("Nombre del negocio *")
                resena = st.text_area("Reseña *")
                google_maps_url = st.text_input("Enlace Google Maps (opcional)", placeholder="https://maps.google.com/...")
                imagenes = st.file_uploader("Fotos (máximo 3)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
                
                if len(imagenes) > 3:
                    st.error("Máximo 3 fotos por negocio")
                elif st.form_submit_button("➕ Agregar Negocio"):
                    if nombre and resena:
                        if add_negocio(nombre, resena, google_maps_url, imagenes):
                            st.success("✅ Negocio agregado correctamente")
                            st.rerun()
                        else:
                            st.error("❌ Error al agregar negocio")
                    else:
                        st.error("❌ Nombre y reseña son obligatorios")
        
        st.markdown("---")
        st.markdown("### 📋 Negocios existentes")
        
        negocios = get_negocios()
        if not negocios.empty:
            for _, n in negocios.iterrows():
                with st.expander(f"🏪 {n['nombre']}"):
                    if n.get('imagenes_url') and n['imagenes_url']:
                        if isinstance(n['imagenes_url'], list):
                            for img_url in n['imagenes_url']:
                                mostrar_imagen_segura(img_url, 200)
                        elif isinstance(n['imagenes_url'], str):
                            mostrar_imagen_segura(n['imagenes_url'], 200)
                    else:
                        st.caption("📷 Sin imágenes")
                    
                    st.write(f"**Reseña:** {n['resena']}")
                    if n.get('google_maps_url') and n['google_maps_url']:
                        st.markdown(f"📍 [Ver en Google Maps]({n['google_maps_url']})")
                    
                    st.markdown("---")
                    st.markdown("#### 💬 Opiniones del negocio")
                    
                    opiniones_neg = get_opiniones_negocio(n['id'])
                    if not opiniones_neg.empty:
                        for _, op in opiniones_neg.iterrows():
                            stars = "⭐" * int(op['calificacion']) + "☆" * (5 - int(op['calificacion']))
                            st.markdown(f"**👤 {op['usuario']}** {stars}")
                            st.write(f"\"{op['comentario']}\"")
                            st.caption(f"📅 {op['fecha']}")
                            if st.button(f"🗑️ Eliminar opinión", key=f"del_opinion_{op['id']}"):
                                if delete_opinion_negocio(op['id']):
                                    st.rerun()
                            st.divider()
                    else:
                        st.info("No hay opiniones para este negocio")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✏️ MODIFICAR", key=f"edit_neg_{n['id']}"):
                            st.session_state.edit_negocio = n.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR", key=f"del_neg_{n['id']}"):
                            if delete_negocio(n['id']):
                                st.success("✅ Negocio eliminado")
                                st.rerun()
        else:
            st.info("No hay negocios registrados")
        
        if 'edit_negocio' in st.session_state:
            n = st.session_state.edit_negocio
            st.markdown("---")
            st.subheader(f"✏️ Modificando: {n['nombre']}")
            with st.form("edit_negocio_form"):
                nuevo_nombre = st.text_input("Nombre", value=n['nombre'])
                nueva_resena = st.text_area("Reseña", value=n['resena'])
                nuevo_google_maps = st.text_input("Enlace Google Maps", value=n.get('google_maps_url', ''))
                nuevas_imagenes = st.file_uploader("Nuevas fotos (opcional, máximo 3)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Guardar cambios"):
                        if update_negocio(n['id'], nuevo_nombre, nueva_resena, nuevo_google_maps, nuevas_imagenes):
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
        
        with st.expander("➕ CREAR nueva reflexión", expanded=True):
            with st.form("fref"):
                titulo = st.text_input("Título *")
                versiculo = st.text_input("Versículo (opcional)")
                contenido = st.text_area("Contenido *")
                if st.form_submit_button("💾 Guardar como activa"):
                    if titulo and contenido:
                        if add_reflexion(titulo, contenido, versiculo):
                            st.success("✅ Reflexión guardada")
                            st.rerun()
                        else:
                            st.error("❌ Error al guardar")
                    else:
                        st.error("❌ Título y contenido son obligatorios")
        
        st.markdown("---")
        st.markdown("### 📋 Reflexiones existentes")
        
        reflexiones = get_reflexiones()
        if not reflexiones.empty:
            for _, r in reflexiones.iterrows():
                with st.expander(f"📖 {r['titulo']} - {r['fecha']}"):
                    st.write(r['contenido'])
                    if r.get('versiculo'):
                        st.caption(f"📖 {r['versiculo']}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✏️ MODIFICAR", key=f"edit_ref_{r['id']}"):
                            st.session_state.edit_reflexion = r.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR", key=f"del_ref_{r['id']}"):
                            if delete_reflexion(r['id']):
                                st.success("✅ Reflexión eliminada")
                                st.rerun()
        else:
            st.info("No hay reflexiones registradas")
        
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
        
        with st.expander("➕ CREAR nueva crónica", expanded=True):
            with st.form("fcro"):
                titulo = st.text_input("Título *")
                lugar = st.text_input("Lugar *")
                estado = st.selectbox("Estado", ["Miranda", "Carabobo", "Distrito Capital", "Zulia", "Lara", "Aragua", "Bolivar", "Anzoategui", "Merida", "Tachira", "Nueva Esparta", "Sucre", "Falcon", "Barinas", "Portuguesa", "Guarico", "Cojedes", "Trujillo", "Yaracuy", "Apure", "Amazonas", "Delta Amacuro", "Vargas"])
                contenido = st.text_area("Contenido *")
                imagenes = st.file_uploader("Fotos (opcional, máximo 3)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
                
                if len(imagenes) > 3:
                    st.error("Máximo 3 fotos por crónica")
                elif st.form_submit_button("💾 Guardar Crónica"):
                    if titulo and contenido:
                        if add_cronica(titulo, contenido, lugar, estado, imagenes):
                            st.success("✅ Crónica guardada")
                            st.rerun()
                        else:
                            st.error("❌ Error al guardar")
                    else:
                        st.error("❌ Título y contenido son obligatorios")
        
        st.markdown("---")
        st.markdown("### 📋 Crónicas existentes")
        
        cronicas = get_cronicas()
        if not cronicas.empty:
            for _, c in cronicas.iterrows():
                with st.expander(f"📜 {c['titulo']} - {c['lugar']}, {c['estado']}"):
                    if c.get('imagenes_url') and c['imagenes_url']:
                        if isinstance(c['imagenes_url'], list):
                            for img_url in c['imagenes_url']:
                                mostrar_imagen_segura(img_url, 200)
                        elif isinstance(c['imagenes_url'], str):
                            mostrar_imagen_segura(c['imagenes_url'], 200)
                    st.write(c['contenido'])
                    st.caption(f"📅 {c['fecha']}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✏️ MODIFICAR", key=f"edit_cron_{c['id']}"):
                            st.session_state.edit_cronica = c.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR", key=f"del_cron_{c['id']}"):
                            if delete_cronica(c['id']):
                                st.success("✅ Crónica eliminada")
                                st.rerun()
        else:
            st.info("No hay crónicas registradas")
        
        if 'edit_cronica' in st.session_state:
            c = st.session_state.edit_cronica
            st.markdown("---")
            st.subheader(f"✏️ Modificando: {c['titulo']}")
            with st.form("edit_cronica_form"):
                nuevo_titulo = st.text_input("Título", value=c['titulo'])
                nuevo_lugar = st.text_input("Lugar", value=c['lugar'])
                nuevo_estado = st.selectbox("Estado", ["Miranda", "Carabobo", "Distrito Capital", "Zulia", "Lara", "Aragua", "Bolivar", "Anzoategui", "Merida", "Tachira", "Nueva Esparta", "Sucre", "Falcon", "Barinas", "Portuguesa", "Guarico", "Cojedes", "Trujillo", "Yaracuy", "Apure", "Amazonas", "Delta Amacuro", "Vargas"], index=["Miranda", "Carabobo", "Distrito Capital", "Zulia", "Lara", "Aragua", "Bolivar", "Anzoategui", "Merida", "Tachira", "Nueva Esparta", "Sucre", "Falcon", "Barinas", "Portuguesa", "Guarico", "Cojedes", "Trujillo", "Yaracuy", "Apure", "Amazonas", "Delta Amacuro", "Vargas"].index(c['estado']))
                nuevo_contenido = st.text_area("Contenido", value=c['contenido'])
                nuevas_imagenes = st.file_uploader("Nuevas fotos (opcional)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Guardar cambios"):
                        if update_cronica(c['id'], nuevo_titulo, nuevo_contenido, nuevo_lugar, nuevo_estado, nuevas_imagenes):
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
        
        with st.expander("➕ CREAR nuevo video", expanded=True):
            with st.form("fvid"):
                titulo = st.text_input("Título del video *")
                url_youtube = st.text_input("URL de YouTube *", placeholder="https://www.youtube.com/watch?v=XXXXX")
                
                if url_youtube and url_youtube.strip():
                    video_id = extraer_video_id(url_youtube)
                    if video_id:
                        st.video(f"https://www.youtube.com/embed/{video_id}")
                    else:
                        st.warning("⚠️ URL no válida")
                
                if st.form_submit_button("📤 Agregar Video"):
                    if titulo and url_youtube:
                        if add_video(titulo, url_youtube):
                            st.rerun()
                    else:
                        st.error("❌ Título y URL son obligatorios")
        
        st.markdown("---")
        st.markdown("### 📋 Videos existentes")
        
        videos = get_videos()
        if not videos.empty:
            for _, v in videos.iterrows():
                with st.expander(f"🎬 {v['titulo']}"):
                    mostrar_video_youtube(v['video_url'], width_percent=25)
                    st.caption(f"📅 {v['fecha']}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✏️ MODIFICAR", key=f"edit_vid_{v['id']}"):
                            st.session_state.edit_video = v.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR", key=f"del_vid_{v['id']}"):
                            if delete_video(v['id']):
                                st.success("✅ Video eliminado")
                                st.rerun()
        else:
            st.info("No hay videos registrados")
        
        if 'edit_video' in st.session_state:
            v = st.session_state.edit_video
            st.markdown("---")
            st.subheader(f"✏️ Modificando: {v['titulo']}")
            with st.form("edit_video_form"):
                nuevo_titulo = st.text_input("Título", value=v['titulo'])
                nueva_url = st.text_input("URL de YouTube", value=v['video_url'])
                
                if nueva_url:
                    video_id = extraer_video_id(nueva_url)
                    if video_id:
                        st.video(f"https://www.youtube.com/embed/{video_id}")
                
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
    
    # --- TIKTOK ---
    elif "📱 TikTok" in admin_opt:
        st.subheader("📱 Gestionar Videos de TikTok")
        
        with st.expander("➕ CREAR nuevo TikTok", expanded=True):
            with st.form("ftik"):
                titulo = st.text_input("Título del video *")
                url_tiktok = st.text_input("URL de TikTok *", placeholder="https://www.tiktok.com/@usuario/video/123456789")
                
                if st.form_submit_button("📤 Agregar TikTok"):
                    if titulo and url_tiktok:
                        if add_tiktok(titulo, url_tiktok):
                            st.rerun()
                    else:
                        st.error("❌ Título y URL son obligatorios")
        
        st.markdown("---")
        st.markdown("### 📋 TikToks existentes")
        
        tiktoks = get_tiktoks()
        if not tiktoks.empty:
            for _, t in tiktoks.iterrows():
                with st.expander(f"📱 {t['titulo']}"):
                    mostrar_tiktok(t['tiktok_url'], width_percent=25)
                    st.caption(f"📅 {t['fecha']}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✏️ MODIFICAR", key=f"edit_tik_{t['id']}"):
                            st.session_state.edit_tiktok = t.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR", key=f"del_tik_{t['id']}"):
                            if delete_tiktok(t['id']):
                                st.success("✅ TikTok eliminado")
                                st.rerun()
        else:
            st.info("No hay TikToks registrados")
    
    # --- MUSICA ---
    elif "🎵 Música" in admin_opt:
        st.subheader("🎵 Gestionar Música")
        st.info("📌 Sube tu música desde tu laptop (formato MP3)")
        
        with st.expander("➕ CREAR nueva canción", expanded=True):
            with st.form("fmus"):
                titulo = st.text_input("Título de la canción *")
                audio_file = st.file_uploader("Archivo de audio (MP3) *", type=["mp3"])
                
                if st.form_submit_button("📤 Agregar Música"):
                    if titulo and audio_file:
                        if add_musica(titulo, audio_file):
                            st.rerun()
                        else:
                            st.error("❌ Error al agregar música")
                    else:
                        st.error("❌ Título y archivo de audio son obligatorios")
        
        st.markdown("---")
        st.markdown("### 📋 Canciones existentes")
        
        musicas = get_musicas()
        if not musicas.empty:
            for _, m in musicas.iterrows():
                with st.expander(f"🎵 {m['titulo']}"):
                    if m.get('audio_url') and m['audio_url']:
                        mostrar_musica(m['audio_url'])
                        st.caption(f"📅 {m['fecha']}")
                    else:
                        st.warning("No hay URL de audio disponible")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✏️ MODIFICAR", key=f"edit_mus_{m['id']}"):
                            st.session_state.edit_musica = m.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR", key=f"del_mus_{m['id']}"):
                            if delete_musica(m['id']):
                                st.success("✅ Música eliminada")
                                st.rerun()
        else:
            st.info("No hay canciones registradas")
        
        if 'edit_musica' in st.session_state:
            m = st.session_state.edit_musica
            st.markdown("---")
            st.subheader(f"✏️ Modificando: {m['titulo']}")
            with st.form("edit_musica_form"):
                nuevo_titulo = st.text_input("Título", value=m['titulo'])
                nuevo_audio = st.file_uploader("Nuevo archivo de audio (opcional)", type=["mp3"])
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Guardar cambios"):
                        if update_musica(m['id'], nuevo_titulo, nuevo_audio):
                            st.success("✅ Música actualizada")
                            del st.session_state.edit_musica
                            st.rerun()
                with col2:
                    if st.form_submit_button("❌ Cancelar"):
                        del st.session_state.edit_musica
                        st.rerun()
    
    # --- DENUNCIAS ---
    elif "⚠️ Denuncias" in admin_opt:
        st.subheader("⚠️ Gestionar Denuncias")
        
        denuncias = get_denuncias()
        if not denuncias.empty:
            for _, d in denuncias.iterrows():
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
                            if update_denuncia_status(d['id'], nuevo_estado):
                                st.rerun()
                    with col2:
                        if st.button("🗑️ ELIMINAR denuncia", key=f"del_den_{d['id']}"):
                            if delete_denuncia(d['id']):
                                st.success("✅ Denuncia eliminada")
                                st.rerun()
        else:
            st.info("No hay denuncias registradas")
    
    # --- OPINIONES GENERALES ---
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
                            if st.button("✅ APROBAR", key=f"aprob_{op['id']}"):
                                if approve_opinion(op['id']):
                                    st.rerun()
                        with col2:
                            if st.button("🗑️ ELIMINAR", key=f"del_op_{op['id']}"):
                                if delete_opinion(op['id']):
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
                    if st.button("🗑️ ELIMINAR", key=f"del_op_aprob_{op['id']}"):
                        if delete_opinion(op['id']):
                            st.rerun()
        else:
            st.info("No hay opiniones aprobadas")
    
    # --- PERSONAJES ---
    elif "👥 Personajes" in admin_opt:
        st.subheader("👥 Gestionar Personajes")
        
        with st.expander("➕ CREAR nuevo personaje", expanded=True):
            with st.form("fpersonaje_admin"):
                nombre = st.text_input("Nombre del personaje *")
                fecha_personaje = st.date_input("Fecha a mostrar", value=datetime.now().date())
                descripcion = st.text_area("Biografía *")
                imagen = st.file_uploader("Imagen", type=["jpg", "png", "jpeg"])
                if st.form_submit_button("💾 Guardar Personaje"):
                    if nombre and descripcion:
                        if add_personaje(nombre, descripcion, imagen, fecha_personaje.strftime("%d/%m/%Y")):
                            st.success("✅ Personaje guardado")
                            st.rerun()
                        else:
                            st.error("❌ Error al guardar")
                    else:
                        st.error("❌ Nombre y biografía obligatorios")
        
        st.markdown("---")
        st.markdown("### 📋 Personajes Registrados")
        
        personajes = get_personajes()
        if not personajes.empty:
            for _, p in personajes.iterrows():
                with st.expander(f"👤 {p['nombre']} - {p['fecha']}"):
                    mostrar_imagen_segura(p.get('imagen_url'), 150)
                    st.write(f"**Biografía:** {p['descripcion']}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button(f"✏️ MODIFICAR", key=f"edit_{p['id']}"):
                            st.session_state.edit_personaje = p.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR", key=f"del_{p['id']}"):
                            if delete_personaje(p['id']):
                                st.success(f"✅ {p['nombre']} eliminado")
                                st.rerun()
                    with col3:
                        if st.button(f"⭐ DESTACAR HOY", key=f"destacar_{p['id']}"):
                            if update_personaje(p['id'], p['nombre'], p['descripcion'], None, datetime.now().strftime("%d/%m/%Y")):
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
        
        # Mostrar estadísticas de Me gusta (SOLO ADMIN)
        st.markdown("### ❤️ Estadísticas de Me gusta")
        col_est1, col_est2, col_est3 = st.columns(3)
        
        total_likes_admin = obtener_total_likes()
        likes_df_admin = obtener_lista_likes()
        
        with col_est1:
            st.metric("👍 Total Me gusta", total_likes_admin)
        
        with col_est2:
            likes_hoy = 0
            hoy_str = datetime.now().strftime("%Y-%m-%d")
            if not likes_df_admin.empty:
                for _, l in likes_df_admin.iterrows():
                    try:
                        fecha_like = datetime.fromisoformat(l['fecha']).strftime("%Y-%m-%d")
                        if fecha_like == hoy_str:
                            likes_hoy += 1
                    except:
                        pass
            st.metric("📅 Me gusta hoy", likes_hoy)
        
        with col_est3:
            st.metric("👥 Personas que apoyan", len(likes_df_admin))
        
        # Mostrar lista completa de Me gusta (solo admin)
        with st.expander("📋 Lista completa de Me gusta"):
            if not likes_df_admin.empty:
                for _, l in likes_df_admin.iterrows():
                    try:
                        fecha_like = datetime.fromisoformat(l['fecha']).strftime("%d/%m/%Y %H:%M")
                    except:
                        fecha_like = l['fecha'][:16] if len(l['fecha']) > 16 else l['fecha']
                    st.markdown(f"👍 **{l['usuario_nombre']}** - Tel: {l['usuario_telefono'] if l['usuario_telefono'] else 'No registrado'} - {fecha_like}")
            else:
                st.info("No hay Me gusta registrados")
        
        st.markdown("---")
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
                if save_logo(url_logo):
                    st.success("✅ Logo guardado")
                    st.rerun()
                else:
                    st.error("❌ Error al guardar logo")

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
        <p style="color: #ffd700; font-family: 'Times New Roman', serif; font-weight: bold;">Prohibida la reproducción total o parcial</p>
        <p style="color: #ffd700; font-family: 'Times New Roman', serif; font-weight: bold;">DERECHOS RESERVADOS</p>
        <p style="color: #ffd700; font-family: 'Times New Roman', serif; font-weight: bold;">Santa Teresa del Tuy, 2026</p>
    </div>
</div>
""", unsafe_allow_html=True)
