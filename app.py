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
# FUNCIONES DE COMENTARIOS Y OPINIONES (CON ADMIN)
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

def obtener_comentarios_todos(seccion=None):
    """Obtiene todos los comentarios para el admin, opcionalmente filtrados por sección"""
    try:
        if seccion:
            response = supabase.table("comentarios").select("*").eq("seccion", seccion).order("id", desc=True).execute()
        else:
            response = supabase.table("comentarios").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def eliminar_comentario(id_):
    try:
        supabase.table("comentarios").delete().eq("id", id_).execute()
        return True
    except Exception:
        return False

def actualizar_comentario(id_, nuevo_comentario):
    try:
        supabase.table("comentarios").update({"comentario": nuevo_comentario}).eq("id", id_).execute()
        return True
    except Exception:
        return False

# ============================================
# FUNCIÓN PARA MOSTRAR COMENTARIOS
# ============================================
def mostrar_seccion_comentarios(seccion, item_id, titulo_item, es_admin=False):
    st.markdown("---")
    st.markdown("### 💬 Comentarios y Opiniones")
    
    # Formulario para agregar comentario
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
    
    # Mostrar comentarios existentes
    comentarios = obtener_comentarios(seccion, item_id)
    if not comentarios.empty:
        st.markdown(f"#### 📌 {len(comentarios)} comentarios")
        for _, com in comentarios.iterrows():
            with st.container():
                col1, col2 = st.columns([8, 2])
                with col1:
                    st.markdown(f"**👤 {com['usuario']}** *{com['fecha']}*")
                    st.markdown(f"💬 {com['comentario']}")
                with col2:
                    if es_admin:
                        if st.button(f"🛠️", key=f"admin_com_{com['id']}_{seccion}_{item_id}", help="Gestionar comentario (solo admin)"):
                            st.session_state.edit_comentario_id = com['id']
                            st.session_state.edit_comentario_text = com['comentario']
                            st.session_state.edit_comentario_seccion = seccion
                            st.session_state.edit_comentario_item = item_id
                            st.rerun()
                st.divider()
    
    # Formulario de edición (si está activo)
    if st.session_state.get('edit_comentario_id') and st.session_state.edit_comentario_id:
        edit_id = st.session_state.edit_comentario_id
        if st.session_state.get('edit_comentario_seccion') == seccion and st.session_state.get('edit_comentario_item') == item_id:
            st.markdown("### ✏️ Editar comentario")
            with st.form(key=f"edit_com_form_{edit_id}_{seccion}_{item_id}"):
                nuevo_texto = st.text_area("Nuevo texto del comentario", value=st.session_state.edit_comentario_text)
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    if st.form_submit_button("💾 Guardar cambios"):
                        if actualizar_comentario(edit_id, nuevo_texto):
                            st.success("✅ Comentario actualizado")
                            del st.session_state.edit_comentario_id
                            if 'edit_comentario_text' in st.session_state:
                                del st.session_state.edit_comentario_text
                            if 'edit_comentario_seccion' in st.session_state:
                                del st.session_state.edit_comentario_seccion
                            if 'edit_comentario_item' in st.session_state:
                                del st.session_state.edit_comentario_item
                            st.rerun()
                with col2:
                    if st.form_submit_button("🗑️ Eliminar"):
                        if eliminar_comentario(edit_id):
                            st.success("✅ Comentario eliminado")
                            del st.session_state.edit_comentario_id
                            if 'edit_comentario_text' in st.session_state:
                                del st.session_state.edit_comentario_text
                            if 'edit_comentario_seccion' in st.session_state:
                                del st.session_state.edit_comentario_seccion
                            if 'edit_comentario_item' in st.session_state:
                                del st.session_state.edit_comentario_item
                            st.rerun()
                with col3:
                    if st.form_submit_button("❌ Cancelar"):
                        del st.session_state.edit_comentario_id
                        if 'edit_comentario_text' in st.session_state:
                            del st.session_state.edit_comentario_text
                        if 'edit_comentario_seccion' in st.session_state:
                            del st.session_state.edit_comentario_seccion
                        if 'edit_comentario_item' in st.session_state:
                            del st.session_state.edit_comentario_item
                        st.rerun()

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
# FUNCIONES CRUD COMPLETAS
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
st.set_page_config(page_title="Santa Teresa al Dia", page_icon="🇻🇪", layout="wide")

if 'visitante_contado' not in st.session_state:
    actualizar_visitas()
    st.session_state.visitante_contado = True

# ============================================
# ESTILOS - CON FONDO DE IMAGEN
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
.stInfo, .stSuccess, .stWarning, .stError {{ background-color: rgba(0,0,0,0.8) !important; color: white !important; }}
[data-testid="stMetricValue"] {{ color: #FFD700 !important; font-size: 1.5rem !important; }}
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
    <a href="https://api.whatsapp.com/send?text=Santa Teresa al Dia - {APP_URL}" target="_blank" style="display: inline-block; padding: 10px 25px; border-radius: 25px; background: #25D366;">📱 WhatsApp</a>
    <a href="https://www.facebook.com/sharer/sharer.php?u={APP_URL}" target="_blank" style="display: inline-block; padding: 10px 25px; border-radius: 25px; background: #1877F2;">📘 Facebook</a>
    <a href="https://www.instagram.com/" target="_blank" style="display: inline-block; padding: 10px 25px; border-radius: 25px; background: linear-gradient(45deg, #f09433, #d62976);">📸 Instagram</a>
    <button id="copyButton" style="display: inline-block; padding: 10px 25px; border-radius: 25px; background: #3498db; border: none; cursor: pointer;">📋 Copiar</button>
</div>
<script>
document.getElementById('copyButton').addEventListener('click', function() {{
    navigator.clipboard.writeText('{APP_URL}');
    alert('Enlace copiado: {APP_URL}');
}});
</script>
""", unsafe_allow_html=True)

st.markdown("---")

# ============================================
# ENCABEZADO PRINCIPAL
# ============================================
ahora = get_fecha_hora_venezuela()
dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
visitas = get_visitas()
dolar = get_dolar()
hora_str = ahora.strftime("%I:%M %p").lstrip("0")
total_likes = obtener_total_likes()

if 'usuario_id_permanente' not in st.session_state:
    query_params = st.query_params
    if 'uid' in query_params:
        st.session_state.usuario_id_permanente = query_params['uid']
    else:
        nuevo_id = hashlib.md5(f"{time.time()}_{uuid.uuid4()}".encode()).hexdigest()
        st.query_params['uid'] = nuevo_id
        st.session_state.usuario_id_permanente = nuevo_id

usuario_id_permanente = st.session_state.usuario_id_permanente
ya_like = ya_dio_like(usuario_id_permanente)

st.markdown(f"""
<div style="background: linear-gradient(135deg, #1a1a1a, #2a2a2a); border-radius: 20px; padding: 30px 20px; border: 2px solid #FFD700; margin-bottom: 20px; text-align: center;">
    <div style="font-size: 2.2em; font-weight: bold; color: #FFD700;">Santa Teresa al Dia</div>
    <div style="font-size: 1.2em; margin-bottom: 20px;">Informacion, Cultura y Fe de nuestro pueblo</div>
    <div style="font-size: 0.95em; color: #FFD700;">⭐ {dias[ahora.weekday()]}, {ahora.day} de {meses[ahora.month-1]} de {ahora.year} ⭐</div>
    <div style="font-size: 1.05em;">🕐 {hora_str}</div>
    <div style="font-size: 0.95em; color: #FFD700;">👥 Visitantes: {visitas:,} | 💵 Dólar BCV: {dolar:.2f} Bs</div>
    <div style="border-top: 1px solid rgba(255,215,0,0.3); margin-top: 15px; padding-top: 15px;">
        <div style="display: flex; justify-content: center; gap: 20px;">
            <div>❤️ Apoya</div>
            <div>👍 <span style="color:#FFD700; font-size:1.5em;">{total_likes:,}</span></div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

if not ya_like:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("👍 Dar Me gusta", use_container_width=True):
            exito, mensaje = agregar_like_usuario(usuario_id_permanente)
            if exito:
                st.success(f"✅ {mensaje}!")
                st.balloons()
                st.rerun()
            else:
                st.error(f"❌ {mensaje}")
else:
    st.info("❤️ ¡Gracias por tu apoyo!")

st.markdown("---")

# Mostrar mensaje de likes automáticos
if 'likes_automaticos_agregados' in st.session_state and st.session_state.likes_automaticos_agregados:
    st.info(f"🎉 ¡Gracias a la comunidad! Se han agregado {st.session_state.likes_automaticos_agregados} likes automáticos.")
    st.session_state.likes_automaticos_agregados = 0

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
            "💬 Opiniones", "👥 Personajes", "⚖️ El Crimen No Paga", "⚙️ Configuración"
        ])
        st.session_state.admin_opt = admin_opt
        st.session_state.es_admin = True
        
        st.markdown("---")
        st.markdown("### 📊 Estadísticas")
        st.metric("👍 Total Me gusta", f"{total_likes:,}")
        st.metric("👤 Likes reales", f"{obtener_likes_reales():,}")
        st.metric("🤖 Likes automáticos", f"{obtener_likes_automaticos():,}")
        st.metric("👥 Visitantes", f"{visitas:,}")
        
        with st.expander("🔧 Depuración"):
            st.code(f"Tu ID: {usuario_id_permanente}")
            st.code(f"¿Ya dio like?: {ya_like}")
    else:
        st.session_state.es_admin = False

# ============================================
# MENÚ PRINCIPAL
# ============================================
st.markdown("### 📌 Secciones Principales")
col_linea1 = st.columns(4)
with col_linea1[0]:
    if st.button("🏠 Portada", use_container_width=True, key="tab_0"):
        st.session_state.selected_tab = 0
with col_linea1[1]:
    if st.button("📰 Noticias", use_container_width=True, key="tab_1"):
        st.session_state.selected_tab = 1
with col_linea1[2]:
    if st.button("📍 Donde ir - Donde comprar", use_container_width=True, key="tab_2"):
        st.session_state.selected_tab = 2
with col_linea1[3]:
    if st.button("💭 Reflexiones", use_container_width=True, key="tab_3"):
        st.session_state.selected_tab = 3

st.markdown("### 🎬 Contenido Multimedia")
col_linea2 = st.columns(4)
with col_linea2[0]:
    if st.button("📜 Crónicas", use_container_width=True, key="tab_4"):
        st.session_state.selected_tab = 4
with col_linea2[1]:
    if st.button("🎬 Multimedia", use_container_width=True, key="tab_5"):
        st.session_state.selected_tab = 5
with col_linea2[2]:
    if st.button("⚠️ Denuncias", use_container_width=True, key="tab_6"):
        st.session_state.selected_tab = 6
with col_linea2[3]:
    if st.button("💬 Opiniones", use_container_width=True, key="tab_7"):
        st.session_state.selected_tab = 7

st.markdown("### 📖 Otras Secciones")
col_linea3 = st.columns(4)
with col_linea3[0]:
    if st.button("👥 Personajes", use_container_width=True, key="tab_8"):
        st.session_state.selected_tab = 8
with col_linea3[1]:
    if st.button("⚖️ El Crimen No Paga", use_container_width=True, key="tab_9"):
        st.session_state.selected_tab = 9
with col_linea3[2]:
    if st.button("📅 Efemérides Médicas", use_container_width=True, key="tab_10"):
        st.session_state.selected_tab = 10
with col_linea3[3]:
    st.markdown(" ")

st.markdown("---")

if 'selected_tab' not in st.session_state:
    st.session_state.selected_tab = 0

# ============================================
# CONTENIDO DE LAS SECCIONES
# ============================================

# --- PORTADA (TAB 0) ---
if st.session_state.selected_tab == 0:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📰 Últimas Noticias")
        noticias = get_noticias()
        if not noticias.empty:
            for _, n in noticias.head(5).iterrows():
                with st.expander(f"📰 {n['titulo']} - {n['categoria']} ({n['fecha']})"):
                    mostrar_imagen_segura(n.get('imagen_url'), 300)
                    st.write(n['contenido'])
                    mostrar_seccion_comentarios("noticia", n['id'], n['titulo'], es_admin)
        else:
            st.info("No hay noticias disponibles")
        
        st.markdown("### 📽️ Últimos Reportajes")
        reportajes = get_noticias(categoria="Reportajes")
        if not reportajes.empty:
            for _, r in reportajes.head(3).iterrows():
                with st.expander(f"📽️ {r['titulo']} - {r['fecha']}"):
                    mostrar_imagen_segura(r.get('imagen_url'), 300)
                    st.write(r['contenido'])
                    mostrar_seccion_comentarios("reportaje", r['id'], r['titulo'], es_admin)
        else:
            st.info("No hay reportajes disponibles")
    
    with col2:
        st.markdown("### ✝️ Reflexión del Día")
        ref = get_reflexion_activa()
        if ref:
            with st.expander(f"✨ {ref['titulo']}", expanded=True):
                st.write(ref['contenido'])
                if ref.get('versiculo'):
                    st.caption(f"📖 {ref['versiculo']}")
                mostrar_seccion_comentarios("reflexion", ref['id'], ref['titulo'], es_admin)
        else:
            st.info("No hay reflexión activa")
        
        st.markdown("---")
        st.markdown("### 💬 Opiniones de la Comunidad")
        
        opiniones_portada = get_opiniones(aprobadas=True)
        
        if not opiniones_portada.empty:
            for _, op in opiniones_portada.head(5).iterrows():
                stars = "⭐" * int(op['calificacion']) + "☆" * (5 - int(op['calificacion']))
                with st.container():
                    st.markdown(f"**👤 {op['usuario']}** {stars}")
                    st.markdown(f"\"{op['comentario']}\"")
                    st.caption(f"📅 {op['fecha']}")
                    st.divider()
            
            if len(opiniones_portada) > 5:
                st.caption(f"📌 Mostrando 5 de {len(opiniones_portada)} opiniones. Ve a la sección 'Opiniones' para ver todas.")
        else:
            st.info("💬 No hay opiniones aún. ¡Sé el primero en opinar!")

# --- NOTICIAS (TAB 1) ---
elif st.session_state.selected_tab == 1:
    st.title("📰 Noticias")
    tab_nac, tab_inter, tab_dep, tab_suc, tab_far, tab_rep = st.tabs(["🇻🇪 Nacionales", "🌎 Internacionales", "⚽ Deportes", "🚨 Sucesos", "🎭 Farándula", "📽️ Reportajes"])
    
    for tab, categoria in zip([tab_nac, tab_inter, tab_dep, tab_suc, tab_far, tab_rep], 
                               ["Nacional", "Internacional", "Deportes", "Sucesos", "Farándula", "Reportajes"]):
        with tab:
            noticias_cat = get_noticias(categoria=categoria)
            if not noticias_cat.empty:
                for _, n in noticias_cat.iterrows():
                    with st.expander(f"📰 {n['titulo']} - {n['fecha']}"):
                        mostrar_imagen_segura(n.get('imagen_url'), 300)
                        st.write(n['contenido'])
                        mostrar_seccion_comentarios("noticia" if categoria != "Reportajes" else "reportaje", n['id'], n['titulo'], es_admin)
            else:
                st.info(f"No hay noticias de {categoria}")

# --- NEGOCIOS (TAB 2) ---
elif st.session_state.selected_tab == 2:
    st.title("📍 Donde ir - Donde comprar")
    negocios = get_negocios()
    if not negocios.empty:
        for _, n in negocios.iterrows():
            with st.expander(f"🏪 {n['nombre']}"):
                if n.get('imagenes_url') and n['imagenes_url']:
                    if isinstance(n['imagenes_url'], list) and len(n['imagenes_url']) > 0:
                        mostrar_imagenes_en_fila(n['imagenes_url'], max_imagenes=3)
                    elif isinstance(n['imagenes_url'], str):
                        mostrar_imagen_segura(n['imagenes_url'], 300)
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

# --- REFLEXIONES (TAB 3) ---
elif st.session_state.selected_tab == 3:
    st.title("💭 Reflexiones")
    ref = get_reflexion_activa()
    if ref:
        with st.expander(f"✨ ACTUAL: {ref['titulo']}", expanded=True):
            st.write(ref['contenido'])
            if ref.get('versiculo'):
                st.caption(f"📖 {ref['versiculo']}")
            st.caption(f"📅 {ref['fecha']}")
            mostrar_seccion_comentarios("reflexion", ref['id'], ref['titulo'], es_admin)
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
                    mostrar_seccion_comentarios("reflexion", r['id'], r['titulo'], es_admin)
    else:
        st.info("No hay reflexiones anteriores")

# --- CRÓNICAS (TAB 4) ---
elif st.session_state.selected_tab == 4:
    st.title("📜 Crónicas")
    estados = ["Todos", "Miranda", "Carabobo", "Distrito Capital", "Zulia", "Lara", "Aragua", "Bolivar", "Anzoategui", "Merida", "Tachira", "Nueva Esparta", "Sucre", "Falcon", "Barinas", "Portuguesa", "Guarico", "Cojedes", "Trujillo", "Yaracuy", "Apure", "Amazonas", "Delta Amacuro", "Vargas"]
    estado_filtro = st.selectbox("Filtrar por estado:", estados)
    cronicas = get_cronicas(estado_filtro if estado_filtro != "Todos" else None)
    if not cronicas.empty:
        for _, c in cronicas.iterrows():
            with st.expander(f"📖 {c['titulo']} - {c['lugar']}, {c['estado']}"):
                if c.get('imagenes_url') and c['imagenes_url']:
                    if isinstance(c['imagenes_url'], list) and len(c['imagenes_url']) > 0:
                        mostrar_imagenes_en_fila(c['imagenes_url'], max_imagenes=3)
                    elif isinstance(c['imagenes_url'], str):
                        mostrar_imagen_segura(c['imagenes_url'], 200)
                st.write(c['contenido'])
                st.caption(f"📅 {c['fecha']}")
                
                # Mostrar comentarios con funcionalidad admin
                mostrar_seccion_comentarios("cronica", c['id'], c['titulo'], es_admin)
                
                # Panel de administración de la crónica (solo visible para admin)
                if es_admin:
                    st.markdown("---")
                    st.markdown("### 🔧 Administrar esta crónica")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✏️ MODIFICAR CRÓNICA", key=f"edit_cron_{c['id']}"):
                            st.session_state.edit_cronica = c.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR CRÓNICA", key=f"del_cron_{c['id']}"):
                            if delete_cronica(c['id']):
                                st.success("✅ Crónica eliminada")
                                st.rerun()
    else:
        st.info("No hay crónicas disponibles")
    
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

# --- MULTIMEDIA (TAB 5) ---
elif st.session_state.selected_tab == 5:
    st.title("🎬 Multimedia")
    tab_vid, tab_tik, tab_mus, tab_rad = st.tabs(["🎥 YouTube", "📱 TikTok", "🎵 Música", "📻 Radio"])
    
    with tab_vid:
        st.markdown("### 🎥 Videos de YouTube")
        videos = get_videos()
        if not videos.empty:
            for _, v in videos.iterrows():
                with st.expander(f"🎬 {v['titulo']}"):
                    mostrar_video_youtube(v['video_url'], width_percent=50)
                    st.caption(f"📅 {v['fecha']}")
                    mostrar_seccion_comentarios("video", v['id'], v['titulo'], es_admin)
        else:
            st.info("No hay videos disponibles")
    
    with tab_tik:
        st.markdown("### 📱 Videos de TikTok")
        tiktoks = get_tiktoks()
        if not tiktoks.empty:
            for _, t in tiktoks.iterrows():
                with st.expander(f"📱 {t['titulo']}"):
                    mostrar_tiktok(t['tiktok_url'], width_percent=50)
                    st.caption(f"📅 {t['fecha']}")
                    mostrar_seccion_comentarios("tiktok", t['id'], t['titulo'], es_admin)
        else:
            st.info("No hay videos de TikTok disponibles")
    
    with tab_mus:
        st.markdown("### 🎵 Lista de Música")
        musicas = get_musicas()
        if not musicas.empty:
            for _, m in musicas.iterrows():
                with st.expander(f"🎵 {m['titulo']}"):
                    if m.get('audio_url') and m['audio_url']:
                        st.audio(m['audio_url'], format="audio/mp3")
                        st.caption(f"📅 {m['fecha']}")
                    else:
                        st.warning("No hay URL de audio disponible")
                    mostrar_seccion_comentarios("musica", m['id'], m['titulo'], es_admin)
        else:
            st.info("No hay música disponible")
    
    with tab_rad:
        st.markdown("### 📻 Radio Online")
        
        st.markdown("#### 🎵 Estaciones de Radio")
        
        radio_opcion = st.selectbox("Selecciona una emisora:", [
            "🎵 80s Forever (Inglés)",
            "💕 Baladas Románticas (Inglés)",
            "🕺 Disco Hits 70s 80s",
            "🎺 Salsa Clásica"
        ])
        
        if radio_opcion == "🎵 80s Forever (Inglés)":
            st.audio("https://stream.zeno.fm/fsx7rzc2x1zuv", format="audio/mp3")
            st.caption("🎶 Madonna, Michael Jackson, Whitney Houston, Prince")
        elif radio_opcion == "💕 Baladas Románticas (Inglés)":
            st.audio("https://stream.zeno.fm/08f62gs7mg0uv", format="audio/mp3")
            st.caption("🎶 Air Supply, Chicago, Foreigner, Journey")
        elif radio_opcion == "🕺 Disco Hits 70s 80s":
            st.audio("https://stream.zeno.fm/76pz71spy7zuv", format="audio/mp3")
            st.caption("🎶 Bee Gees, ABBA, Donna Summer")
        elif radio_opcion == "🎺 Salsa Clásica":
            st.audio("https://stream.zeno.fm/cf6uxm5sd6quv", format="audio/mp3")
            st.caption("🎺 Héctor Lavoe, Celia Cruz, Rubén Blades")

# --- DENUNCIAS (TAB 6) ---
elif st.session_state.selected_tab == 6:
    st.title("⚠️ Denuncias Ciudadanas")
    
    tab_den, tab_ver = st.tabs(["📝 Hacer Denuncia", "👁️ Ver Denuncias"])
    
    with tab_den:
        st.markdown("### Formulario de Denuncia")
        st.info("Tu identidad se mantendrá en el anonimato si así lo deseas.")
        
        with st.form("form_denuncia"):
            nombre = st.text_input("Nombre (opcional - puede ser anónimo)")
            titulo = st.text_input("Título de la denuncia *")
            descripcion = st.text_area("Descripción detallada de los hechos *", height=150)
            ubicacion = st.text_input("Ubicación (sector, calle, dirección)")
            
            st.markdown("---")
            submitted = st.form_submit_button("📤 Enviar Denuncia", use_container_width=True)
            
            if submitted:
                if titulo and descripcion:
                    if add_denuncia(nombre, titulo, descripcion, ubicacion):
                        st.success("✅ ¡Denuncia enviada correctamente!")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("❌ Error al enviar la denuncia. Intenta nuevamente.")
                else:
                    st.error("❌ El título y la descripción son obligatorios.")
    
    with tab_ver:
        st.markdown("### Listado de Denuncias")
        denuncias = get_denuncias()
        
        if not denuncias.empty:
            for _, d in denuncias.iterrows():
                with st.expander(f"📌 {d['titulo']}"):
                    st.write(f"**Denunciante:** {d['denunciante']}")
                    st.write(f"**Descripción:** {d['descripcion']}")
                    if d.get('ubicacion') and d['ubicacion'] != "No especificada":
                        st.write(f"**Ubicación:** {d['ubicacion']}")
                    
                    if d['estatus'] == "Pendiente":
                        st.warning(f"**Estado:** {d['estatus']}")
                    elif d['estatus'] == "En revisión":
                        st.info(f"**Estado:** {d['estatus']}")
                    elif d['estatus'] == "Resuelta":
                        st.success(f"**Estado:** {d['estatus']}")
                    else:
                        st.error(f"**Estado:** {d['estatus']}")
                    st.caption(f"📅 Fecha: {d['fecha']}")
        else:
            st.info("No hay denuncias registradas aún.")

# --- OPINIONES (TAB 7) ---
elif st.session_state.selected_tab == 7:
    st.title("💬 Opiniones de la Comunidad")
    
    tab_op, tab_ver_op = st.tabs(["✍️ Dar Opinión", "👁️ Todas las Opiniones Aprobadas"])
    
    with tab_op:
        st.markdown("### Comparte tu opinión sobre Santa Teresa al Día")
        st.caption("Tu opinión será revisada por un administrador antes de ser publicada.")
        
        with st.form("form_opinion"):
            nombre = st.text_input("Nombre o apodo *")
            comentario = st.text_area("Tu comentario u opinión *", height=120)
            calificacion = st.slider("Calificación (1 a 5 estrellas)", 1, 5, 5)
            
            st.markdown("---")
            submitted = st.form_submit_button("📤 Enviar Opinión", use_container_width=True)
            
            if submitted:
                if nombre and comentario:
                    if add_opinion(nombre, comentario, calificacion):
                        st.success("✅ ¡Opinión enviada! Será revisada por el administrador.")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("❌ Error al enviar la opinión. Intenta nuevamente.")
                else:
                    st.error("❌ El nombre y el comentario son obligatorios.")
    
    with tab_ver_op:
        st.markdown("### Todas las Opiniones Aprobadas")
        opiniones = get_opiniones(aprobadas=True)
        
        if not opiniones.empty:
            for _, op in opiniones.iterrows():
                stars = "⭐" * int(op['calificacion']) + "☆" * (5 - int(op['calificacion']))
                st.markdown(f"**👤 {op['usuario']}** {stars}")
                st.write(f"\"{op['comentario']}\"")
                st.caption(f"📅 {op['fecha']}")
                st.divider()
        else:
            st.info("No hay opiniones aprobadas aún. ¡Sé el primero en dar tu opinión!")

# --- PERSONAJES (TAB 8) ---
elif st.session_state.selected_tab == 8:
    st.title("👥 Personajes que hicieron historia")
    st.markdown("### 📋 Personajes Registrados")
    personajes = get_personajes()
    if not personajes.empty:
        for _, p in personajes.iterrows():
            with st.expander(f"👤 {p['nombre']} - {p['fecha']}"):
                mostrar_imagen_segura(p.get('imagen_url'), 200)
                st.write(f"**Biografía:** {p['descripcion']}")
                mostrar_seccion_comentarios("personaje", p['id'], p['nombre'], es_admin)
    else:
        st.info("No hay personajes registrados")

# --- EL CRIMEN NO PAGA (TAB 9) ---
elif st.session_state.selected_tab == 9:
    st.title("⚖️ El Crimen No Paga")
    st.markdown("### Casos y noticias sobre justicia")
    crimenes = get_crimen_no_paga()
    if not crimenes.empty:
        for _, c in crimenes.iterrows():
            with st.expander(f"⚖️ {c['titulo']} - {c['fecha']}"):
                if c.get('imagenes_url') and c['imagenes_url']:
                    if isinstance(c['imagenes_url'], list) and len(c['imagenes_url']) > 0:
                        mostrar_imagenes_en_fila(c['imagenes_url'], max_imagenes=3)
                    elif isinstance(c['imagenes_url'], str):
                        mostrar_imagen_segura(c['imagenes_url'], 200)
                st.write(f"**Descripción:** {c['descripcion']}")
                st.caption(f"📅 Publicado: {c['fecha']}")
                mostrar_seccion_comentarios("crimen", c['id'], c['titulo'], es_admin)
    else:
        st.info("No hay casos registrados")

# --- EFEMÉRIDES MÉDICAS (TAB 10) ---
elif st.session_state.selected_tab == 10:
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
# PANEL ADMIN (COMPLETO - CON GESTIÓN DE COMENTARIOS EN CRÓNICAS)
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
    
    # --- CRÓNICAS (ADMIN) --- CON BOTÓN GENERAL PARA GESTIONAR COMENTARIOS
    elif "📜 Crónicas" in admin_opt:
        st.subheader("📜 Gestionar Crónicas")
        
        with st.expander("➕ CREAR nueva crónica", expanded=True):
            with st.form("fcronica_admin"):
                titulo = st.text_input("Título *")
                lugar = st.text_input("Lugar *")
                estado = st.selectbox("Estado", ["Miranda", "Carabobo", "Distrito Capital", "Zulia", "Lara", "Aragua", "Bolivar", "Anzoategui", "Merida", "Tachira", "Nueva Esparta", "Sucre", "Falcon", "Barinas", "Portuguesa", "Guarico", "Cojedes", "Trujillo", "Yaracuy", "Apure", "Amazonas", "Delta Amacuro", "Vargas"])
                contenido = st.text_area("Contenido *")
                imagenes = st.file_uploader("Fotos (máximo 3)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
                if len(imagenes) > 3:
                    st.error("Máximo 3 fotos por crónica")
                elif st.form_submit_button("➕ Agregar Crónica"):
                    if titulo and lugar and contenido:
                        if add_cronica(titulo, contenido, lugar, estado, imagenes):
                            st.success("✅ Crónica agregada correctamente")
                            st.rerun()
                        else:
                            st.error("❌ Error al agregar crónica")
                    else:
                        st.error("❌ Título, lugar y contenido son obligatorios")
        
        st.markdown("---")
        st.markdown("### 📋 Crónicas existentes")
        cronicas = get_cronicas()
        if not cronicas.empty:
            for _, c in cronicas.iterrows():
                with st.expander(f"📖 {c['titulo']} - {c['lugar']}, {c['estado']}"):
                    if c.get('imagenes_url') and c['imagenes_url']:
                        if isinstance(c['imagenes_url'], list):
                            for img_url in c['imagenes_url']:
                                mostrar_imagen_segura(img_url, 200)
                        elif isinstance(c['imagenes_url'], str):
                            mostrar_imagen_segura(c['imagenes_url'], 200)
                    st.write(f"**Contenido:** {c['contenido']}")
                    st.caption(f"📅 {c['fecha']}")
                    
                    # BOTÓN GENERAL PARA GESTIONAR COMENTARIOS DE ESTA CRÓNICA
                    if st.button(f"💬 GESTIONAR COMENTARIOS", key=f"gestionar_com_cron_admin_{c['id']}"):
                        st.session_state.gestionar_comentarios_cronica = c['id']
                        st.rerun()
                    
                    # Gestión de comentarios con botón general para eliminar/modificar
                    if st.session_state.get('gestionar_comentarios_cronica') == c['id']:
                        st.markdown("---")
                        st.markdown("### 💬 Gestión de Comentarios")
                        
                        # Obtener comentarios de esta crónica
                        comentarios_cronica = obtener_comentarios_todos(seccion="cronica")
                        comentarios_filtrados = comentarios_cronica[comentarios_cronica['item_id'] == str(c['id'])] if not comentarios_cronica.empty else pd.DataFrame()
                        
                        if comentarios_filtrados.empty:
                            st.info("Esta crónica no tiene comentarios")
                        else:
                            st.markdown(f"**Total de comentarios:** {len(comentarios_filtrados)}")
                            
                            # Botón para eliminar TODOS los comentarios
                            if st.button(f"🗑️ ELIMINAR TODOS LOS COMENTARIOS", key=f"eliminar_todos_cron_{c['id']}"):
                                if st.session_state.get(f'confirmar_eliminar_cron_{c['id']}', False):
                                    for _, com in comentarios_filtrados.iterrows():
                                        eliminar_comentario(com['id'])
                                    st.success(f"✅ Se eliminaron {len(comentarios_filtrados)} comentarios")
                                    st.session_state[f'confirmar_eliminar_cron_{c['id']}'] = False
                                    st.rerun()
                                else:
                                    st.session_state[f'confirmar_eliminar_cron_{c['id']}'] = True
                                    st.warning("⚠️ ¡CONFIRMAR! Haz clic nuevamente en ELIMINAR TODOS para confirmar")
                            
                            st.markdown("---")
                            
                            # Mostrar comentarios individuales con opciones de modificar y eliminar
                            for idx, com in comentarios_filtrados.iterrows():
                                with st.container():
                                    # Usar un key único para el text area
                                    text_key = f"text_cron_{com['id']}_{c['id']}"
                                    
                                    col1, col2, col3 = st.columns([6, 2, 2])
                                    with col1:
                                        st.markdown(f"**👤 {com['usuario']}** *{com['fecha']}*")
                                        # Text area para editar el comentario
                                        nuevo_texto = st.text_area(
                                            f"Comentario", 
                                            value=com['comentario'], 
                                            key=text_key,
                                            label_visibility="collapsed"
                                        )
                                    with col2:
                                        if st.button(f"💾 Guardar", key=f"guardar_cron_{com['id']}_{c['id']}"):
                                            # Obtener el valor actual del text area
                                            texto_actualizado = st.session_state.get(text_key, com['comentario'])
                                            if actualizar_comentario(com['id'], texto_actualizado):
                                                st.success("✅ Comentario actualizado")
                                                st.rerun()
                                            else:
                                                st.error("❌ Error al actualizar")
                                    with col3:
                                        if st.button(f"🗑️ Eliminar", key=f"eliminar_cron_{com['id']}_{c['id']}"):
                                            if eliminar_comentario(com['id']):
                                                st.success("✅ Comentario eliminado")
                                                st.rerun()
                                            else:
                                                st.error("❌ Error al eliminar")
                                    st.divider()
                        
                        # Botón para cerrar la gestión
                        if st.button("❌ Cerrar gestión de comentarios", key=f"cerrar_gestion_cron_{c['id']}"):
                            del st.session_state.gestionar_comentarios_cronica
                            if f'confirmar_eliminar_cron_{c['id']}' in st.session_state:
                                del st.session_state[f'confirmar_eliminar_cron_{c['id']}']
                            st.rerun()
                    
                    # Botones de acción para la crónica
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✏️ MODIFICAR", key=f"edit_cron_admin_{c['id']}"):
                            st.session_state.edit_cronica = c.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR", key=f"del_cron_admin_{c['id']}"):
                            if delete_cronica(c['id']):
                                st.success("✅ Crónica eliminada")
                                st.rerun()
        else:
            st.info("No hay crónicas registradas")
        
        if 'edit_cronica' in st.session_state:
            c = st.session_state.edit_cronica
            st.markdown("---")
            st.subheader(f"✏️ Modificando: {c['titulo']}")
            with st.form("edit_cronica_admin_form"):
                nuevo_titulo = st.text_input("Título", value=c['titulo'])
                nuevo_lugar = st.text_input("Lugar", value=c['lugar'])
                nuevo_estado = st.selectbox("Estado", ["Miranda", "Carabobo", "Distrito Capital", "Zulia", "Lara", "Aragua", "Bolivar", "Anzoategui", "Merida", "Tachira", "Nueva Esparta", "Sucre", "Falcon", "Barinas", "Portuguesa", "Guarico", "Cojedes", "Trujillo", "Yaracuy", "Apure", "Amazonas", "Delta Amacuro", "Vargas"], index=["Miranda", "Carabobo", "Distrito Capital", "Zulia", "Lara", "Aragua", "Bolivar", "Anzoategui", "Merida", "Tachira", "Nueva Esparta", "Sucre", "Falcon", "Barinas", "Portuguesa", "Guarico", "Cojedes", "Trujillo", "Yaracuy", "Apure", "Amazonas", "Delta Amacuro", "Vargas"].index(c['estado']))
                nuevo_contenido = st.text_area("Contenido", value=c['contenido'])
                nuevas_imagenes = st.file_uploader("Nuevas fotos (opcional, máximo 3)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
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
                    mostrar_video_youtube(v['video_url'], width_percent=50)
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
                    mostrar_tiktok(t['tiktok_url'], width_percent=50)
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
                        st.audio(m['audio_url'], format="audio/mp3")
                        st.caption(f"📅 {m['fecha']}")
                    else:
                        st.warning("No hay URL de audio disponible")
                    mostrar_seccion_comentarios("musica", m['id'], m['titulo'], es_admin)
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
    
    # --- DENUNCIAS (ADMIN) ---
    elif "⚠️ Denuncias" in admin_opt:
        st.subheader("⚠️ Gestionar Denuncias")
        
        denuncias = get_denuncias()
        if not denuncias.empty:
            for _, d in denuncias.iterrows():
                with st.expander(f"📌 {d['titulo']} - {d['estatus']}"):
                    st.write(f"**Denunciante:** {d['denunciante']}")
                    st.write(f"**Descripción:** {d['descripcion']}")
                    st.write(f"**Ubicación:** {d['ubicacion']}")
                    st.caption(f"📅 {d['fecha']}")
                    
                    nuevo_estado = st.selectbox("Cambiar estado:", ["Pendiente", "En revisión", "Resuelta", "Descartada"], 
                                               index=["Pendiente", "En revisión", "Resuelta", "Descartada"].index(d['estatus']),
                                               key=f"est_{d['id']}")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Actualizar estado", key=f"upd_{d['id']}"):
                            if update_denuncia_status(d['id'], nuevo_estado):
                                st.success("Estado actualizado")
                                st.rerun()
                    with col2:
                        if st.button("🗑️ ELIMINAR denuncia", key=f"del_den_{d['id']}"):
                            if delete_denuncia(d['id']):
                                st.success("Denuncia eliminada")
                                st.rerun()
        else:
            st.info("No hay denuncias registradas")
    
    # --- OPINIONES GENERALES (ADMIN) ---
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
                                    st.success("Opinión aprobada")
                                    st.rerun()
                        with col2:
                            if st.button("🗑️ ELIMINAR", key=f"del_op_{op['id']}"):
                                if delete_opinion(op['id']):
                                    st.success("Opinión eliminada")
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
                            st.success("Opinión eliminada")
                            st.rerun()
        else:
            st.info("No hay opiniones aprobadas")
    
    # --- PERSONAJES (ADMIN) ---
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
    
    # --- EL CRIMEN NO PAGA (ADMIN) ---
    elif "⚖️ El Crimen No Paga" in admin_opt:
        st.subheader("⚖️ Gestionar El Crimen No Paga")
        
        with st.expander("➕ CREAR nuevo caso", expanded=True):
            with st.form("fcrimen"):
                titulo = st.text_input("Título del caso *")
                descripcion = st.text_area("Descripción *")
                imagenes = st.file_uploader("Fotos (máximo 3)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
                if len(imagenes) > 3:
                    st.error("Máximo 3 fotos por caso")
                elif st.form_submit_button("➕ Agregar Caso"):
                    if titulo and descripcion:
                        if add_crimen_no_paga(titulo, descripcion, imagenes):
                            st.success("✅ Caso agregado correctamente")
                            st.rerun()
                        else:
                            st.error("❌ Error al agregar caso")
                    else:
                        st.error("❌ Título y descripción son obligatorios")
        
        st.markdown("---")
        st.markdown("### 📋 Casos existentes")
        crimenes = get_crimen_no_paga()
        if not crimenes.empty:
            for _, c in crimenes.iterrows():
                with st.expander(f"⚖️ {c['titulo']} - {c['fecha']}"):
                    if c.get('imagenes_url') and c['imagenes_url']:
                        if isinstance(c['imagenes_url'], list):
                            for img_url in c['imagenes_url']:
                                mostrar_imagen_segura(img_url, 200)
                        elif isinstance(c['imagenes_url'], str):
                            mostrar_imagen_segura(c['imagenes_url'], 200)
                    st.write(f"**Descripción:** {c['descripcion']}")
                    st.caption(f"📅 Publicado: {c['fecha']}")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✏️ MODIFICAR", key=f"edit_crimen_{c['id']}"):
                            st.session_state.edit_crimen = c.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR", key=f"del_crimen_{c['id']}"):
                            if delete_crimen_no_paga(c['id']):
                                st.success("✅ Caso eliminado")
                                st.rerun()
        else:
            st.info("No hay casos registrados")
        
        if 'edit_crimen' in st.session_state:
            c = st.session_state.edit_crimen
            st.markdown("---")
            st.subheader(f"✏️ Modificando: {c['titulo']}")
            with st.form("edit_crimen_form"):
                nuevo_titulo = st.text_input("Título", value=c['titulo'])
                nueva_descripcion = st.text_area("Descripción", value=c['descripcion'])
                nuevas_imagenes = st.file_uploader("Nuevas fotos (opcional, máximo 3)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Guardar cambios"):
                        if update_crimen_no_paga(c['id'], nuevo_titulo, nueva_descripcion, nuevas_imagenes):
                            st.success("✅ Caso actualizado")
                            del st.session_state.edit_crimen
                            st.rerun()
                with col2:
                    if st.form_submit_button("❌ Cancelar"):
                        del st.session_state.edit_crimen
                        st.rerun()
    
    # --- CONFIGURACION ---
    elif "⚙️ Configuración" in admin_opt:
        st.subheader("⚙️ Configuración del Sistema")
        
        st.markdown("### ❤️ Estadísticas de Me gusta")
        col_est1, col_est2, col_est3 = st.columns(3)
        total_likes_admin = obtener_total_likes()
        likes_reales_admin = obtener_likes_reales()
        likes_auto_admin = obtener_likes_automaticos()
        
        with col_est1:
            st.metric("👍 Total Me gusta", f"{total_likes_admin:,}")
        with col_est2:
            st.metric("👤 Likes reales", f"{likes_reales_admin:,}")
        with col_est3:
            st.metric("🤖 Likes automáticos", f"{likes_auto_admin:,}")
        
        st.markdown("---")
        st.markdown("### 👥 Estadísticas de Visitantes")
        visitas_admin = get_visitas()
        st.metric("🚪 Total Visitantes", f"{visitas_admin:,}")
        st.caption("💡 Cada 20 visitas se agregan 2 likes automáticos")
        
        st.markdown("---")
        st.markdown("### 💬 Estadísticas de Comentarios")
        try:
            response = supabase.table("comentarios").select("*", count="exact").execute()
            total_comentarios = response.count if response.count else 0
            st.metric("📝 Total Comentarios", total_comentarios)
        except:
            st.info("No hay comentarios registrados")
        
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
        logo_actual = get_logo()
        if logo_actual:
            st.image(logo_actual, width=150)
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
