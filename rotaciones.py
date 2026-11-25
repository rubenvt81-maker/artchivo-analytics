import streamlit as st
import pandas as pd


def generar_rotacion_sugerida(convocados, acum_df):
    """
    Calcula una rotación base para 10, 11 o 12 jugadores convocados
    cumpliendo la regla pasarela (mínimo 2 sextos antes del 6.º y máximo 4 totales),
    arrancando y cerrando con los quintetos de mayor impacto.
    """
    sub = acum_df[acum_df["JUGADOR"].isin(convocados)].copy()
    sub["REB_SEX"] = sub["REB"] / sub["SEXTOS"]
    # Índice combinado de impacto colectivo (NET_ON) + producción por sexto
    sub["SCORE"] = sub["NET_ON"] * 10 + sub["PTS/SEX"] * 0.5 + sub["REB_SEX"] * 0.4
    p = sub.sort_values("SCORE", ascending=False)["JUGADOR"].tolist()
    n = len(p)

    if n == 12:
        return {
            1: [p[0], p[1], p[2], p[3], p[4]],
            2: [p[5], p[6], p[7], p[8], p[9]],
            3: [p[0], p[1], p[6], p[10], p[11]],
            4: [p[2], p[3], p[5], p[7], p[8]],
            5: [p[0], p[4], p[9], p[10], p[11]],
            6: [p[0], p[1], p[2], p[3], p[4]],
        }
    elif n == 11:
        return {
            1: [p[0], p[1], p[2], p[3], p[4]],
            2: [p[5], p[6], p[7], p[8], p[9]],
            3: [p[0], p[1], p[2], p[10], p[5]],
            4: [p[3], p[4], p[6], p[7], p[8]],
            5: [p[0], p[1], p[2], p[9], p[10]],
            6: [p[0], p[1], p[2], p[3], p[4]],
        }
    elif n == 10:
        return {
            1: [p[0], p[1], p[2], p[3], p[4]],
            2: [p[5], p[6], p[7], p[8], p[9]],
            3: [p[0], p[1], p[2], p[5], p[6]],
            4: [p[3], p[4], p[7], p[8], p[9]],
            5: [p[0], p[1], p[2], p[3], p[4]],
            6: [p[0], p[1], p[2], p[3], p[4]],
        }
    else:
        return {q: p[: min(5, n)] for q in range(1, 7)}


def mostrar_planificador_rotaciones(acum):
    """
    Dibuja la pestaña interactiva de planificación de sextos y control de regla pasarela.
    """
    st.subheader("⏱️ Planificador Táctico de Rotaciones (6 Sextos — Regla Pasarela)")
    st.caption(
        "Configura la convocatoria del partido, aplica la rotación sugerida por datos o ajusta manualmente cada sexto con verificación automática de reglas."
    )

    acum_work = acum.sort_values("NUM").copy()
    acum_work["REB/SEX"] = (acum_work["REB"] / acum_work["SEXTOS"]).round(2)
    todos_jugadores = acum_work["JUGADOR"].tolist()
    mapa_dorsal = dict(zip(acum_work["JUGADOR"], acum_work["NUM"]))

    # 1. Selección de convocatoria
    convocados = st.multiselect(
        "1️⃣ Jugadores convocados para el partido (recomendado: 10, 11 o 12):",
        options=todos_jugadores,
        default=todos_jugadores,
        format_func=lambda j: f"#{mapa_dorsal[j]} {j}",
    )

    if len(convocados) < 8:
        st.warning("Selecciona al menos 8 jugadores convocados para poder organizar los sextos.")
        return

    # Botón para regenerar automáticamente según los convocados actuales
    clave_conv = tuple(sorted(convocados))
    if (
        "rotacion_actual" not in st.session_state
        or st.session_state.get("ultima_convocatoria") != clave_conv
        or st.button("🔄 Restablecer rotación óptima según estadísticas")
    ):
        st.session_state["rotacion_actual"] = generar_rotacion_sugerida(convocados, acum_work)
        st.session_state["ultima_convocatoria"] = clave_conv

    st.divider()
    st.markdown("### 2️⃣ Pizarra de Quintetos por Sexto (haz clic para modificar jugadores)")

    # 2. Editor interactivo en 2 filas de 3 columnas (Sextos 1-3 arriba, Sextos 4-6 abajo)
    rotacion_editada = {}
    fila1 = st.columns(3)
    fila2 = st.columns(3)
    columnas_sextos = fila1 + fila2

    idx_jugadores = acum_work.set_index("JUGADOR")

    for sexto in range(1, 7):
        with columnas_sextos[sexto - 1]:
            st.markdown(f"**Sexto {sexto}**")
            seleccion = st.multiselect(
                f"Quinteto S{sexto}",
                options=convocados,
                default=[j for j in st.session_state["rotacion_actual"][sexto] if j in convocados],
                max_selections=5,
                format_func=lambda j: f"#{mapa_dorsal[j]} {j}",
                key=f"sel_sexto_{sexto}",
                label_visibility="collapsed",
            )
            rotacion_editada[sexto] = seleccion

            # Mini-resumen estadístico del quinteto en tiempo real
            if len(seleccion) == 5:
                sub_q = idx_jugadores.loc[seleccion]
                st.caption(
                    f"OER_ON: **{sub_q['OER_ON'].mean():.2f}** | "
                    f"DER_ON: **{sub_q['DER_ON'].mean():.2f}** | "
                    f"NET: **{sub_q['NET_ON'].mean():+.2f}**\n\n"
                    f"PTS/Sex: **{sub_q['PTS/SEX'].sum():.1f}** | "
                    f"REB/Sex: **{sub_q['REB/SEX'].sum():.1f}** | "
                    f"%USO: **{sub_q['%USO'].sum():.0f}%**"
                )
            else:
                st.error(f"Faltan {5 - len(seleccion)} jugador(es) en este sexto.")

    st.divider()

    # 3. Auditoría automática de Regla Pasarela y Cargas por Jugador
    st.markdown("### 3️⃣ Verificación de Regla Pasarela y Cargas por Jugador")

    filas_auditoria = []
    errores_regla = []

    for sexto in range(1, 7):
        if len(rotacion_editada[sexto]) != 5:
            errores_regla.append(f"El **Sexto {sexto}** tiene {len(rotacion_editada[sexto])} jugadores (debe tener 5).")

    for j in convocados:
        sextos_j = [q for q in range(1, 7) if j in rotacion_editada[j_q := q]]
        en_p1_p5 = sum(1 for q in sextos_j if q <= 5)
        total_j = len(sextos_j)

        # Comprobar si juega 3 sextos seguidos en P1-P5
        seq_p1_p5 = [1 if q in sextos_j else 0 for q in range(1, 6)]
        tres_seguidos = any(sum(seq_p1_p5[i : i + 3]) == 3 for i in range(3))

        estado = "✅ OK"
        if en_p1_p5 < 2:
            estado = "❌ Menos de 2 sextos antes del 6.º"
            errores_regla.append(f"**#{mapa_dorsal[j]} {j}** solo juega {en_p1_p5} sexto(s) antes del último (mínimo 2).")
        elif total_j > 4:
            estado = "❌ Más de 4 sextos"
            errores_regla.append(f"**#{mapa_dorsal[j]} {j}** juega {total_j} sextos (máximo 4).")
        elif tres_seguidos:
            estado = "⚠️ 3 sextos seguidos (P1-P5)"

        filas_auditoria.append({
            "Dorsal": mapa_dorsal[j],
            "Jugador": j,
            "Sextos": ", ".join(f"{q}º" for q in sextos_j) if sextos_j else "Ninguno",
            "Antes del 6.º (P1-P5)": en_p1_p5,
            "Total Sextos": total_j,
            "Estado": estado,
        })

    if not errores_regla:
        st.success("✅ **Rotación 100% válida:** Todos los jugadores cumplen la regla pasarela (≥ 2 sextos en P1–P5 y ≤ 4 sextos totales).")
    else:
        for err in errores_regla:
            st.error(err)

    df_auditoria = pd.DataFrame(filas_auditoria)
    st.dataframe(df_auditoria, use_container_width=True, hide_index=True)

    # 4. Botón de descarga de la hoja de rotación para llevar al partido
    resumen_export = []
    for q in range(1, 7):
        jugs = [f"#{mapa_dorsal[j]} {j}" for j in rotacion_editada[q]]
        resumen_export.append({
            "Sexto": f"Sexto {q}",
            "J1": jugs[0] if len(jugs) > 0 else "",
            "J2": jugs[1] if len(jugs) > 1 else "",
            "J3": jugs[2] if len(jugs) > 2 else "",
            "J4": jugs[3] if len(jugs) > 3 else "",
            "J5": jugs[4] if len(jugs) > 4 else "",
        })
    csv_banquillo = pd.DataFrame(resumen_export).to_csv(index=False, sep=";").encode("utf-8-sig")

    st.download_button(
        label="📥 Descargar hoja de rotación para banquillo (.csv)",
        data=csv_banquillo,
        file_name="rotacion_artchivo_u12.csv",
        mime="text/csv",
    )