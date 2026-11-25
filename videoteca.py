import streamlit as st
import pandas as pd
import os
import re
from datetime import time, timedelta

EXCEL_MAESTRO = "alevin_tabla_estadistica_v2.xlsx"


def tiempo_a_segundos(valor):
    """Convierte 'MM:SS', 'HH:MM:SS' o formatos de hora de Excel a segundos enteros."""
    if pd.isna(valor) or valor == "":
        return 0
    if isinstance(valor, time):
        return valor.hour * 3600 + valor.minute * 60 + valor.second
    if isinstance(valor, timedelta):
        return int(valor.total_seconds())

    texto = str(valor).strip()
    partes = [p for p in texto.split(":") if p.isdigit()]
    if len(partes) == 2:
        return int(partes[0]) * 60 + int(partes[1])
    if len(partes) == 3:
        return int(partes[0]) * 3600 + int(partes[1]) * 60 + int(partes[2])
    return 0


def segundos_a_mmss(segundos):
    segundos = max(0, int(segundos))
    m = segundos // 60
    s = segundos % 60
    return f"{m:02d}:{s:02d}"


def url_youtube_con_segundo(url, segundos):
    """Devuelve el enlace de YouTube apuntando al segundo exacto para abrir en móvil."""
    url = str(url).strip()
    if not url:
        return ""
    url_limpia = re.sub(r"([?&])t=\d+s?", "", url).rstrip("?&")
    separador = "&" if "?" in url_limpia else "?"
    return f"{url_limpia}{separador}t={int(segundos)}s"


def cargar_clips_desde_excel(fuente):
    """Lee la hoja VIDEOS desde el Excel maestro o desde un borrador subido."""
    try:
        xls = pd.ExcelFile(fuente)
        if "VIDEOS" not in xls.sheet_names:
            return pd.DataFrame()
        df = pd.read_excel(xls, sheet_name="VIDEOS")
        return df.dropna(how="all")
    except Exception:
        return pd.DataFrame()


def mostrar_videoteca():
    st.header("🎬 Videoteca Táctica del Cuerpo Técnico")
    st.caption(
        "Filtra acciones por jugador, concepto o jornada. El reproductor salta directamente "
        "al segundo exacto del partido en YouTube."
    )

    df_videos = cargar_clips_desde_excel(EXCEL_MAESTRO)

    # Opción extra: previsualizar un borrador .xlsx antes de volcarlo al Excel maestro
    with st.expander("📂 Cargar o combinar un borrador de partido (.xlsx)", expanded=df_videos.empty):
        archivo_borrador = st.file_uploader(
            "Sube un borrador exportado desde la Calculadora para revisar sus clips:",
            type=["xlsx"],
            key="uploader_videoteca_borrador",
        )
        if archivo_borrador is not None:
            df_borr = cargar_clips_desde_excel(archivo_borrador)
            if not df_borr.empty:
                df_videos = pd.concat([df_videos, df_borr], ignore_index=True)
                st.success(f"Se han cargado {len(df_borr)} clips desde el borrador.")

    if df_videos.empty:
        st.info(
            "Todavía no hay clips registrados en la hoja `VIDEOS` de `alevin_tabla_estadistica_v2.xlsx`. "
            "Marca jugadas en la Calculadora Post-Partido y copia la pestaña `VIDEOS` a tu Excel maestro "
            "(o sube aquí un borrador `.xlsx` para verlo al instante)."
        )
        return

    # Normalizar columnas esperadas
    for col in ["JORNADA", "RIVAL", "TRAMO", "JUGADOR", "CONCEPTO", "INICIO_CLIP", "NOTA_ENTRENADOR", "URL_VIDEO"]:
        if col not in df_videos.columns:
            df_videos[col] = ""

    df_videos["JORNADA_STR"] = df_videos["JORNADA"].fillna("").astype(str).str.replace(r"\.0$", "", regex=True)
    df_videos["RIVAL"] = df_videos["RIVAL"].fillna("RIVAL").astype(str).str.strip().str.upper()
    df_videos["JUGADOR"] = df_videos["JUGADOR"].fillna("EQUIPO").astype(str).str.strip().str.upper()
    df_videos["CONCEPTO"] = df_videos["CONCEPTO"].fillna("General").astype(str).str.strip()
    df_videos["PARTIDO_LABEL"] = "J" + df_videos["JORNADA_STR"] + " vs " + df_videos["RIVAL"]

    # --- FILTROS SUPERIORES ---
    f1, f2, f3 = st.columns(3)
    jugadores_disp = ["Todos"] + sorted([j for j in df_videos["JUGADOR"].unique() if j])
    conceptos_disp = ["Todos"] + sorted([c for c in df_videos["CONCEPTO"].unique() if c])
    partidos_disp = ["Todos"] + list(dict.fromkeys(df_videos["PARTIDO_LABEL"].tolist()))

    sel_jugador = f1.selectbox("👤 Filtrar por Jugador:", jugadores_disp)
    sel_concepto = f2.selectbox("📋 Concepto Táctico:", conceptos_disp)
    sel_partido = f3.selectbox("🏀 Jornada / Rival:", partidos_disp)

    df_filtrado = df_videos.copy()
    if sel_jugador != "Todos":
        df_filtrado = df_filtrado[df_filtrado["JUGADOR"] == sel_jugador]
    if sel_concepto != "Todos":
        df_filtrado = df_filtrado[df_filtrado["CONCEPTO"] == sel_concepto]
    if sel_partido != "Todos":
        df_filtrado = df_filtrado[df_filtrado["PARTIDO_LABEL"] == sel_partido]

    st.markdown(f"**Mostrando {len(df_filtrado)} de {len(df_videos)} clips tácticos**")
    st.markdown("---")

    if df_filtrado.empty:
        st.warning("No hay clips que coincidan con esa combinación de filtros.")
        return

    # --- LISTADO DE CLIPS CON REPRODUCTOR YOUTUBE AL SEGUNDO EXACTO ---
    for idx, row in df_filtrado.iterrows():
        seg_inicio = tiempo_a_segundos(row["INICIO_CLIP"])
        minuto_legible = segundos_a_mmss(seg_inicio)
        url_base = str(row["URL_VIDEO"]).strip() if pd.notna(row["URL_VIDEO"]) else ""
        url_directa = url_youtube_con_segundo(url_base, seg_inicio)
        nota = str(row["NOTA_ENTRENADOR"]).strip() if pd.notna(row["NOTA_ENTRENADOR"]) else ""

        with st.container(border=True):
            c_info, c_vid = st.columns([1.1, 1.4])

            with c_info:
                st.markdown(f"### {row['PARTIDO_LABEL']} · `{row['TRAMO']}`")
                st.markdown(f"**Protagonista:** `{row['JUGADOR']}` &nbsp;|&nbsp; **Concepto:** `{row['CONCEPTO']}`")
                st.markdown(f"⏱️ **Arranca en el minuto:** `{minuto_legible}`")

                if nota:
                    st.info(f"💬 **Nota técnica:** {nota}")

                if url_directa:
                    st.link_button("▶️ Abrir en YouTube en este segundo", url_directa, use_container_width=True)
                    mensaje_ws = f"{row['PARTIDO_LABEL']} (Min {minuto_legible}) - {row['JUGADOR']} [{row['CONCEPTO']}]: {nota} -> {url_directa}"
                    st.caption("Texto rápido para WhatsApp:")
                    st.code(mensaje_ws, language=None)
                else:
                    st.warning("Falta pegar el enlace de YouTube en la columna `URL_VIDEO` de esta fila.")

            with c_vid:
                if url_base:
                    st.video(url_base, start_time=seg_inicio)
                else:
                    st.markdown("*Sin vídeo enlazado todavía.*")