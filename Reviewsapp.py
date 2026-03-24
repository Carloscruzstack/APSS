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

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Cecotec BI Dashboard", layout="wide")
st.sidebar.image("https://cecotec.es/img/cecotec-logo-1621516053.jpg", width=200)
st.title("🛡️ Cecotec Business & Quality Control")

# --- LÓGICA DE HISTÓRICO ---
# Listamos archivos y los presentamos de forma amigable: "Día DD/MM/AAAA - HH:MM"
archivos_crudos = sorted([f for f in os.listdir(PATH_HISTORICO) if f.endswith('.xlsx')], reverse=True)
archivo_comparar = st.sidebar.selectbox("🕒 Comparar con subida anterior:", ["Ninguno"] + archivos_crudos)

# --- CARGADORES ---
col_a, col_b = st.columns(2)
with col_a: keepa_file = st.file_uploader("📥 1. KEEPA ACTUAL", type=["xlsx"])
with col_b: listings_file = st.file_uploader("📥 2. MAESTRO", type=["xlsx"])

if keepa_file and listings_file:
    try:
        df_k = pd.read_excel(keepa_file, engine='openpyxl')
        df_l = pd.read_excel(listings_file, engine='openpyxl')
        
        # GUARDADO CON NOMBRE DESCRIPTIVO (Día y Hora)
        ahora = datetime.now().strftime('%Y-%m-%d_%H-%M')
        nombre_archivo = f"Keepa_{ahora}.xlsx"
        path_save = os.path.join(PATH_HISTORICO, nombre_archivo)
        if not os.path.exists(path_save):
            df_k.to_excel(path_save, index=False)

        # Normalización de columnas
        df_k.columns = [normalizar_texto(c) for c in df_k.columns]
        df_l.columns = [normalizar_texto(c) for c in df_l.columns]
        
        n_tit = next((c for c in df_l.columns if any(p in c for p in ["titul", "product", "name"])), None)
        n_rat = normalizar_texto("Opiniones: Valoraciones")
        n_rev = normalizar_texto("Opiniones: Cantidad de valoraciones")
        n_bsr = normalizar_texto("Clasificación de Ventas: Subcategoría Clasificación de Ventas")
        n_fac = normalizar_texto("Facturación Mensual")

        # Conversión numérica limpia para ordenar correctamente
        df_k[n_fac] = pd.to_numeric(df_k[n_fac], errors='coerce').fillna(0)
        if n_rev in df_k.columns:
            df_k[n_rev] = pd.to_numeric(df_k[n_rev], errors='coerce').fillna(0).astype(int)
        if n_bsr in df_k.columns:
            df_k[n_bsr] = df_k[n_bsr].apply(extraer_solo_numero_bsr).fillna(0)

        # --- TENDENCIA ---
        col_tendencia_key = None
        if archivo_comparar != "Ninguno":
            df_p = pd.read_excel(os.path.join(PATH_HISTORICO, archivo_comparar), engine='openpyxl')
            df_p.columns = [normalizar_texto(c) for c in df_p.columns]
            df_k = pd.merge(df_k, df_p[['asin', n_rat]], on='asin', how='left', suffixes=('', '_old'))
            
            col_tendencia_key = "tendencia_valoracion"
            def calcular_flecha(n, o):
                try:
                    if float(n) > float(o): return " 📈"
                    if float(n) < float(o): return " 📉"
                    return " ="
                except: return " ="
            
            df_k[col_tendencia_key] = df_k.apply(lambda x: f"{x[n_rat]:.1f}{calcular_flecha(x[n_rat], x[n_rat+'_old'])}" if pd.notnull(x[n_rat]) else "", axis=1)

        df = pd.merge(df_k, df_l.drop_duplicates('asin'), on='asin', how='left')
        
        # Limpieza de Subfamilia
        n_sub = normalizar_texto("Subfamilia")
        if n_sub in df.columns:
            df = df[~df[n_sub].astype(str).str.lower().str.contains("accesorios", na=False)]
            df[n_sub] = df[n_sub].apply(unificar_subfamilias)

        df['gl_display'] = df[normalizar_texto("GL")].fillna("Sin GL").apply(añadir_emoticono)
        df['sub_display'] = df[n_sub].fillna("Otros").apply(añadir_emoticono)

        # --- FILTROS ---
        st.sidebar.header("Filtros")
        opciones_gl = sorted(df['gl_display'].unique())
        default_gl = [g for g in opciones_gl if "kitchen" in g.lower()]
        sel_gl = st.sidebar.multiselect("GL:", opciones_gl, default=default_gl)
        sel_sub = st.sidebar.multiselect("Subfamilia:", sorted(df['sub_display'].unique()), default=[])

        df_f = df.copy()
        if sel_gl: df_f = df_f[df_f['gl_display'].isin(sel_gl)]
        if sel_sub: df_f = df_f[df_f['sub_display'].isin(sel_sub)]

        # --- GRÁFICO (SIN LÍMITE DE 5) ---
        if not df_f.empty and n_rat in df_f.columns:
            resumen = df_f.groupby('sub_display')[n_rat].mean().reset_index()
            resumen = resumen[resumen[n_rat] > 0].sort_values(by=n_rat)
            st.subheader(f"📊 Calidad Media: {', '.join(sel_gl) if sel_gl else 'Todo'}")
            fig = px.bar(resumen, x=n_rat, y='sub_display', orientation='h', color=n_rat, color_continuous_scale="Blues", text_auto='.2f')
            fig.update_layout(bargap=0.4, coloraxis_showscale=False, xaxis_range=[0, 5], height=300 + (len(resumen)*25))
            st.plotly_chart(fig, use_container_width=True)

        # --- TABLA (CON ORDENACIÓN NUMÉRICA Y PUNTOS) ---
        st.markdown("### 📋 Detalle de Surtido")
        
        c_img_n = next((c for c in df_f.columns if "imagen" in c), None)
        n_stk_amz = normalizar_texto("Stock Amazon")
        n_stk_ope = normalizar_texto("Stock Operativo")
        n_con = normalizar_texto("Consumo")

        # Mapeo de nombres para la tabla
        labels = {
            c_img_n: "📸", n_tit: "Título", normalizar_texto("SKU"): "SKU", n_sub: "Subfamilia",
            n_rat: "Val.", col_tendencia_key: "Tend.", n_rev: "Reseñas", n_bsr: "BSR",
            n_fac: "Facturación", n_stk_amz: "Stock AMZ", n_stk_ope: "Stock Op.", n_con: "Consumo",
            normalizar_texto("URL: Amazon"): "Link"
        }

        # Filtramos solo las que existan en el DF
        final_labels = {k: v for k, v in labels.items() if k in df_f.columns}
        sel_cols = st.multiselect("Columnas:", list(final_labels.keys()), default=list(final_labels.keys()), format_func=lambda x: final_labels[x])

        # CONFIGURACIÓN DE COLUMNAS PARA QUE EL PUNTO NO ROMPA EL ORDEN
        st.dataframe(
            df_f[sel_cols],
            column_config={
                c_img_n: st.column_config.ImageColumn("📸"),
                n_fac: st.column_config.NumberColumn("Facturación", format="%.0f €"), # El punto se pone solo por locale
                n_stk_amz: st.column_config.NumberColumn("Stock AMZ", format="%d"),
                n_stk_ope: st.column_config.NumberColumn("Stock Op.", format="%d"),
                n_con: st.column_config.NumberColumn("Consumo", format="%d"),
                n_bsr: st.column_config.NumberColumn("BSR", format="%d"),
                n_rat: st.column_config.NumberColumn("Val.", format="%.1f"),
                normalizar_texto("URL: Amazon"): st.column_config.LinkColumn("Link")
            },
            hide_index=True, use_container_width=True
        )

    except Exception as e:
        st.error(f"Error: {e}")
        
        
