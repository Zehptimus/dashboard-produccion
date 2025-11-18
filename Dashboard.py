import streamlit as st
import pandas as pd
import plotly.express as px
from st_aggrid import AgGrid, GridOptionsBuilder
import io
import numpy as np
import random
from datetime import datetime, timedelta

# ==============================
# CONFIGURACIÓN DE PÁGINA
# ==============================
st.set_page_config(page_title="Dashboard Producción DEMO", layout="wide")
st.title("📊 Dashboard de Producción Multi-Máquina (Demo)")
st.caption("Versión demo con datos simulados para Streamlit Cloud")

# ==============================
# GENERAR DATOS SIMULADOS
# ==============================
maquinas = ["Maquina1", "Maquina2", "Maquina3"]
operadores = ["Juan", "Pedro", "Ana", "Luis", "Maria"]
estados = ["Aceptada", "Rechazada"]

# Simular 500 registros
n = 500
fechas = [datetime.now() - timedelta(days=random.randint(0, 30)) for _ in range(n)]
horas = [f"{random.randint(6, 22)}:{random.randint(0,59):02d}" for _ in range(n)]
duraciones = [round(random.uniform(3, 10), 2) for _ in range(n)]
seriales = [f"S{str(i).zfill(4)}" for i in range(n)]
df = pd.DataFrame({
    "Serial": seriales,
    "Duracion": duraciones,
    "Operador": [random.choice(operadores) for _ in range(n)],
    "Maquina": [random.choice(maquinas) for _ in range(n)],
    "Fecha": fechas,
    "Hora": horas,
    "Estado": [random.choice(estados) for _ in range(n)]
})

# ==============================
# FILTROS
# ==============================
fecha_min, fecha_max = df["Fecha"].min(), df["Fecha"].max()
rango = st.sidebar.date_input("Selecciona rango de fechas", [fecha_min, fecha_max])
operadores_filtro = st.sidebar.multiselect("Filtrar por operador", df["Operador"].unique())
serial_busqueda = st.sidebar.text_input("Buscar por Serial")

df_filtrado = df[(df["Fecha"] >= pd.to_datetime(rango[0])) & (df["Fecha"] <= pd.to_datetime(rango[1]))]
if operadores_filtro:
    df_filtrado = df_filtrado[df_filtrado["Operador"].isin(operadores_filtro)]
if serial_busqueda:
    df_filtrado = df_filtrado[df_filtrado["Serial"].str.contains(serial_busqueda, case=False, na=False)]

# ==============================
# KPIs
# ==============================
total_piezas = len(df_filtrado)
df_aceptadas = df_filtrado[df_filtrado["Estado"] == "Aceptada"]
promedio = round(df_aceptadas["Duracion"].mean(), 2) if not df_aceptadas.empty else 0
rechazadas = len(df_filtrado[df_filtrado["Estado"] == "Rechazada"])
tasa_rechazo = round((rechazadas / total_piezas * 100), 2) if total_piezas > 0 else 0

# ==============================
# PESTAÑAS
# ==============================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📌 Resumen", "📈 Gráficos", "🏆 Ranking", "🔍 Búsqueda por Serial", "📋 Lista de Seriales"
])

# --- Tab 1: KPIs ---
with tab1:
    st.subheader("KPIs Globales")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total piezas", total_piezas)
    col2.metric("Promedio duración aceptadas", promedio)
    col3.metric("Piezas rechazadas", rechazadas)
    col4.metric("Tasa de rechazo (%)", tasa_rechazo)

# --- Tab 2: Gráficos ---
with tab2:
    if not df_filtrado.empty:
        fig1 = px.bar(df_filtrado.groupby(["Maquina", "Operador"])["Serial"].count().reset_index(),
                      x="Operador", y="Serial", color="Maquina", barmode="group",
                      title="Piezas por operador y máquina")
        st.plotly_chart(fig1, use_container_width=True)

        fig2 = px.pie(df_filtrado, names="Estado", title="Clasificación por estado")
        st.plotly_chart(fig2, use_container_width=True)

# --- Tab 3: Ranking ---
with tab3:
    if not df_filtrado.empty:
        ranking = df_filtrado.groupby(["Operador"])["Serial"].count().reset_index().sort_values(by="Serial", ascending=False)
        ranking.rename(columns={"Serial": "TotalPiezas"}, inplace=True)
        st.dataframe(ranking)

# --- Tab 4: Búsqueda por Serial ---
with tab4:
    if serial_busqueda:
        st.write(f"Resultados para Serial: **{serial_busqueda}**")
        st.dataframe(df_filtrado)
    else:
        st.info("Ingresa un Serial en la barra lateral para buscar.")

# --- Tab 5: Lista completa con AgGrid ---
with tab5:
    if not df_filtrado.empty:
        columnas_mostrar = ["Serial", "Duracion", "Operador", "Maquina", "Fecha", "Hora", "Estado"]
        df_lista = df_filtrado[columnas_mostrar].sort_values(by="Fecha", ascending=False)

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
        fig_operador = px.bar(df_lista.groupby("Operador")["Duracion"].mean().reset_index(),
                              x="Operador", y="Duracion", title="Tiempo promedio (min) por operador", color="Operador")
        st.plotly_chart(fig_operador, use_container_width=True)
