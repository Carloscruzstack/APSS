import streamlit as st
import pandas as pd
import plotly.express as px
import unicodedata
import re
import os
from datetime import datetime

# --- CONFIGURACIÓN DE CARPETAS ---
PATH_HISTORICO = "historico_keepa" 
if not os.path.exists(PATH_HISTORICO):
    os.makedirs(PATH_HISTORICO)

# --- FUNCIONES DE SOPORTE ---
def normalizar_texto(texto):
    if not isinstance(texto, str): return str(texto).lower().strip()
    return unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('utf-8').lower().strip()

def extraer_solo_numero_bsr(valor):
    if pd.isna(valor) or valor == "": return None
    if isinstance(valor, (int, float)): return int(valor)
    match = re.search(r'#\s*([\d\.,]+)', str(valor))
    if match:
        num_str = match.group(1).replace('.', '').replace(',', '')
        return int(num_str)
    return None

def unificar_subfamilias(nombre):
    if not isinstance(nombre, str): return "Otros"
    n = normalizar_texto(nombre)
    mapeo = {
        "aire acondicionado": "Aire acondicionado", "afeitadora": "Afeitadora",
        "aspirador trineo": "Aspirador trineo", "barbacoa": "Barbacoa",
        "cuchillo": "Cuchillos", "exprimidor": "Exprimidor",
        "robot aspirador": "Robot aspirador", "freidora": "Freidora de aire",
        "cafetera": "Cafeteras", "microondas": "Microondas", "ventilador": "Ventilador"
    }
    for clave, final in mapeo.items():
        if clave in n: return final
    return nombre.strip().capitalize()

def añadir_emoticono(nombre):
    if not isinstance(nombre, str): return nombre
    iconos = {"aire": "❄️", "cocina": "🍳", "freidora": "🍟", "cafe": "☕", "robot": "🤖", "kitchen": "🍳"}
    for clave, icono in iconos.items():
        if clave in nombre.lower(): return f"{icono} {nombre}"
    return f"📦 {nombre}"

def formato_miles(valor):
    if pd.isnull(valor) or valor == "": return "0"
    try:
        return f"{int(valor):,}".replace(",", ".")
    except:
        return str(valor)

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Cecotec BI Dashboard", layout="wide")
st.sidebar.image("https://cecotec.es/img/cecotec-logo-1621516053.jpg", width=200)
st.title("🛡️ Cecotec Business & Quality Control")

# --- CARGADORES ---
col_a, col_b = st.columns(2)
with col_a: keepa_file = st.file_uploader("📥 1. KEEPA ACTUAL", type=["xlsx"])
with col_b: listings_file = st.file_uploader("📥 2. MAESTRO", type=["xlsx"])

if keepa_file and listings_file:
    try:
        df_k = pd.read_excel(keepa_file, engine='openpyxl')
        df_l = pd.read_excel(listings_file, engine='openpyxl')
        
        df_k.columns = [normalizar_texto(c) for c in df_k.columns]
        df_l.columns = [normalizar_texto(c) for c in df_l.columns]
        
        # Identificación de columnas solicitadas
        n_tit = next((c for c in df_l.columns if any(p in c for p in ["titul", "product", "name"])), None)
        n_rat = normalizar_texto("Opiniones: Valoraciones")
        n_rev = normalizar_texto("Opiniones: Cantidad de valoraciones")
        n_bsr = normalizar_texto("Clasificación de Ventas: Subcategoría Clasificación de Ventas")
        n_fac = normalizar_texto("Facturación Mensual")
        n_stk_amz = normalizar_texto("Stock Amazon")
        n_stk_ope = normalizar_texto("Stock Operativo")
        n_sub = normalizar_texto("Subfamilia")
        n_con = normalizar_texto("Consumo")

        if n_rev in df_k.columns:
            df_k[n_rev] = pd.to_numeric(df_k[n_rev], errors='coerce').fillna(0).astype(int)
        if n_bsr in df_k.columns:
            df_k[n_bsr] = df_k[n_bsr].apply(extraer_solo_numero_bsr)

        # Cruce de datos
        df = pd.merge(df_k, df_l.drop_duplicates('asin'), on='asin', how='left')
        
        # Limpieza de Subfamilia y Filtro Accesorios
        if n_sub in df.columns:
            df = df[~df[n_sub].astype(str).str.lower().str.contains("accesorios", na=False)]
            df[n_sub] = df[n_sub].apply(unificar_subfamilias)

        df['gl_display'] = df[normalizar_texto("GL")].fillna("Sin GL").apply(añadir_emoticono)
        df['sub_display'] = df[n_sub].fillna("Otros").apply(añadir_emoticono)

        # --- FILTROS SIDEBAR ---
        st.sidebar.header("Filtros")
        opciones_gl = sorted(df['gl_display'].unique())
        default_gl = [g for g in opciones_gl if "kitchen" in g.lower()]
        sel_gl = st.sidebar.multiselect("GL:", opciones_gl, default=default_gl)
        
        opciones_sub = sorted(df['sub_display'].unique())
        sel_sub = st.sidebar.multiselect("Subfamilia:", opciones_sub, default=[])

        df_f = df.copy()
        if sel_gl: df_f = df_f[df_f['gl_display'].isin(sel_gl)]
        if sel_sub: df_f = df_f[df_f['sub_display'].isin(sel_sub)]

        # --- GRÁFICO ---
        if not df_f.empty and n_rat in df_f.columns:
            resumen = df_f.groupby('sub_display')[n_rat].mean().dropna().reset_index()
            resumen = resumen[resumen[n_rat] > 0].sort_values(by=n_rat)
            if not resumen.empty:
                st.subheader("📊 Calidad Media por Subfamilia")
                fig = px.bar(resumen, x=n_rat, y='sub_display', orientation='h', color=n_rat, color_continuous_scale="Blues", text_auto='.2f')
                fig.update_layout(bargap=0.6, coloraxis_showscale=False, xaxis_range=[0, 5.1])
                st.plotly_chart(fig, use_container_width=True)

        # --- TABLA DE DETALLE ---
        st.markdown("### 📋 Detalle de Surtido")
        
        # Formateo de columnas numéricas con puntos (Miles)
        cols_para_puntos = [n_fac, n_stk_amz, n_stk_ope, n_con]
        for col in cols_para_puntos:
            if col in df_f.columns:
                suffix = " €" if col == n_fac else ""
                df_f[col] = df_f[col].apply(lambda x: formato_miles(x) + suffix)

        c_img_n = next((c for c in df_f.columns if "imagen" in c), None)
        
        labels_map = {}
        if c_img_n: labels_map[c_img_n] = "📸"
        if n_tit: labels_map[n_tit] = "Título del Producto"
        
        columnas_finales = {
            normalizar_texto("SKU"): "SKU",
            n_sub: "Subfamilia",
            n_rat: "Valoración",
            n_rev: "Reseñas",
            n_bsr: "BSR",
            n_fac: "Facturación",
            n_stk_amz: "Stock AMZ",
            n_stk_ope: "Stock Op.",
            n_con: "Consumo",
            normalizar_texto("URL: Amazon"): "Link"
        }
        
        for k, v in columnas_finales.items():
            if k in df_f.columns: labels_map[k] = v

        sel_cols = st.multiselect("Columnas visibles:", options=list(labels_map.keys()), 
                                  default=list(labels_map.keys()), format_func=lambda x: labels_map[x])

        st.dataframe(
            df_f[sel_cols].fillna(""),
            column_config={
                c_img_n: st.column_config.ImageColumn("📸"),
                n_rev: st.column_config.NumberColumn("Reseñas", format="%d"),
                n_bsr: st.column_config.NumberColumn("BSR", format="%d"),
                normalizar_texto("URL: Amazon"): st.column_config.LinkColumn("Link")
            },
            hide_index=True, use_container_width=True
        )

    except Exception as e:
        st.error(f"Error en el procesado: {e}")



