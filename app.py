import os
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from motor_datos import cargar_y_procesar_excel, calcular_acumulado_jugadores
from ficha_jugador import mostrar_ficha_jugador
from rotaciones import mostrar_planificador_rotaciones
from tagger import mostrar_tagger
from videoteca import mostrar_videoteca

# ---------------------------------------------------------
# 1. CONFIGURACIÓN DE LA PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="CB Artchivo U12 | Analytics",
    page_icon="🏀",
    layout="wide",
)

st.title("🏀 CB Artchivo Alevín — Panel de Analítica Avanzada")
st.caption("Métricas ponderadas por volumen real de posesiones en pista")

# ---------------------------------------------------------
# 2. BARRA LATERAL: CARGA DE EXCEL Y FILTROS
# ---------------------------------------------------------
with st.sidebar:
    st.header("📂 Fuente de Datos")
    archivo_subido = st.file_uploader(
        "Sube tu Excel actualizado (.xlsx)",
        type=["xlsx"],
        help="Si no subes ninguno, lee automáticamente 'alevin_tabla_estadistica_v2.xlsx' de tu carpeta.",
    )

    ruta_defecto = "alevin_tabla_estadistica_v2.xlsx"
    if archivo_subido is not None:
        fuente = archivo_subido
    elif os.path.exists(ruta_defecto):
        fuente = ruta_defecto
        st.success(f"Conectado a `{ruta_defecto}`")
    else:
        st.warning("Coloca `alevin_tabla_estadistica_v2.xlsx` en la carpeta del proyecto o súbelo arriba.")
        st.stop()

# Procesamos el Excel usando nuestro motor
df_games, resumen_jornadas, jugados, _ = cargar_y_procesar_excel(fuente)

with st.sidebar:
    st.divider()
    st.header("🔎 Filtro de Jornadas")
    jornadas_disp = sorted(resumen_jornadas["JORNADA"].unique())

    modo_filtro = st.radio(
        "Modo de selección:",
        ["Rango continuo", "Jornadas sueltas"],
        horizontal=True,
    )

    if modo_filtro == "Rango continuo":
        rango_jornadas = st.select_slider(
            "Selecciona el rango de jornadas:",
            options=jornadas_disp,
            value=(min(jornadas_disp), max(jornadas_disp)),
        )
        jornadas_elegidas = [
            j for j in jornadas_disp if rango_jornadas[0] <= j <= rango_jornadas[1]
        ]
    else:
        etiquetas_map = {}
        etiquetas_derrotas = []
        for _, r in resumen_jornadas.sort_values("JORNADA").iterrows():
            j_num = r["JORNADA"]
            rival_txt = str(r.get("RIVAL", "")).strip()
            res_txt = str(r.get("RESULTADO", "")).strip()
            etiqueta = f"J{j_num} vs {rival_txt} ({res_txt})"
            etiquetas_map[etiqueta] = j_num
            if res_txt == "L":
                etiquetas_derrotas.append(etiqueta)

        if st.button("📉 Cargar solo derrotas (L)", use_container_width=True, disabled=len(etiquetas_derrotas) == 0):
            st.session_state.ms_jornadas_sueltas = etiquetas_derrotas

        if "ms_jornadas_sueltas" not in st.session_state:
            st.session_state.ms_jornadas_sueltas = list(etiquetas_map.keys())
        else:
            st.session_state.ms_jornadas_sueltas = [
                e for e in st.session_state.ms_jornadas_sueltas if e in etiquetas_map
            ]

        seleccion_etiquetas = st.multiselect(
            "Elige las jornadas concretas:",
            options=list(etiquetas_map.keys()),
            key="ms_jornadas_sueltas",
            placeholder="Selecciona una o varias jornadas...",
        )
        jornadas_elegidas = [etiquetas_map[e] for e in seleccion_etiquetas]

if not jornadas_elegidas:
    st.warning("⚠️ Selecciona al menos una jornada en el menú lateral para calcular los indicadores.")
    st.stop()

# Filtramos partidos y actuaciones individuales según las jornadas elegidas
res_f = resumen_jornadas[resumen_jornadas["JORNADA"].isin(jornadas_elegidas)].copy()
jugados_f = jugados[jugados["JORNADA"].isin(jornadas_elegidas)].copy()
acum_f = calcular_acumulado_jugadores(jugados_f)

# ---------------------------------------------------------
# 3. INDICADORES CLAVE DEL EQUIPO (KPIs)
# ---------------------------------------------------------
victorias = (res_f["RESULTADO"] == "W").sum()
derrotas = (res_f["RESULTADO"] == "L").sum()
pos_tot = res_f["POS_EQ"].sum()
pts_fav_tot = res_f["PTS_FAV"].sum()

oer_global = pts_fav_tot / pos_tot if pos_tot > 0 else 0.0
der_global = res_f["PTS_CON"].sum() / pos_tot if pos_tot > 0 else 0.0
net_global = oer_global - der_global
pts_transicion = (
    (res_f["CONTRA_TOT"].sum() + res_f["PRESION_TOT"].sum()) / pts_fav_tot * 100
    if pts_fav_tot > 0
    else 0.0
)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Balance", f"{victorias}V - {derrotas}D", f"{len(res_f)} jornadas")
c2.metric("OER Equipo", f"{oer_global:.2f} ppp", f"{res_f['PTS_FAV'].mean():.1f} pts/part.")
c3.metric("DER Equipo", f"{der_global:.2f} ppp", f"{res_f['PTS_CON'].mean():.1f} enc/part.", delta_color="inverse")
c4.metric("NET Rating", f"{net_global:+.2f} ppp", f"Dif: {res_f['DIF_PTS'].mean():+.1f} pts")
c5.metric("Pts Contra + Presión", f"{pts_transicion:.1f}%", f"{int(res_f['CONTRA_TOT'].sum() + res_f['PRESION_TOT'].sum())} pts totales")

st.divider()

# ---------------------------------------------------------
# 4. NAVEGACIÓN POR PESTAÑAS
# ---------------------------------------------------------
tab_equipo, tab_jugador, tab_rotaciones, tab_tagger, tab_videoteca = st.tabs([
    "📊 Panel del Equipo",
    "👤 Ficha Individual y Comparador",
    "⏱️ Planificador de Rotaciones",
    "🎯 Calculadora Post-Partido",
    "🎬 Videoteca Táctica",
])

# --- PESTAÑA 1: PANEL DEL EQUIPO ---
with tab_equipo:
    col_izq, col_der = st.columns(2)

    with col_izq:
        st.subheader("📊 Impacto Colectivo en Pista (OER_ON vs DER_ON)")
        acum_ord = acum_f.sort_values("NET_ON", ascending=True)

        fig_on = go.Figure()
        fig_on.add_trace(go.Bar(
            y=acum_ord["JUGADOR"],
            x=acum_ord["OER_ON"],
            name="OER_ON (Ataque)",
            orientation="h",
            marker_color="#2563EB",
            text=acum_ord["OER_ON"].map(lambda v: f"{v:.2f}"),
            textposition="outside",
        ))
        fig_on.add_trace(go.Bar(
            y=acum_ord["JUGADOR"],
            x=acum_ord["DER_ON"],
            name="DER_ON (Defensa)",
            orientation="h",
            marker_color="#F97316",
            text=acum_ord["DER_ON"].map(lambda v: f"{v:.2f}"),
            textposition="outside",
        ))
        fig_on.update_layout(
            barmode="group",
            height=450,
            margin=dict(l=10, r=30, t=20, b=20),
            xaxis_title="Puntos por posesión",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_on, use_container_width=True)

    with col_der:
        st.subheader("🎯 Volumen de Uso (%USO) vs Eficiencia Individual (OER)")
        fig_uso = px.scatter(
            acum_f,
            x="%USO",
            y="OER",
            size="SEXTOS",
            color="NET_ON",
            text="JUGADOR",
            color_continuous_scale="RdYlGn",
            labels={
                "%USO": "% Uso en pista (neutro = 20%)",
                "OER": "OER Individual (pts/pos)",
                "NET_ON": "NET_ON",
            },
        )
        fig_uso.update_traces(textposition="top center")
        fig_uso.add_vline(x=20.0, line_dash="dash", line_color="gray", annotation_text="Uso neutro (20%)")
        fig_uso.add_hline(y=acum_f["OER"].mean(), line_dash="dot", line_color="gray", annotation_text="OER medio")
        fig_uso.update_layout(
            height=450,
            margin=dict(l=10, r=20, t=20, b=20),
        )
        st.plotly_chart(fig_uso, use_container_width=True)

    st.subheader("📋 Estadísticas Acumuladas de la Plantilla (Ponderadas)")
    columnas_vista = [
        "NUM", "JUGADOR", "PART", "SEXTOS", "PTS", "PTS/PART", "PTS/SEX",
        "REB", "AS", "REC", "PER", "VAL/SEX",
        "TS%", "%eFG", "POS", "OER", "%USO", "OER_ON", "DER_ON", "NET_ON", "%STOPS", "RATIO_PER/USO"
    ]
    st.dataframe(
        acum_f[columnas_vista].sort_values("NET_ON", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("📅 Ver desglose jornada a jornada de CB Artchivo"):
        st.dataframe(
            res_f[["JORNADA", "RIVAL", "LOCALIA", "RESULTADO", "PTS_FAV", "PTS_CON", "DIF_PTS", "POS_EQ", "OER_EQ", "DER_EQ", "NET_EQ", "CONTRA_TOT", "PRESION_TOT"]],
            use_container_width=True,
            hide_index=True,
        )

# --- PESTAÑA 2: FICHA INDIVIDUAL Y COMPARADOR ---
with tab_jugador:
    mostrar_ficha_jugador(jugados_f, acum_f)

# --- PESTAÑA 3: PLANIFICADOR DE ROTACIONES ---
with tab_rotaciones:
    mostrar_planificador_rotaciones(acum_f)

# --- PESTAÑA 4: CALCULADORA POST-PARTIDO ---
with tab_tagger:
    mostrar_tagger()

# --- PESTAÑA 5: VIDEOTECA TÁCTICA ---
with tab_videoteca:
    mostrar_videoteca()