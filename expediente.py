import streamlit as st
import pandas as pd
import plotly.graph_objects as go


def _inject_print_css():
    """Oculta la barra lateral y botones al imprimir o guardar como PDF desde el navegador."""
    st.markdown(
        """
        <style>
        @media print {
            [data-testid="stSidebar"],
            [data-testid="stHeader"],
            [data-testid="stToolbar"],
            .stTabs [data-baseweb="tab-list"],
            .no-print {
                display: none !important;
            }
            .block-container {
                padding-top: 1rem !important;
                max-width: 100% !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _zscore(serie):
    """Calcula la puntuación Z de una serie numérica evitando divisiones por cero."""
    s = pd.to_numeric(serie, errors="coerce")
    std = s.std(ddof=0)
    if pd.isna(std) or std == 0:
        return pd.Series(0.0, index=s.index)
    return (s - s.mean()) / std


def calcular_indices_totales(acum_f):
    """Calcula IND_DEF e IND_ATK normalizados (Z) sobre los jugadores con SEXTOS > 0."""
    if acum_f.empty or "SEXTOS" not in acum_f.columns:
        return pd.DataFrame()

    df = acum_f.copy()
    df["SEXTOS"] = pd.to_numeric(df["SEXTOS"], errors="coerce").fillna(0)
    df = df[df["SEXTOS"] > 0].copy()
    if df.empty:
        return pd.DataFrame()

    rd_sex = pd.to_numeric(df["RD"], errors="coerce").fillna(0) / df["SEXTOS"] if "RD" in df.columns else pd.Series(0.0, index=df.index)
    rec_sex = pd.to_numeric(df["REC"], errors="coerce").fillna(0) / df["SEXTOS"] if "REC" in df.columns else pd.Series(0.0, index=df.index)
    as_sex = pd.to_numeric(df["AS"], errors="coerce").fillna(0) / df["SEXTOS"] if "AS" in df.columns else pd.Series(0.0, index=df.index)
    ro_sex = pd.to_numeric(df["RO"], errors="coerce").fillna(0) / df["SEXTOS"] if "RO" in df.columns else pd.Series(0.0, index=df.index)
    per_sex = pd.to_numeric(df["PER"], errors="coerce").fillna(0) / df["SEXTOS"] if "PER" in df.columns else pd.Series(0.0, index=df.index)

    der_on = pd.to_numeric(df["DER_ON"], errors="coerce").fillna(0) if "DER_ON" in df.columns else pd.Series(0.0, index=df.index)
    stops = pd.to_numeric(df["%STOPS"], errors="coerce").fillna(0) if "%STOPS" in df.columns else pd.Series(0.0, index=df.index)
    oer_on = pd.to_numeric(df["OER_ON"], errors="coerce").fillna(0) if "OER_ON" in df.columns else pd.Series(0.0, index=df.index)
    ts_pct = pd.to_numeric(df["TS%"], errors="coerce").fillna(0) if "TS%" in df.columns else pd.Series(0.0, index=df.index)

    df["IND_DEF"] = (
        0.40 * (-_zscore(der_on))
        + 0.30 * _zscore(stops)
        + 0.15 * _zscore(rd_sex)
        + 0.15 * _zscore(rec_sex)
    )
    df["IND_ATK"] = (
        0.35 * _zscore(oer_on)
        + 0.25 * _zscore(ts_pct)
        + 0.20 * _zscore(as_sex)
        + 0.10 * _zscore(ro_sex)
        - 0.10 * _zscore(per_sex)
    )
    return df


def mostrar_graficas_jugador_total(acum_f, jugador_sel=None):
    """Muestra las gráficas de Jugador Total en Defensa (IND_DEF) y en Ataque (IND_ATK)."""
    df = calcular_indices_totales(acum_f)
    if df.empty:
        st.info("No hay datos suficientes de sextos para calcular los índices de jugador total.")
        return

    st.subheader("Jugador Total en Defensa vs Ataque (índice normalizado del grupo)")
    col_d, col_a = st.columns(2)

    with col_d:
        st.caption("🛡️ Jugador Total en Defensa (`IND_DEF`: 40% -DER_ON, 30% %STOPS, 15% RD/Sex, 15% REC/Sex)")
        d_ord = df.sort_values("IND_DEF", ascending=True)
        colores_def = [
            "#0f172a" if j == jugador_sel else ("#16a34a" if v >= 0 else "#dc2626")
            for j, v in zip(d_ord["JUGADOR"], d_ord["IND_DEF"])
        ]
        fig_def = go.Figure(
            go.Bar(
                y=d_ord["JUGADOR"],
                x=d_ord["IND_DEF"],
                orientation="h",
                marker_color=colores_def,
                text=d_ord["IND_DEF"].map(lambda v: f"{v:+.2f}"),
                textposition="outside",
            )
        )
        fig_def.add_vline(x=0, line_dash="dash", line_color="#64748b")
        fig_def.update_layout(
            height=350,
            margin=dict(l=10, r=40, t=20, b=20),
            xaxis_title="Puntuación Z defensiva",
        )
        st.plotly_chart(fig_def, use_container_width=True)

    with col_a:
        st.caption("⚔️ Jugador Total en Ataque (`IND_ATK`: 35% OER_ON, 25% TS%, 20% AS/Sex, 10% RO/Sex, -10% PER/Sex)")
        a_ord = df.sort_values("IND_ATK", ascending=True)
        colores_atk = [
            "#0f172a" if j == jugador_sel else ("#2563eb" if v >= 0 else "#f97316")
            for j, v in zip(a_ord["JUGADOR"], a_ord["IND_ATK"])
        ]
        fig_atk = go.Figure(
            go.Bar(
                y=a_ord["JUGADOR"],
                x=a_ord["IND_ATK"],
                orientation="h",
                marker_color=colores_atk,
                text=a_ord["IND_ATK"].map(lambda v: f"{v:+.2f}"),
                textposition="outside",
            )
        )
        fig_atk.add_vline(x=0, line_dash="dash", line_color="#64748b")
        fig_atk.update_layout(
            height=350,
            margin=dict(l=10, r=40, t=20, b=20),
            xaxis_title="Puntuación Z ofensiva",
        )
        st.plotly_chart(fig_atk, use_container_width=True)


def mostrar_expediente_familias(jugados_f, acum_f, etiqueta_filtro="Temporada seleccionada"):
    """Renderiza el expediente individual formativo para las familias."""
    _inject_print_css()

    if acum_f.empty or jugados_f.empty:
        st.warning("No hay datos de jugadores para las jornadas seleccionadas.")
        return

    # Selector de jugador (oculto al imprimir)
    st.markdown('<div class="no-print">', unsafe_allow_html=True)
    col_sel, col_info = st.columns([2, 3])
    with col_sel:
        jugadores_lista = acum_f.sort_values("NUM")["JUGADOR"].tolist()
        jugador_sel = st.selectbox("Selecciona jugador para el expediente:", jugadores_lista, key="exp_jugador_sel")
    with col_info:
        st.info("Para entregar a las familias: redacta la reseña abajo y pulsa **Ctrl + P** (Guardar como PDF).")
    st.markdown("</div>", unsafe_allow_html=True)

    fila = acum_f[acum_f["JUGADOR"] == jugador_sel].iloc[0]
    dorsal = int(fila["NUM"])
    df_jug = jugados_f[jugados_f["JUGADOR"] == jugador_sel].sort_values("JORNADA").copy()

    # Medianas de la plantilla en el tramo filtrado
    med_oer_on = float(acum_f["OER_ON"].median())
    med_der_on = float(acum_f["DER_ON"].median())
    med_net_on = float(acum_f["NET_ON"].median())
    med_ts = float(acum_f["TS%"].median())
    med_stops = float(acum_f["%STOPS"].median())
    med_oreb = float(acum_f["%OREB"].median())
    med_asto = float(acum_f["AS/TO"].median())

    # 1. Cabecera del expediente
    st.markdown(f"## Expediente Formativo — #{dorsal} {jugador_sel}")
    st.caption(f"**CB Artchivo U12** · Tramo analizado: **{etiqueta_filtro}**")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Partidos / Sextos", f"{int(fila['PART'])} P / {int(fila['SEXTOS'])} Sex")
    c2.metric(
        "Impacto Neto (NET_ON)",
        f"{fila['NET_ON']:+.2f}",
        delta=f"{fila['NET_ON'] - med_net_on:+.2f} vs mediana",
    )
    c3.metric("Participación (%USO)", f"{fila['%USO']:.1f}%")
    c4.metric(
        "Paradas Def. (%STOPS)",
        f"{fila['%STOPS']:.1f}%",
        delta=f"{fila['%STOPS'] - med_stops:+.1f}% vs mediana",
    )

    st.divider()

    # 2. Gráficas con mediana de referencia
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("Evolución por jornada")
        fig_evol = go.Figure()
        fig_evol.add_trace(
            go.Bar(
                x=[f"J{j}" for j in df_jug["JORNADA"]],
                y=df_jug["SEXTOS"],
                name="Sextos jugados",
                marker_color="rgba(59, 130, 246, 0.35)",
                yaxis="y",
            )
        )
        fig_evol.add_trace(
            go.Scatter(
                x=[f"J{j}" for j in df_jug["JORNADA"]],
                y=df_jug["NET_ON"],
                name="NET_ON partido",
                mode="lines+markers",
                line=dict(color="#16a34a", width=3),
                marker=dict(size=8),
                yaxis="y2",
            )
        )
        fig_evol.add_hline(
            y=med_net_on,
            line_dash="dash",
            line_color="#64748b",
            annotation_text=f"Mediana equipo ({med_net_on:+.2f})",
            annotation_position="top left",
            yref="y2",
        )
        fig_evol.update_layout(
            height=340,
            margin=dict(l=20, r=20, t=30, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(title="Sextos", range=[0, 6.5], showgrid=False),
            yaxis2=dict(title="NET_ON", overlaying="y", side="right", zeroline=True),
        )
        st.plotly_chart(fig_evol, use_container_width=True)

    with col_g2:
        st.subheader("Eficiencia colectiva en pista vs Mediana")
        fig_on = go.Figure()
        fig_on.add_trace(
            go.Bar(
                x=["Ataque en pista (OER_ON)", "Defensa en pista (DER_ON)"],
                y=[fila["OER_ON"], fila["DER_ON"]],
                name=jugador_sel,
                marker_color=["#2563eb", "#f97316"],
                text=[f"{fila['OER_ON']:.2f}", f"{fila['DER_ON']:.2f}"],
                textposition="inside",
                insidetextanchor="start",
                textfont=dict(color="white", size=12),
            )
        )
        fig_on.add_trace(
            go.Scatter(
                x=["Ataque en pista (OER_ON)", "Defensa en pista (DER_ON)"],
                y=[med_oer_on, med_der_on],
                name="Mediana plantilla",
                mode="markers+text",
                marker=dict(
                    color="#facc15",
                    size=14,
                    symbol="diamond",
                    line=dict(color="#0f172a", width=2),
                ),
                text=[f"Mediana: {med_oer_on:.2f}", f"Mediana: {med_der_on:.2f}"],
                textposition="top center",
                textfont=dict(color="#0f172a", size=11),
            )
        )
        max_val = max(fila["OER_ON"], fila["DER_ON"], med_oer_on, med_der_on)
        fig_on.update_layout(
            height=340,
            margin=dict(l=20, r=20, t=35, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(title="Puntos por posesión", range=[0, max_val * 1.25]),
        )
        st.plotly_chart(fig_on, use_container_width=True)

    # Gráfica 3: Cuatro pilares formativos vs Mediana del grupo
    st.subheader("Pilares formativos del tramo (Jugador vs Mediana del equipo)")
    pilares = ["Acierto real tiro (TS%)", "Paradas defensivas (%STOPS)", "Rebote ofensivo (%OREB)", "Ratio Asist/Pérd (AS/TO)"]
    vals_jug = [fila["TS%"], fila["%STOPS"], fila["%OREB"], fila["AS/TO"]]
    vals_med = [med_ts, med_stops, med_oreb, med_asto]

    fig_pilares = go.Figure()
    fig_pilares.add_trace(
        go.Bar(
            y=pilares,
            x=vals_jug,
            name=jugador_sel,
            orientation="h",
            marker_color="#0ea5e9",
            text=[f"{v:.1f}" for v in vals_jug],
            textposition="auto",
        )
    )
    fig_pilares.add_trace(
        go.Scatter(
            y=pilares,
            x=vals_med,
            name="Mediana plantilla",
            mode="markers",
            marker=dict(color="#dc2626", size=13, symbol="line-ns-open", line=dict(width=3)),
        )
    )
    fig_pilares.update_layout(
        height=280,
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_pilares, use_container_width=True)

    # Gráfica 4: Índices de Jugador Total en Defensa y Ataque
    mostrar_graficas_jugador_total(acum_f, jugador_sel=jugador_sel)

    # 3. Tabla resumen de estadísticas del tramo
    st.subheader("Resumen estadístico del tramo")
    cols_tabla = [
        "PART", "SEXTOS", "PTS", "PTS/SEX", "REB", "%OREB", "AS", "REC", "PER",
        "AS/TO", "TS%", "%USO", "OER_ON", "DER_ON", "NET_ON", "%STOPS", "VAL/SEX"
    ]
    cols_disp = [c for c in cols_tabla if c in acum_f.columns]
    st.dataframe(acum_f[acum_f["JUGADOR"] == jugador_sel][cols_disp], hide_index=True, use_container_width=True)

    st.divider()

    # 4. Reseña individual del entrenador
    st.subheader("Valoración del cuerpo técnico")

    with st.expander("Editar reseña del entrenador para este jugador", expanded=True):
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            fortalezas = st.text_area(
                "1. Fortalezas en pista",
                value="Buena actitud defensiva y energía en los sextos disputados. Ayuda al equipo a mantener el ritmo colectivo.",
                height=110,
                key=f"fort_{jugador_sel}",
            )
        with col_r2:
            foco = st.text_area(
                "2. Foco de trabajo actual",
                value="Seguir mejorando la lectura sin balón (ocupación de espacios) y la toma de decisiones tras bote.",
                height=110,
                key=f"foco_{jugador_sel}",
            )
        with col_r3:
            reto = st.text_area(
                "3. Reto próximas jornadas",
                value="Mantener la intensidad en el cierre del rebote defensivo y buscar el pase extra antes de finalizar.",
                height=110,
                key=f"reto_{jugador_sel}",
            )

    st.markdown(
        f"""
        **Fortalezas observadas:** {fortalezas}  
        **Foco de trabajo:** {foco}  
        **Reto próximo:** {reto}
        """
    )

    st.divider()

    # 5. Glosario familiar
    st.subheader("Glosario de métricas para familias")
    glosario_data = [
        ("SEXTOS", "Sextos jugados", "Tramos disputados en formato minibasket según la rotación y el plan de partido."),
        ("OER_ON", "Eficiencia ofensiva en pista", "Puntos que anota el equipo por cada posesión mientras el jugador está en pista."),
        ("DER_ON", "Eficiencia defensiva en pista", "Puntos que recibe el equipo por cada posesión cuando está en pista (cuanto más bajo, mejor)."),
        ("NET_ON", "Impacto neto en pista", "Diferencia entre OER_ON y DER_ON; mide el balance colectivo del equipo con el jugador en cancha."),
        ("%USO", "Participación ofensiva", "Porcentaje de posesiones del equipo que finaliza el jugador (tiro, tiro libre o pérdida) en sus sextos."),
        ("TS%", "Acierto real de tiro", "Eficiencia global al lanzar teniendo en cuenta tiros de 2, triples y tiros libres."),
        ("%STOPS", "Paradas defensivas", "Porcentaje de posesiones rivales frenadas con rebote defensivo, robo o tapón estando en pista."),
        ("%OREB", "Rebote ofensivo", "Porcentaje de rebotes de ataque capturados sobre los disponibles durante sus sextos."),
        ("AS/TO", "Asistencias por pérdida", "Relación entre pases de canasta y balones perdidos; refleja criterio y control."),
        ("VAL/SEX", "Valoración por sexto", "Aportación global positiva (puntos, rebotes, asistencias, robos, faltas recibidas) por sexto jugado."),
        ("IND_DEF", "Jugador Total en Defensa", "Combina defensa en pista (DER_ON), paradas (%STOPS), rebote defensivo y robos por sexto respecto al grupo; valores > 0 superan el nivel medio defensivo."),
        ("IND_ATK", "Jugador Total en Ataque", "Combina ataque en pista (OER_ON), acierto real (TS%), asistencias y rebote ofensivo por sexto ajustando por pérdidas; mide aportación ofensiva global."),
    ]
    df_glosario = pd.DataFrame(glosario_data, columns=["Sigla", "Nombre", "Qué significa en baloncesto de formación"])
    st.dataframe(df_glosario, hide_index=True, use_container_width=True)
    