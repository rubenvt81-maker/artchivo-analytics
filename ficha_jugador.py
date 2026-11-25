import streamlit as st
import plotly.express as px
import plotly.graph_objects as go


def mostrar_ficha_jugador(jugados, acum):
    """
    Dibuja la pestaña de análisis individual y comparador cara a cara.
    Recibe las tablas 'jugados' (partido a partido) y 'acum' (totales ponderados).
    """
    st.subheader("👤 Expediente Individual y Comparador de Jugadores")

    # 1. Selector de jugador ordenado por dorsal
    lista_jugadores = acum.sort_values("NUM")["JUGADOR"].tolist()
    mapa_dorsal = dict(zip(acum["JUGADOR"], acum["NUM"]))

    jugador_sel = st.selectbox(
        "Selecciona un jugador de la plantilla:",
        options=lista_jugadores,
        format_func=lambda nombre: f"#{mapa_dorsal[nombre]} — {nombre}",
    )

    # Filtramos los datos acumulados y los partidos de ese jugador
    datos_j = acum[acum["JUGADOR"] == jugador_sel].iloc[0]
    partidos_j = jugados[jugados["JUGADOR"] == jugador_sel].sort_values("JORNADA").copy()
    partidos_j["PARTIDO"] = "J" + partidos_j["JORNADA"].astype(str) + " (" + partidos_j["RIVAL"] + ")"

    # 2. Tarjetas resumen del jugador (KPIs)
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Partidos / Sextos", f"{int(datos_j['PART'])} P / {datos_j['SEXTOS']:.1f} S")
    c2.metric("Puntos / Sexto", f"{datos_j['PTS/SEX']:.2f}", f"{int(datos_j['PTS'])} pts tot.")
    c3.metric("OER Ind. / TS%", f"{datos_j['OER']:.2f} ppp", f"TS: {datos_j['TS%']:.1f}%")
    c4.metric("%USO en Pista", f"{datos_j['%USO']:.1f}%", f"{datos_j['POS']:.1f} pos. fin.")
    c5.metric("NET_ON en Pista", f"{datos_j['NET_ON']:+.2f}", f"OER {datos_j['OER_ON']:.2f} / DER {datos_j['DER_ON']:.2f}")
    c6.metric("%STOPS / VAL-Sex", f"{datos_j['%STOPS']:.1f}%", f"VAL/Sex: {datos_j['VAL/SEX']:.2f}")

    st.divider()

    # 3. Gráficos individuales: Evolución por jornada y Perfil de Tiro
    col_evol, col_tiro = st.columns([1.4, 1])

    with col_evol:
        st.markdown(f"**📈 Evolución jornada a jornada — {jugador_sel}**")
        fig_evol = go.Figure()
        fig_evol.add_trace(go.Bar(
            x=partidos_j["PARTIDO"],
            y=partidos_j["PTS"],
            name="Puntos anotados",
            marker_color="#93C5FD",
            yaxis="y",
        ))
        fig_evol.add_trace(go.Scatter(
            x=partidos_j["PARTIDO"],
            y=partidos_j["OER"],
            name="OER Individual",
            mode="lines+markers",
            line=dict(color="#1D4ED8", width=2.5),
            yaxis="y2",
        ))
        fig_evol.add_trace(go.Scatter(
            x=partidos_j["PARTIDO"],
            y=partidos_j["NET_ON"],
            name="NET_ON en pista",
            mode="lines+markers",
            line=dict(color="#059669", width=2.5, dash="dot"),
            yaxis="y2",
        ))
        fig_evol.update_layout(
            height=380,
            margin=dict(l=10, r=10, t=20, b=20),
            yaxis=dict(title="Puntos", side="left"),
            yaxis2=dict(title="Pts / Posesión", side="right", overlaying="y", showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_evol, use_container_width=True)

    with col_tiro:
        st.markdown("**🎯 Acierto por Tipo de Lanzamiento**")
        df_tiro = {
            "Tipo": ["Tiros de 2 (2P%)", "Triples (3P%)", "Tiros Libres (TL%)", "Tiro Efectivo (eFG%)", "True Shooting (TS%)"],
            "Porcentaje": [datos_j["%2P"], datos_j["%3P"], datos_j["%TL"], datos_j["%eFG"], datos_j["TS%"]],
            "Detalle": [
                f"{int(datos_j['PM2'])}/{int(datos_j['PA2'])}",
                f"{int(datos_j['PM3'])}/{int(datos_j['PA3'])}",
                f"{int(datos_j['FTM'])}/{int(datos_j['FTA'])}",
                f"{int(datos_j['FGM'])}/{int(datos_j['FGA'])} TC",
                f"{int(datos_j['PTS'])} pts",
            ],
        }
        fig_tiro = px.bar(
            df_tiro,
            x="Porcentaje",
            y="Tipo",
            orientation="h",
            text="Detalle",
            color="Porcentaje",
            color_continuous_scale="Blues",
            range_x=[0, 100],
        )
        fig_tiro.update_traces(textposition="outside")
        fig_tiro.update_layout(
            height=380,
            margin=dict(l=10, r=30, t=20, b=20),
            coloraxis_showscale=False,
            xaxis_title="Porcentaje (%)",
            yaxis_title="",
        )
        st.plotly_chart(fig_tiro, use_container_width=True)

    # 4. Historial de partidos del jugador
    st.markdown(f"**📋 Registro partido a partido de {jugador_sel}**")
    cols_partido = [
        "JORNADA", "RIVAL", "SEXTOS", "PTS", "2PM", "2PA", "3PM", "3PA", "FTM", "FTA",
        "RO", "RD", "AS", "STL", "TO", "VAL", "POS", "OER", "TS%", "%USO", "OER_ON", "DER_ON", "NET_ON"
    ]
    st.dataframe(partidos_j[cols_partido], use_container_width=True, hide_index=True)

    st.divider()

    # 5. Comparador directo entre dos jugadores
    st.markdown("### ⚖️ Comparador Cara a Cara")
    jugador_2 = st.selectbox(
        f"Comparar a #{mapa_dorsal[jugador_sel]} {jugador_sel} con:",
        options=[j for j in lista_jugadores if j != jugador_sel],
        format_func=lambda nombre: f"#{mapa_dorsal[nombre]} — {nombre}",
    )

    datos_j2 = acum[acum["JUGADOR"] == jugador_2].iloc[0]

    metricas_comp = [
        ("Puntos / Sexto", "PTS/SEX"),
        ("Rebotes / Sexto", "REB"),
        ("Asistencias", "AS"),
        ("Valoración / Sexto", "VAL/SEX"),
        ("OER Individual", "OER"),
        ("TS%", "TS%"),
        ("%USO en Pista", "%USO"),
        ("OER_ON (Ataque)", "OER_ON"),
        ("DER_ON (Defensa)", "DER_ON"),
        ("NET_ON (Impacto)", "NET_ON"),
        ("%STOPS Defensa", "%STOPS"),
        ("Ratio AS/TO", "AS/TO"),
    ]

    tabla_comp = []
    for etiqueta, col in metricas_comp:
        v1 = datos_j[col]
        v2 = datos_j2[col]
        tabla_comp.append({
            "Métrica": etiqueta,
            f"#{mapa_dorsal[jugador_sel]} {jugador_sel}": v1,
            f"#{mapa_dorsal[jugador_2]} {jugador_2}": v2,
            "Diferencia": round(v1 - v2, 2),
        })

    st.dataframe(tabla_comp, use_container_width=True, hide_index=True)
    