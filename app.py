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
# BASE DE DATOS DE ENFERMEDADES (MOTOR DE DIAGNÓSTICO)
# ============================================
BASE_DATOS_ENFERMEDADES = {
    # === ENFERMEDADES CARDIOVASCULARES ===
    "Hipertensión Arterial": {
        "sintomas": ["dolor de cabeza", "visión borrosa", "fatiga", "palpitaciones", "mareos", "sangrado nasal", "dificultad para respirar", "zumbido en oídos"],
        "factores_riesgo": ["sobrepeso", "obesidad", "tabaquismo", "sedentarismo", "estrés", "historia familiar", "consumo de sal"],
        "especialidad": "Cardiología",
        "urgencia": "Alta",
        "recomendaciones": ["Medir presión arterial diariamente", "Reducir consumo de sal", "Ejercicio regular", "Consulta con cardiólogo"],
        "tratamiento": "Enalapril, losartán, diuréticos, cambios en estilo de vida"
    },
    "Hipotensión Arterial": {
        "sintomas": ["mareos", "visión borrosa", "fatiga", "náuseas", "palidez", "desmayos", "dificultad para concentrarse", "sed"],
        "factores_riesgo": ["deshidratación", "embarazo", "problemas cardíacos", "diabetes", "anemia", "medicamentos"],
        "especialidad": "Cardiología",
        "urgencia": "Media",
        "recomendaciones": ["Aumentar consumo de líquidos", "Consumir sal moderadamente", "Evitar cambios bruscos de posición", "Consulta con cardiólogo"],
        "tratamiento": "Aumento de líquidos, sal en dieta, medicamentos según causa"
    },
    "Isquemia Cardíaca": {
        "sintomas": ["dolor en el pecho", "dificultad para respirar", "fatiga", "palpitaciones", "dolor en brazo izquierdo", "náuseas", "sudoración"],
        "factores_riesgo": ["hipertensión", "colesterol alto", "tabaquismo", "diabetes", "sedentarismo", "historia familiar"],
        "especialidad": "Cardiología",
        "urgencia": "Alta",
        "recomendaciones": ["ACUDIR A URGENCIAS INMEDIATAMENTE", "Reposo absoluto", "No automedicarse", "Consulta con cardiólogo urgente"],
        "tratamiento": "Nitroglicerina, antiagregantes, angioplastia, cirugía de bypass"
    },
    "Infarto Agudo de Miocardio": {
        "sintomas": ["dolor en el pecho", "dificultad para respirar", "sudoración", "náuseas", "vómitos", "dolor en brazo izquierdo", "palpitaciones", "ansiedad"],
        "factores_riesgo": ["hipertensión", "colesterol alto", "tabaquismo", "diabetes", "sedentarismo", "historia familiar", "obesidad"],
        "especialidad": "Cardiología",
        "urgencia": "Alta",
        "recomendaciones": ["LLAMAR AL 911 INMEDIATAMENTE", "Reposo absoluto", "No automedicarse", "Masticar aspirina si no es alérgico"],
        "tratamiento": "Angioplastia, trombolíticos, anticoagulantes, cirugía de bypass"
    },
    "Arritmia Cardíaca": {
        "sintomas": ["palpitaciones", "mareos", "dificultad para respirar", "dolor en el pecho", "fatiga", "desmayos", "ansiedad"],
        "factores_riesgo": ["hipertensión", "enfermedad coronaria", "hipertiroidismo", "consumo de cafeína", "estrés", "tabaquismo"],
        "especialidad": "Cardiología",
        "urgencia": "Media",
        "recomendaciones": ["Evitar cafeína y alcohol", "Manejar el estrés", "Consulta con cardiólogo", "Monitoreo cardíaco"],
        "tratamiento": "Antiarrítmicos, betabloqueadores, marcapasos"
    },
    
    # === ENFERMEDADES RESPIRATORIAS ===
    "Bronquitis Aguda": {
        "sintomas": ["tos", "producción de moco", "dificultad para respirar", "sibilancias", "dolor en el pecho", "fiebre", "fatiga"],
        "factores_riesgo": ["tabaquismo", "exposición a contaminantes", "infecciones virales", "bajas defensas", "cambios bruscos de temperatura"],
        "especialidad": "Neumología",
        "urgencia": "Media",
        "recomendaciones": ["Reposo", "Aumentar consumo de líquidos", "Usar humidificador", "Consulta con neumólogo si persiste"],
        "tratamiento": "Broncodilatadores, antiinflamatorios, antibióticos si es bacteriana"
    },
    "Catarro Común (Resfriado)": {
        "sintomas": ["congestión nasal", "estornudos", "tos", "dolor de garganta", "fiebre leve", "fatiga", "dolor de cabeza"],
        "factores_riesgo": ["cambios de temperatura", "bajas defensas", "contacto con personas enfermas", "estrés"],
        "especialidad": "Medicina General",
        "urgencia": "Baja",
        "recomendaciones": ["Reposo", "Aumentar consumo de líquidos", "Té con miel y limón", "Consulta si empeora"],
        "tratamiento": "Antihistamínicos, analgésicos, descongestionantes"
    },
    "Neumonía": {
        "sintomas": ["fiebre alta", "tos con flema", "dificultad para respirar", "dolor en el pecho", "fatiga", "escalofríos", "sudoración"],
        "factores_riesgo": ["edad avanzada", "tabaquismo", "enfermedades crónicas", "bajas defensas", "influenza"],
        "especialidad": "Neumología",
        "urgencia": "Alta",
        "recomendaciones": ["ACUDIR AL MÉDICO URGENTEMENTE", "Reposo absoluto", "Aumentar líquidos", "No automedicarse"],
        "tratamiento": "Antibióticos, antipiréticos, oxigenoterapia si es necesario"
    },
    "Asma Bronquial": {
        "sintomas": ["dificultad para respirar", "sibilancias", "tos", "opresión en el pecho", "fatiga", "sensación de ahogo"],
        "factores_riesgo": ["alergias", "historia familiar", "tabaquismo", "obesidad", "exposición a alérgenos"],
        "especialidad": "Neumología",
        "urgencia": "Alta",
        "recomendaciones": ["Usar inhalador de rescate", "Evitar alérgenos", "Consulta con neumólogo"],
        "tratamiento": "Broncodilatadores, corticosteroides inhalados"
    },
    "EPOC (Enfermedad Pulmonar Obstructiva Crónica)": {
        "sintomas": ["dificultad para respirar", "tos crónica", "producción de moco", "fatiga", "sibilancias", "opresión en el pecho"],
        "factores_riesgo": ["tabaquismo", "exposición a contaminantes", "historia familiar", "edad > 40"],
        "especialidad": "Neumología",
        "urgencia": "Alta",
        "recomendaciones": ["Dejar de fumar", "Rehabilitación pulmonar", "Uso de broncodilatadores", "Consulta con neumólogo"],
        "tratamiento": "Broncodilatadores, corticosteroides, oxigenoterapia"
    },
    
    # === ENFERMEDADES NEUROLÓGICAS ===
    "Cefalea Tensional": {
        "sintomas": ["dolor de cabeza", "sensación de presión", "dolor en la nuca", "dolor en los hombros", "irritabilidad", "dificultad para concentrarse"],
        "factores_riesgo": ["estrés", "ansiedad", "falta de sueño", "mala postura", "tensión muscular"],
        "especialidad": "Neurología",
        "urgencia": "Baja",
        "recomendaciones": ["Descanso", "Técnicas de relajación", "Aplicar compresas frías", "Consulta si persiste"],
        "tratamiento": "Analgésicos, relajantes musculares, terapia de relajación"
    },
    "Migraña": {
        "sintomas": ["dolor de cabeza pulsátil", "náuseas", "vómitos", "sensibilidad a la luz", "sensibilidad al sonido", "aura visual", "fatiga"],
        "factores_riesgo": ["estrés", "cambios hormonales", "falta de sueño", "historia familiar", "consumo de alcohol", "alimentos específicos"],
        "especialidad": "Neurología",
        "urgencia": "Media",
        "recomendaciones": ["Descanso en lugar oscuro", "Hidratación", "Evitar factores desencadenantes", "Consulta con neurólogo"],
        "tratamiento": "Triptanos, antiinflamatorios, betabloqueadores"
    },
    "Neuritis": {
        "sintomas": ["dolor agudo", "hormigueo", "entumecimiento", "debilidad muscular", "quemazón", "sensibilidad al tacto", "dificultad para mover"],
        "factores_riesgo": ["diabetes", "alcoholismo", "infecciones virales", "deficiencias nutricionales", "enfermedades autoinmunes"],
        "especialidad": "Neurología",
        "urgencia": "Media",
        "recomendaciones": ["Reposo", "Fisioterapia", "Calor local", "Consulta con neurólogo"],
        "tratamiento": "Antiinflamatorios, analgésicos, vitaminas del complejo B"
    },
    "Accidente Cerebrovascular (ACV)": {
        "sintomas": ["adormecimiento del labio", "debilidad en un lado del cuerpo", "dificultad para hablar", "visión borrosa", "dolor de cabeza", "mareos", "pérdida de equilibrio"],
        "factores_riesgo": ["hipertensión", "diabetes", "tabaquismo", "colesterol alto", "edad avanzada", "historia familiar"],
        "especialidad": "Neurología",
        "urgencia": "Alta",
        "recomendaciones": ["ACUDIR A URGENCIAS INMEDIATAMENTE", "No automedicarse", "Mantener reposo", "LLAMAR AL 911"],
        "tratamiento": "Trombólisis, anticoagulantes, rehabilitación"
    },
    "Tic Nervioso": {
        "sintomas": ["tic nervioso en el ojo", "movimientos involuntarios", "parpadeo excesivo", "contracciones faciales", "estrés", "ansiedad"],
        "factores_riesgo": ["estrés", "ansiedad", "fatiga", "falta de sueño", "consumo de cafeína"],
        "especialidad": "Neurología",
        "urgencia": "Baja",
        "recomendaciones": ["Reducir el estrés", "Técnicas de relajación", "Dormir adecuadamente", "Consulta con neurólogo si persiste"],
        "tratamiento": "Terapia de relajación, medicamentos en casos severos"
    },
    "Parálisis Facial": {
        "sintomas": ["adormecimiento del labio", "debilidad facial", "caída de un lado de la cara", "dificultad para sonreír", "babeo", "dificultad para cerrar el ojo"],
        "factores_riesgo": ["infecciones virales", "estrés", "diabetes", "embarazo", "sistema inmunológico débil"],
        "especialidad": "Neurología",
        "urgencia": "Alta",
        "recomendaciones": ["ACUDIR AL MÉDICO URGENTEMENTE", "Proteger el ojo", "Fisioterapia facial", "Evitar corrientes de aire"],
        "tratamiento": "Corticosteroides, antivirales, fisioterapia"
    },
    "Parkinson": {
        "sintomas": ["temblores", "rigidez muscular", "bradicinesia", "inestabilidad postural", "dificultad para hablar", "trastornos del sueño", "depresión"],
        "factores_riesgo": ["edad > 60", "historia familiar", "exposición a toxinas", "sexo masculino"],
        "especialidad": "Neurología",
        "urgencia": "Media",
        "recomendaciones": ["Fisioterapia", "Terapia ocupacional", "Ejercicio regular", "Consulta con neurólogo"],
        "tratamiento": "Levodopa, agonistas dopaminérgicos"
    },
    "Alzheimer": {
        "sintomas": ["pérdida de memoria", "confusión", "dificultad para hablar", "cambios de humor", "desorientación", "dificultad para realizar tareas", "aislamiento social"],
        "factores_riesgo": ["edad > 65", "historia familiar", "sedentarismo", "hipertensión", "diabetes", "tabaquismo"],
        "especialidad": "Neurología",
        "urgencia": "Alta",
        "recomendaciones": ["Estimulación cognitiva", "Estructura y rutina", "Apoyo familiar", "Consulta con neurólogo"],
        "tratamiento": "Donepezilo, memantina"
    },
    
    # === ENFERMEDADES GASTROINTESTINALES ===
    "Diarrea Aguda": {
        "sintomas": ["deposiciones líquidas", "dolor abdominal", "náuseas", "vómitos", "fiebre", "deshidratación", "pérdida de apetito"],
        "factores_riesgo": ["alimentos contaminados", "virus", "bacterias", "intolerancias alimentarias", "estrés", "medicamentos"],
        "especialidad": "Gastroenterología",
        "urgencia": "Media",
        "recomendaciones": ["Hidratación oral", "Dieta blanda", "Reposo", "Consulta si persiste más de 3 días"],
        "tratamiento": "Sales de rehidratación, probióticos, antidiarreicos"
    },
    "Gastroenteritis": {
        "sintomas": ["diarrea", "vómitos", "dolor abdominal", "fiebre", "deshidratación", "pérdida de apetito", "malestar general"],
        "factores_riesgo": ["alimentos contaminados", "falta de higiene", "sistema inmunológico débil", "viajes"],
        "especialidad": "Gastroenterología",
        "urgencia": "Media",
        "recomendaciones": ["Reposo", "Hidratación", "Dieta blanda", "Consulta si hay deshidratación"],
        "tratamiento": "Sales de rehidratación, probióticos, medicamentos según causa"
    },
    "Enfermedad de Crohn": {
        "sintomas": ["dolor abdominal", "diarrea crónica", "fatiga", "pérdida de peso", "sangre en heces", "fiebre", "úlceras bucales"],
        "factores_riesgo": ["historia familiar", "tabaquismo", "edad < 40", "origen judío", "consumo de antiinflamatorios"],
        "especialidad": "Gastroenterología",
        "urgencia": "Media",
        "recomendaciones": ["Dieta baja en fibra", "Suplementos nutricionales", "Evitar irritantes", "Consulta con gastroenterólogo"],
        "tratamiento": "Corticosteroides, inmunomoduladores, biológicos"
    },
    "Gastritis": {
        "sintomas": ["dolor abdominal", "náuseas", "vómitos", "sensación de llenura", "pérdida de apetito", "ardor estomacal", "eructos"],
        "factores_riesgo": ["consumo de antiinflamatorios", "estrés", "alcohol", "tabaquismo", "infección por H. pylori"],
        "especialidad": "Gastroenterología",
        "urgencia": "Media",
        "recomendaciones": ["Evitar alimentos irritantes", "Comer porciones pequeñas", "Reducir estrés", "Consulta con gastroenterólogo"],
        "tratamiento": "Antiacidos, protectores gástricos, antibióticos si es por H. pylori"
    },
    "Úlcera Gástrica": {
        "sintomas": ["dolor abdominal", "ardor", "náuseas", "vómitos", "pérdida de peso", "sangre en heces", "vómitos con sangre"],
        "factores_riesgo": ["consumo de antiinflamatorios", "estrés", "alcohol", "tabaquismo", "infección por H. pylori"],
        "especialidad": "Gastroenterología",
        "urgencia": "Alta",
        "recomendaciones": ["ACUDIR AL MÉDICO URGENTEMENTE", "Evitar alimentos irritantes", "Reducir estrés", "No automedicarse"],
        "tratamiento": "Protectores gástricos, antibióticos, cambios en dieta"
    },
    
    # === ENFERMEDADES MUSCULOESQUELÉTICAS ===
    "Artritis Reumatoide": {
        "sintomas": ["dolor articular", "rigidez matutina", "inflamación", "fatiga", "fiebre", "pérdida de peso", "deformidad articular"],
        "factores_riesgo": ["historia familiar", "tabaquismo", "obesidad", "sexo femenino", "edad > 40"],
        "especialidad": "Reumatología",
        "urgencia": "Media",
        "recomendaciones": ["Reposo", "Fisioterapia", "Medicamentos antiinflamatorios", "Consulta con reumatólogo"],
        "tratamiento": "Metotrexato, corticosteroides, anti-TNF"
    },
    "Artrosis (Osteoartritis)": {
        "sintomas": ["dolor articular", "rigidez", "dificultad para moverse", "crujidos", "inflamación leve", "deformidad", "pérdida de flexibilidad"],
        "factores_riesgo": ["edad avanzada", "obesidad", "sobreuso de articulaciones", "lesiones previas", "historia familiar"],
        "especialidad": "Reumatología",
        "urgencia": "Baja",
        "recomendaciones": ["Ejercicio de bajo impacto", "Pérdida de peso", "Fisioterapia", "Consulta con reumatólogo"],
        "tratamiento": "Analgésicos, antiinflamatorios, fisioterapia, cirugía en casos graves"
    },
    "Cervicalgia (Dolor de Cuello)": {
        "sintomas": ["dolor en el cuello", "rigidez", "dolor de cabeza", "dificultad para mover el cuello", "dolor en hombros", "hormigueo en brazos"],
        "factores_riesgo": ["mala postura", "uso excesivo de dispositivos", "estrés", "lesiones", "sobrepeso"],
        "especialidad": "Traumatología",
        "urgencia": "Baja",
        "recomendaciones": ["Aplicar calor local", "Ejercicios de estiramiento", "Mejorar postura", "Consulta si persiste"],
        "tratamiento": "Analgésicos, relajantes musculares, fisioterapia"
    },
    "Lumbalgia (Dolor de Espalda)": {
        "sintomas": ["dolor lumbar", "rigidez", "dificultad para moverse", "dolor al estar de pie", "dolor al sentarse", "irradiación a piernas"],
        "factores_riesgo": ["mala postura", "sedentarismo", "sobrepeso", "levantar objetos pesados", "estrés"],
        "especialidad": "Traumatología",
        "urgencia": "Baja",
        "recomendaciones": ["Aplicar calor o frío", "Reposo", "Ejercicios de fortalecimiento", "Consulta si persiste"],
        "tratamiento": "Analgésicos, relajantes musculares, fisioterapia"
    },
    "Hernia Discal": {
        "sintomas": ["dolor lumbar", "irradiación a piernas", "hormigueo", "debilidad en piernas", "dificultad para moverse", "dolor al estornudar"],
        "factores_riesgo": ["levantar objetos pesados", "sedentarismo", "sobrepeso", "mala postura", "traumatismos"],
        "especialidad": "Traumatología",
        "urgencia": "Alta",
        "recomendaciones": ["ACUDIR AL MÉDICO URGENTEMENTE", "Reposo", "Evitar esfuerzos", "Fisioterapia"],
        "tratamiento": "Analgésicos, antiinflamatorios, fisioterapia, cirugía en casos graves"
    },
    
    # === INFECCIONES ===
    "Infección Urinaria": {
        "sintomas": ["dolor al orinar", "micción frecuente", "orina turbia", "olor fuerte en orina", "dolor pélvico", "fiebre", "escalofríos"],
        "factores_riesgo": ["falta de higiene", "relaciones sexuales", "embarazo", "diabetes", "uso de anticonceptivos"],
        "especialidad": "Urología",
        "urgencia": "Media",
        "recomendaciones": ["Aumentar consumo de agua", "Jugo de arándano", "Higiene adecuada", "Consulta con urólogo"],
        "tratamiento": "Antibióticos, analgésicos, aumento de líquidos"
    },
    "Cistitis": {
        "sintomas": ["dolor al orinar", "micción frecuente", "urgencia urinaria", "orina con sangre", "dolor pélvico", "fiebre", "malestar general"],
        "factores_riesgo": ["infecciones recurrentes", "embarazo", "diabetes", "uso de catéteres", "relaciones sexuales"],
        "especialidad": "Urología",
        "urgencia": "Media",
        "recomendaciones": ["Hidratación", "Higiene", "Evitar irritantes", "Consulta con urólogo"],
        "tratamiento": "Antibióticos, analgésicos, aumento de líquidos"
    },
    "Pielonefritis": {
        "sintomas": ["fiebre alta", "escalofríos", "dolor lumbar", "dolor al orinar", "náuseas", "vómitos", "fatiga"],
        "factores_riesgo": ["infección urinaria no tratada", "embarazo", "diabetes", "cálculos renales", "catéteres"],
        "especialidad": "Urología",
        "urgencia": "Alta",
        "recomendaciones": ["ACUDIR AL MÉDICO URGENTEMENTE", "Reposo", "Hidratación", "No automedicarse"],
        "tratamiento": "Antibióticos, antipiréticos, hidratación"
    },
    
    # === ENFERMEDADES METABÓLICAS Y ENDOCRINAS ===
    "Diabetes Tipo 2": {
        "sintomas": ["sed excesiva", "micción frecuente", "fatiga", "visión borrosa", "hambre extrema", "pérdida de peso", "infecciones frecuentes"],
        "factores_riesgo": ["sobrepeso", "obesidad", "hipertensión", "historia familiar", "sedentarismo", "edad > 45"],
        "especialidad": "Endocrinología",
        "urgencia": "Media",
        "recomendaciones": ["Control de glucosa", "Dieta balanceada", "Ejercicio regular", "Consulta con endocrinólogo"],
        "tratamiento": "Metformina, insulina, cambios en estilo de vida"
    },
    "Hipotiroidismo": {
        "sintomas": ["fatiga", "aumento de peso", "sensibilidad al frío", "piel seca", "caída de cabello", "depresión", "estreñimiento"],
        "factores_riesgo": ["historia familiar", "mujeres > 40", "enfermedad autoinmune", "embarazo", "radiación"],
        "especialidad": "Endocrinología",
        "urgencia": "Media",
        "recomendaciones": ["Control de tiroides", "Dieta balanceada", "Ejercicio regular", "Consulta con endocrinólogo"],
        "tratamiento": "Levotiroxina, cambios en estilo de vida"
    },
    "Hipertiroidismo": {
        "sintomas": ["pérdida de peso", "palpitaciones", "ansiedad", "intolerancia al calor", "sudoración", "fatiga", "temblores"],
        "factores_riesgo": ["historia familiar", "mujeres", "enfermedad autoinmune", "embarazo", "estrés"],
        "especialidad": "Endocrinología",
        "urgencia": "Media",
        "recomendaciones": ["Control de tiroides", "Dieta balanceada", "Técnicas de relajación", "Consulta con endocrinólogo"],
        "tratamiento": "Metimazol, yodo radioactivo, cirugía"
    },
    
    # === ENFERMEDADES AUTOINMUNES ===
    "Lupus Eritematoso Sistémico": {
        "sintomas": ["fatiga", "dolor articular", "erupción en la cara", "fiebre", "caída de cabello", "úlceras bucales", "dolor en el pecho"],
        "factores_riesgo": ["sexo femenino", "edad 15-45", "historia familiar", "exposición solar", "infecciones"],
        "especialidad": "Reumatología",
        "urgencia": "Alta",
        "recomendaciones": ["Protección solar", "Reposo", "Medicamentos antiinflamatorios", "Consulta con reumatólogo"],
        "tratamiento": "Corticosteroides, antipalúdicos, inmunosupresores"
    },
    "Anemia": {
        "sintomas": ["fatiga", "debilidad", "palidez", "mareos", "dificultad para respirar", "palpitaciones", "manos y pies fríos"],
        "factores_riesgo": ["deficiencia de hierro", "dieta pobre", "sangrado menstrual", "embarazo", "enfermedades crónicas"],
        "especialidad": "Hematología",
        "urgencia": "Media",
        "recomendaciones": ["Dieta rica en hierro", "Suplementos", "Descanso", "Consulta con hematólogo"],
        "tratamiento": "Suplementos de hierro, vitamina B12, ácido fólico"
    },
    "Anemia Perniciosa": {
        "sintomas": ["fatiga", "debilidad", "palidez", "mareos", "hormigueo", "dificultad para caminar", "depresión", "confusión"],
        "factores_riesgo": ["deficiencia de B12", "gastritis atrófica", "historia familiar", "edad avanzada", "cirugía gástrica"],
        "especialidad": "Hematología",
        "urgencia": "Media",
        "recomendaciones": ["Suplementos de B12", "Dieta balanceada", "Descanso", "Consulta con hematólogo"],
        "tratamiento": "Inyecciones de B12, suplementos orales"
    },
    
    # === ENFERMEDADES INFECCIOSAS ===
    "Fiebre Tifoidea": {
        "sintomas": ["fiebre alta", "dolor de cabeza", "dolor abdominal", "estreñimiento", "diarrea", "erupción cutánea", "fatiga"],
        "factores_riesgo": ["consumo de agua contaminada", "falta de higiene", "viajes a zonas endémicas", "contacto con infectados"],
        "especialidad": "Infectología",
        "urgencia": "Alta",
        "recomendaciones": ["ACUDIR AL MÉDICO URGENTEMENTE", "Reposo", "Hidratación", "Aislamiento"],
        "tratamiento": "Antibióticos, antipiréticos, hidratación"
    },
    "Dengue": {
        "sintomas": ["fiebre alta", "dolor de cabeza", "dolor muscular", "dolor articular", "erupción cutánea", "sangrado", "fatiga"],
        "factores_riesgo": ["picaduras de mosquitos", "vivir en zonas tropicales", "temporada de lluvias"],
        "especialidad": "Infectología",
        "urgencia": "Alta",
        "recomendaciones": ["ACUDIR AL MÉDICO URGENTEMENTE", "Reposo", "Hidratación", "No tomar aspirina"],
        "tratamiento": "Antipiréticos, hidratación, vigilancia médica"
    },
    "Hepatitis B": {
        "sintomas": ["fatiga", "dolor abdominal", "orina oscura", "ictericia", "náuseas", "vómitos", "fiebre"],
        "factores_riesgo": ["contacto sexual sin protección", "compartir agujas", "transfusiones", "transmisión perinatal"],
        "especialidad": "Gastroenterología",
        "urgencia": "Alta",
        "recomendaciones": ["ACUDIR AL MÉDICO URGENTEMENTE", "Reposo", "Dieta ligera", "Evitar alcohol"],
        "tratamiento": "Antivirales, inmunomoduladores, seguimiento médico"
    },
    "Gripe (Influenza)": {
        "sintomas": ["fiebre alta", "tos", "dolor de garganta", "dolor muscular", "dolor de cabeza", "fatiga", "escalofríos"],
        "factores_riesgo": ["contacto con personas enfermas", "bajas defensas", "cambios de temperatura"],
        "especialidad": "Medicina General",
        "urgencia": "Media",
        "recomendaciones": ["Reposo", "Aumentar líquidos", "Antipiréticos", "Consulta si empeora"],
        "tratamiento": "Antivirales, antipiréticos, descanso"
    },
    "Varicela": {
        "sintomas": ["fiebre", "erupción con ampollas", "picazón", "dolor de cabeza", "fatiga", "pérdida de apetito"],
        "factores_riesgo": ["contacto con infectados", "bajas defensas", "no vacunado"],
        "especialidad": "Dermatología",
        "urgencia": "Media",
        "recomendaciones": ["Reposo", "No rascar", "Baños de avena", "Consulta si fiebre alta"],
        "tratamiento": "Antipiréticos, antihistamínicos, antivirales"
    },
    "Sarampión": {
        "sintomas": ["fiebre alta", "tos", "congestión nasal", "conjuntivitis", "erupción", "dolor de cabeza", "fatiga"],
        "factores_riesgo": ["no vacunado", "contacto con infectados", "bajas defensas"],
        "especialidad": "Infectología",
        "urgencia": "Alta",
        "recomendaciones": ["ACUDIR AL MÉDICO URGENTEMENTE", "Aislamiento", "Hidratación", "Reposo"],
        "tratamiento": "Sintomático, vitaminas, vigilancia médica"
    },
    "Paperas": {
        "sintomas": ["inflamación de parótidas", "fiebre", "dolor al masticar", "dolor de cabeza", "fatiga", "pérdida de apetito"],
        "factores_riesgo": ["no vacunado", "contacto con infectados"],
        "especialidad": "Infectología",
        "urgencia": "Media",
        "recomendaciones": ["Reposo", "Aumentar líquidos", "Compresas frías", "Consulta si complicaciones"],
        "tratamiento": "Analgésicos, antipiréticos, hidratación"
    },
    "COVID-19": {
        "sintomas": ["fiebre", "tos", "dificultad para respirar", "fatiga", "dolor de cabeza", "pérdida de olfato", "pérdida de gusto", "dolor de garganta"],
        "factores_riesgo": ["edad avanzada", "enfermedades crónicas", "obesidad", "inmunosupresión", "contacto con infectados"],
        "especialidad": "Infectología",
        "urgencia": "Alta",
        "recomendaciones": ["AISLAMIENTO INMEDIATO", "ACUDIR AL MÉDICO URGENTEMENTE", "Hidratación", "Monitoreo de oxígeno"],
        "tratamiento": "Antivirales, antipiréticos, oxigenoterapia, vacunación"
    },
    
    # === ENFERMEDADES DERMATOLÓGICAS ===
    "Dermatitis Atópica": {
        "sintomas": ["picazón", "enrojecimiento", "piel seca", "descamación", "lesiones cutáneas", "inflamación", "sensibilidad"],
        "factores_riesgo": ["historia familiar", "alergias", "asmática", "estrés", "cambios de temperatura"],
        "especialidad": "Dermatología",
        "urgencia": "Baja",
        "recomendaciones": ["Hidratar la piel", "Evitar irritantes", "Ropa de algodón", "Consulta con dermatólogo"],
        "tratamiento": "Cremas hidratantes, corticosteroides tópicos, antihistamínicos"
    },
    "Psoriasis": {
        "sintomas": ["lesiones cutáneas", "descamación", "enrojecimiento", "picazón", "dolor", "inflamación", "uñas deformadas"],
        "factores_riesgo": ["historia familiar", "estrés", "infecciones", "tabaquismo", "obesidad"],
        "especialidad": "Dermatología",
        "urgencia": "Media",
        "recomendaciones": ["Hidratar la piel", "Evitar estrés", "No rascar", "Consulta con dermatólogo"],
        "tratamiento": "Corticosteroides tópicos, fototerapia, medicamentos sistémicos"
    },
    
    # === ENFERMEDADES OFTALMOLÓGICAS ===
    "Conjuntivitis": {
        "sintomas": ["enrojecimiento ocular", "picazón", "lagrimeo", "secreción", "sensibilidad a la luz", "visión borrosa"],
        "factores_riesgo": ["contacto con infectados", "alergias", "bajas defensas", "uso de lentes de contacto"],
        "especialidad": "Oftalmología",
        "urgencia": "Media",
        "recomendaciones": ["Lavado de manos frecuente", "No compartir toallas", "No usar lentes de contacto", "Consulta con oftalmólogo"],
        "tratamiento": "Gotas antibióticas, antihistamínicas, compresas frías"
    },
    
    # === ENFERMEDADES GINECOLÓGICAS ===
    "Infección Vaginal": {
        "sintomas": ["picazón", "secreción anormal", "olor", "dolor", "ardor", "enrojecimiento", "inflamación"],
        "factores_riesgo": ["antibióticos", "diabetes", "embarazo", "anticonceptivos", "relaciones sexuales"],
        "especialidad": "Ginecología",
        "urgencia": "Media",
        "recomendaciones": ["Higiene adecuada", "Ropa interior de algodón", "Evitar irritantes", "Consulta con ginecólogo"],
        "tratamiento": "Antifúngicos, antibióticos, cremas tópicas"
    }
}

# ============================================
# LISTA COMPLETA DE SÍNTOMAS
# ============================================
SINTOMAS_COMPLETOS = [
    # Síntomas generales
    "Dolor de cabeza", "Dolor de garganta", "Fiebre", "Tos", "Dolor abdominal",
    "Dolor de espalda", "Náuseas", "Mareos", "Dificultad para respirar",
    "Dolor en el pecho", "Erupción cutánea", "Fatiga", "Sed excesiva",
    "Micción frecuente", "Visión borrosa", "Hambre extrema", "Pérdida de peso",
    "Infecciones frecuentes", "Dolor articular", "Rigidez matutina",
    "Inflamación", "Temblores", "Rigidez muscular", "Bradicinesia",
    "Inestabilidad postural", "Pérdida de memoria", "Confusión",
    "Cambios de humor", "Desorientación", "Bulto en el pecho",
    "Sangre en orina", "Dificultad para orinar", "Tristeza persistente",
    "Preocupación excesiva", "Irritabilidad", "Palpitaciones", "Sangrado nasal",
    "Congestión nasal", "Estornudos", "Diarrea", "Vómitos",
    "Dolor al orinar", "Orina turbia", "Dolor pélvico", "Zumbido en oídos",
    "Dificultad para concentrarse", "Pérdida de apetito", "Desmayos",
    "Palidez", "Sibilancias", "Producción de moco", "Sensibilidad a la luz",
    "Sensibilidad al sonido", "Aura visual", "Quemazón", "Hormigueo",
    "Entumecimiento", "Debilidad muscular", "Crujidos articulares",
    "Dolor en la nuca", "Dolor en hombros", "Dificultad para mover",
    "Dolor lumbar", "Irradiación a piernas", "Dolor al estar de pie",
    "Dolor al sentarse", "Olor fuerte en orina", "Escalofríos", "Ictericia",
    "Orina oscura", "Inflamación de parótidas", "Dolor al masticar",
    "Ampollas", "Picazón", "Conjuntivitis", "Dolor muscular",
    
    # Nuevos síntomas neurológicos
    "Adormecimiento del labio", "Tic nervioso en el ojo", "Parpadeo excesivo",
    "Contracciones faciales", "Movimientos involuntarios", "Debilidad en un lado del cuerpo",
    "Dificultad para hablar", "Pérdida de equilibrio", "Caída de un lado de la cara",
    "Dificultad para sonreír", "Babeo", "Dificultad para cerrar el ojo",
    "Sensación de presión en la cabeza", "Dolor en la mandíbula",
    
    # Síntomas cardiovasculares
    "Dolor en el pecho", "Palpitaciones", "Sudoración", "Ansiedad", "Dificultad para respirar",
    
    # Síntomas gastrointestinales
    "Sensación de llenura", "Ardor estomacal", "Eructos", "Sangre en heces", "Vómitos con sangre",
    
    # Síntomas metabólicos
    "Aumento de peso", "Sensibilidad al frío", "Piel seca", "Caída de cabello", "Depresión",
    "Estreñimiento", "Intolerancia al calor", "Temblores",
    
    # Síntomas dermatológicos
    "Enrojecimiento", "Piel seca", "Descamación", "Lesiones cutáneas", "Sensibilidad",
    
    # Síntomas oftalmológicos
    "Enrojecimiento ocular", "Lagrimeo", "Secreción ocular",
    
    # Síntomas ginecológicos
    "Secreción anormal", "Olor vaginal", "Ardor vaginal"
]

# ============================================
# DIRECTORIO REAL DE SANTA TERESA DEL TUY
# ============================================
DIRECTORIO_SALUD = [
    {
        "nombre": "Hospital General de Santa Teresa",
        "tipo": "Hospital",
        "direccion": "Av. Principal, Santa Teresa del Tuy, Estado Miranda",
        "telefono": "0212-XXX-XXXX",
        "servicios": ["Emergencias 24h", "Consulta Externa", "Hospitalización", "Cirugía", "Maternidad"],
        "horario": "24 horas",
        "coordenadas": "10.2305° N, 66.6647° W"
    },
    {
        "nombre": "Ambulatorio Urbano I",
        "tipo": "Ambulatorio",
        "direccion": "Barrio El Centro, Santa Teresa del Tuy, Estado Miranda",
        "telefono": "0212-XXX-XXXX",
        "servicios": ["Medicina General", "Pediatría", "Odontología", "Vacunación", "Control de embarazo"],
        "horario": "7:00 AM - 3:00 PM",
        "coordenadas": "10.2280° N, 66.6620° W"
    },
    {
        "nombre": "Ambulatorio Urbano II",
        "tipo": "Ambulatorio",
        "direccion": "Sector La Trinidad, Santa Teresa del Tuy, Estado Miranda",
        "telefono": "0212-XXX-XXXX",
        "servicios": ["Medicina General", "Pediatría", "Odontología", "Vacunación"],
        "horario": "7:00 AM - 3:00 PM",
        "coordenadas": "10.2320° N, 66.6670° W"
    },
    {
        "nombre": "CDI (Centro de Diagnóstico Integral)",
        "tipo": "Centro de Diagnóstico",
        "direccion": "Av. Principal, Santa Teresa del Tuy, Estado Miranda",
        "telefono": "0212-XXX-XXXX",
        "servicios": ["Laboratorio", "Rayos X", "Ecografía", "Electrocardiograma", "Consulta Especializada"],
        "horario": "7:00 AM - 5:00 PM",
        "coordenadas": "10.2310° N, 66.6635° W"
    },
    {
        "nombre": "Farmacia Santa Teresa 24h",
        "tipo": "Farmacia",
        "direccion": "Esquina Bolívar, Santa Teresa del Tuy, Estado Miranda",
        "telefono": "0212-XXX-XXXX",
        "servicios": ["Venta de medicamentos", "Delivery 24h", "Productos de cuidado personal"],
        "horario": "24 horas",
        "coordenadas": "10.2295° N, 66.6650° W"
    },
    {
        "nombre": "Farmacia La Trinidad",
        "tipo": "Farmacia",
        "direccion": "Sector La Trinidad, Santa Teresa del Tuy, Estado Miranda",
        "telefono": "0212-XXX-XXXX",
        "servicios": ["Venta de medicamentos", "Productos naturales", "Cuidado personal"],
        "horario": "8:00 AM - 8:00 PM",
        "coordenadas": "10.2325° N, 66.6665° W"
    },
    {
        "nombre": "Clínica Santa Teresa",
        "tipo": "Clínica Privada",
        "direccion": "Calle 5, Santa Teresa del Tuy, Estado Miranda",
        "telefono": "0212-XXX-XXXX",
        "servicios": ["Consultas Especializadas", "Laboratorio", "Imagenología", "Medicina Interna"],
        "horario": "8:00 AM - 6:00 PM",
        "coordenadas": "10.2300° N, 66.6625° W"
    },
    {
        "nombre": "Módulo de Barrio Adentro",
        "tipo": "Módulo de Salud",
        "direccion": "Urbanización El Samán, Santa Teresa del Tuy, Estado Miranda",
        "telefono": "0212-XXX-XXXX",
        "servicios": ["Medicina General", "Odontología", "Vacunación", "Control de embarazo"],
        "horario": "8:00 AM - 4:00 PM",
        "coordenadas": "10.2340° N, 66.6680° W"
    },
    {
        "nombre": "Farmacia El Samán",
        "tipo": "Farmacia",
        "direccion": "Urbanización El Samán, Santa Teresa del Tuy, Estado Miranda",
        "telefono": "0212-XXX-XXXX",
        "servicios": ["Venta de medicamentos", "Productos de cuidado personal"],
        "horario": "8:00 AM - 7:00 PM",
        "coordenadas": "10.2345° N, 66.6675° W"
    },
    {
        "nombre": "Clínica Odontológica Santa Teresa",
        "tipo": "Clínica Odontológica",
        "direccion": "Av. Principal, Santa Teresa del Tuy, Estado Miranda",
        "telefono": "0212-XXX-XXXX",
        "servicios": ["Odontología General", "Ortodoncia", "Blanqueamiento", "Cirugía Dental"],
        "horario": "8:00 AM - 5:00 PM",
        "coordenadas": "10.2290° N, 66.6640° W"
    }
]

# ============================================
# FUNCIÓN DE DIAGNÓSTICO
# ============================================
def diagnosticar_enfermedades(sintomas_usuario, condiciones_preexistentes, edad, sexo):
    """
    Función de diagnóstico que analiza múltiples enfermedades.
    """
    diagnosticos = []
    
    # Normalizar síntomas
    sintomas_normalizados = []
    for s in sintomas_usuario:
        s_lower = s.lower().strip()
        s_lower = s_lower.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
        sintomas_normalizados.append(s_lower)
    
    # Analizar cada enfermedad
    for nombre, info in BASE_DATOS_ENFERMEDADES.items():
        sintomas_coincidentes = []
        factores_riesgo = []
        total_sintomas = len(info["sintomas"])
        
        # Verificar coincidencia de síntomas
        for sintoma in info["sintomas"]:
            s_lower = sintoma.lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
            if any(s_lower in s_usuario or s_usuario in s_lower for s_usuario in sintomas_normalizados):
                sintomas_coincidentes.append(sintoma)
        
        # Verificar factores de riesgo
        for factor in info["factores_riesgo"]:
            factor_lower = factor.lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
            for condicion in condiciones_preexistentes:
                cond_lower = condicion.lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
                if factor_lower in cond_lower or cond_lower in factor_lower:
                    factores_riesgo.append(factor)
        
        # Solo considerar si hay al menos 2 síntomas coincidentes
        if len(sintomas_coincidentes) >= 2:
            # Calcular nivel de coincidencia
            if len(sintomas_coincidentes) >= total_sintomas * 0.6:
                nivel = "Alta"
                color = "#4CAF50"
            elif len(sintomas_coincidentes) >= total_sintomas * 0.3:
                nivel = "Media"
                color = "#FFC107"
            else:
                nivel = "Baja"
                color = "#FF6B6B"
            
            diagnosticos.append({
                "enfermedad": nombre,
                "nivel": nivel,
                "color": color,
                "sintomas_coincidentes": sintomas_coincidentes,
                "factores_riesgo": factores_riesgo,
                "especialidad": info["especialidad"],
                "urgencia": info["urgencia"],
                "recomendaciones": info["recomendaciones"],
                "tratamiento": info["tratamiento"],
                "total_sintomas": total_sintomas
            })
    
    # Ordenar por nivel de coincidencia
    orden_nivel = {"Alta": 0, "Media": 1, "Baja": 2}
    diagnosticos.sort(key=lambda x: (orden_nivel[x["nivel"]], -len(x["sintomas_coincidentes"])))
    
    return diagnosticos[:8]

# ============================================
# FUNCIÓN DE CHATBOT PARA PREGUNTA AL DOCTOR
# ============================================
def responder_pregunta_medica(pregunta):
    """
    Función que simula una respuesta médica basada en palabras clave.
    Siempre advierte que no reemplaza una consulta real.
    """
    pregunta_lower = pregunta.lower()
    
    # Buscar palabras clave
    if any(word in pregunta_lower for word in ["dolor de cabeza", "migraña", "cefalea"]):
        return """
        **Posible diagnóstico:** Cefalea o Migraña
        
        **Recomendación:**
        - Descansa en un lugar tranquilo y oscuro
        - Aplica compresas frías en la frente
        - Mantente hidratado
        - Si el dolor es intenso o recurrente, consulta a un neurólogo
        
        ⚠️ **Recuerda:** Esta es solo una guía informativa. Consulta a un médico para un diagnóstico preciso.
        """
    elif any(word in pregunta_lower for word in ["dolor de garganta", "garganta"]):
        return """
        **Posible diagnóstico:** Faringitis o Amigdalitis
        
        **Recomendación:**
        - Haz gárgaras con agua tibia y sal
        - Bebe líquidos calientes
        - Descansa la voz
        - Si hay fiebre o dura más de 3 días, consulta a un médico
        
        ⚠️ **Recuerda:** Esta es solo una guía informativa. Consulta a un médico para un diagnóstico preciso.
        """
    elif any(word in pregunta_lower for word in ["fiebre", "temperatura"]):
        return """
        **Posible diagnóstico:** Infección viral o bacteriana
        
        **Recomendación:**
        - Reposo absoluto
        - Bebe abundantes líquidos
        - Toma paracetamol para bajar la fiebre
        - Si la fiebre supera los 38.5°C o dura más de 3 días, consulta a un médico
        
        ⚠️ **Recuerda:** Esta es solo una guía informativa. Consulta a un médico para un diagnóstico preciso.
        """
    elif any(word in pregunta_lower for word in ["dolor en el pecho", "pecho"]):
        return """
        ⚠️ **ATENCIÓN URGENTE**
        
        **Posible diagnóstico:** Problema cardíaco
        
        **Recomendación:**
        - **ACUDE A URGENCIAS INMEDIATAMENTE O LLAMA AL 911**
        - Reposo absoluto
        - No te automediques
        - Si el dolor se irradia al brazo izquierdo, es una emergencia
        
        ⚠️ **Recuerda:** Esta es solo una guía informativa. ACUDE AL MÉDICO URGENTEMENTE.
        """
    elif any(word in pregunta_lower for word in ["dificultad para respirar", "respirar"]):
        return """
        ⚠️ **ATENCIÓN URGENTE**
        
        **Posible diagnóstico:** Problema respiratorio (Asma, EPOC, Neumonía)
        
        **Recomendación:**
        - **ACUDE A URGENCIAS INMEDIATAMENTE O LLAMA AL 911**
        - Siéntate en posición recta
        - Mantén la calma
        - Usa inhalador si tienes
        
        ⚠️ **Recuerda:** Esta es solo una guía informativa. ACUDE AL MÉDICO URGENTEMENTE.
        """
    elif any(word in pregunta_lower for word in ["mareos", "mareo", "vértigo"]):
        return """
        **Posible diagnóstico:** Vértigo o Hipotensión
        
        **Recomendación:**
        - Siéntate o acuéstate inmediatamente
        - Bebe agua lentamente
        - Evita cambios bruscos de posición
        - Si persiste o hay desmayos, consulta a un médico
        
        ⚠️ **Recuerda:** Esta es solo una guía informativa. Consulta a un médico para un diagnóstico preciso.
        """
    elif any(word in pregunta_lower for word in ["diarrea", "vómito", "vómitos"]):
        return """
        **Posible diagnóstico:** Gastroenteritis
        
        **Recomendación:**
        - Hidratación oral con suero
        - Dieta blanda (arroz, manzana)
        - Reposo
        - Si la diarrea persiste más de 3 días o hay sangre, consulta a un médico
        
        ⚠️ **Recuerda:** Esta es solo una guía informativa. Consulta a un médico para un diagnóstico preciso.
        """
    else:
        return """
        **Análisis preliminar:**
        
        Tus síntomas requieren una evaluación médica presencial para un diagnóstico preciso.
        
        **Recomendación general:**
        - Monitorea tus síntomas
        - Descansa y mantente hidratado
        - Consulta a un médico para una evaluación completa
        
        ⚠️ **Recuerda:** Esta es solo una guía informativa. NO reemplaza una consulta médica real.
        """

# ============================================
# FUNCIONES DE ADMINISTRACIÓN DE ENFERMEDADES
# ============================================
def guardar_enfermedad_en_supabase(nombre, info):
    try:
        data = {
            "nombre": nombre,
            "sintomas": info["sintomas"],
            "factores_riesgo": info["factores_riesgo"],
            "especialidad": info["especialidad"],
            "urgencia": info["urgencia"],
            "recomendaciones": info["recomendaciones"],
            "tratamiento": info["tratamiento"]
        }
        existing = supabase.table("enfermedades").select("*").eq("nombre", nombre).execute()
        if existing.data:
            supabase.table("enfermedades").update(data).eq("nombre", nombre).execute()
        else:
            supabase.table("enfermedades").insert(data).execute()
        return True
    except Exception as e:
        print(f"Error guardando enfermedad: {e}")
        return False

def cargar_enfermedades_de_supabase():
    try:
        response = supabase.table("enfermedades").select("*").execute()
        if response.data:
            for item in response.data:
                nombre = item.pop("nombre")
                BASE_DATOS_ENFERMEDADES[nombre] = item
        return True
    except Exception as e:
        print(f"Error cargando enfermedades: {e}")
        return False

def eliminar_enfermedad_de_supabase(nombre):
    try:
        supabase.table("enfermedades").delete().eq("nombre", nombre).execute()
        if nombre in BASE_DATOS_ENFERMEDADES:
            del BASE_DATOS_ENFERMEDADES[nombre]
        return True
    except Exception as e:
        print(f"Error eliminando enfermedad: {e}")
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
        result = supabase.table("comentarios").delete().eq("id", id_).execute()
        return True
    except Exception as e:
        print(f"Error eliminando comentario: {e}")
        return False

def actualizar_comentario(id_, nuevo_comentario):
    try:
        result = supabase.table("comentarios").update({"comentario": nuevo_comentario}).eq("id", id_).execute()
        return True
    except Exception as e:
        print(f"Error actualizando comentario: {e}")
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
        for idx, com in comentarios.iterrows():
            with st.container():
                col1, col2 = st.columns([8, 2])
                with col1:
                    st.markdown(f"**👤 {com['usuario']}** *{com['fecha']}*")
                    st.markdown(f"💬 {com['comentario']}")
                with col2:
                    if es_admin:
                        if st.button(f"🛠️", key=f"admin_com_{com['id']}_{seccion}_{item_id}_{idx}", help="Gestionar comentario (solo admin)"):
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

def add_negocio(nombre, resena, google_maps_url, video_url, imagenes):
    try:
        ahora = get_fecha_hora_venezuela()
        data = {
            "nombre": nombre, 
            "resena": resena, 
            "google_maps_url": google_maps_url if google_maps_url else None,
            "video_url": video_url if video_url else None,
            "imagenes_url": subir_multiples_imagenes(imagenes, "negocios") if imagenes else [], 
            "fecha": ahora.strftime("%d/%m/%Y")
        }
        supabase.table("negocios").insert(data).execute()
        return True
    except Exception as e:
        print(f"Error en add_negocio: {e}")
        return False

def update_negocio(id_, nombre, resena, google_maps_url, video_url, imagenes):
    try:
        imagenes_urls = subir_multiples_imagenes(imagenes, "negocios") if imagenes else None
        if not imagenes_urls:
            existing = supabase.table("negocios").select("imagenes_url").eq("id", id_).execute()
            if existing.data: 
                imagenes_urls = existing.data[0].get("imagenes_url")
        
        # Si no se proporciona video_url, mantener el existente
        if not video_url:
            existing = supabase.table("negocios").select("video_url").eq("id", id_).execute()
            if existing.data:
                video_url = existing.data[0].get("video_url")
        
        supabase.table("negocios").update({
            "nombre": nombre, 
            "resena": resena, 
            "google_maps_url": google_maps_url if google_maps_url else None,
            "video_url": video_url if video_url else None,
            "imagenes_url": imagenes_urls if imagenes_urls else []
        }).eq("id", id_).execute()
        return True
    except Exception as e:
        print(f"Error en update_negocio: {e}")
        return False

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
        data = {
            "titulo": titulo,
            "contenido": contenido,
            "versiculo": versiculo if versiculo else None,
            "fecha": ahora.strftime("%d/%m/%Y"),
            "activo": True
        }
        result = supabase.table("reflexiones").insert(data).execute()
        return True if result.data else False
    except Exception as e:
        print(f"Error en add_reflexion: {str(e)}")
        return False

def update_reflexion(id_, titulo, contenido, versiculo):
    try:
        data = {
            "titulo": titulo,
            "contenido": contenido,
            "versiculo": versiculo if versiculo else None
        }
        result = supabase.table("reflexiones").update(data).eq("id", id_).execute()
        return True if result.data else False
    except Exception as e:
        print(f"Error en update_reflexion: {str(e)}")
        return False

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
# ESTILOS - CORREGIDO: TEXTO NEGRO SOBRE FONDO BLANCO EN INPUTS
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

/* ============================================
   CORRECCIÓN: Inputs con texto NEGRO y fondo BLANCO
   ============================================ */
input, textarea, .stTextInput > div > div > input, .stTextArea > div > div > textarea {{
    background-color: #ffffff !important;
    color: #000000 !important;
    border: 2px solid #cccccc !important;
    border-radius: 12px !important;
}}

/* Select boxes */
.stSelectbox > div > div {{
    background-color: #ffffff !important;
    color: #000000 !important;
}}
.stSelectbox > div > div > div {{
    color: #000000 !important;
}}
.stSelectbox label {{
    color: #FFFFFF !important;
}}

/* Multiselect */
.stMultiSelect > div > div {{
    background-color: #ffffff !important;
    color: #000000 !important;
}}
.stMultiSelect > div > div > div {{
    color: #000000 !important;
}}
.stMultiSelect label {{
    color: #FFFFFF !important;
}}

/* Tags del multiselect */
.stMultiSelect [data-baseweb="tag"] {{
    background-color: #e0e0e0 !important;
    color: #000000 !important;
}}
.stMultiSelect [data-baseweb="tag"] span {{
    color: #000000 !important;
}}
.stMultiSelect [data-baseweb="tag"] svg {{
    fill: #000000 !important;
}}

/* Opciones desplegables */
div[data-baseweb="popover"] {{
    background-color: #ffffff !important;
    border: 2px solid #cccccc !important;
    border-radius: 12px !important;
    z-index: 9999 !important;
}}
div[data-baseweb="popover"] ul {{
    background-color: #ffffff !important;
}}
div[data-baseweb="popover"] li {{
    color: #000000 !important;
    background-color: #ffffff !important;
    padding: 8px 12px !important;
}}
div[data-baseweb="popover"] li:hover {{
    background-color: #e0e0e0 !important;
    color: #000000 !important;
}}
div[data-baseweb="popover"] li[aria-selected="true"] {{
    background-color: #d0d0d0 !important;
    color: #000000 !important;
}}

/* Number inputs */
input[type="number"] {{
    background-color: #ffffff !important;
    color: #000000 !important;
    border: 2px solid #cccccc !important;
    border-radius: 12px !important;
}}

/* Slider */
.stSlider > div > div > div {{
    color: #FFFFFF !important;
}}
.stSlider label {{
    color: #FFFFFF !important;
}}
.stSlider [data-baseweb="slider"] {{
    background-color: #FFD700 !important;
}}

/* Checkbox y Radio */
.stCheckbox label, .stRadio label {{
    color: #FFFFFF !important;
}}
.stCheckbox label span, .stRadio label span {{
    color: #FFFFFF !important;
}}

/* Botones */
.stButton > button {{ 
    background: linear-gradient(135deg, #FFD700, #CF142B) !important; 
    color: white !important; 
    border-radius: 25px !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3) !important;
    border: none !important;
}}
.stButton > button:hover {{
    transform: translateY(-3px) !important;
    box-shadow: 0 8px 20px rgba(255, 215, 0, 0.4) !important;
    background: linear-gradient(135deg, #FFE44D, #E01830) !important;
}}
.stButton > button:active {{
    transform: translateY(0px) !important;
    box-shadow: 0 2px 10px rgba(255, 215, 0, 0.2) !important;
}}

/* Botones de salud */
div[data-testid="column"] .stButton > button {{
    background: linear-gradient(135deg, #0a6b8a, #1a8aaa) !important;
    color: #FFFFFF !important;
    border: 2px solid #00d4ff !important;
    border-radius: 14px !important;
    padding: 14px 10px !important;
    font-size: 1em !important;
    font-weight: bold !important;
    box-shadow: 0 4px 20px rgba(0, 180, 216, 0.3) !important;
    transition: all 0.3s ease !important;
    width: 100% !important;
    text-shadow: 0 1px 2px rgba(0,0,0,0.3) !important;
}}
div[data-testid="column"] .stButton > button:hover {{
    background: linear-gradient(135deg, #00d4ff, #0099cc) !important;
    transform: translateY(-4px) !important;
    box-shadow: 0 8px 35px rgba(0, 180, 216, 0.6) !important;
    border-color: #FFD700 !important;
    color: #FFFFFF !important;
}}
div[data-testid="column"] .stButton > button:active {{
    transform: translateY(0px) !important;
    box-shadow: 0 2px 10px rgba(0, 180, 216, 0.2) !important;
}}
div[data-testid="column"] .stButton > button p {{
    color: #FFFFFF !important;
    font-weight: bold !important;
    margin: 0 !important;
}}

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
    <a href="https://api.whatsapp.com/send?text=Santa Teresa al Dia - {APP_URL}" target="_blank" style="display: inline-block; padding: 10px 25px; border-radius: 25px; background: #25D366; transition: all 0.3s ease;">📱 WhatsApp</a>
    <a href="https://www.facebook.com/sharer/sharer.php?u={APP_URL}" target="_blank" style="display: inline-block; padding: 10px 25px; border-radius: 25px; background: #1877F2; transition: all 0.3s ease;">📘 Facebook</a>
    <a href="https://www.instagram.com/" target="_blank" style="display: inline-block; padding: 10px 25px; border-radius: 25px; background: linear-gradient(45deg, #f09433, #d62976); transition: all 0.3s ease;">📸 Instagram</a>
    <button id="copyButton" style="display: inline-block; padding: 10px 25px; border-radius: 25px; background: #3498db; border: none; cursor: pointer; transition: all 0.3s ease;">📋 Copiar</button>
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
            "💬 Opiniones", "👥 Personajes", "⚖️ El Crimen No Paga", 
            "⚙️ Configuración", "💬 GESTIONAR COMENTARIOS",
            "🏥 GESTIONAR ENFERMEDADES"
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

# ============================================
# NUEVA SECCIÓN: HABLANDO CON TUS DOCTORES
# ============================================
st.markdown("### 🩺 Hablando con tus doctores")

col_salud = st.columns(4)
with col_salud[0]:
    if st.button("🩺 Evaluar Síntomas", use_container_width=True, key="tab_20"):
        st.session_state.selected_tab = 20
        st.rerun()
with col_salud[1]:
    if st.button("📍 Directorio Médico", use_container_width=True, key="tab_21"):
        st.session_state.selected_tab = 21
        st.rerun()
with col_salud[2]:
    if st.button("📚 Guías de Salud", use_container_width=True, key="tab_22"):
        st.session_state.selected_tab = 22
        st.rerun()
with col_salud[3]:
    if st.button("💬 Pregunta al Doctor", use_container_width=True, key="tab_23"):
        st.session_state.selected_tab = 23
        st.rerun()

st.markdown("---")

if 'selected_tab' not in st.session_state:
    st.session_state.selected_tab = 0

# ============================================
# CONTENIDO DE LAS SECCIONES EXISTENTES
# ============================================
# [Todas las secciones existentes TAB 0 - 10 van aquí]
# ============================================

# --- PORTADA (TAB 0) ---
if st.session_state.selected_tab == 0:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📰 Últimas Noticias")
        noticias = get_noticias()
        if not noticias.empty:
            for idx, n in noticias.head(5).iterrows():
                with st.expander(f"📰 {n['titulo']} - {n['categoria']} ({n['fecha']})"):
                    mostrar_imagen_segura(n.get('imagen_url'), 300)
                    st.write(n['contenido'])
                    mostrar_seccion_comentarios("noticia", n['id'], n['titulo'], es_admin)
        else:
            st.info("No hay noticias disponibles")
        
        st.markdown("### 📽️ Últimos Reportajes")
        reportajes = get_noticias(categoria="Reportajes")
        if not reportajes.empty:
            for idx, r in reportajes.head(3).iterrows():
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
            for idx, op in opiniones_portada.head(5).iterrows():
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
                for idx, n in noticias_cat.iterrows():
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
        for idx, n in negocios.iterrows():
            with st.expander(f"🏪 {n['nombre']}"):
                if n.get('imagenes_url') and n['imagenes_url']:
                    if isinstance(n['imagenes_url'], list) and len(n['imagenes_url']) > 0:
                        mostrar_imagenes_en_fila(n['imagenes_url'], max_imagenes=3)
                    elif isinstance(n['imagenes_url'], str):
                        mostrar_imagen_segura(n['imagenes_url'], 300)
                else:
                    st.caption("📷 Sin imágenes")
                
                st.write(f"**Reseña:** {n['resena']}")
                
                if n.get('video_url') and n['video_url']:
                    st.markdown("#### 🎥 Video del negocio")
                    mostrar_video_youtube(n['video_url'], width_percent=50)
                
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
                    for idx2, op in opiniones.iterrows():
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
    
    if es_admin:
        st.markdown("### ✏️ Crear Nueva Reflexión")
        with st.form("nueva_reflexion_form"):
            nuevo_titulo = st.text_input("Título de la reflexión *")
            nuevo_versiculo = st.text_input("Versículo (opcional)")
            nuevo_contenido = st.text_area("Contenido de la reflexión *", height=150)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("💾 Guardar como activa", use_container_width=True):
                    if nuevo_titulo and nuevo_contenido:
                        if add_reflexion(nuevo_titulo, nuevo_contenido, nuevo_versiculo):
                            st.success("✅ Reflexión guardada correctamente")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error("❌ Error al guardar la reflexión")
                    else:
                        st.error("❌ Título y contenido son obligatorios")
            with col2:
                if st.form_submit_button("❌ Limpiar", use_container_width=True):
                    st.rerun()
        
        st.markdown("---")
    
    st.markdown("### 📜 Reflexiones Anteriores")
    reflexiones = get_reflexiones()
    if not reflexiones.empty:
        for idx, r in reflexiones.iterrows():
            if ref is None or r['id'] != ref['id']:
                with st.expander(f"📖 {r['titulo']} - {r['fecha']}"):
                    st.write(r['contenido'])
                    if r.get('versiculo'):
                        st.caption(f"📖 {r['versiculo']}")
                    
                    if es_admin:
                        st.markdown("---")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(f"✏️ MODIFICAR", key=f"edit_ref_{r['id']}_{idx}"):
                                st.session_state.edit_reflexion = r.to_dict()
                                st.rerun()
                        with col2:
                            if st.button(f"🗑️ ELIMINAR", key=f"del_ref_{r['id']}_{idx}"):
                                if delete_reflexion(r['id']):
                                    st.success("✅ Reflexión eliminada")
                                    st.rerun()
                    
                    mostrar_seccion_comentarios("reflexion", r['id'], r['titulo'], es_admin)
    else:
        st.info("No hay reflexiones anteriores")
    
    if st.session_state.get('edit_reflexion'):
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

# --- CRÓNICAS (TAB 4) ---
elif st.session_state.selected_tab == 4:
    st.title("📜 Crónicas")
    estados = ["Todos", "Miranda", "Carabobo", "Distrito Capital", "Zulia", "Lara", "Aragua", "Bolivar", "Anzoategui", "Merida", "Tachira", "Nueva Esparta", "Sucre", "Falcon", "Barinas", "Portuguesa", "Guarico", "Cojedes", "Trujillo", "Yaracuy", "Apure", "Amazonas", "Delta Amacuro", "Vargas"]
    estado_filtro = st.selectbox("Filtrar por estado:", estados)
    cronicas = get_cronicas(estado_filtro if estado_filtro != "Todos" else None)
    if not cronicas.empty:
        for idx, c in cronicas.iterrows():
            with st.expander(f"📖 {c['titulo']} - {c['lugar']}, {c['estado']}"):
                if c.get('imagenes_url') and c['imagenes_url']:
                    if isinstance(c['imagenes_url'], list) and len(c['imagenes_url']) > 0:
                        mostrar_imagenes_en_fila(c['imagenes_url'], max_imagenes=3)
                    elif isinstance(c['imagenes_url'], str):
                        mostrar_imagen_segura(c['imagenes_url'], 200)
                st.write(c['contenido'])
                st.caption(f"📅 {c['fecha']}")
                mostrar_seccion_comentarios("cronica", c['id'], c['titulo'], es_admin)
                
                if es_admin:
                    st.markdown("---")
                    st.markdown("### 🔧 Administrar esta crónica")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✏️ MODIFICAR CRÓNICA", key=f"edit_cron_{c['id']}_{idx}"):
                            st.session_state.edit_cronica = c.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR CRÓNICA", key=f"del_cron_{c['id']}_{idx}"):
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
            for idx, v in videos.iterrows():
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
            for idx, t in tiktoks.iterrows():
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
            for idx, m in musicas.iterrows():
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
            for idx, d in denuncias.iterrows():
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
            for idx, op in opiniones.iterrows():
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
        for idx, p in personajes.iterrows():
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
        for idx, c in crimenes.iterrows():
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
# NUEVA SECCIÓN: HABLANDO CON TUS DOCTORES (TAB 20, 21, 22, 23)
# ============================================

# --- TAB 20: EVALUAR SÍNTOMAS ---
elif st.session_state.selected_tab == 20:
    st.title("🩺 Evaluación de Síntomas - Diagnóstico Inteligente")
    
    # ADVERTENCIA IMPORTANTE
    st.markdown("""
    <div style="background: rgba(255, 0, 0, 0.15); border: 2px solid #FF6B6B; border-radius: 15px; padding: 20px; margin-bottom: 25px;">
        <div style="display: flex; align-items: center; gap: 15px;">
            <span style="font-size: 2.5em;">⚠️</span>
            <div>
                <h3 style="color: #FF6B6B; margin: 0;">ADVERTENCIA IMPORTANTE</h3>
                <p style="margin: 5px 0 0 0; color: #FFFFFF;">
                    Esta herramienta es <strong>SOLO INFORMATIVA</strong> y NO reemplaza una consulta médica profesional.
                    Los resultados son una guía preliminar basada en la información proporcionada.
                    <br><br>
                    <strong>SI TIENES UNA EMERGENCIA, LLAMA INMEDIATAMENTE AL 911 O ACUDE AL CENTRO DE SALUD MÁS CERCANO.</strong>
                    <br>
                    Siempre consulta con un médico calificado para cualquier problema de salud.
                </p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    ### ¿Cómo funciona?
    1. Responde unas preguntas sobre tus síntomas (solo toma 3 minutos)
    2. Nuestro sistema analizará tus síntomas con una base de datos de más de 40 enfermedades
    3. Obtendrás un análisis probable de tu condición
    4. El reporte te ayudará a saber cuándo debes consultar a un médico
    """)
    
    if 'cuestionario_paso' not in st.session_state:
        st.session_state.cuestionario_paso = 1
    if 'respuestas' not in st.session_state:
        st.session_state.respuestas = {}
    if 'historial_consultas' not in st.session_state:
        st.session_state.historial_consultas = []
    
    # --- PASO 1: Datos Personales ---
    if st.session_state.cuestionario_paso == 1:
        with st.form("paso_1_consulta"):
            st.subheader("📋 Paso 1: Información Personal")
            st.markdown("Estos datos ayudan a personalizar los resultados.")
            
            col1, col2 = st.columns(2)
            with col1:
                edad = st.number_input("Edad", min_value=1, max_value=120, value=30, step=1)
            with col2:
                sexo = st.selectbox("Sexo biológico", ["Masculino", "Femenino", "Prefiero no decir"])
            
            peso = st.number_input("Peso aproximado (kg) - Opcional", min_value=10, max_value=300, value=70, step=1)
            altura = st.number_input("Altura aproximada (cm) - Opcional", min_value=50, max_value=250, value=170, step=1)
            
            condiciones = st.multiselect(
                "¿Tienes alguna condición médica preexistente?",
                ["Diabetes", "Hipertensión", "Asma", "Alergias", "Enfermedad cardíaca", "Depresión", "Ansiedad", "Artritis", "Ninguna", "Otra"]
            )
            
            submitted = st.form_submit_button("Siguiente →", use_container_width=True)
            if submitted:
                st.session_state.respuestas['edad'] = edad
                st.session_state.respuestas['sexo'] = sexo
                st.session_state.respuestas['peso'] = peso
                st.session_state.respuestas['altura'] = altura
                st.session_state.respuestas['condiciones'] = condiciones
                st.session_state.cuestionario_paso = 2
                st.rerun()
    
    # --- PASO 2: Síntomas ---
    elif st.session_state.cuestionario_paso == 2:
        with st.form("paso_2_consulta"):
            st.subheader("🩺 Paso 2: Cuéntanos tus síntomas")
            st.markdown("Selecciona todos los síntomas que estás experimentando.")
            
            sintomas_seleccionados = st.multiselect(
                "Selecciona tus síntomas (puedes elegir varios):",
                SINTOMAS_COMPLETOS
            )
            
            # Campo para síntomas adicionales
            otros_sintomas = st.text_input("¿Tienes algún síntoma adicional no listado? (Separado por comas)")
            
            if otros_sintomas:
                sintomas_adicionales = [s.strip() for s in otros_sintomas.split(",") if s.strip()]
                sintomas_seleccionados.extend(sintomas_adicionales)
            
            duracion = st.selectbox(
                "¿Cuánto tiempo llevas con estos síntomas?",
                ["Menos de 24 horas", "1-3 días", "4-7 días", "Más de una semana", "Más de un mes"]
            )
            
            intensidad = st.slider(
                "¿Cómo calificas la intensidad de los síntomas? (1 = Leve, 10 = Insoportable)",
                min_value=1, max_value=10, value=5
            )
            
            st.markdown("---")
            st.markdown("**Información adicional:**")
            
            medicamentos = st.text_input("¿Estás tomando algún medicamento? (Opcional)")
            alergias_med = st.text_input("¿Tienes alergias a medicamentos? (Opcional)")
            
            submitted = st.form_submit_button("Generar Diagnóstico", use_container_width=True)
            if submitted:
                if sintomas_seleccionados:
                    st.session_state.respuestas['sintomas'] = sintomas_seleccionados
                    st.session_state.respuestas['duracion'] = duracion
                    st.session_state.respuestas['intensidad'] = intensidad
                    st.session_state.respuestas['medicamentos'] = medicamentos
                    st.session_state.respuestas['alergias_med'] = alergias_med
                    st.session_state.cuestionario_paso = 3
                    st.rerun()
                else:
                    st.error("❌ Debes seleccionar al menos un síntoma.")
    
    # --- PASO 3: Diagnóstico ---
    elif st.session_state.cuestionario_paso == 3:
        st.subheader("📋 Análisis de Diagnóstico")
        st.markdown("*Basado en la información que proporcionaste.*")
        
        resp = st.session_state.respuestas
        sintomas = resp.get('sintomas', [])
        condiciones = resp.get('condiciones', [])
        edad = resp.get('edad', 30)
        sexo = resp.get('sexo', 'Femenino')
        
        # Ejecutar diagnóstico
        diagnosticos = diagnosticar_enfermedades(sintomas, condiciones, edad, sexo)
        
        if diagnosticos:
            st.markdown("### 📊 Análisis Probable")
            st.markdown(f"**Síntomas analizados:** {len(sintomas)} síntomas")
            st.markdown(f"**Edad:** {edad} años | **Sexo:** {sexo}")
            
            st.markdown("---")
            
            # Mostrar los diagnósticos
            for i, diag in enumerate(diagnosticos):
                nivel = diag["nivel"]
                color = diag["color"]
                
                if nivel == "Alta":
                    emoji = "🟢"
                    descripcion = "Alta coincidencia"
                elif nivel == "Media":
                    emoji = "🟡"
                    descripcion = "Coincidencia media"
                else:
                    emoji = "🟠"
                    descripcion = "Coincidencia baja"
                
                urgencia_emoji = "🔴" if diag["urgencia"] == "Alta" else "🟡" if diag["urgencia"] == "Media" else "🟢"
                
                with st.expander(f"#{i+1} Posible: {diag['enfermedad']} ({descripcion})"):
                    st.markdown(f"""
                    <div style="background: {color}20; border-left: 4px solid {color}; padding: 15px; border-radius: 8px;">
                        <h4 style="color: {color};">🔍 Posible {diag['enfermedad']}</h4>
                        <p><strong>Nivel de coincidencia:</strong> {emoji} {descripcion}</p>
                        <p><strong>Urgencia sugerida:</strong> {urgencia_emoji} {diag['urgencia']}</p>
                        <p><strong>Especialidad sugerida:</strong> {diag['especialidad']}</p>
                        <p><strong>Síntomas coincidentes:</strong> {', '.join(diag['sintomas_coincidentes'])}</p>
                        {f"<p><strong>Factores de riesgo:</strong> {', '.join(diag['factores_riesgo'])}</p>" if diag['factores_riesgo'] else ""}
                        <p><strong>Tratamiento sugerido:</strong> {diag['tratamiento']}</p>
                        <p><strong>Recomendaciones:</strong></p>
                        <ul>
                            {''.join([f'<li>{r}</li>' for r in diag['recomendaciones']])}
                        </ul>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Recomendaciones generales
            st.markdown("---")
            st.markdown("### 💡 Recomendaciones Generales")
            
            if any(d["urgencia"] == "Alta" for d in diagnosticos):
                st.warning("""
                ⚠️ **Se recomienda atención médica URGENTE.**
                Algunos de tus síntomas coinciden con condiciones que requieren evaluación médica inmediata.
                Por favor, acude a un centro de salud o llama al 911.
                """)
            elif any(d["urgencia"] == "Media" for d in diagnosticos):
                st.info("""
                🟡 **Se recomienda consulta médica PRONTO.**
                Tus síntomas sugieren condiciones que deben ser evaluadas por un especialista.
                Agenda una cita médica en los próximos días.
                """)
            else:
                st.success("""
                🟢 **Puedes manejar esto en casa.**
                Tus síntomas son leves y no sugieren condiciones graves. Descansa, hidrátate y monitorea tus síntomas.
                Si empeoran, consulta a un médico.
                """)
            
            # Resumen para el médico
            st.markdown("---")
            st.markdown("### 📋 Resumen para tu médico")
            st.info("""
            **Lleva esta información a tu consulta médica:**
            - Síntomas: {sintomas}
            - Duración: {duracion}
            - Intensidad: {intensidad}/10
            - Edad: {edad} años
            - Sexo: {sexo}
            - Medicamentos: {medicamentos}
            - Condiciones preexistentes: {condiciones}
            - Diagnósticos sugeridos: {diagnosticos}
            """.format(
                sintomas=', '.join(sintomas),
                duracion=resp.get('duracion', 'No especificada'),
                intensidad=resp.get('intensidad', 0),
                edad=edad,
                sexo=sexo,
                medicamentos=resp.get('medicamentos', 'Ninguno'),
                condiciones=', '.join(condiciones) if condiciones else 'Ninguna',
                diagnosticos=', '.join([d['enfermedad'] for d in diagnosticos[:3]])
            ))
            
            st.markdown("""
            <div style="background: rgba(255, 215, 0, 0.15); border: 2px solid #FFD700; border-radius: 10px; padding: 15px; margin: 20px 0;">
                <p style="text-align: center; margin: 0;">
                    <strong>⚠️ RECUERDA:</strong> Esta herramienta es solo informativa. 
                    Siempre consulta con un médico calificado para cualquier problema de salud.
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # Guardar en historial
            consulta = {
                "fecha": ahora.strftime("%d/%m/%Y %H:%M"),
                "sintomas": len(sintomas),
                "diagnostico": diagnosticos[0]["enfermedad"] if diagnosticos else "Sin diagnóstico",
                "urgencia": diagnosticos[0]["urgencia"] if diagnosticos else "Baja"
            }
            st.session_state.historial_consultas.append(consulta)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("📥 Descargar Reporte", use_container_width=True):
                    st.info("Funcionalidad de descarga en desarrollo")
            with col2:
                if st.button("🔄 Nueva Consulta", use_container_width=True):
                    st.session_state.cuestionario_paso = 1
                    st.session_state.respuestas = {}
                    st.rerun()
            with col3:
                if st.button("📋 Ver Mi Historial", use_container_width=True):
                    st.session_state.ver_historial = True
                    st.rerun()
            
            if st.session_state.get('ver_historial', False):
                st.markdown("---")
                st.markdown("### 📋 Tu Historial de Consultas")
                if st.session_state.historial_consultas:
                    for h in st.session_state.historial_consultas:
                        st.markdown(f"- **{h['fecha']}** - {h['sintomas']} síntomas - {h['diagnostico']} ({h['urgencia']})")
                else:
                    st.info("No tienes consultas guardadas")
                if st.button("Ocultar Historial"):
                    st.session_state.ver_historial = False
                    st.rerun()
        else:
            st.warning("No se encontraron coincidencias significativas con las enfermedades en nuestra base de datos.")
            st.info("""
            **Posibles razones:**
            - Los síntomas seleccionados son muy generales
            - La combinación de síntomas es poco común
            - Podría tratarse de una condición no incluida en nuestra base de datos
            
            **Recomendación:** Consulta a un médico para una evaluación profesional.
            """)
            if st.button("🔄 Nueva Consulta", use_container_width=True):
                st.session_state.cuestionario_paso = 1
                st.session_state.respuestas = {}
                st.rerun()

# --- TAB 21: DIRECTORIO MÉDICO (CON DIRECTORIO REAL DE SANTA TERESA) ---
elif st.session_state.selected_tab == 21:
    st.title("📍 Directorio Médico de Santa Teresa del Tuy")
    st.markdown("### Centros de salud, farmacias y especialistas locales")
    
    st.info("""
    ℹ️ **Información importante:**
    - Este directorio es colaborativo y se actualiza constantemente
    - Si conoces un centro de salud que no está listado, ¡puedes sugerirlo!
    - Los horarios y servicios pueden cambiar, verifica con el establecimiento
    """)
    
    # Mostrar el directorio real
    for centro in DIRECTORIO_SALUD:
        with st.expander(f"{centro['tipo']}: {centro['nombre']}"):
            st.markdown(f"**Dirección:** {centro['direccion']}")
            st.markdown(f"**Teléfono:** {centro['telefono']}")
            st.markdown(f"**Horario:** {centro['horario']}")
            st.markdown(f"**Servicios:** {', '.join(centro['servicios'])}")
            st.caption(f"📍 Coordenadas aproximadas: {centro['coordenadas']}")
            col1, col2 = st.columns(2)
            with col1:
                st.button("📍 Ver en Mapa", key=f"mapa_{centro['nombre']}")
            with col2:
                st.button("📞 Llamar", key=f"llamar_{centro['nombre']}")
    
    st.markdown("---")
    st.markdown("### ➕ Sugerir un centro de salud")
    with st.form("sugerir_centro"):
        nombre_sug = st.text_input("Nombre del centro *")
        tipo_sug = st.selectbox("Tipo", ["Hospital", "Ambulatorio", "Farmacia", "Clínica Privada", "CDI", "Módulo de Salud", "Clínica Odontológica"])
        direccion_sug = st.text_area("Dirección *")
        telefono_sug = st.text_input("Teléfono")
        horario_sug = st.text_input("Horario")
        servicios_sug = st.text_input("Servicios que ofrece")
        
        submitted = st.form_submit_button("Enviar Sugerencia")
        if submitted:
            if nombre_sug and direccion_sug:
                st.success("✅ ¡Gracias! Tu sugerencia será revisada por el administrador.")
                st.balloons()
            else:
                st.error("❌ El nombre y la dirección son obligatorios")

# --- TAB 22: GUÍAS DE SALUD ---
elif st.session_state.selected_tab == 22:
    st.title("📚 Guías de Salud")
    st.markdown("### Información útil para el cuidado de tu salud")
    
    st.info("""
    ℹ️ **Nota importante:** Estas guías son educativas y no reemplazan el consejo médico profesional.
    """)
    
    guias = {
        "Primeros Auxilios Básicos": {
            "descripcion": "Qué hacer en situaciones de emergencia comunes",
            "contenido": """
            **🩹 Heridas y cortes:**
            1. Lava el área con agua y jabón
            2. Aplica presión con una gasa limpia para detener el sangrado
            3. Cubre con un vendaje limpio
            
            **🔥 Quemaduras:**
            1. Enfría la quemadura con agua fría (no hielo) por 10-15 minutos
            2. No apliques cremas, manteca o remedios caseros
            3. Cubre con un paño limpio y húmedo
            
            **🦴 Fracturas:**
            1. Inmoviliza el área afectada
            2. Aplica hielo envuelto en un paño
            3. Busca atención médica inmediata
            """
        },
        "Fiebre en Adultos": {
            "descripcion": "Cómo manejar la fiebre y cuándo preocuparse",
            "contenido": """
            **¿Qué es fiebre?**
            - Temperatura mayor a 38°C (100.4°F)
            - Es un mecanismo de defensa del cuerpo
            
            **Cuándo consultar al médico:**
            - Fiebre de más de 39.5°C (103°F)
            - Fiebre que dura más de 3 días
            - Acompañada de dolor de cabeza intenso, dificultad para respirar o confusión
            - En niños menores de 3 meses: cualquier fiebre requiere atención médica
            
            **Recomendaciones:**
            - Descansa y mantente hidratado
            - Toma medicamentos para bajar la fiebre (paracetamol) según indicaciones
            - No te automediques con antibióticos
            """
        },
        "Prevención de Enfermedades": {
            "descripcion": "Consejos para mantenerte saludable",
            "contenido": """
            **💧 Hidratación:**
            - Bebe al menos 2 litros de agua al día
            - Aumenta la ingesta en clima caliente o con actividad física
            
            **🍎 Alimentación saludable:**
            - Come frutas y verduras diariamente
            - Reduce el consumo de azúcar y grasas saturadas
            - Incluye proteínas magras en tu dieta
            
            **🏃 Actividad física:**
            - Realiza al menos 30 minutos de ejercicio moderado al día
            - Camina, trota o práctica deporte regularmente
            
            **💤 Descanso:**
            - Duerme entre 7-8 horas diarias
            - Mantén horarios regulares de sueño
            """
        },
        "Enfermedades Crónicas más Comunes": {
            "descripcion": "Información sobre condiciones de salud frecuentes",
            "contenido": """
            **🩸 Diabetes Tipo 2:**
            - Control de glucosa regular
            - Dieta balanceada baja en azúcares
            - Ejercicio diario
            - Medicación según indicación médica
            
            **❤️ Hipertensión Arterial:**
            - Medir presión arterial regularmente
            - Reducir consumo de sal
            - Mantener peso saludable
            - Evitar el estrés
            
            **🫁 EPOC (Enfermedad Pulmonar Obstructiva Crónica):**
            - Dejar de fumar
            - Ejercicios respiratorios
            - Evitar contaminantes
            - Seguir tratamiento médico
            
            **🦴 Artrosis:**
            - Ejercicio de bajo impacto
            - Control de peso
            - Fisioterapia
            - Medicamentos antiinflamatorios
            
            **🧠 Ansiedad y Depresión:**
            - Terapia psicológica
            - Ejercicio regular
            - Técnicas de relajación
            - Apoyo familiar y social
            """
        },
        "Enfermedades Cardiológicas": {
            "descripcion": "Información sobre el corazón y su cuidado",
            "contenido": """
            **❤️ Infarto Agudo de Miocardio:**
            - Dolor en el pecho que se irradia al brazo izquierdo
            - LLAMAR AL 911 INMEDIATAMENTE
            - No automedicarse
            - Mantener reposo
            
            **🫀 Arritmias Cardíacas:**
            - Palpitaciones irregulares
            - Evitar cafeína y alcohol
            - Control médico regular
            
            **🩺 Hipertensión:**
            - Control periódico de presión
            - Reducir consumo de sal
            - Ejercicio moderado
            """
        }
    }
    
    for titulo, info in guias.items():
        with st.expander(f"📖 {titulo}"):
            st.markdown(f"**{info['descripcion']}**")
            st.markdown("---")
            st.markdown(info['contenido'])
    
    st.markdown("---")
    st.markdown("### 🏥 Recursos de Emergencia")
    st.markdown("""
    - **🚑 Emergencias Médicas:** 911
    - **🚒 Bomberos:** 0800-BOMBEROS (0800-266-2376)
    - **🚨 Policía:** 911
    - **Hospital General de Santa Teresa:** 0212-XXX-XXXX
    """)

# --- TAB 23: PREGUNTA AL DOCTOR (CON RESPUESTAS INTELIGENTES) ---
elif st.session_state.selected_tab == 23:
    st.title("💬 Pregunta al Doctor")
    st.markdown("### Haz una pregunta sobre tu salud a nuestro equipo de expertos")
    
    st.info("""
    ⚠️ **Nota importante:** Las respuestas son orientativas y NO reemplazan una consulta médica presencial.
    """)
    
    # Inicializar estado para preguntas
    if 'preguntas_doctor' not in st.session_state:
        st.session_state.preguntas_doctor = []
    if 'pregunta_actual' not in st.session_state:
        st.session_state.pregunta_actual = ""
    
    st.markdown("---")
    st.markdown("### 📝 Haz tu pregunta")
    st.caption("Escribe tu pregunta de salud de forma clara y detallada.")
    
    with st.form("form_pregunta_doctor"):
        nombre_pregunta = st.text_input("Tu nombre (opcional)")
        titulo_pregunta = st.text_input("Título de tu pregunta *")
        pregunta = st.text_area("Describe tu pregunta o inquietud de salud *", height=150)
        
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("📤 Enviar Pregunta", use_container_width=True)
        with col2:
            # Botón para simular respuesta automática
            if st.form_submit_button("🤖 Respuesta Automática", use_container_width=True):
                if titulo_pregunta and pregunta:
                    respuesta_auto = responder_pregunta_medica(pregunta)
                    nueva_pregunta = {
                        "id": len(st.session_state.preguntas_doctor) + 1,
                        "nombre": nombre_pregunta if nombre_pregunta else "Anónimo",
                        "titulo": titulo_pregunta,
                        "pregunta": pregunta,
                        "fecha": ahora.strftime("%d/%m/%Y %H:%M"),
                        "respuesta": respuesta_auto,
                        "respondida": True,
                        "automatica": True
                    }
                    st.session_state.preguntas_doctor.append(nueva_pregunta)
                    st.success("✅ ¡Respuesta generada automáticamente!")
                    st.rerun()
                else:
                    st.error("❌ El título y la descripción son obligatorios.")
        
        if submitted:
            if titulo_pregunta and pregunta:
                nueva_pregunta = {
                    "id": len(st.session_state.preguntas_doctor) + 1,
                    "nombre": nombre_pregunta if nombre_pregunta else "Anónimo",
                    "titulo": titulo_pregunta,
                    "pregunta": pregunta,
                    "fecha": ahora.strftime("%d/%m/%Y %H:%M"),
                    "respuesta": None,
                    "respondida": False,
                    "automatica": False
                }
                st.session_state.preguntas_doctor.append(nueva_pregunta)
                st.success("✅ ¡Pregunta enviada! Un especialista la responderá pronto.")
                st.rerun()
            else:
                st.error("❌ El título y la descripción son obligatorios.")
    
    st.markdown("---")
    st.markdown("### 📋 Preguntas y respuestas")
    
    # Mostrar preguntas (solo las respondidas para el público general)
    preguntas_respondidas = [p for p in st.session_state.preguntas_doctor if p['respondida']]
    preguntas_pendientes = [p for p in st.session_state.preguntas_doctor if not p['respondida']]
    
    # Si es admin, mostrar todas las preguntas
    if es_admin:
        st.markdown("#### 👨‍⚕️ Panel de Administración - Preguntas Pendientes")
        if preguntas_pendientes:
            for p in preguntas_pendientes:
                with st.container():
                    st.markdown(f"**ID: {p['id']}** - **{p['titulo']}**")
                    st.markdown(f"**👤 {p['nombre']}** *{p['fecha']}*")
                    st.markdown(f"**Pregunta:** {p['pregunta']}")
                    
                    # Opción para respuesta automática desde admin
                    if st.button(f"🤖 Generar Respuesta", key=f"gen_resp_{p['id']}"):
                        respuesta_auto = responder_pregunta_medica(p['pregunta'])
                        p['respuesta'] = respuesta_auto
                        p['respondida'] = True
                        p['automatica'] = True
                        st.success("✅ Respuesta generada")
                        st.rerun()
                    
                    with st.form(key=f"responder_pregunta_{p['id']}"):
                        respuesta = st.text_area("Respuesta del doctor", key=f"respuesta_{p['id']}")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("✅ Responder", use_container_width=True):
                                if respuesta:
                                    p['respuesta'] = respuesta
                                    p['respondida'] = True
                                    st.success("✅ Respuesta publicada")
                                    st.rerun()
                                else:
                                    st.error("❌ Escribe una respuesta")
                        with col2:
                            if st.form_submit_button("🗑️ Eliminar", use_container_width=True):
                                st.session_state.preguntas_doctor.remove(p)
                                st.success("✅ Pregunta eliminada")
                                st.rerun()
                    st.divider()
        else:
            st.info("No hay preguntas pendientes")
        
        st.markdown("---")
        st.markdown("#### ✅ Preguntas Respondidas")
    else:
        st.markdown("#### ✅ Preguntas Respondidas")
    
    if preguntas_respondidas:
        for p in preguntas_respondidas:
            with st.expander(f"📝 {p['titulo']}"):
                st.markdown(f"**👤 {p['nombre']}** *{p['fecha']}*")
                st.markdown(f"**Pregunta:** {p['pregunta']}")
                st.markdown(f"**💬 Respuesta del Doctor:**")
                st.markdown(f"*{p['respuesta']}*")
                if p.get('automatica', False):
                    st.caption("🤖 Respuesta generada automáticamente (orientativa)")
                st.divider()
    else:
        st.info("No hay preguntas respondidas aún. ¡Sé el primero en preguntar!")

# ============================================
# PANEL ADMIN (COMPLETO)
# ============================================
if st.session_state.get('es_admin', False):
    admin_opt = st.session_state.get('admin_opt', "📰 Noticias")
    st.title("🔧 Panel de Administración")
    
    # --- GESTIONAR ENFERMEDADES ---
    if "🏥 GESTIONAR ENFERMEDADES" in admin_opt:
        st.subheader("🏥 Gestión de Enfermedades")
        st.markdown("### Base de datos de enfermedades para el diagnóstico")
        st.info("Desde aquí puedes agregar, modificar o eliminar enfermedades de la base de datos.")
        
        # Cargar enfermedades desde Supabase
        cargar_enfermedades_de_supabase()
        
        # --- Agregar nueva enfermedad ---
        with st.expander("➕ AGREGAR NUEVA ENFERMEDAD", expanded=True):
            with st.form("form_agregar_enfermedad"):
                st.markdown("#### Información de la enfermedad")
                
                nombre_nuevo = st.text_input("Nombre de la enfermedad *")
                col1, col2 = st.columns(2)
                with col1:
                    especialidad_nueva = st.text_input("Especialidad *")
                    urgencia_nueva = st.selectbox("Urgencia", ["Baja", "Media", "Alta"])
                with col2:
                    tratamiento_nuevo = st.text_area("Tratamiento sugerido *")
                
                sintomas_nuevos = st.text_area("Síntomas (separados por coma) *", help="Ejemplo: dolor de cabeza, fiebre, tos")
                factores_riesgo_nuevos = st.text_area("Factores de riesgo (separados por coma)", help="Ejemplo: tabaquismo, obesidad, estrés")
                recomendaciones_nuevas = st.text_area("Recomendaciones (una por línea)", help="Ejemplo: Descanso, Hidratación, Consulta con médico")
                
                if st.form_submit_button("💾 Guardar Enfermedad"):
                    if nombre_nuevo and especialidad_nueva and tratamiento_nuevo and sintomas_nuevos:
                        # Procesar datos
                        sintomas_lista = [s.strip() for s in sintomas_nuevos.split(",") if s.strip()]
                        factores_lista = [f.strip() for f in factores_riesgo_nuevos.split(",") if f.strip()] if factores_riesgo_nuevos else []
                        recomendaciones_lista = [r.strip() for r in recomendaciones_nuevas.split("\n") if r.strip()] if recomendaciones_nuevas else []
                        
                        nueva_enfermedad = {
                            "sintomas": sintomas_lista,
                            "factores_riesgo": factores_lista,
                            "especialidad": especialidad_nueva,
                            "urgencia": urgencia_nueva,
                            "recomendaciones": recomendaciones_lista,
                            "tratamiento": tratamiento_nuevo
                        }
                        
                        if guardar_enfermedad_en_supabase(nombre_nuevo, nueva_enfermedad):
                            BASE_DATOS_ENFERMEDADES[nombre_nuevo] = nueva_enfermedad
                            st.success(f"✅ Enfermedad '{nombre_nuevo}' agregada correctamente")
                            st.rerun()
                        else:
                            st.error("❌ Error al guardar la enfermedad")
                    else:
                        st.error("❌ Los campos marcados con * son obligatorios")
        
        st.markdown("---")
        st.markdown("### 📋 Enfermedades registradas")
        st.markdown(f"**Total de enfermedades:** {len(BASE_DATOS_ENFERMEDADES)}")
        
        # Buscador
        busqueda = st.text_input("🔍 Buscar enfermedad:", placeholder="Escribe el nombre de la enfermedad...")
        
        enfermedades_mostrar = BASE_DATOS_ENFERMEDADES
        if busqueda:
            enfermedades_mostrar = {k: v for k, v in BASE_DATOS_ENFERMEDADES.items() if busqueda.lower() in k.lower()}
        
        if enfermedades_mostrar:
            for nombre, info in list(enfermedades_mostrar.items())[:20]:
                with st.expander(f"📋 {nombre}", expanded=False):
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"**Especialidad:** {info['especialidad']}")
                        st.markdown(f"**Urgencia:** {info['urgencia']}")
                        st.markdown(f"**Síntomas:** {', '.join(info['sintomas'])}")
                        st.markdown(f"**Factores de riesgo:** {', '.join(info['factores_riesgo']) if info['factores_riesgo'] else 'Ninguno'}")
                        st.markdown(f"**Tratamiento:** {info['tratamiento']}")
                        st.markdown(f"**Recomendaciones:**")
                        for rec in info['recomendaciones']:
                            st.markdown(f"- {rec}")
                    with col2:
                        if st.button(f"✏️ Editar", key=f"edit_enf_{nombre}"):
                            st.session_state.edit_enfermedad = nombre
                            st.rerun()
                    with col3:
                        if st.button(f"🗑️ Eliminar", key=f"del_enf_{nombre}"):
                            if eliminar_enfermedad_de_supabase(nombre):
                                st.success(f"✅ Enfermedad '{nombre}' eliminada")
                                st.rerun()
                            else:
                                st.error("❌ Error al eliminar")
            
            if len(enfermedades_mostrar) > 20:
                st.info(f"Mostrando 20 de {len(enfermedades_mostrar)} enfermedades. Usa el buscador para filtrar.")
        else:
            st.info("No se encontraron enfermedades")
        
        # --- Editar enfermedad ---
        if st.session_state.get('edit_enfermedad'):
            nombre_edit = st.session_state.edit_enfermedad
            info_edit = BASE_DATOS_ENFERMEDADES.get(nombre_edit)
            
            if info_edit:
                st.markdown("---")
                st.markdown(f"### ✏️ Editando: {nombre_edit}")
                with st.form("form_editar_enfermedad"):
                    nuevo_nombre = st.text_input("Nombre", value=nombre_edit)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        nueva_especialidad = st.text_input("Especialidad", value=info_edit['especialidad'])
                        nueva_urgencia = st.selectbox("Urgencia", ["Baja", "Media", "Alta"], index=["Baja", "Media", "Alta"].index(info_edit['urgencia']))
                    with col2:
                        nuevo_tratamiento = st.text_area("Tratamiento", value=info_edit['tratamiento'])
                    
                    nuevos_sintomas = st.text_area("Síntomas (separados por coma)", value=", ".join(info_edit['sintomas']))
                    nuevos_factores = st.text_area("Factores de riesgo (separados por coma)", value=", ".join(info_edit['factores_riesgo']) if info_edit['factores_riesgo'] else "")
                    nuevas_recomendaciones = st.text_area("Recomendaciones (una por línea)", value="\n".join(info_edit['recomendaciones']) if info_edit['recomendaciones'] else "")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("💾 Guardar cambios"):
                            sintomas_lista = [s.strip() for s in nuevos_sintomas.split(",") if s.strip()]
                            factores_lista = [f.strip() for f in nuevos_factores.split(",") if f.strip()] if nuevos_factores else []
                            recomendaciones_lista = [r.strip() for r in nuevas_recomendaciones.split("\n") if r.strip()] if nuevas_recomendaciones else []
                            
                            enfermedad_editada = {
                                "sintomas": sintomas_lista,
                                "factores_riesgo": factores_lista,
                                "especialidad": nueva_especialidad,
                                "urgencia": nueva_urgencia,
                                "recomendaciones": recomendaciones_lista,
                                "tratamiento": nuevo_tratamiento
                            }
                            
                            # Eliminar la antigua si cambió el nombre
                            if nuevo_nombre != nombre_edit:
                                eliminar_enfermedad_de_supabase(nombre_edit)
                            
                            if guardar_enfermedad_en_supabase(nuevo_nombre, enfermedad_editada):
                                if nuevo_nombre != nombre_edit and nombre_edit in BASE_DATOS_ENFERMEDADES:
                                    del BASE_DATOS_ENFERMEDADES[nombre_edit]
                                BASE_DATOS_ENFERMEDADES[nuevo_nombre] = enfermedad_editada
                                st.success("✅ Enfermedad actualizada correctamente")
                                del st.session_state.edit_enfermedad
                                st.rerun()
                            else:
                                st.error("❌ Error al guardar los cambios")
                    with col2:
                        if st.form_submit_button("❌ Cancelar"):
                            del st.session_state.edit_enfermedad
                            st.rerun()
    
    # --- GESTIONAR COMENTARIOS ---
    elif "💬 GESTIONAR COMENTARIOS" in admin_opt:
        st.subheader("💬 Gestión Centralizada de Comentarios")
        st.markdown("### Todos los comentarios de las crónicas")
        st.info("Desde aquí puedes modificar o eliminar cualquier comentario de las crónicas")
        
        comentarios = obtener_comentarios_todos(seccion="cronica")
        
        if comentarios.empty:
            st.info("No hay comentarios registrados en las crónicas")
        else:
            cronicas = get_cronicas()
            cronica_dict = {str(c['id']): c['titulo'] for idx, c in cronicas.iterrows()}
            
            st.markdown(f"**Total de comentarios:** {len(comentarios)}")
            
            if st.button("🗑️ ELIMINAR TODOS LOS COMENTARIOS", key="eliminar_todos_comentarios"):
                if st.session_state.get('confirmar_eliminar_todos', False):
                    for idx2, com in comentarios.iterrows():
                        eliminar_comentario(com['id'])
                    st.success(f"✅ Se eliminaron {len(comentarios)} comentarios")
                    st.session_state['confirmar_eliminar_todos'] = False
                    st.rerun()
                else:
                    st.session_state['confirmar_eliminar_todos'] = True
                    st.warning("⚠️ ¡CONFIRMAR! Haz clic nuevamente en ELIMINAR TODOS para confirmar")
            
            st.markdown("---")
            
            for idx, com in comentarios.iterrows():
                with st.container():
                    titulo_cronica = cronica_dict.get(str(com['item_id']), f"ID: {com['item_id']}")
                    
                    col1, col2, col3, col4 = st.columns([4, 2, 1, 1])
                    with col1:
                        st.markdown(f"**📖 Crónica:** {titulo_cronica}")
                        st.markdown(f"**👤 {com['usuario']}** *{com['fecha']}*")
                        text_key = f"text_com_central_{com['id']}_{idx}"
                        nuevo_texto = st.text_area(
                            "Comentario", 
                            value=com['comentario'], 
                            key=text_key,
                            label_visibility="collapsed"
                        )
                    with col2:
                        st.markdown(f"**ID:** {com['id']}")
                    with col3:
                        if st.button(f"💾 Guardar", key=f"guardar_central_{com['id']}_{idx}"):
                            texto_actualizado = st.session_state.get(text_key, com['comentario'])
                            if actualizar_comentario(com['id'], texto_actualizado):
                                st.success("✅ Comentario actualizado")
                                st.rerun()
                            else:
                                st.error("❌ Error al actualizar")
                    with col4:
                        if st.button(f"🗑️ Eliminar", key=f"eliminar_central_{com['id']}_{idx}"):
                            if eliminar_comentario(com['id']):
                                st.success("✅ Comentario eliminado")
                                st.rerun()
                            else:
                                st.error("❌ Error al eliminar")
                    st.divider()
    
    # --- NOTICIAS ---
    elif "📰 Noticias" in admin_opt:
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
            for idx, n in noticias.iterrows():
                with st.expander(f"📰 {n['titulo']} - {n['categoria']} ({n['fecha']})"):
                    mostrar_imagen_segura(n.get('imagen_url'), 300)
                    st.write(f"**Contenido:** {n['contenido']}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button(f"✏️ MODIFICAR", key=f"edit_noti_{n['id']}_{idx}"):
                            st.session_state.edit_noticia = n.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR", key=f"del_noti_{n['id']}_{idx}"):
                            if delete_noticia(n['id']):
                                st.success("✅ Noticia eliminada")
                                st.rerun()
                    with col3:
                        if st.button(f"💬 COMENTARIOS", key=f"com_noti_{n['id']}_{idx}"):
                            st.session_state.gestionar_comentarios_noticia = n['id']
                            st.rerun()
                    
                    if st.session_state.get('gestionar_comentarios_noticia') == n['id']:
                        gestionar_comentarios_admin("noticia", n['id'], n['titulo'])
                        if st.button("❌ Cerrar", key=f"cerrar_com_noti_{n['id']}_{idx}"):
                            del st.session_state.gestionar_comentarios_noticia
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
    
    # --- NEGOCIOS (ADMIN) ---
    elif "🏪 Negocios" in admin_opt:
        st.subheader("🏪 Gestionar Negocios")
        
        with st.expander("➕ CREAR nuevo negocio", expanded=True):
            with st.form("fneg"):
                nombre = st.text_input("Nombre del negocio *")
                resena = st.text_area("Reseña *")
                google_maps_url = st.text_input("Enlace Google Maps (opcional)", placeholder="https://maps.google.com/...")
                video_url = st.text_input("Enlace YouTube (opcional)", placeholder="https://www.youtube.com/watch?v=XXXXX")
                
                if video_url and video_url.strip():
                    video_id = extraer_video_id(video_url)
                    if video_id:
                        st.markdown("#### 📹 Vista previa del video")
                        st.video(f"https://www.youtube.com/embed/{video_id}")
                    else:
                        st.warning("⚠️ URL de YouTube no válida")
                
                imagenes = st.file_uploader("Fotos (máximo 3)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
                if len(imagenes) > 3:
                    st.error("Máximo 3 fotos por negocio")
                elif st.form_submit_button("➕ Agregar Negocio"):
                    if nombre and resena:
                        if add_negocio(nombre, resena, google_maps_url, video_url, imagenes):
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
            for idx, n in negocios.iterrows():
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
                    
                    if n.get('video_url') and n['video_url']:
                        st.markdown("#### 🎥 Video actual")
                        mostrar_video_youtube(n['video_url'], width_percent=30)
                    
                    if n.get('google_maps_url') and n['google_maps_url']:
                        st.markdown(f"📍 [Ver en Google Maps]({n['google_maps_url']})")
                    
                    st.markdown("---")
                    st.markdown("#### 💬 Opiniones del negocio")
                    opiniones_neg = get_opiniones_negocio(n['id'])
                    if not opiniones_neg.empty:
                        for idx2, op in opiniones_neg.iterrows():
                            stars = "⭐" * int(op['calificacion']) + "☆" * (5 - int(op['calificacion']))
                            st.markdown(f"**👤 {op['usuario']}** {stars}")
                            st.write(f"\"{op['comentario']}\"")
                            st.caption(f"📅 {op['fecha']}")
                            if st.button(f"🗑️ Eliminar opinión", key=f"del_opinion_{op['id']}_{idx2}"):
                                if delete_opinion_negocio(op['id']):
                                    st.rerun()
                            st.divider()
                    else:
                        st.info("No hay opiniones para este negocio")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✏️ MODIFICAR", key=f"edit_neg_{n['id']}_{idx}"):
                            st.session_state.edit_negocio = n.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR", key=f"del_neg_{n['id']}_{idx}"):
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
                nuevo_video = st.text_input("Enlace YouTube", value=n.get('video_url', ''))
                
                if nuevo_video and nuevo_video.strip():
                    video_id = extraer_video_id(nuevo_video)
                    if video_id:
                        st.markdown("#### 📹 Vista previa del video")
                        st.video(f"https://www.youtube.com/embed/{video_id}")
                    else:
                        st.warning("⚠️ URL de YouTube no válida")
                
                nuevas_imagenes = st.file_uploader("Nuevas fotos (opcional, máximo 3)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Guardar cambios"):
                        if update_negocio(n['id'], nuevo_nombre, nueva_resena, nuevo_google_maps, nuevo_video, nuevas_imagenes):
                            st.success("✅ Negocio actualizado")
                            del st.session_state.edit_negocio
                            st.rerun()
                with col2:
                    if st.form_submit_button("❌ Cancelar"):
                        del st.session_state.edit_negocio
                        st.rerun()
    
    # --- REFLEXIONES (ADMIN) ---
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
            for idx, r in reflexiones.iterrows():
                with st.expander(f"📖 {r['titulo']} - {r['fecha']}"):
                    st.write(r['contenido'])
                    if r.get('versiculo'):
                        st.caption(f"📖 {r['versiculo']}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button(f"✏️ MODIFICAR", key=f"edit_ref_admin_{r['id']}_{idx}"):
                            st.session_state.edit_reflexion = r.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR", key=f"del_ref_admin_{r['id']}_{idx}"):
                            if delete_reflexion(r['id']):
                                st.success("✅ Reflexión eliminada")
                                st.rerun()
                    with col3:
                        if st.button(f"💬 COMENTARIOS", key=f"com_ref_{r['id']}_{idx}"):
                            st.session_state.gestionar_comentarios_reflexion = r['id']
                            st.rerun()
                    
                    if st.session_state.get('gestionar_comentarios_reflexion') == r['id']:
                        gestionar_comentarios_admin("reflexion", r['id'], r['titulo'])
                        if st.button("❌ Cerrar", key=f"cerrar_com_ref_{r['id']}_{idx}"):
                            del st.session_state.gestionar_comentarios_reflexion
                            st.rerun()
        else:
            st.info("No hay reflexiones registradas")
        
        if 'edit_reflexion' in st.session_state:
            r = st.session_state.edit_reflexion
            st.markdown("---")
            st.subheader(f"✏️ Modificando: {r['titulo']}")
            with st.form("edit_reflexion_admin_form"):
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
    
    # --- CRÓNICAS (ADMIN) ---
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
            for idx, c in cronicas.iterrows():
                with st.expander(f"📖 {c['titulo']} - {c['lugar']}, {c['estado']}"):
                    if c.get('imagenes_url') and c['imagenes_url']:
                        if isinstance(c['imagenes_url'], list):
                            for img_url in c['imagenes_url']:
                                mostrar_imagen_segura(img_url, 200)
                        elif isinstance(c['imagenes_url'], str):
                            mostrar_imagen_segura(c['imagenes_url'], 200)
                    st.write(f"**Contenido:** {c['contenido']}")
                    st.caption(f"📅 {c['fecha']}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button(f"✏️ MODIFICAR", key=f"edit_cron_admin_{c['id']}_{idx}"):
                            st.session_state.edit_cronica = c.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR", key=f"del_cron_admin_{c['id']}_{idx}"):
                            if delete_cronica(c['id']):
                                st.success("✅ Crónica eliminada")
                                st.rerun()
                    with col3:
                        if st.button(f"💬 COMENTARIOS", key=f"com_cron_{c['id']}_{idx}"):
                            st.session_state.gestionar_comentarios_cronica = c['id']
                            st.rerun()
                    
                    if st.session_state.get('gestionar_comentarios_cronica') == c['id']:
                        gestionar_comentarios_admin("cronica", c['id'], c['titulo'])
                        if st.button("❌ Cerrar", key=f"cerrar_com_cron_{c['id']}_{idx}"):
                            del st.session_state.gestionar_comentarios_cronica
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
            for idx, v in videos.iterrows():
                with st.expander(f"🎬 {v['titulo']}"):
                    mostrar_video_youtube(v['video_url'], width_percent=50)
                    st.caption(f"📅 {v['fecha']}")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✏️ MODIFICAR", key=f"edit_vid_{v['id']}_{idx}"):
                            st.session_state.edit_video = v.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR", key=f"del_vid_{v['id']}_{idx}"):
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
            for idx, t in tiktoks.iterrows():
                with st.expander(f"📱 {t['titulo']}"):
                    mostrar_tiktok(t['tiktok_url'], width_percent=50)
                    st.caption(f"📅 {t['fecha']}")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✏️ MODIFICAR", key=f"edit_tik_{t['id']}_{idx}"):
                            st.session_state.edit_tiktok = t.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR", key=f"del_tik_{t['id']}_{idx}"):
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
            for idx, m in musicas.iterrows():
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
            for idx, d in denuncias.iterrows():
                with st.expander(f"📌 {d['titulo']} - {d['estatus']}"):
                    st.write(f"**Denunciante:** {d['denunciante']}")
                    st.write(f"**Descripción:** {d['descripcion']}")
                    st.write(f"**Ubicación:** {d['ubicacion']}")
                    st.caption(f"📅 {d['fecha']}")
                    
                    nuevo_estado = st.selectbox("Cambiar estado:", ["Pendiente", "En revisión", "Resuelta", "Descartada"], 
                                               index=["Pendiente", "En revisión", "Resuelta", "Descartada"].index(d['estatus']),
                                               key=f"est_{d['id']}_{idx}")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Actualizar estado", key=f"upd_{d['id']}_{idx}"):
                            if update_denuncia_status(d['id'], nuevo_estado):
                                st.success("Estado actualizado")
                                st.rerun()
                    with col2:
                        if st.button("🗑️ ELIMINAR denuncia", key=f"del_den_{d['id']}_{idx}"):
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
            for idx, op in opiniones_pendientes.iterrows():
                if not op['aprobada']:
                    with st.expander(f"👤 {op['usuario']} - {op['calificacion']}⭐"):
                        st.write(f"**Comentario:** {op['comentario']}")
                        st.caption(f"📅 {op['fecha']}")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ APROBAR", key=f"aprob_{op['id']}_{idx}"):
                                if approve_opinion(op['id']):
                                    st.success("Opinión aprobada")
                                    st.rerun()
                        with col2:
                            if st.button("🗑️ ELIMINAR", key=f"del_op_{op['id']}_{idx}"):
                                if delete_opinion(op['id']):
                                    st.success("Opinión eliminada")
                                    st.rerun()
        else:
            st.info("No hay opiniones pendientes")
        
        st.markdown("---")
        st.markdown("### ✅ Opiniones aprobadas")
        opiniones_aprobadas = get_opiniones(aprobadas=True)
        if not opiniones_aprobadas.empty:
            for idx, op in opiniones_aprobadas.iterrows():
                with st.expander(f"👤 {op['usuario']} - {op['calificacion']}⭐"):
                    st.write(f"**Comentario:** {op['comentario']}")
                    st.caption(f"📅 {op['fecha']}")
                    if st.button("🗑️ ELIMINAR", key=f"del_op_aprob_{op['id']}_{idx}"):
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
            for idx, p in personajes.iterrows():
                with st.expander(f"👤 {p['nombre']} - {p['fecha']}"):
                    mostrar_imagen_segura(p.get('imagen_url'), 150)
                    st.write(f"**Biografía:** {p['descripcion']}")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button(f"✏️ MODIFICAR", key=f"edit_pers_{p['id']}_{idx}"):
                            st.session_state.edit_personaje = p.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR", key=f"del_pers_{p['id']}_{idx}"):
                            if delete_personaje(p['id']):
                                st.success(f"✅ {p['nombre']} eliminado")
                                st.rerun()
                    with col3:
                        if st.button(f"⭐ DESTACAR HOY", key=f"destacar_pers_{p['id']}_{idx}"):
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
            for idx, c in crimenes.iterrows():
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
                        if st.button(f"✏️ MODIFICAR", key=f"edit_crimen_{c['id']}_{idx}"):
                            st.session_state.edit_crimen = c.to_dict()
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ ELIMINAR", key=f"del_crimen_{c['id']}_{idx}"):
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
