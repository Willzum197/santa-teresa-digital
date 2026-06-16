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
# URL DE LA IMAGEN DE FONDO
# ============================================
FONDO_URL = "https://assets.change.org/photos/0/lt/kp/EelTkpfkXQbEiEQ-800x450-noPad.jpg?1528608279"

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
# FUNCIONES DE ME GUSTA (HÍBRIDO)
# ============================================

def agregar_like_usuario(usuario_id):
    try:
        existing = supabase.table("likes").select("*").eq("usuario_id", usuario_id).eq("es_automatico", False).execute()
        
        if existing.data:
            return False, "Ya apoyaste esta página anteriormente"
        else:
            data = {
                "usuario_id": usuario_id,
                "fecha": datetime.now(pytz.UTC).isoformat(),
                "activo": True,
                "es_automatico": False
            }
            result = supabase.table("likes").insert(data).execute()
            return True if result.data else False, "Gracias por tu apoyo"
    except Exception as e:
        return False, str(e)

def agregar_likes_automaticos():
    try:
        response = supabase.table("likes").select("usuario_id").eq("es_automatico", True).order("id", desc=True).limit(1).execute()
        
        if response.data:
            last_id = response.data[0]["usuario_id"]
            import re
            match = re.search(r'auto_(\d+)', last_id)
            if match:
                lote = int(match.group(1)) + 1
            else:
                lote = 1
        else:
            lote = 1
        
        for i in range(2):
            data = {
                "usuario_id": f"auto_{lote}_{i}",
                "fecha": datetime.now(pytz.UTC).isoformat(),
                "activo": True,
                "es_automatico": True
            }
            supabase.table("likes").insert(data).execute()
        return 2
    except Exception as e:
        print(f"Error agregando likes automáticos: {e}")
        return 0

def obtener_total_likes():
    try:
        response = supabase.table("likes").select("*", count="exact").eq("activo", True).execute()
        return response.count if response.count else 0
    except Exception:
        return 0

def obtener_likes_reales():
    try:
        response = supabase.table("likes").select("*", count="exact").eq("activo", True).eq("es_automatico", False).execute()
        return response.count if response.count else 0
    except Exception:
        return 0

def obtener_likes_automaticos():
    try:
        response = supabase.table("likes").select("*", count="exact").eq("activo", True).eq("es_automatico", True).execute()
        return response.count if response.count else 0
    except Exception:
        return 0

def ya_dio_like(usuario_id):
    try:
        response = supabase.table("likes").select("*").eq("usuario_id", usuario_id).eq("es_automatico", False).execute()
        return len(response.data) > 0
    except Exception:
        return False

# ============================================
# FUNCIONES DE VISITAS
# ============================================

def actualizar_visitas():
    try:
        response = supabase.table("visitas").select("conteo").eq("id", 1).execute()
        
        if response.data:
            conteo_actual = response.data[0]["conteo"]
            nuevo_conteo = conteo_actual + 1
            
            visitas_procesadas = nuevo_conteo // 20
            visitas_anteriores_procesadas = conteo_actual // 20
            
            if visitas_procesadas > visitas_anteriores_procesadas:
                likes_agregados = agregar_likes_automaticos()
                if likes_agregados > 0:
                    st.session_state.likes_automaticos_agregados = likes_agregados
            
            supabase.table("visitas").update({"conteo": nuevo_conteo}).eq("id", 1).execute()
        else:
            supabase.table("visitas").insert({"id": 1, "conteo": 2500}).execute()
    except Exception:
        pass

def get_visitas():
    try:
        response = supabase.table("visitas").select("conteo").eq("id", 1).execute()
        if response.data:
            return int(response.data[0]["conteo"])
        return 2500
    except Exception:
        return 2500

# ============================================
# FUNCIONES DE COMENTARIOS
# ============================================
def get_fecha_hora_venezuela():
    caracas_tz = pytz.timezone('America/Caracas')
    return datetime.now(pytz.UTC).astimezone(caracas_tz)

def agregar_comentario(seccion, item_id, usuario, comentario):
    try:
        ahora = get_fecha_hora_venezuela()
        data = {
            "seccion": seccion,
            "item_id": str(item_id),
            "usuario": usuario if usuario else "Anónimo",
            "comentario": comentario,
            "fecha": ahora.strftime("%d/%m/%Y %H:%M"),
            "aprobado": True
        }
        result = supabase.table("comentarios").insert(data).execute()
        return True if result.data else False
    except Exception as e:
        st.error(f"Error al agregar comentario: {str(e)}")
        return False

def obtener_comentarios(seccion, item_id):
    try:
        response = supabase.table("comentarios").select("*").eq("seccion", seccion).eq("item_id", str(item_id)).eq("aprobado", True).order("id", desc=True).execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def mostrar_seccion_comentarios(seccion, item_id, titulo_item):
    st.markdown("---")
    st.markdown("### 💬 Comentarios y Opiniones")
    
    with st.form(key=f"comentario_form_{seccion}_{item_id}"):
        col_nom, col_com = st.columns([1, 3])
        with col_nom:
            nombre_com = st.text_input("Tu nombre", placeholder="Anónimo", key=f"nombre_{seccion}_{item_id}")
        with col_com:
            comentario_text = st.text_area("Escribe tu comentario u opinión", placeholder="Comparte tu opinión sobre este contenido...", key=f"comentario_{seccion}_{item_id}")
        
        if st.form_submit_button("📝 Enviar comentario"):
            if comentario_text and comentario_text.strip():
                if agregar_comentario(seccion, item_id, nombre_com if nombre_com else "Anónimo", comentario_text):
                    st.success("✅ ¡Comentario enviado correctamente!")
                    st.rerun()
                else:
                    st.error("❌ Error al enviar comentario")
            else:
                st.error("❌ Escribe un comentario antes de enviar")
    
    comentarios = obtener_comentarios(seccion, item_id)
    if not comentarios.empty:
        st.markdown(f"#### 📌 {len(comentarios)} comentarios")
        for _, com in comentarios.iterrows():
            with st.container():
                st.markdown(f"**👤 {com['usuario']}** *{com['fecha']}*")
                st.markdown(f"💬 {com['comentario']}")
                st.divider()
    else:
        st.info("💬 No hay comentarios aún. ¡Sé el primero en opinar!")

# ============================================
# FUNCIÓN DE OPTIMIZACIÓN DE IMÁGENES
# ============================================
def optimizar_imagen(file, max_width=1024, quality=75):
    try:
        if file is None: return None
        img = Image.open(file)
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        buffer.seek(0)
        class OptimizedFile:
            def __init__(self, buffer, original_name):
                self.buffer = buffer
                self.name = original_name.rsplit('.', 1)[0] + '.jpg'
                self.type = "image/jpeg"
                self.size = len(buffer.getvalue())
            def getvalue(self): return self.buffer.getvalue()
        return OptimizedFile(buffer, file.name)
    except Exception: return file

def subir_imagen_storage(file, carpeta="imagenes"):
    try:
        if file is None: return None
        archivo_optimizado = optimizar_imagen(file)
        if archivo_optimizado is None: return None
        nombre_archivo = f"{carpeta}/{uuid.uuid4()}.jpg"
        supabase.storage.from_("imagenes").upload(nombre_archivo, archivo_optimizado.getvalue(), {"content-type": "image/jpeg"})
        return supabase.storage.from_("imagenes").get_public_url(nombre_archivo)
    except Exception as e:
        st.error(f"Error al subir imagen: {str(e)}")
        return None

def subir_multiples_imagenes(files, carpeta):
    urls = []
    if files:
        for file in files:
            url = subir_imagen_storage(file, carpeta)
            if url: urls.append(url)
    return urls

def subir_audio_storage(file):
    try:
        if file is None: return None
        nombre_archivo = f"audio_{uuid.uuid4()}.mp3"
        supabase.storage.from_("imagenes").upload(nombre_archivo, file.getvalue(), {"content-type": "audio/mpeg"})
        return supabase.storage.from_("imagenes").get_public_url(nombre_archivo)
    except Exception as e:
        st.error(f"Error al subir audio: {str(e)}")
        return None

def update_musica(id_, titulo, audio_file=None):
    try:
        audio_url = None
        if audio_file:
            audio_url = subir_audio_storage(audio_file)
        else:
            existing = supabase.table("musicas").select("audio_url").eq("id", id_).execute()
            if existing.data: audio_url = existing.data[0].get("audio_url")
        supabase.table("musicas").update({"titulo": titulo, "audio_url": audio_url}).eq("id", id_).execute()
        return True
    except Exception as e:
        st.error(f"Error al actualizar música: {str(e)}")
        return False

def extraer_video_id(url_youtube):
    if not url_youtube: return None
    patterns = [r'(?:youtube\.com\/watch\?v=)([\w-]+)', r'(?:youtu\.be\/)([\w-]+)', r'(?:youtube\.com\/embed\/)([\w-]+)', r'(?:youtube\.com\/shorts\/)([\w-]+)']
    for pattern in patterns:
        match = re.search(pattern, url_youtube)
        if match: return match.group(1)
    return None

def mostrar_video_youtube(url_youtube, width_percent=25):
    video_id = extraer_video_id(url_youtube)
    if video_id:
        st.markdown(f'<div style="width:{width_percent}%"><iframe width="100%" height="200" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe></div>', unsafe_allow_html=True)
    else:
        st.error("URL de YouTube no válida")

def extraer_tiktok_id(url_tiktok):
    if not url_tiktok: return None
    patterns = [r'tiktok\.com/(?:@[\w.-]+/video/|v/|embed/)(\d+)', r'tiktok\.com/t/([\w-]+)']
    for pattern in patterns:
        match = re.search(pattern, url_tiktok)
        if match: return match.group(1)
    return None

def mostrar_tiktok(url_tiktok, width_percent=25):
    tiktok_id = extraer_tiktok_id(url_tiktok)
    if tiktok_id:
        st.markdown(f'<div style="width:{width_percent}%"><blockquote class="tiktok-embed" cite="{url_tiktok}"><a target="_blank" href="{url_tiktok}">Ver en TikTok</a></blockquote><script async src="https://www.tiktok.com/embed.js"></script></div>', unsafe_allow_html=True)
    else:
        st.markdown(f"📱 [Ver video en TikTok]({url_tiktok})")

def mostrar_imagenes_en_fila(urls, max_imagenes=3):
    if not urls: return
    cols = st.columns(min(len(urls), max_imagenes))
    for i, url in enumerate(urls[:max_imagenes]):
        with cols[i]: st.image(url, use_container_width=True)

def mostrar_imagen_segura(url, width=300, use_container_width=False):
    if url and isinstance(url, str) and url.startswith(('http://', 'https://')):
        if use_container_width: st.image(url, use_container_width=True)
        else: st.image(url, width=width)
        return True
    return False

# ============================================
# FUNCIONES CRUD COMPLETAS (RESUMIDAS)
# ============================================
def get_noticias(categoria=None):
    try:
        if categoria and categoria != "Todas":
            response = supabase.table("noticias").select("*").eq("categoria", categoria).order("id", desc=True).execute()
        else:
            response = supabase.table("noticias").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except: return pd.DataFrame()

def add_noticia(titulo, categoria, contenido, imagen):
    try:
        ahora = get_fecha_hora_venezuela()
        data = {"titulo": titulo, "categoria": categoria, "contenido": contenido, "imagen_url": subir_imagen_storage(imagen, "noticias") if imagen else None, "fecha": ahora.strftime("%d/%m/%Y"), "autor": "Admin"}
        supabase.table("noticias").insert(data).execute()
        return True
    except: return False

def update_noticia(id_, titulo, categoria, contenido, imagen):
    try:
        img_url = None
        if imagen: img_url = subir_imagen_storage(imagen, "noticias")
        else:
            existing = supabase.table("noticias").select("imagen_url").eq("id", id_).execute()
            if existing.data: img_url = existing.data[0].get("imagen_url")
        supabase.table("noticias").update({"titulo": titulo, "categoria": categoria, "contenido": contenido, "imagen_url": img_url}).eq("id", id_).execute()
        return True
    except: return False

def delete_noticia(id_):
    try: supabase.table("noticias").delete().eq("id", id_).execute(); return True
    except: return False

def get_negocios():
    try:
        response = supabase.table("negocios").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except: return pd.DataFrame()

def add_negocio(nombre, resena, google_maps_url, imagenes):
    try:
        ahora = get_fecha_hora_venezuela()
        data = {"nombre": nombre, "resena": resena, "google_maps_url": google_maps_url, "imagenes_url": subir_multiples_imagenes(imagenes, "negocios") if imagenes else [], "fecha": ahora.strftime("%d/%m/%Y")}
        supabase.table("negocios").insert(data).execute()
        return True
    except: return False

def update_negocio(id_, nombre, resena, google_maps_url, imagenes):
    try:
        imagenes_urls = subir_multiples_imagenes(imagenes, "negocios") if imagenes else None
        if not imagenes_urls:
            existing = supabase.table("negocios").select("imagenes_url").eq("id", id_).execute()
            if existing.data: imagenes_urls = existing.data[0].get("imagenes_url")
        supabase.table("negocios").update({"nombre": nombre, "resena": resena, "google_maps_url": google_maps_url, "imagenes_url": imagenes_urls if imagenes_urls else []}).eq("id", id_).execute()
        return True
    except: return False

def delete_negocio(id_):
    try: supabase.table("negocios").delete().eq("id", id_).execute(); return True
    except: return False

def add_opinion_negocio(negocio_id, usuario, comentario, calificacion):
    try:
        ahora = get_fecha_hora_venezuela()
        supabase.table("opiniones_negocios").insert({"negocio_id": negocio_id, "usuario": usuario, "comentario": comentario, "calificacion": calificacion, "fecha": ahora.strftime("%d/%m/%Y %H:%M"), "aprobada": True}).execute()
        return True
    except: return False

def get_opiniones_negocio(negocio_id):
    try:
        response = supabase.table("opiniones_negocios").select("*").eq("negocio_id", negocio_id).order("id", desc=True).execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except: return pd.DataFrame()

def delete_opinion_negocio(id_):
    try: supabase.table("opiniones_negocios").delete().eq("id", id_).execute(); return True
    except: return False

def get_reflexion_activa():
    try:
        response = supabase.table("reflexiones").select("*").eq("activo", True).limit(1).execute()
        if response.data: return response.data[0]
        response = supabase.table("reflexiones").select("*").order("id", desc=True).limit(1).execute()
        return response.data[0] if response.data else None
    except: return None

def get_reflexiones():
    try:
        response = supabase.table("reflexiones").select("*").order("fecha", desc=True).execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except: return pd.DataFrame()

def add_reflexion(titulo, contenido, versiculo):
    try:
        ahora = get_fecha_hora_venezuela()
        supabase.table("reflexiones").update({"activo": False}).execute()
        supabase.table("reflexiones").insert({"titulo": titulo, "contenido": contenido, "versiculo": versiculo, "fecha": ahora.strftime("%d/%m/%Y"), "activo": True}).execute()
        return True
    except: return False

def update_reflexion(id_, titulo, contenido, versiculo):
    try: supabase.table("reflexiones").update({"titulo": titulo, "contenido": contenido, "versiculo": versiculo}).eq("id", id_).execute(); return True
    except: return False

def delete_reflexion(id_):
    try: supabase.table("reflexiones").delete().eq("id", id_).execute(); return True
    except: return False

def get_cronicas(estado=None):
    try:
        if estado and estado != "Todos":
            response = supabase.table("cronicas").select("*").eq("estado", estado).order("id", desc=True).execute()
        else:
            response = supabase.table("cronicas").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except: return pd.DataFrame()

def add_cronica(titulo, contenido, lugar, estado, imagenes):
    try:
        ahora = get_fecha_hora_venezuela()
        supabase.table("cronicas").insert({"titulo": titulo, "contenido": contenido, "lugar": lugar, "estado": estado, "imagenes_url": subir_multiples_imagenes(imagenes, "cronicas") if imagenes else [], "fecha": ahora.strftime("%d/%m/%Y")}).execute()
        return True
    except: return False

def update_cronica(id_, titulo, contenido, lugar, estado, imagenes):
    try:
        imagenes_urls = subir_multiples_imagenes(imagenes, "cronicas") if imagenes else None
        if not imagenes_urls:
            existing = supabase.table("cronicas").select("imagenes_url").eq("id", id_).execute()
            if existing.data: imagenes_urls = existing.data[0].get("imagenes_url")
        supabase.table("cronicas").update({"titulo": titulo, "contenido": contenido, "lugar": lugar, "estado": estado, "imagenes_url": imagenes_urls}).eq("id", id_).execute()
        return True
    except: return False

def delete_cronica(id_):
    try: supabase.table("cronicas").delete().eq("id", id_).execute(); return True
    except: return False

def get_videos():
    try:
        response = supabase.table("videos").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except: return pd.DataFrame()

def add_video(titulo, url_youtube):
    try:
        if not extraer_video_id(url_youtube): return False
        ahora = get_fecha_hora_venezuela()
        supabase.table("videos").insert({"titulo": titulo, "video_url": url_youtube, "fecha": ahora.strftime("%d/%m/%Y")}).execute()
        return True
    except: return False

def update_video(id_, titulo, url_youtube):
    try: supabase.table("videos").update({"titulo": titulo, "video_url": url_youtube}).eq("id", id_).execute(); return True
    except: return False

def delete_video(id_):
    try: supabase.table("videos").delete().eq("id", id_).execute(); return True
    except: return False

def get_tiktoks():
    try:
        response = supabase.table("tiktoks").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except: return pd.DataFrame()

def add_tiktok(titulo, url_tiktok):
    try:
        ahora = get_fecha_hora_venezuela()
        supabase.table("tiktoks").insert({"titulo": titulo, "tiktok_url": url_tiktok, "fecha": ahora.strftime("%d/%m/%Y")}).execute()
        return True
    except: return False

def delete_tiktok(id_):
    try: supabase.table("tiktoks").delete().eq("id", id_).execute(); return True
    except: return False

def get_musicas():
    try:
        response = supabase.table("musicas").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except: return pd.DataFrame()

def add_musica(titulo, audio_file):
    try:
        ahora = get_fecha_hora_venezuela()
        audio_url = subir_audio_storage(audio_file)
        if not audio_url: return False
        supabase.table("musicas").insert({"titulo": titulo, "audio_url": audio_url, "fecha": ahora.strftime("%d/%m/%Y")}).execute()
        return True
    except: return False

def delete_musica(id_):
    try: supabase.table("musicas").delete().eq("id", id_).execute(); return True
    except: return False

def get_denuncias():
    try:
        response = supabase.table("denuncias").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except: return pd.DataFrame()

def add_denuncia(denunciante, titulo, descripcion, ubicacion):
    try:
        ahora = get_fecha_hora_venezuela()
        supabase.table("denuncias").insert({"denunciante": denunciante or "Anonimo", "titulo": titulo, "descripcion": descripcion, "ubicacion": ubicacion, "fecha": ahora.strftime("%d/%m/%Y"), "estatus": "Pendiente"}).execute()
        return True
    except: return False

def update_denuncia_status(id_, status):
    try: supabase.table("denuncias").update({"estatus": status}).eq("id", id_).execute(); return True
    except: return False

def delete_denuncia(id_):
    try: supabase.table("denuncias").delete().eq("id", id_).execute(); return True
    except: return False

def get_opiniones(aprobadas=True):
    try:
        if aprobadas:
            response = supabase.table("opiniones").select("*").eq("aprobada", True).order("id", desc=True).execute()
        else:
            response = supabase.table("opiniones").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except: return pd.DataFrame()

def add_opinion(usuario, comentario, calificacion):
    try:
        ahora = get_fecha_hora_venezuela()
        supabase.table("opiniones").insert({"usuario": usuario, "comentario": comentario, "calificacion": calificacion, "fecha": ahora.strftime("%d/%m/%Y %H:%M"), "aprobada": False}).execute()
        return True
    except: return False

def approve_opinion(id_):
    try: supabase.table("opiniones").update({"aprobada": True}).eq("id", id_).execute(); return True
    except: return False

def delete_opinion(id_):
    try: supabase.table("opiniones").delete().eq("id", id_).execute(); return True
    except: return False

def get_personajes():
    try:
        response = supabase.table("personajes").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except: return pd.DataFrame()

def add_personaje(nombre, descripcion, imagen, fecha):
    try:
        supabase.table("personajes").insert({"nombre": nombre, "descripcion": descripcion, "imagen_url": subir_imagen_storage(imagen, "personajes") if imagen else None, "fecha": fecha, "activo": True}).execute()
        return True
    except: return False

def update_personaje(id_, nombre, descripcion, imagen, fecha):
    try:
        img_url = None
        if imagen: img_url = subir_imagen_storage(imagen, "personajes")
        else:
            existing = supabase.table("personajes").select("imagen_url").eq("id", id_).execute()
            if existing.data: img_url = existing.data[0].get("imagen_url")
        supabase.table("personajes").update({"nombre": nombre, "descripcion": descripcion, "imagen_url": img_url, "fecha": fecha}).eq("id", id_).execute()
        return True
    except: return False

def delete_personaje(id_):
    try: supabase.table("personajes").delete().eq("id", id_).execute(); return True
    except: return False

def get_crimen_no_paga():
    try:
        response = supabase.table("crimen_no_paga").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except: return pd.DataFrame()

def add_crimen_no_paga(titulo, descripcion, imagenes):
    try:
        ahora = get_fecha_hora_venezuela()
        supabase.table("crimen_no_paga").insert({"titulo": titulo, "descripcion": descripcion, "imagenes_url": subir_multiples_imagenes(imagenes, "crimen") if imagenes else [], "fecha": ahora.strftime("%d/%m/%Y")}).execute()
        return True
    except: return False

def update_crimen_no_paga(id_, titulo, descripcion, imagenes):
    try:
        imagenes_urls = subir_multiples_imagenes(imagenes, "crimen") if imagenes else None
        if not imagenes_urls:
            existing = supabase.table("crimen_no_paga").select("imagenes_url").eq("id", id_).execute()
            if existing.data: imagenes_urls = existing.data[0].get("imagenes_url")
        supabase.table("crimen_no_paga").update({"titulo": titulo, "descripcion": descripcion, "imagenes_url": imagenes_urls}).eq("id", id_).execute()
        return True
    except: return False

def delete_crimen_no_paga(id_):
    try: supabase.table("crimen_no_paga").delete().eq("id", id_).execute(); return True
    except: return False

def get_logo():
    try:
        response = supabase.table("configuracion").select("logo_url").eq("id", 1).execute()
        return response.data[0].get("logo_url") if response.data else None
    except: return None

def save_logo(url):
    try: supabase.table("configuracion").update({"logo_url": url}).eq("id", 1).execute(); return True
    except: return False

def inicializar_configuracion():
    try:
        response = supabase.table("configuracion").select("*").eq("id", 1).execute()
        if not response.data: supabase.table("configuracion").insert({"id": 1, "logo_url": None, "dolar": 55.0}).execute()
    except: pass

inicializar_configuracion()

# ============================================
# CONFIGURACIÓN DE PÁGINA
# ============================================
st.set_page_config(page_title="Santa Teresa al Dia", page_icon="🇻🇪", layout="wide")

if 'visitante_contado' not in st.session_state:
    actualizar_visitas()
    st.session_state.visitante_contado = True

# ============================================
# ESTILOS
# ============================================
st.markdown(f"""
<style>
.stApp {{
    background: linear-gradient(rgba(0, 0, 0, 0.75), rgba(0, 0, 0, 0.75)), url('{FONDO_URL}') !important;
    background-size: cover !important;
    background-position: center !important;
    background-attachment: fixed !important;
}}
.block-container {{
    background-color: rgba(0, 0, 0, 0.85) !important;
    border-radius: 20px !important;
    padding: 20px !important;
}}
*, .main, .main p, .main span, .main div, .main label, .stMarkdown {{
    color: #FFFFFF !important;
    font-weight: bold !important;
}}
.main h1, .main h2, .main h3, .main h4 {{ color: #FFD700 !important; }}
a {{ color: #FFD700 !important; text-decoration: underline !important; }}
div[data-testid="stTabs"] button {{
    background-color: #1a1a1a !important;
    border: 1px solid #FFD700 !important;
    color: white !important;
    border-radius: 10px !important;
}}
div[data-testid="stTabs"] button:hover {{ background-color: #FFD700 !important; color: black !important; }}
.streamlit-expanderHeader {{ background-color: #1a1a1a !important; border-left: 4px solid #FFD700 !important; color: #FFD700 !important; }}
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, #87CEEB 0%, #4682B4 100%) !important; border-right: 3px solid #FFD700 !important; }}
[data-testid="stSidebar"] * {{ color: #1a1a2e !important; }}
input, textarea {{ background-color: #f0f0f0 !important; color: #000000 !important; border: 2px solid #FFD700 !important; border-radius: 12px !important; }}
.stButton > button {{ background: linear-gradient(135deg, #FFD700, #CF142B) !important; color: white !important; border-radius: 25px !important; }}
.bronze-footer {{ background: linear-gradient(145deg, #8c6a31, #5d431a) !important; border: 5px solid #d4af37 !important; padding: 35px 25px !important; border-radius: 20px !important; text-align: center !important; margin-top: 50px !important; }}
.bronze-footer p {{ color: #ffd700 !important; }}
[data-testid="stMetricValue"] {{ color: #FFD700 !important; font-size: 1.5rem !important; }}
</style>
""", unsafe_allow_html=True)

# ============================================
# LOGO
# ============================================
logo = get_logo()
if logo:
    st
