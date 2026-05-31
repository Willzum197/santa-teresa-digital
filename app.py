import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
from supabase import create_client, Client
from PIL import Image
import io
import uuid
import re
import hashlib
import time

# ============================================
# CONFIGURACION SUPABASE
# ============================================
def init_supabase():
    try:
        supabase_url = st.secrets["SUPABASE_URL"]
        supabase_key = st.secrets["SUPABASE_KEY"]
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        st.error(f"Error de conexión con Supabase: {str(e)}")
        st.stop()

supabase = init_supabase()

# ============================================
# 🔥 AQUÍ PONES LA URL DE LA IMAGEN DE FONDO 🔥
# ============================================
# PEGA AQUÍ LA URL DE LA IMAGEN QUE QUIERAS USAR
FONDO_URL = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcT37-Oz8QN1gFWPwiCOFW1zS1DDySvQBe3W4g&s"

# Si esa URL no funciona, prueba con esta otra (bandera de Venezuela)
# FONDO_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Flag_of_Venezuela_%28state%29.svg/1920px-Flag_of_Venezuela_%28state%29.svg.png"

# ============================================
# FUNCIONES BÁSICAS
# ============================================
def get_fecha_hora_venezuela():
    caracas_tz = pytz.timezone('America/Caracas')
    return datetime.now(pytz.UTC).astimezone(caracas_tz)

def get_dolar():
    try:
        response = supabase.table("configuracion").select("dolar").eq("id", 1).execute()
        if response.data and response.data[0].get("dolar"):
            return float(response.data[0]["dolar"])
        return 55.0
    except:
        return 55.0

def actualizar_dolar_manual(nuevo_valor):
    try:
        supabase.table("configuracion").update({"dolar": nuevo_valor}).eq("id", 1).execute()
        return True
    except:
        return False

def get_visitas():
    try:
        response = supabase.table("visitas").select("conteo").eq("id", 1).execute()
        if response.data:
            return int(response.data[0]["conteo"])
        return 2500
    except:
        return 2500

def actualizar_visitas():
    try:
        response = supabase.table("visitas").select("conteo").eq("id", 1).execute()
        if response.data:
            nuevo_conteo = response.data[0]["conteo"] + 1
            supabase.table("visitas").update({"conteo": nuevo_conteo}).eq("id", 1).execute()
        else:
            supabase.table("visitas").insert({"id": 1, "conteo": 2501}).execute()
    except:
        pass

def obtener_total_likes():
    try:
        response = supabase.table("likes").select("*", count="exact").eq("activo", True).execute()
        return response.count if response.count else 0
    except:
        return 0

def ya_dio_like(usuario_id):
    try:
        response = supabase.table("likes").select("*").eq("usuario_id", usuario_id).eq("es_automatico", False).execute()
        return len(response.data) > 0
    except:
        return False

def agregar_like_usuario(usuario_id):
    try:
        existing = supabase.table("likes").select("*").eq("usuario_id", usuario_id).eq("es_automatico", False).execute()
        if existing.data:
            return False, "Ya apoyaste esta página"
        data = {
            "usuario_id": usuario_id,
            "fecha": datetime.now(pytz.UTC).isoformat(),
            "activo": True,
            "es_automatico": False
        }
        supabase.table("likes").insert(data).execute()
        return True, "Gracias por tu apoyo"
    except Exception as e:
        return False, str(e)

def agregar_comentario(seccion, item_id, usuario, comentario):
    try:
        ahora = get_fecha_hora_venezuela()
        data = {
            "seccion": seccion, "item_id": item_id,
            "usuario": usuario or "Anónimo", "comentario": comentario,
            "fecha": ahora.strftime("%d/%m/%Y %H:%M"), "aprobado": True
        }
        supabase.table("comentarios").insert(data).execute()
        return True
    except:
        return False

def obtener_comentarios(seccion, item_id):
    try:
        response = supabase.table("comentarios").select("*").eq("seccion", seccion).eq("item_id", item_id).eq("aprobado", True).order("id", desc=True).execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except:
        return pd.DataFrame()

def mostrar_seccion_comentarios(seccion, item_id, titulo_item):
    st.markdown("---")
    st.markdown("### 💬 Comentarios y Opiniones")
    with st.form(key=f"comentario_form_{seccion}_{item_id}"):
        nombre_com = st.text_input("Tu nombre", placeholder="Anónimo", key=f"nombre_{seccion}_{item_id}")
        comentario_text = st.text_area("Escribe tu comentario", key=f"comentario_{seccion}_{item_id}")
        if st.form_submit_button("📝 Enviar comentario"):
            if comentario_text and comentario_text.strip():
                if agregar_comentario(seccion, item_id, nombre_com, comentario_text):
                    st.success("✅ ¡Comentario enviado!")
                    st.rerun()
            else:
                st.error("❌ Escribe un comentario")
    comentarios = obtener_comentarios(seccion, item_id)
    if not comentarios.empty:
        for _, com in comentarios.iterrows():
            st.markdown(f"**👤 {com['usuario']}** *{com['fecha']}*")
            st.markdown(f"💬 {com['comentario']}")
            st.divider()

def extraer_video_id(url_youtube):
    patterns = [r'(?:youtube\.com\/watch\?v=)([\w-]+)', r'(?:youtu\.be\/)([\w-]+)']
    for pattern in patterns:
        match = re.search(pattern, url_youtube)
        if match:
            return match.group(1)
    return None

def mostrar_video_youtube(url_youtube, width_percent=25):
    video_id = extraer_video_id(url_youtube)
    if video_id:
        st.markdown(f'<div style="width:{width_percent}%"><iframe width="100%" height="200" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe></div>', unsafe_allow_html=True)

def mostrar_imagen_segura(url, width=300):
    if url and isinstance(url, str) and url.startswith(('http://', 'https://')):
        st.image(url, width=width)
        return True
    return False

# ============================================
# FUNCIONES CRUD SIMPLIFICADAS (ejemplos)
# ============================================
def get_noticias(categoria=None):
    try:
        if categoria and categoria != "Todas":
            response = supabase.table("noticias").select("*").eq("categoria", categoria).order("id", desc=True).execute()
        else:
            response = supabase.table("noticias").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except:
        return pd.DataFrame()

def get_reflexion_activa():
    try:
        response = supabase.table("reflexiones").select("*").eq("activo", True).limit(1).execute()
        if response.data:
            return response.data[0]
        response = supabase.table("reflexiones").select("*").order("id", desc=True).limit(1).execute()
        return response.data[0] if response.data else None
    except:
        return None

def get_negocios():
    try:
        response = supabase.table("negocios").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except:
        return pd.DataFrame()

# ... (el resto de funciones CRUD son similares a las originales)

# ============================================
# CONFIGURACIÓN DE PÁGINA
# ============================================
st.set_page_config(page_title="Santa Teresa al Dia", page_icon="🇻🇪", layout="wide")

# Inicializar visitas
if 'visitante_contado' not in st.session_state:
    actualizar_visitas()
    st.session_state.visitante_contado = True

# ============================================
# 🎨 ESTILOS CON LA IMAGEN DE FONDO
# ============================================
st.markdown(f"""
<style>
.stApp {{
    background: linear-gradient(rgba(0, 0, 0, 0.75), rgba(0, 0, 0, 0.75)), url('{FONDO_URL}');
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}}
.block-container {{
    background-color: rgba(0, 0, 0, 0.85) !important;
    border-radius: 20px !important;
    padding: 20px !important;
}}
* {{ color: #FFFFFF !important; font-weight: bold !important; }}
h1, h2, h3, h4 {{ color: #FFD700 !important; }}
a {{ color: #FFD700 !important; }}
div[data-testid="stTabs"] button {{
    background-color: #1a1a1a !important;
    border: 1px solid #FFD700 !important;
    color: white !important;
}}
.stButton > button {{
    background: linear-gradient(135deg, #FFD700, #CF142B) !important;
    color: white !important;
    border-radius: 25px !important;
}}
.bronze-footer {{
    background: linear-gradient(145deg, #8c6a31, #5d431a) !important;
    border: 5px solid #d4af37 !important;
    padding: 20px !important;
    border-radius: 20px !important;
    text-align: center !important;
    margin-top: 30px !important;
}}
</style>
""", unsafe_allow_html=True)

# ============================================
# ENCABEZADO PRINCIPAL (CON RECUADRO CORREGIDO)
# ============================================
ahora = get_fecha_hora_venezuela()
dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

visitas = get_visitas()
dolar = get_dolar()
hora_str = ahora.strftime("%I:%M %p").lstrip("0")
total_likes = obtener_total_likes()

# ID de usuario para like
if 'usuario_id' not in st.session_state:
    nuevo_id = hashlib.md5(f"{time.time()}_{uuid.uuid4()}".encode()).hexdigest()
    st.session_state.usuario_id = nuevo_id
    st.query_params['uid'] = nuevo_id

usuario_id = st.session_state.usuario_id
ya_dio_like_usuario = ya_dio_like(usuario_id)

# RECUADRO PRINCIPAL (AHORA SÍ SE VE BIEN)
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

# Botón Me gusta
if not ya_dio_like_usuario:
    if st.button("👍 Dar Me gusta", use_container_width=True):
        exito, mensaje = agregar_like_usuario(usuario_id)
        if exito:
            st.success(f"✅ {mensaje}")
            st.balloons()
            st.rerun()
        else:
            st.error(f"❌ {mensaje}")
else:
    st.info("❤️ ¡Gracias por tu apoyo!")

st.markdown("---")

# ============================================
# MENÚ PRINCIPAL
# ============================================
st.markdown("### 📌 Secciones Principales")
cols = st.columns(4)
secciones = ["🏠 Portada", "📰 Noticias", "📍 Negocios", "💭 Reflexiones"]
for i, sec in enumerate(secciones):
    with cols[i]:
        if st.button(sec, use_container_width=True, key=f"tab_{i}"):
            st.session_state.tab = i

st.markdown("---")

if 'tab' not in st.session_state:
    st.session_state.tab = 0

# ============================================
# CONTENIDO POR SECCIÓN (VERSIÓN RESUMIDA PERO FUNCIONAL)
# ============================================
if st.session_state.tab == 0:  # Portada
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📰 Últimas Noticias")
        noticias = get_noticias()
        if not noticias.empty:
            for _, n in noticias.head(3).iterrows():
                with st.expander(f"📰 {n['titulo']}"):
                    if n.get('imagen_url'):
                        mostrar_imagen_segura(n['imagen_url'], 200)
                    st.write(n['contenido'][:200] + "...")
                    mostrar_seccion_comentarios("noticia", n['id'], n['titulo'])
    with col2:
        st.markdown("### ✝️ Reflexión del Día")
        ref = get_reflexion_activa()
        if ref:
            with st.expander(f"✨ {ref['titulo']}", expanded=True):
                st.write(ref['contenido'])
                if ref.get('versiculo'):
                    st.caption(f"📖 {ref['versiculo']}")
                mostrar_seccion_comentarios("reflexion", ref['id'], ref['titulo'])
        st.markdown("### 🏪 Negocio Destacado")
        negocios = get_negocios()
        if not negocios.empty:
            n = negocios.iloc[0]
            st.markdown(f"**{n['nombre']}**")
            st.write(n['resena'][:150] + "...")

elif st.session_state.tab == 1:  # Noticias
    st.title("📰 Noticias")
    categorias = ["Nacional", "Internacional", "Deportes", "Sucesos", "Farándula", "Reportajes"]
    tabs = st.tabs(categorias)
    for tab, cat in zip(tabs, categorias):
        with tab:
            noticias = get_noticias(categoria=cat)
            if not noticias.empty:
                for _, n in noticias.iterrows():
                    with st.expander(f"{n['titulo']} - {n['fecha']}"):
                        if n.get('imagen_url'):
                            mostrar_imagen_segura(n['imagen_url'], 300)
                        st.write(n['contenido'])
                        mostrar_seccion_comentarios("noticia", n['id'], n['titulo'])

elif st.session_state.tab == 2:  # Negocios
    st.title("📍 Donde ir - Donde comprar")
    negocios = get_negocios()
    if not negocios.empty:
        for _, n in negocios.iterrows():
            with st.expander(f"🏪 {n['nombre']}"):
                st.write(f"**Reseña:** {n['resena']}")
                if n.get('google_maps_url'):
                    st.markdown(f"📍 [Ver en Maps]({n['google_maps_url']})")
                mostrar_seccion_comentarios("negocio", n['id'], n['nombre'])

elif st.session_state.tab == 3:  # Reflexiones
    st.title("💭 Reflexiones")
    ref = get_reflexion_activa()
    if ref:
        with st.expander(f"✨ REFLEXIÓN ACTUAL: {ref['titulo']}", expanded=True):
            st.write(ref['contenido'])
            if ref.get('versiculo'):
                st.caption(f"📖 {ref['versiculo']}")
            mostrar_seccion_comentarios("reflexion", ref['id'], ref['titulo'])

# ============================================
# FOOTER
# ============================================
st.markdown("""
<div class="bronze-footer">
    <p style="font-size:1.5em;">DESARROLLADO POR WILLIAN ALMENAR</p>
    <p>Prohibida la reproducción total o parcial</p>
    <p>DERECHOS RESERVADOS</p>
    <p>Santa Teresa del Tuy, 2026</p>
</div>
""", unsafe_allow_html=True)
