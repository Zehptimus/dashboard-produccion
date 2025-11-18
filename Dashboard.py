import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import configparser
from pathlib import Path
from st_aggrid import AgGrid, GridOptionsBuilder
import io
import base64

# ==============================
# LEER CONFIGURACIÓN
# ==============================
config = configparser.ConfigParser()
config.read("config.ini")

base_output = config.get("GENERAL", "base_output", fallback="\\gumfp01\\Group\\DATA\\GENERAL\\ME FRDR\\Usuarios\\Misael\\Base de Tiempo promedio")
UMBRAL_TIEMPO = float(config.get("ALERTAS", "alerta_tiempo_promedio", fallback=6))
UMBRAL_RECHAZO = float(config.get("ALERTAS", "alerta_tasa_rechazo", fallback=10))

mañana_inicio = int(config.get("TURNOS", "turno_mañana_inicio", fallback=6))
mañana_fin = int(config.get("TURNOS", "turno_mañana_fin", fallback=14))
tarde_inicio = int(config.get("TURNOS", "turno_tarde_inicio", fallback=14))
tarde_fin = int(config.get("TURNOS", "turno_tarde_fin", fallback=22))

def clasificar_turno(hora):
    if mañana_inicio <= hora < mañana_fin:
        return "Mañana"
    elif tarde_inicio <= hora < tarde_fin:
        return "Tarde"
    else:
        return "Noche"

# ==============================
# CONFIGURACIÓN DE PÁGINA
# ==============================
st.set_page_config(page_title="Dashboard Producción", layout="wide")
st.title("📊 Dashboard de Producción Multi-Máquina")
st.caption(f"Turnos: Mañana {mañana_inicio}-{mañana_fin}, Tarde {tarde_inicio}-{tarde_fin}, Noche resto")

# ==============================
# SELECCIÓN DE MÁQUINAS
# ==============================
maquinas = [p.name for p in Path(base_output).iterdir() if p.is_dir()]
seleccion = st.sidebar.multiselect("Selecciona máquinas", maquinas, default=maquinas[:3])

# ==============================
# CARGAR DATOS
# ==============================
dfs = []
for maquina in seleccion:
    db_path = Path(base_output) / maquina / "produccion.db"
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        df_temp = pd.read_sql_query("SELECT * FROM produccion", conn)
        conn.close()
        df_temp["Maquina"] = maquina
        dfs.append(df_temp)

if not dfs:
    st.error("No se encontraron datos para las máquinas seleccionadas.")
    st.stop()

df = pd.concat(dfs, ignore_index=True)
df["Fecha"] = pd.to_datetime(df["Fecha"])
df["Duracion"] = pd.to_numeric(df["Duracion"], errors="coerce")

# ==============================
# FILTROS
# ==============================
fecha_min, fecha_max = df["Fecha"].min(), df["Fecha"].max()
rango = st.sidebar.date_input("Selecciona rango de fechas", [fecha_min, fecha_max])
operadores = st.sidebar.multiselect("Filtrar por operador", df["Operador"].dropna().unique())
serial_busqueda = st.sidebar.text_input("Buscar por Serial")

df_filtrado = df[(df["Fecha"] >= pd.to_datetime(rango[0])) & (df["Fecha"] <= pd.to_datetime(rango[1]))]
if operadores:
    df_filtrado = df_filtrado[df_filtrado["Operador"].isin(operadores)]
if serial_busqueda:
    df_filtrado = df_filtrado[df_filtrado["Serial"].str.contains(serial_busqueda, case=False, na=False)]

# ==============================
# CALCULAR MÉTRICAS
# ==============================
total_piezas = len(df_filtrado)
df_aceptadas = df_filtrado[df_filtrado["Estado"] == "Aceptada"]
promedio = round(df_aceptadas["Duracion"].mean(), 2) if not df_aceptadas.empty else 0
rechazadas = len(df_filtrado[df_filtrado["Estado"] == "Rechazada"])
tasa_rechazo = round((rechazadas / total_piezas * 100), 2) if total_piezas > 0 else 0

# Tiempo promedio entre piezas
if len(df_filtrado) > 1:
    df_sorted = df_filtrado.sort_values(by=["Fecha", "Hora"])
    df_sorted["HoraCompleta"] = pd.to_datetime(df_sorted["Fecha"].astype(str) + " " + df_sorted["Hora"])
    df_sorted["DiffMin"] = df_sorted["HoraCompleta"].diff().dt.total_seconds() / 60
    tiempo_promedio_entre_piezas = round(df_sorted["DiffMin"].mean(), 2)
else:
    tiempo_promedio_entre_piezas = 0

# ==============================
# PESTAÑAS
# ==============================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📌 Resumen", "📈 Gráficos", "🏆 Ranking & Turnos", "🔍 Búsqueda por Serial", "📋 Lista de Seriales"
])

# --- Tab 1: KPIs ---
with tab1:
    st.subheader("KPIs Globales")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total piezas", total_piezas)
    col2.metric("Promedio duración aceptadas", promedio)
    col3.metric("Piezas rechazadas", rechazadas)
    col4.metric("Tasa de rechazo (%)", tasa_rechazo)
    col5.metric("Tiempo entre piezas (min)", tiempo_promedio_entre_piezas)

    if promedio > UMBRAL_TIEMPO:
        st.error(f"⚠ ALERTA: Tiempo promedio aceptado ({promedio} min) supera {UMBRAL_TIEMPO} min.")
    if tasa_rechazo > UMBRAL_RECHAZO:
        st.warning(f"⚠ ALERTA: Tasa de rechazo ({tasa_rechazo}%) supera {UMBRAL_RECHAZO}%.")

# --- Tab 2: Gráficos ---
with tab2:
    st.subheader("Gráficos Comparativos")
    if not df_filtrado.empty:
        fig1 = px.bar(df_filtrado.groupby(["Maquina", "Operador"])["Serial"].count().reset_index(),
                      x="Operador", y="Serial", color="Maquina", barmode="group",
                      title="Piezas por operador y máquina")
        st.plotly_chart(fig1, use_container_width=True)

        fig2 = px.line(df_filtrado.groupby(["Maquina", "Hora"])["Duracion"].mean().reset_index(),
                       x="Hora", y="Duracion", color="Maquina", title="Promedio duración por hora")
        st.plotly_chart(fig2, use_container_width=True)

        fig3 = px.pie(df_filtrado, names="Estado", title="Clasificación por estado")
        st.plotly_chart(fig3, use_container_width=True)

# --- Tab 3: Ranking ---
with tab3:
    st.subheader("Ranking de operadores por eficiencia (piezas/hora)")
    if not df_filtrado.empty:
        df_filtrado["HoraCompleta"] = pd.to_datetime(df_filtrado["Fecha"].astype(str) + " " + df_filtrado["Hora"])
        df_filtrado["HoraRedondeada"] = df_filtrado["HoraCompleta"].dt.floor("H")

        ranking = df_filtrado.groupby(["Maquina", "Operador", "HoraRedondeada"])["Serial"].count().reset_index()
        ranking_promedio = ranking.groupby(["Maquina", "Operador"])["Serial"].mean().reset_index().sort_values(by="Serial", ascending=False)
        ranking_promedio.rename(columns={"Serial": "PiezasPromedioHora"}, inplace=True)

        st.dataframe(ranking_promedio)

    st.subheader("Eficiencia por turno")
    df_filtrado["Turno"] = pd.to_datetime(df_filtrado["Hora"]).dt.hour.apply(clasificar_turno)
    turno_data = df_filtrado.groupby(["Maquina", "Turno"])["Serial"].count().reset_index()
    fig_turno = px.bar(turno_data, x="Turno", y="Serial", color="Maquina", barmode="group", title="Piezas por turno y máquina")
    st.plotly_chart(fig_turno, use_container_width=True)

# --- Tab 4: Búsqueda por Serial ---
with tab4:
    st.subheader("Resultados de búsqueda por Serial")
    if serial_busqueda:
        st.write(f"Resultados para Serial: **{serial_busqueda}**")
        st.dataframe(df_filtrado)
    else:
        st.info("Ingresa un Serial en la barra lateral para buscar.")

# --- Tab 5: Lista completa con AgGrid ---
with tab5:
    st.subheader("Lista completa de seriales con duración y operador")
    if not df_filtrado.empty:
        estado_filtro = st.multiselect("Filtrar por estado", df_filtrado["Estado"].unique())
        df_lista = df_filtrado.copy()
        if estado_filtro:
            df_lista = df_lista[df_lista["Estado"].isin(estado_filtro)]

        busqueda = st.text_input("Buscar en la lista (Serial, Operador, Máquina)")
        if busqueda:
            df_lista = df_lista[df_lista.apply(lambda row: busqueda.lower() in str(row.values).lower(), axis=1)]

        columnas_mostrar = ["Serial", "Duracion", "Operador", "Maquina", "Fecha", "Hora", "Estado"]
        df_lista = df_lista[columnas_mostrar].sort_values(by="Fecha", ascending=False)

        gb = GridOptionsBuilder.from_dataframe(df_lista)
        gb.configure_pagination(enabled=True)
        gb.configure_default_column(editable=False, groupable=True)
        gridOptions = gb.build()
        AgGrid(df_lista, gridOptions=gridOptions, height=400)

        # Descarga Excel
        buffer_excel = io.BytesIO()
        with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
            df_lista.to_excel(writer, index=False)
        st.download_button("📥 Descargar Excel", buffer_excel.getvalue(), "lista_seriales.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # Descarga CSV
        csv_data = df_lista.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar CSV", csv_data, "lista_seriales.csv", mime="text/csv")

        # Gráfico adicional
        st.subheader("Tiempo promedio por operador")
        if not df_lista.empty:
            fig_operador = px.bar(df_lista.groupby("Operador")["Duracion"].mean().reset_index(),
                                  x="Operador", y="Duracion", title="Tiempo promedio (min) por operador", color="Operador")
            st.plotly_chart(fig_operador, use_container_width=True)

    else:
        st.info("No hay datos disponibles para mostrar.")
