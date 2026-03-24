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

def formato_miles(valor, es_moneda=False):
    if pd.isnull(valor) or valor == "": return "0"
    try:
        num = int(float(valor))
        formateado = f"{num:,.0f}".replace(",", ".")
        return f"{formateado} €" if es_moneda else formateado
    except:
        return str(valor)

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Cecotec BI Dashboard", layout="wide")
st.sidebar.image("https://cecotec.es/img/cecotec-logo-1621516053.jpg", width=200)
st.title("🛡️ Cecotec Business & Quality Control")

# --- LÓGICA DE HISTÓRICO (RESTAURADA) ---
archivos_pasados = sorted([f for f in os.listdir(PATH_HISTORICO) if f.endswith('.xlsx')], reverse=True)
archivo_comparar = st.sidebar.selectbox("🕒 Comparativa Temporal:", ["Ninguno"] + archivos_pasados)

# --- CARGADORES ---
col_a, col_b = st.columns(2)
with col_a: keepa_file = st.file_uploader("📥 1. KEEPA ACTUAL", type=["xlsx"])
with col_b: listings_file = st.file_uploader("📥 2. MAESTRO", type=["xlsx"])

if keepa_file and listings_file:
    try:
        df_k = pd.read_excel(keepa_file, engine='openpyxl')
        df_l = pd.read_excel(listings_file, engine='openpyxl')
        
        # Guardar copia para el histórico si no existe
        ts = datetime.now().strftime('%Y%m%d_%H%M')
        path_save = os.path.join(PATH_HISTORICO, f"keepa_{ts}.xlsx")
        if not os.path.exists(path_save):
            df_k.to_excel(path_save, index=False)

        # Normalización
        df_k.columns = [normalizar_texto(c) for c in df_k.columns]
        df_l.columns = [normalizar_texto(c) for c in df_l.columns]
        
        n_tit = next((c for c in df_l.columns if any(p in c for p in ["titul", "product", "name"])), None)
        n_rat = normalizar_texto("Opiniones: Valoraciones")
        n_rev = normalizar_texto("Opiniones: Cantidad de valoraciones")
        n_bsr = normalizar_texto("Clasificación de Ventas: Subcategoría Clasificación de Ventas")
        n_fac = normalizar_texto("Facturación Mensual")

        if n_rev in df_k.columns:
            df_k[n_rev] = pd.to_numeric(df_k[n_rev], errors='coerce').fillna(0).astype(int)
        if n_bsr in df_k.columns:
            df_k[n_bsr] = df_k[n_bsr].apply(extraer_solo_numero_bsr)

        # --- LÓGICA DE TENDENCIAS ---
        col_tendencia = None
        if archivo_comparar != "Ninguno":
            df_p = pd.read_excel(os.path.join(PATH_HISTORICO, archivo_comparar), engine='openpyxl')
            df_p.columns = [normalizar_texto(c) for c in df_p.columns]
            df_k = pd.merge(df_k, df_p[['asin', n_rat]], on='asin', how='left', suffixes=('', '_old'))
            
            def get_trend(n, o):
                try:
                    n_f, o_f = float(n), float(o)
                    if n_f > o_f: return " 📈"
                    if n_f < o_f: return " 📉"
                    return " ="
                except: return " ="

            col_tendencia = "Valoración (Tendencia)"
            df_k[normalizar_texto(col_tendencia)] = df_k.apply(
                lambda x: f"{float(x[n_rat]):.1f}{get_trend(x[n_rat], x[n_rat+'_old'])}" if not pd.isna(x[n_rat]) else "", axis=1
            )

        df = pd.merge(df_k, df_l.drop_duplicates('asin'), on='asin', how='left')
        
        # Filtros y Limpieza
        n_sub = normalizar_texto("Subfamilia")
        if n_sub in df.columns:
            df = df[~df[n_sub].astype(str).str.lower().str.contains("accesorios", na=False)]
            df[n_sub] = df[n_sub].apply(unificar_subfamilias)

        df['gl_display'] = df[normalizar_texto("GL")].fillna("Sin GL").apply(añadir_emoticono)
        df['sub_display'] = df[n_sub].fillna("Otros").apply(añadir_emoticono)

        # Sidebar Filtros
        st.sidebar.header("Filtros")
        opciones_gl = sorted(df['gl_display'].unique())
        default_gl = [g for g in opciones_gl if "kitchen" in g.lower()]
        sel_gl = st.sidebar.multiselect("GL:", opciones_gl, default=default_gl)
        sel_sub = st.sidebar.multiselect("Subfamilia:", sorted(df['sub_display'].unique()), default=[])

        df_f = df.copy()
        if sel_gl: df_f = df_f[df_f['gl_display'].isin(sel_gl)]
        if sel_sub: df_f = df_f[df_f['sub_display'].isin(sel_sub)]

        # --- GRÁFICO ESTILIZADO ---
        if not df_f.empty and n_rat in df_f.columns:
            resumen = df_f.groupby('sub_display')[n_rat].mean().dropna().reset_index()
            resumen = resumen[resumen[n_rat] > 0].sort_values(by=n_rat)
            if not resumen.empty:
                st.subheader("📊 Calidad Media por Subfamilia")
                fig = px.bar(resumen, x=n_rat, y='sub_display', orientation='h', color=n_rat, color_continuous_scale="Blues", text_auto='.2f')
                fig.update_layout(bargap=0.6, coloraxis_showscale=False, xaxis_range=[0, 5.1])
                st.plotly_chart(fig, use_container_width=True)

        # --- TABLA ---
        st.markdown("### 📋 Detalle de Surtido")
        
        # Formateo visual de miles
        cols_num = [n_fac, normalizar_texto("Stock Amazon"), normalizar_texto("Stock Operativo"), normalizar_texto("Consumo"), n_bsr]
        for c in cols_num:
            if c in df_f.columns:
                es_m = (c == n_fac)
                df_f[c] = df_f[c].apply(lambda x: formato_miles(x, es_moneda=es_m))

        c_img_n = next((c for c in df_f.columns if "imagen" in c), None)
        labels_map = {c_img_n: "📸", n_tit: "Título"}
        
        resto = {
            normalizar_texto("SKU"): "SKU", n_sub: "Subfamilia", 
            n_rat: "Valoración", normalizar_texto(col_tendencia) if col_tendencia else None: col_tendencia,
            n_rev: "Reseñas", n_bsr: "BSR", n_fac: "Facturación",
            normalizar_texto("Stock Amazon"): "Stock AMZ", normalizar_texto("Stock Operativo"): "Stock Op.",
            normalizar_texto("Consumo"): "Consumo", normalizar_texto("URL: Amazon"): "Link"
        }
        
        for k, v in resto.items():
            if k and k in df_f.columns: labels_map[k] = v

        sel_cols = st.multiselect("Columnas:", list(labels_map.keys()), default=list(labels_map.keys()), format_func=lambda x: labels_map[x])
        
        st.dataframe(df_f[sel_cols].fillna(""), column_config={
            c_img_n: st.column_config.ImageColumn("📸"),
            normalizar_texto("URL: Amazon"): st.column_config.LinkColumn("Link")
        }, hide_index=True, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
