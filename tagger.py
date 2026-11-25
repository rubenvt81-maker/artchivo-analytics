import streamlit as st
import pandas as pd
import json
import os
import re
from io import BytesIO
from datetime import datetime

EXCEL_MAESTRO = "alevin_tabla_estadistica_v2.xlsx"

PLANTILLA_RESPALDO = [
    "SERGIO", "MIGUEL", "ANDRÉS", "JUAN", "ÁLVARO", "PABLO",
    "VÍCTOR", "IVÁN", "PRIETO", "BITTOR", "JUGADOR 11", "JUGADOR 12"
]

TRAMOS_BASE_1_5 = ["Sexto 1", "Sexto 2", "Sexto 3", "Sexto 4", "Sexto 5"]
TRAMOS_FINAL = ["Sexto 6A (0,5)", "Sexto 6B (0,5)"]


def cargar_plantilla_solo_lectura():
    """Lee los nombres de los jugadores desde el Excel maestro sin modificarlo jamás."""
    if not os.path.exists(EXCEL_MAESTRO):
        return PLANTILLA_RESPALDO
    try:
        xls = pd.ExcelFile(EXCEL_MAESTRO)
        if "REGISTRO_PARTIDOS" in xls.sheet_names:
            df_reg = pd.read_excel(xls, sheet_name="REGISTRO_PARTIDOS")
            col_jug = next((c for c in df_reg.columns if "JUGADOR" in str(c).upper()), None)
            if col_jug:
                jugadores = (
                    df_reg[col_jug]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .unique()
                    .tolist()
                )
                jugadores = [j for j in jugadores if j and j.upper() not in ("TOTAL", "EQUIPO", "NAN")]
                if len(jugadores) >= 5:
                    return jugadores
    except Exception:
        pass
    return PLANTILLA_RESPALDO


def construir_tramos_disponibles(sexto6_sin_cambios, sextos_excepcion):
    """Construye la lista de tramos activos respetando cambios excepcionales en sextos 1-5 y el 6º sexto."""
    tramos = []
    for s in TRAMOS_BASE_1_5:
        if s in sextos_excepcion:
            tramos.extend([f"{s}A (0,5)", f"{s}B (0,5)"])
        else:
            tramos.append(s)

    if sexto6_sin_cambios:
        tramos.append("Sexto 6A (0,5)")
    else:
        tramos.extend(TRAMOS_FINAL)
    return tramos


def inicializar_estado_tagger(plantilla):
    if "tagger_meta" not in st.session_state:
        st.session_state.tagger_meta = {
            "jornada": 10,
            "rival": "RIVAL",
            "fecha": datetime.today().strftime("%d/%m/%Y"),
            "condicion": "LOCAL",
            "sexto6_sin_cambios": False,
            "sextos_excepcion": [],
        }
    if "sextos_excepcion" not in st.session_state.tagger_meta:
        st.session_state.tagger_meta["sextos_excepcion"] = []

    if "tagger_quintets" not in st.session_state:
        todos_posibles = (
            TRAMOS_BASE_1_5
            + [f"{s}A (0,5)" for s in TRAMOS_BASE_1_5]
            + [f"{s}B (0,5)" for s in TRAMOS_BASE_1_5]
            + TRAMOS_FINAL
        )
        st.session_state.tagger_quintets = {t: [] for t in todos_posibles}
    if "tagger_eventos" not in st.session_state:
        st.session_state.tagger_eventos = []
    if "tagger_clips" not in st.session_state:
        st.session_state.tagger_clips = []
    if "tagger_tramo_activo" not in st.session_state:
        st.session_state.tagger_tramo_activo = "Sexto 1"
    if "tagger_jugador_activo" not in st.session_state:
        st.session_state.tagger_jugador_activo = plantilla[0] if plantilla else ""


def convertir_tiempo_a_segundos(tiempo_str):
    """Convierte 'MM:SS' o 'HH:MM:SS' a segundos enteros."""
    partes = [p.strip() for p in str(tiempo_str).split(":") if p.strip().isdigit()]
    if len(partes) == 2:
        return int(partes[0]) * 60 + int(partes[1])
    elif len(partes) == 3:
        return int(partes[0]) * 3600 + int(partes[1]) * 60 + int(partes[2])
    return None


def formatear_hhmmss(segundos):
    segundos = max(0, int(segundos))
    h = segundos // 3600
    m = (segundos % 3600) // 60
    s = segundos % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def recalcular_estadisticas(plantilla, quintets, eventos, sexto6_sin_cambios, sextos_excepcion):
    """Recalcula toda la estadística individual y colectiva desde cero a partir de quintetos y eventos."""
    cols_ind = [
        "JUGADOR", "SEXTOS", "PTS", "PTS_FAV", "PTS_REC",
        "2PM", "2PA", "3PM", "3PA", "FTM", "FTA",
        "OR", "DR", "AS", "ST", "TO", "TAP_F", "TAP_C", "FC", "FR"
    ]
    ind = {j: {c: 0 for c in cols_ind} for j in plantilla}
    for j in plantilla:
        ind[j]["JUGADOR"] = j
        ind[j]["SEXTOS"] = 0.0

    # 1. Calcular SEXTOS según quintetos configurados (incluyendo cambios excepcionales en 1-5)
    for s in TRAMOS_BASE_1_5:
        if s in sextos_excepcion:
            for sub in (f"{s}A (0,5)", f"{s}B (0,5)"):
                for j in quintets.get(sub, []):
                    if j in ind:
                        ind[j]["SEXTOS"] = round(ind[j]["SEXTOS"] + 0.5, 2)
        else:
            for j in quintets.get(s, []):
                if j in ind:
                    ind[j]["SEXTOS"] = round(ind[j]["SEXTOS"] + 1.0, 2)

    if sexto6_sin_cambios:
        for j in quintets.get("Sexto 6A (0,5)", []):
            if j in ind:
                ind[j]["SEXTOS"] = round(ind[j]["SEXTOS"] + 1.0, 2)
    else:
        for tramo in TRAMOS_FINAL:
            for j in quintets.get(tramo, []):
                if j in ind:
                    ind[j]["SEXTOS"] = round(ind[j]["SEXTOS"] + 0.5, 2)

    # 2. Contadores colectivos Artchivo y Rival
    eq_art = {
        "PTS": 0, "2PM": 0, "2PA": 0, "3PM": 0, "3PA": 0, "FTM": 0, "FTA": 0,
        "OR": 0, "DR": 0, "AS": 0, "ST": 0, "TO": 0, "TAP_F": 0, "TAP_C": 0, "FC": 0, "FR": 0,
        "CONTRA_REB": 0, "CONTRA_PER": 0, "PRESION_EXT": 0, "PRESION_FR": 0
    }
    eq_riv = {
        "PTS": 0, "2PM": 0, "2PA": 0, "3PM": 0, "3PA": 0, "FTM": 0, "FTA": 0,
        "OR": 0, "DR": 0, "AS": 0, "ST": 0, "TO": 0, "TAP_F": 0, "TAP_C": 0, "FC": 0, "FR": 0,
        "CONTRA_REB": 0, "CONTRA_PER": 0, "PRESION_EXT": 0, "PRESION_FR": 0
    }

    # 3. Procesar cronológicamente los eventos
    for ev in eventos:
        tramo = ev["tramo"]
        # Si se activó cambio excepcional tras haber anotado el inicio del sexto, reasignar al tramo A
        if tramo in sextos_excepcion:
            tramo = f"{tramo}A (0,5)"
        elif tramo.endswith("A (0,5)") or tramo.endswith("B (0,5)"):
            base_s = tramo[:-7]
            if base_s in TRAMOS_BASE_1_5 and base_s not in sextos_excepcion:
                tramo = base_s

        if sexto6_sin_cambios and tramo == "Sexto 6B (0,5)":
            tramo = "Sexto 6A (0,5)"

        en_pista = [j for j in quintets.get(tramo, []) if j in ind]
        equipo = ev["equipo"]
        jug = ev.get("jugador", "")
        acc = ev["accion"]

        if equipo == "ARTCHIVO":
            if acc in ("CONTRA_REB", "CONTRA_PER", "PRESION_EXT", "PRESION_FR"):
                eq_art[acc] += 1
                continue

            if jug not in ind:
                continue

            pts_jugada = 0
            if acc == "2P+":
                ind[jug]["2PM"] += 1; ind[jug]["2PA"] += 1; ind[jug]["PTS"] += 2
                eq_art["2PM"] += 1; eq_art["2PA"] += 1; eq_art["PTS"] += 2
                pts_jugada = 2
            elif acc == "2P-":
                ind[jug]["2PA"] += 1; eq_art["2PA"] += 1
            elif acc == "3P+":
                ind[jug]["3PM"] += 1; ind[jug]["3PA"] += 1; ind[jug]["PTS"] += 3
                eq_art["3PM"] += 1; eq_art["3PA"] += 1; eq_art["PTS"] += 3
                pts_jugada = 3
            elif acc == "3P-":
                ind[jug]["3PA"] += 1; eq_art["3PA"] += 1
            elif acc == "TL+":
                ind[jug]["FTM"] += 1; ind[jug]["FTA"] += 1; ind[jug]["PTS"] += 1
                eq_art["FTM"] += 1; eq_art["FTA"] += 1; eq_art["PTS"] += 1
                pts_jugada = 1
            elif acc == "TL-":
                ind[jug]["FTA"] += 1; eq_art["FTA"] += 1
            elif acc in ("OR", "DR", "AS", "ST", "TO", "TAP_F"):
                ind[jug][acc] += 1
                eq_art[acc] += 1
            elif acc == "TAP_C":
                ind[jug]["TAP_C"] += 1
                eq_art["TAP_C"] += 1
                eq_riv["TAP_F"] += 1
            elif acc == "FC":
                ind[jug]["FC"] += 1
                eq_art["FC"] += 1
                eq_riv["FR"] += 1
            elif acc == "FR":
                ind[jug]["FR"] += 1
                eq_art["FR"] += 1
                eq_riv["FC"] += 1

            if pts_jugada > 0:
                for p in en_pista:
                    ind[p]["PTS_FAV"] += pts_jugada

        elif equipo == "RIVAL":
            pts_rival = 0
            if acc == "2P+":
                eq_riv["2PM"] += 1; eq_riv["2PA"] += 1; eq_riv["PTS"] += 2
                pts_rival = 2
            elif acc == "2P-":
                eq_riv["2PA"] += 1
            elif acc == "3P+":
                eq_riv["3PM"] += 1; eq_riv["3PA"] += 1; eq_riv["PTS"] += 3
                pts_rival = 3
            elif acc == "3P-":
                eq_riv["3PA"] += 1
            elif acc == "TL+":
                eq_riv["FTM"] += 1; eq_riv["FTA"] += 1; eq_riv["PTS"] += 1
                pts_rival = 1
            elif acc == "TL-":
                eq_riv["FTA"] += 1
            elif acc in ("OR", "DR", "AS", "ST", "TO", "TAP_F", "TAP_C", "FC", "FR"):
                eq_riv[acc] += 1

            if pts_rival > 0:
                for p in en_pista:
                    ind[p]["PTS_REC"] += pts_rival

    df_ind = pd.DataFrame([ind[j] for j in plantilla])
    return df_ind, eq_art, eq_riv


def generar_excel_borrador(meta, df_ind, eq_art, eq_riv, eventos, clips):
    """Genera un archivo Excel borrador aislado alineado con las columnas de tu libro maestro."""
    jornada = meta["jornada"]
    rival = meta["rival"].strip().upper() or "RIVAL"
    res_art = "WIN" if eq_art["PTS"] > eq_riv["PTS"] else ("LOST" if eq_art["PTS"] < eq_riv["PTS"] else "DRAW")
    res_riv = "LOST" if res_art == "WIN" else ("WIN" if res_art == "LOST" else "DRAW")

    df_reg_out = df_ind.copy()
    df_reg_out.insert(0, "JORNADA", jornada)
    df_reg_out.insert(1, "RIVAL", rival)

    fila_art = {
        "NUM GAME": jornada,
        "OFFENSE": "ARTCHIVO",
        "DEFENSE": rival,
        "WIN/\nLOST": res_art,
        "PTS": eq_art["PTS"],
        "2PM": eq_art["2PM"], "2PA": eq_art["2PA"],
        "3PM": eq_art["3PM"], "3PA": eq_art["3PA"],
        "FTM": eq_art["FTM"], "FTA": eq_art["FTA"],
        "OR": eq_art["OR"], "DR": eq_art["DR"],
        "AS": eq_art["AS"], "ST": eq_art["ST"], "TO": eq_art["TO"],
        "TAP_F": eq_art["TAP_F"], "TAP_C": eq_art["TAP_C"],
        "FC": eq_art["FC"], "FR": eq_art["FR"],
        "CONTRA_REB": eq_art["CONTRA_REB"], "CONTRA_PER": eq_art["CONTRA_PER"],
        "PRESION_EXT": eq_art["PRESION_EXT"], "PRESION_FR": eq_art["PRESION_FR"],
    }
    fila_riv = {
        "NUM GAME": jornada,
        "OFFENSE": rival,
        "DEFENSE": "ARTCHIVO",
        "WIN/\nLOST": res_riv,
        "PTS": eq_riv["PTS"],
        "2PM": eq_riv["2PM"], "2PA": eq_riv["2PA"],
        "3PM": eq_riv["3PM"], "3PA": eq_riv["3PA"],
        "FTM": eq_riv["FTM"], "FTA": eq_riv["FTA"],
        "OR": eq_riv["OR"], "DR": eq_riv["DR"],
        "AS": eq_riv["AS"], "ST": eq_riv["ST"], "TO": eq_riv["TO"],
        "TAP_F": eq_riv["TAP_F"], "TAP_C": eq_riv["TAP_C"],
        "FC": eq_riv["FC"], "FR": eq_riv["FR"],
        "CONTRA_REB": 0, "CONTRA_PER": 0,
        "PRESION_EXT": 0, "PRESION_FR": 0,
    }
    df_games_out = pd.DataFrame([fila_art, fila_riv])

    if os.path.exists(EXCEL_MAESTRO):
        try:
            xls = pd.ExcelFile(EXCEL_MAESTRO)
            if "REGISTRO_PARTIDOS" in xls.sheet_names:
                cols_maestro_reg = pd.read_excel(xls, sheet_name="REGISTRO_PARTIDOS", nrows=0).columns.tolist()
                sinonimos = {"OR": "RO", "DR": "RD", "ST": "REC", "TO": "PER"}
                for en, es in sinonimos.items():
                    if es in cols_maestro_reg and en in df_reg_out.columns:
                        df_reg_out = df_reg_out.rename(columns={en: es})
                cols_comunes = [c for c in cols_maestro_reg if c in df_reg_out.columns]
                cols_extra = [c for c in df_reg_out.columns if c not in cols_comunes]
                if cols_comunes:
                    df_reg_out = df_reg_out[cols_comunes + cols_extra]
        except Exception:
            pass

    df_videos_out = pd.DataFrame(clips) if clips else pd.DataFrame(
        columns=["JORNADA", "RIVAL", "TRAMO", "JUGADOR", "CONCEPTO", "INICIO_CLIP", "FIN_CLIP", "NOTA_ENTRENADOR", "URL_VIDEO"]
    )
    df_eventos_out = pd.DataFrame(eventos) if eventos else pd.DataFrame(
        columns=["tramo", "equipo", "jugador", "accion", "etiqueta"]
    )

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_reg_out.to_excel(writer, sheet_name="REGISTRO_PARTIDOS_BORRADOR", index=False)
        df_games_out.to_excel(writer, sheet_name="GAMES_BORRADOR", index=False)
        df_videos_out.to_excel(writer, sheet_name="VIDEOS", index=False)
        df_eventos_out.to_excel(writer, sheet_name="LOG_EVENTOS", index=False)
    buffer.seek(0)
    return buffer


def generar_bat_ffmpeg(meta, clips):
    """Genera un script .bat para cortar automáticamente los clips de 12s con FFmpeg en Windows."""
    jornada = meta["jornada"]
    rival = re.sub(r"[^A-Za-z0-9_-]", "", meta["rival"].upper() or "RIVAL")
    lineas = [
        "@echo off",
        "chcp 65001 >nul",
        f"echo === RECORTANDO CLIPS TACTICOS JORNADA {jornada} vs {rival} ===",
        'set /p VIDEO="Arrastra aqui el archivo de video del partido y pulsa ENTER: "',
        'set VIDEO=%VIDEO:"=%',
        f'if not exist "CLIPS_J{jornada}_{rival}" mkdir "CLIPS_J{jornada}_{rival}"',
        ""
    ]
    for idx, c in enumerate(clips, start=1):
        concepto_limpio = re.sub(r"[^A-Za-z0-9_-]", "_", c["CONCEPTO"])
        jug_limpio = re.sub(r"[^A-Za-z0-9_-]", "_", c["JUGADOR"])
        nombre_salida = f"CLIPS_J{jornada}_{rival}\\J{jornada}_{idx:02d}_{concepto_limpio}_{jug_limpio}.mp4"
        lineas.append(
            f'ffmpeg -y -ss {c["INICIO_CLIP"]} -i "%VIDEO%" -t 12 -c copy "{nombre_salida}"'
        )
    lineas.extend([
        "",
        "echo.",
        f'echo Listo! Clips guardados en la carpeta CLIPS_J{jornada}_{rival}',
        "pause"
    ])
    return "\r\n".join(lineas).encode("utf-8")


def mostrar_tagger():
    st.header("🎯 Calculadora Post-Partido & Cortafuegos Táctico")
    st.caption(
        "Analiza el vídeo del partido con precisión. Tus datos se guardan en un borrador aislado "
        "y pasan una auditoría matemática antes de tocar el Excel maestro."
    )

    plantilla = cargar_plantilla_solo_lectura()
    inicializar_estado_tagger(plantilla)

    # --- BARRA SUPERIOR: CORTAFUEGOS DE SESIÓN (GUARDAR / RECUPERAR) ---
    with st.expander("🛡️ Cortafuegos de Sesión (Guardar o Recuperar trabajo a medias)", expanded=False):
        c_up, c_down, c_reset = st.columns([2, 1, 1])
        with c_up:
            archivo_sesion = st.file_uploader(
                "Recuperar sesión guardada (.json)", type=["json"], key="uploader_sesion_tagger"
            )
            if archivo_sesion is not None:
                if st.button("Cargar sesión seleccionada", use_container_width=True):
                    datos = json.load(archivo_sesion)
                    st.session_state.tagger_meta = datos.get("meta", st.session_state.tagger_meta)
                    st.session_state.tagger_quintets = datos.get("quintets", st.session_state.tagger_quintets)
                    st.session_state.tagger_eventos = datos.get("eventos", [])
                    st.session_state.tagger_clips = datos.get("clips", [])
                    st.success("Sesión recuperada exactamente donde la dejaste.")
                    st.rerun()

        with c_down:
            respaldo_json = json.dumps(
                {
                    "meta": st.session_state.tagger_meta,
                    "quintets": st.session_state.tagger_quintets,
                    "eventos": st.session_state.tagger_eventos,
                    "clips": st.session_state.tagger_clips,
                },
                ensure_ascii=False,
                indent=2,
            )
            st.download_button(
                "💾 Guardar copia (.json)",
                data=respaldo_json,
                file_name=f"sesion_J{st.session_state.tagger_meta['jornada']}_{st.session_state.tagger_meta['rival']}.json",
                mime="application/json",
                use_container_width=True,
            )

        with c_reset:
            if st.button("🗑️ Reiniciar partido", use_container_width=True):
                for k in ["tagger_quintets", "tagger_eventos", "tagger_clips"]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.rerun()

    # --- BLOQUE 1: DATOS DEL PARTIDO Y QUINTETOS ---
    c1, c2, c3, c4 = st.columns([1, 2, 1, 1.5])
    st.session_state.tagger_meta["jornada"] = c1.number_input(
        "Jornada", min_value=1, max_value=40, value=int(st.session_state.tagger_meta["jornada"])
    )
    st.session_state.tagger_meta["rival"] = c2.text_input(
        "Equipo Rival", value=st.session_state.tagger_meta["rival"]
    )
    st.session_state.tagger_meta["condicion"] = c3.selectbox(
        "Condición", ["LOCAL", "VISITANTE"],
        index=0 if st.session_state.tagger_meta["condicion"] == "LOCAL" else 1
    )
    st.session_state.tagger_meta["sexto6_sin_cambios"] = c4.checkbox(
        "6º Sexto sin cambios (1,0)",
        value=st.session_state.tagger_meta["sexto6_sin_cambios"],
        help="Márcalo solo si en el último sexto jugaron los mismos 5 todo el periodo."
    )

    st.session_state.tagger_meta["sextos_excepcion"] = st.multiselect(
        "🚑 Cambio excepcional en Sextos 1–5 (solo si hubo 5ª falta o lesión):",
        options=TRAMOS_BASE_1_5,
        default=[s for s in st.session_state.tagger_meta.get("sextos_excepcion", []) if s in TRAMOS_BASE_1_5],
        help="Divide el sexto elegido en tramos A (0,5) y B (0,5) para registrar el cambio.",
    )

    sexto6_unico = st.session_state.tagger_meta["sexto6_sin_cambios"]
    sextos_exc = st.session_state.tagger_meta["sextos_excepcion"]
    tramos_disponibles = construir_tramos_disponibles(sexto6_unico, sextos_exc)

    if st.session_state.tagger_tramo_activo not in tramos_disponibles:
        st.session_state.tagger_tramo_activo = tramos_disponibles[0]

    st.markdown("---")

    # Recalcular estado actual en tiempo real
    df_ind, eq_art, eq_riv = recalcular_estadisticas(
        plantilla,
        st.session_state.tagger_quintets,
        st.session_state.tagger_eventos,
        sexto6_unico,
        sextos_exc,
    )

    # Marcador en vivo del vídeo
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("ARTCHIVO", f"{eq_art['PTS']} pts")
    m2.metric(st.session_state.tagger_meta["rival"].upper() or "RIVAL", f"{eq_riv['PTS']} pts")
    m3.metric("Total Sextos Asignados", f"{df_ind['SEXTOS'].sum():.1f} / 30.0")
    m4.metric("Jugadas Registradas", len(st.session_state.tagger_eventos))

    # --- BLOQUE 2: SELECTOR DE TRAMO Y QUINTETO EN PISTA ---
    st.subheader("1️⃣ Selección de Sexto y Quinteto en Pista")
    tramo_sel = st.radio(
        "Tramo activo del vídeo:",
        tramos_disponibles,
        horizontal=True,
        key="tagger_tramo_activo",
    )

    quinteto_actual = st.multiselect(
        f"Elige los 5 jugadores en pista para {tramo_sel}:",
        options=plantilla,
        default=[j for j in st.session_state.tagger_quintets.get(tramo_sel, []) if j in plantilla],
        max_selections=5,
        key=f"ms_quinteto_{tramo_sel}",
    )
    st.session_state.tagger_quintets[tramo_sel] = quinteto_actual

    # Resumen compacto de sextos acumulados por jugador
    resumen_sextos = []
    for _, row in df_ind.iterrows():
        s = row["SEXTOS"]
        icono = "🟢" if 2.0 <= s <= 4.0 else ("🟡" if s > 0 else "⚪")
        resumen_sextos.append(f"{icono} **{row['JUGADOR']}**: {s:.1f}")
    st.caption(" · ".join(resumen_sextos))

    if len(quinteto_actual) != 5:
        st.warning(f"⚠️ Selecciona exactamente 5 jugadores en **{tramo_sel}** para que `PTS_FAV` y `PTS_REC` se repartan correctamente.")

    st.markdown("---")

    # --- BLOQUE 3: BOTONERA DUAL DE CAPTURA ---
    st.subheader("2️⃣ Registro de Acciones (Artchivo + Rival)")

    def registrar_evento(equipo, jugador, accion, etiqueta="Normal"):
        st.session_state.tagger_eventos.append(
            {
                "tramo": tramo_sel,
                "equipo": equipo,
                "jugador": jugador,
                "accion": accion,
                "etiqueta": etiqueta,
            }
        )
        st.session_state.reset_etiqueta = True

    col_art, col_riv = st.columns([1.6, 1])

    with col_art:
        st.markdown("**🔵 ARTCHIVO (Jugadores activos en pista)**")
        if quinteto_actual:
            if st.session_state.tagger_jugador_activo not in quinteto_actual:
                st.session_state.tagger_jugador_activo = quinteto_actual[0]
            jug_sel = st.radio(
                "Jugador de la acción:",
                quinteto_actual,
                horizontal=True,
                key="tagger_jugador_activo",
            )
        else:
            jug_sel = st.selectbox("Jugador (sin quinteto completo):", plantilla)

        if st.session_state.get("reset_etiqueta", False):
            st.session_state.sel_etiqueta_form = "Normal"
            st.session_state.reset_etiqueta = False

        etiqueta_form = st.selectbox(
            "Matiz táctico/formativo (opcional):",
            ["Normal", "Buena selección tiro", "Mala selección tiro", "Ayuda tardía", "Buen corte / sin balón", "Pérdida presión"],
            key="sel_etiqueta_form",
        )

        # Fila de tiros
        b1, b2, b3, b4, b5, b6 = st.columns(6)
        if b1.button("2P+ ✅", use_container_width=True):
            registrar_evento("ARTCHIVO", jug_sel, "2P+", etiqueta_form); st.rerun()
        if b2.button("2P- ❌", use_container_width=True):
            registrar_evento("ARTCHIVO", jug_sel, "2P-", etiqueta_form); st.rerun()
        if b3.button("3P+ ✅", use_container_width=True):
            registrar_evento("ARTCHIVO", jug_sel, "3P+", etiqueta_form); st.rerun()
        if b4.button("3P- ❌", use_container_width=True):
            registrar_evento("ARTCHIVO", jug_sel, "3P-", etiqueta_form); st.rerun()
        if b5.button("TL+ ✅", use_container_width=True):
            registrar_evento("ARTCHIVO", jug_sel, "TL+", etiqueta_form); st.rerun()
        if b6.button("TL- ❌", use_container_width=True):
            registrar_evento("ARTCHIVO", jug_sel, "TL-", etiqueta_form); st.rerun()

        # Fila de rebotes, pase y pérdidas
        c_a, c_b, c_c, c_d, c_e = st.columns(5)
        if c_a.button("RO", use_container_width=True):
            registrar_evento("ARTCHIVO", jug_sel, "OR", etiqueta_form); st.rerun()
        if c_b.button("RD", use_container_width=True):
            registrar_evento("ARTCHIVO", jug_sel, "DR", etiqueta_form); st.rerun()
        if c_c.button("AS", use_container_width=True):
            registrar_evento("ARTCHIVO", jug_sel, "AS", etiqueta_form); st.rerun()
        if c_d.button("REC", use_container_width=True):
            registrar_evento("ARTCHIVO", jug_sel, "ST", etiqueta_form); st.rerun()
        if c_e.button("PER", use_container_width=True):
            registrar_evento("ARTCHIVO", jug_sel, "TO", etiqueta_form); st.rerun()

        # Fila de tapones y faltas
        f_a, f_b, f_c, f_d = st.columns(4)
        if f_a.button("TAP Favor", use_container_width=True):
            registrar_evento("ARTCHIVO", jug_sel, "TAP_F", etiqueta_form); st.rerun()
        if f_b.button("TAP Contra", use_container_width=True):
            registrar_evento("ARTCHIVO", jug_sel, "TAP_C", etiqueta_form); st.rerun()
        if f_c.button("Falta Com (FC)", use_container_width=True):
            registrar_evento("ARTCHIVO", jug_sel, "FC", etiqueta_form); st.rerun()
        if f_d.button("Falta Rec (FR)", use_container_width=True):
            registrar_evento("ARTCHIVO", jug_sel, "FR", etiqueta_form); st.rerun()

        # Botones tácticos colectivos de Artchivo
        st.caption("Eventos tácticos colectivos Artchivo:")
        t1, t2, t3, t4 = st.columns(4)
        if t1.button("⚡ Contra Reb", use_container_width=True):
            registrar_evento("ARTCHIVO", "EQUIPO", "CONTRA_REB"); st.rerun()
        if t2.button("⚡ Contra Pér", use_container_width=True):
            registrar_evento("ARTCHIVO", "EQUIPO", "CONTRA_PER"); st.rerun()
        if t3.button("🛡️ Presión Ext", use_container_width=True):
            registrar_evento("ARTCHIVO", "EQUIPO", "PRESION_EXT"); st.rerun()
        if t4.button("🛡️ Presión FR", use_container_width=True):
            registrar_evento("ARTCHIVO", "EQUIPO", "PRESION_FR"); st.rerun()

    with col_riv:
        st.markdown(f"**🔴 {st.session_state.tagger_meta['rival'].upper() or 'RIVAL'} (Equipo)**")
        r1, r2, r3 = st.columns(3)
        if r1.button("Rival 2P+ ✅", use_container_width=True):
            registrar_evento("RIVAL", "RIVAL", "2P+"); st.rerun()
        if r2.button("Rival 3P+ ✅", use_container_width=True):
            registrar_evento("RIVAL", "RIVAL", "3P+"); st.rerun()
        if r3.button("Rival TL+ ✅", use_container_width=True):
            registrar_evento("RIVAL", "RIVAL", "TL+"); st.rerun()

        r4, r5, r6 = st.columns(3)
        if r4.button("Rival 2P- ❌", use_container_width=True):
            registrar_evento("RIVAL", "RIVAL", "2P-"); st.rerun()
        if r5.button("Rival 3P- ❌", use_container_width=True):
            registrar_evento("RIVAL", "RIVAL", "3P-"); st.rerun()
        if r6.button("Rival TL- ❌", use_container_width=True):
            registrar_evento("RIVAL", "RIVAL", "TL-"); st.rerun()

        r7, r8, r9, r10 = st.columns(4)
        if r7.button("Riv RO", use_container_width=True):
            registrar_evento("RIVAL", "RIVAL", "OR"); st.rerun()
        if r8.button("Riv RD", use_container_width=True):
            registrar_evento("RIVAL", "RIVAL", "DR"); st.rerun()
        if r9.button("Riv PER", use_container_width=True):
            registrar_evento("RIVAL", "RIVAL", "TO"); st.rerun()
        if r10.button("Riv FC", use_container_width=True):
            registrar_evento("RIVAL", "RIVAL", "FC"); st.rerun()

        st.markdown("---")
        if st.button("↩️ Deshacer última acción", use_container_width=True, disabled=len(st.session_state.tagger_eventos) == 0):
            st.session_state.tagger_eventos.pop()
            st.rerun()

        if st.session_state.tagger_eventos:
            ultimas = st.session_state.tagger_eventos[-5:][::-1]
            st.caption("Últimas 5 acciones:")
            for u in ultimas:
                st.text(f"[{u['tramo']}] {u['equipo']}: {u['jugador']} -> {u['accion']} ({u['etiqueta']})")

    st.markdown("---")

    # --- BLOQUE 4: MARCADOR DE CLIPS DE VÍDEO (10-12 SEGUNDOS) ---
    with st.expander("🎬 Marcar Clips de Vídeo (10-12 segundos) y Script de Recorte", expanded=False):
        vc1, vc2, vc3, vc4 = st.columns([1, 1.5, 1.5, 2])
        tiempo_vid = vc1.text_input("Minuto vídeo (MM:SS)", placeholder="14:25")
        concepto_vid = vc2.selectbox(
            "Concepto táctico",
            ["Ayudas tardías", "Salida de presión", "Contraataque", "Selección de tiro", "Rebote / Cierre", "Juego sin balón", "Otro"]
        )
        jug_vid = vc3.selectbox("Protagonista", ["EQUIPO"] + plantilla)
        nota_vid = vc4.text_input("Nota para entrenadores", placeholder="Llega tarde desde lado débil...")

        if st.button("➕ Añadir Clip de 12 segundos (-4s / +8s)"):
            seg = convertir_tiempo_a_segundos(tiempo_vid)
            if seg is None:
                st.error("Escribe el tiempo en formato MM:SS (ejemplo: 14:25).")
            else:
                st.session_state.tagger_clips.append(
                    {
                        "JORNADA": st.session_state.tagger_meta["jornada"],
                        "RIVAL": st.session_state.tagger_meta["rival"].upper(),
                        "TRAMO": tramo_sel,
                        "JUGADOR": jug_vid,
                        "CONCEPTO": concepto_vid,
                        "INICIO_CLIP": formatear_hhmmss(seg - 4),
                        "FIN_CLIP": formatear_hhmmss(seg + 8),
                        "NOTA_ENTRENADOR": nota_vid,
                        "URL_VIDEO": "",
                    }
                )
                st.success(f"Clip guardado ({formatear_hhmmss(seg - 4)} -> {formatear_hhmmss(seg + 8)}).")

        if st.session_state.tagger_clips:
            st.dataframe(pd.DataFrame(st.session_state.tagger_clips), use_container_width=True)
            bat_bytes = generar_bat_ffmpeg(st.session_state.tagger_meta, st.session_state.tagger_clips)
            st.download_button(
                "🎞️ Descargar recortador automático (.bat para FFmpeg)",
                data=bat_bytes,
                file_name=f"cortar_clips_J{st.session_state.tagger_meta['jornada']}.bat",
                mime="text/plain",
            )

    # --- BLOQUE 5: CORTAFUEGOS DE AUDITORÍA Y EXPORTACIÓN A BORRADOR ---
    st.subheader("3️⃣ Auditoría Matemática (Cortafuegos) y Exportación")

    suma_pts_ind = int(df_ind["PTS"].sum())
    suma_sextos = round(float(df_ind["SEXTOS"].sum()), 2)
    suma_pts_fav = int(df_ind["PTS_FAV"].sum())
    suma_pts_rec = int(df_ind["PTS_REC"].sum())

    check_pts = (suma_pts_ind == eq_art["PTS"])
    check_sextos = (suma_sextos == 30.0)
    check_fav = (suma_pts_fav == 5 * eq_art["PTS"])
    check_rec = (suma_pts_rec == 5 * eq_riv["PTS"])

    a1, a2, a3, a4 = st.columns(4)
    a1.markdown(f"{'✅' if check_pts else '❌'} **Puntos:** {suma_pts_ind} / {eq_art['PTS']}")
    a2.markdown(f"{'✅' if check_sextos else '❌'} **Sextos:** {suma_sextos:.1f} / 30.0")
    a3.markdown(f"{'✅' if check_fav else '❌'} **PTS_FAV:** {suma_pts_fav} / {5 * eq_art['PTS']}")
    a4.markdown(f"{'✅' if check_rec else '❌'} **PTS_REC:** {suma_pts_rec} / {5 * eq_riv['PTS']}")

    if not (check_pts and check_sextos and check_fav and check_rec):
        st.info(
            "💡 El semáforo se pondrá completamente en verde en cuanto los 6 sextos tengan sus 5 jugadores asignados "
            "(sumando 30,0 sextos) y todas las canastas se hayan registrado con quinteto completo."
        )

    st.markdown("**📊 Resumen Colectivo (Artchivo vs. Rival — hoja `GAMES`)**")
    rival_nombre = st.session_state.tagger_meta["rival"].strip().upper() or "RIVAL"
    df_comp_eq = pd.DataFrame([
        {"EQUIPO": "ARTCHIVO", **eq_art},
        {"EQUIPO": rival_nombre, **eq_riv},
    ])
    st.dataframe(df_comp_eq, use_container_width=True, hide_index=True)

    st.markdown("**👤 Estadística Individual (hoja `REGISTRO_PARTIDOS`)**")
    st.dataframe(df_ind, use_container_width=True, hide_index=True)

    excel_borrador = generar_excel_borrador(
        st.session_state.tagger_meta,
        df_ind,
        eq_art,
        eq_riv,
        st.session_state.tagger_eventos,
        st.session_state.tagger_clips,
    )
    st.download_button(
        label="📥 Descargar Borrador Aislado (.xlsx) para revisar antes de pasar al Excel Maestro",
        data=excel_borrador,
        file_name=f"borrador_J{st.session_state.tagger_meta['jornada']}_{st.session_state.tagger_meta['rival']}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )