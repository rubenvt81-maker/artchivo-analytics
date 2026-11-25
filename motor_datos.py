import pandas as pd
import numpy as np


def calcular_acumulado_jugadores(jugados_df):
    """Calcula el acumulado ponderado por jugador a partir de las actuaciones filtradas."""
    if jugados_df.empty:
        return pd.DataFrame()

    acum = jugados_df.groupby(["NUM", "JUGADOR"], as_index=False).agg(
        PART=("JUEGA", "count"),
        SEXTOS=("SEXTOS", "sum"),
        PTS=("PTS", "sum"),
        PM2=("2PM", "sum"),
        PA2=("2PA", "sum"),
        PM3=("3PM", "sum"),
        PA3=("3PA", "sum"),
        FGM=("FGM", "sum"),
        FGA=("FGA", "sum"),
        FTM=("FTM", "sum"),
        FTA=("FTA", "sum"),
        RO=("RO", "sum"),
        RD=("RD", "sum"),
        REB=("REB", "sum"),
        AS=("AS", "sum"),
        REC=("STL", "sum"),
        PER=("TO", "sum"),
        TAP_F=("BLKF", "sum"),
        TAP_C=("BLKC", "sum"),
        FC=("FC", "sum"),
        FR=("FR", "sum"),
        VAL=("VAL", "sum"),
        PTS_FAV=("PTS_FAV", "sum"),
        PTS_REC=("PTS_REC", "sum"),
        POS_ON=("POS_ON", "sum"),
        OR_EQ_ON=("OR_EQ_ON", "sum"),
    )

    acum["%2P"] = np.where(acum["PA2"] > 0, ((acum["PM2"] / acum["PA2"]) * 100).round(1), 0.0)
    acum["%3P"] = np.where(acum["PA3"] > 0, ((acum["PM3"] / acum["PA3"]) * 100).round(1), 0.0)
    acum["%TL"] = np.where(acum["FTA"] > 0, ((acum["FTM"] / acum["FTA"]) * 100).round(1), 0.0)
    acum["%eFG"] = np.where(acum["FGA"] > 0, (((acum["FGM"] + 0.5 * acum["PM3"]) / acum["FGA"]) * 100).round(1), 0.0)
    acum["TS%"] = np.where(
        (acum["FGA"] + 0.44 * acum["FTA"]) > 0,
        ((acum["PTS"] / (2 * (acum["FGA"] + 0.44 * acum["FTA"]))) * 100).round(1),
        0.0,
    )
    acum["POS"] = (acum["FGA"] + 0.44 * acum["FTA"] - acum["RO"] + acum["PER"]).clip(lower=0).round(1)
    acum["OER"] = np.where(acum["POS"] > 0, (acum["PTS"] / acum["POS"]).round(2), 0.0)
    acum["OER_ON"] = np.where(acum["POS_ON"] > 0, (acum["PTS_FAV"] / acum["POS_ON"]).round(2), 0.0)
    acum["DER_ON"] = np.where(acum["POS_ON"] > 0, (acum["PTS_REC"] / acum["POS_ON"]).round(2), 0.0)
    acum["NET_ON"] = (acum["OER_ON"] - acum["DER_ON"]).round(2)
    acum["%USO"] = np.where(acum["POS_ON"] > 0, ((acum["POS"] / acum["POS_ON"]) * 100).round(1), 0.0)
    acum["%STOPS"] = np.where(
        acum["POS_ON"] > 0,
        (((acum["RD"] + acum["REC"] + acum["TAP_F"]) / acum["POS_ON"]) * 100).round(1),
        0.0,
    )
    acum["%OREB"] = np.where(acum["OR_EQ_ON"] > 0, ((acum["RO"] / acum["OR_EQ_ON"]) * 100).round(1), 0.0)
    acum["AS/TO"] = np.where(acum["PER"] > 0, (acum["AS"] / acum["PER"]).round(2), acum["AS"].astype(float))
    acum["RATIO_PER/USO"] = np.where(
        (acum["POS"] > 0) & (acum["%USO"] > 0),
        (((acum["PER"] / acum["POS"]) * 100) / acum["%USO"]).round(2),
        0.0,
    )
    acum["PTS/PART"] = (acum["PTS"] / acum["PART"]).round(1)
    acum["REB/PART"] = (acum["REB"] / acum["PART"]).round(1)
    acum["AS/PART"] = (acum["AS"] / acum["PART"]).round(1)
    acum["PTS/SEX"] = np.where(acum["SEXTOS"] > 0, (acum["PTS"] / acum["SEXTOS"]).round(2), 0.0)
    acum["VAL/SEX"] = np.where(acum["SEXTOS"] > 0, (acum["VAL"] / acum["SEXTOS"]).round(2), 0.0)

    return acum


def cargar_y_procesar_excel(ruta_o_archivo):
    """
    Lee las pestañas 'GAMES' y 'REGISTRO_PARTIDOS' y devuelve 4 tablas listas:
    1. df_games: Todos los partidos de la competición.
    2. resumen_jornadas: Resumen partido a partido de CB Artchivo.
    3. jugados: Las actuaciones individuales con sus métricas por partido.
    4. acum: El acumulado ponderado de los jugadores.
    """
    xls = pd.ExcelFile(ruta_o_archivo)
    df_games = pd.read_excel(xls, sheet_name="GAMES")
    df_reg = pd.read_excel(xls, sheet_name="REGISTRO_PARTIDOS")

    # 1. Limpiar GAMES y calcular métricas de equipo
    df_games = df_games.dropna(subset=["NUM GAME", "OFFENSE"]).copy()
    df_games["NUM GAME"] = df_games["NUM GAME"].astype(int)

    fga_eq = df_games["2PA"] + df_games["3PA"]
    df_games["PTS_CALC"] = (df_games["2PM"] * 2 + df_games["3PM"] * 3 + df_games["FTM"]).astype(int)
    df_games["POS_CALC"] = (fga_eq + 0.44 * df_games["FTA"] - df_games["OR"] + df_games["TO"]).round(2)
    df_games["OER_CALC"] = np.where(df_games["POS_CALC"] > 0, (df_games["PTS_CALC"] / df_games["POS_CALC"]).round(2), 0.0)
    df_games["eFG_CALC"] = np.where(fga_eq > 0, (((df_games["2PM"] + 1.5 * df_games["3PM"]) / fga_eq) * 100).round(1), 0.0)
    df_games["CONTR_CALC"] = df_games["CONTRA_REB"].fillna(0) + df_games["CONTRA_PER"].fillna(0)
    df_games["PRESION_CALC"] = df_games["PRESION_EXT"].fillna(0) + df_games["PRESION_FR"].fillna(0)

    art_off = df_games[df_games["OFFENSE"] == "ARTCHIVO"].set_index("NUM GAME")
    art_def = df_games[df_games["DEFENSE"] == "ARTCHIVO"].set_index("NUM GAME")

    resumen_jornadas = pd.DataFrame({
        "JORNADA": art_off.index,
        "RIVAL": art_off["DEFENSE"].values,
        "LOCALIA": art_off["HOME/\nROAD"].values,
        "RESULTADO": art_off["WIN/\nLOST"].values,
        "PTS_FAV": art_off["PTS_CALC"].values,
        "PTS_CON": art_def["PTS_CALC"].reindex(art_off.index).values,
        "POS_EQ": art_off["POS_CALC"].values,
        "OER_EQ": art_off["OER_CALC"].values,
        "DER_EQ": art_def["OER_CALC"].reindex(art_off.index).values,
        "eFG_EQ": art_off["eFG_CALC"].values,
        "RO_EQ": art_off["OR"].values,
        "RD_EQ": art_off["DR"].values,
        "AS_EQ": art_off["AS"].values,
        "REC_EQ": art_off["ST"].values,
        "PER_EQ": art_off["TO"].values,
        "CONTRA_TOT": art_off["CONTR_CALC"].values,
        "PRESION_TOT": art_off["PRESION_CALC"].values,
    })
    resumen_jornadas["DIF_PTS"] = resumen_jornadas["PTS_FAV"] - resumen_jornadas["PTS_CON"]
    resumen_jornadas["NET_EQ"] = (resumen_jornadas["OER_EQ"] - resumen_jornadas["DER_EQ"]).round(2)

    # 2. Limpiar REGISTRO_PARTIDOS y calcular métricas por partido
    df_reg = df_reg.dropna(subset=["JORNADA", "JUGADOR"]).copy()
    df_reg["JORNADA"] = df_reg["JORNADA"].astype(int)
    df_reg["NUM"] = df_reg["NUM"].astype(int)

    jugados = df_reg[df_reg["JUEGA"].astype(str).str.upper() == "SI"].copy()

    mapa_pos_eq = resumen_jornadas.set_index("JORNADA")["POS_EQ"]
    mapa_ro_eq = resumen_jornadas.set_index("JORNADA")["RO_EQ"]

    jugados["FGM"] = jugados["2PM"] + jugados["3PM"]
    jugados["FGA"] = jugados["2PA"] + jugados["3PA"]
    jugados["REB"] = jugados["RO"] + jugados["RD"]
    jugados["VAL"] = (
        (jugados["PTS"] + jugados["REB"] + jugados["AS"] + jugados["STL"] + jugados["BLKF"] + jugados["FR"])
        - ((jugados["FGA"] - jugados["FGM"]) + (jugados["FTA"] - jugados["FTM"]) + jugados["TO"] + jugados["BLKC"] + jugados["FC"])
    )

    jugados["POS"] = (jugados["FGA"] + 0.44 * jugados["FTA"] - jugados["RO"] + jugados["TO"]).clip(lower=0).round(1)
    jugados["POS_ON"] = (jugados["JORNADA"].map(mapa_pos_eq) * (jugados["SEXTOS"] / 6.0)).round(1)
    jugados["OR_EQ_ON"] = (jugados["JORNADA"].map(mapa_ro_eq) * (jugados["SEXTOS"] / 6.0)).round(1)
    jugados["OER"] = np.where(jugados["POS"] > 0, (jugados["PTS"] / jugados["POS"]).round(2), 0.0)
    jugados["TS%"] = np.where(
        (jugados["FGA"] + 0.44 * jugados["FTA"]) > 0,
        ((jugados["PTS"] / (2 * (jugados["FGA"] + 0.44 * jugados["FTA"]))) * 100).round(1),
        0.0,
    )
    jugados["OER_ON"] = np.where(jugados["POS_ON"] > 0, (jugados["PTS_FAV"] / jugados["POS_ON"]).round(2), 0.0)
    jugados["DER_ON"] = np.where(jugados["POS_ON"] > 0, (jugados["PTS_REC"] / jugados["POS_ON"]).round(2), 0.0)
    jugados["NET_ON"] = (jugados["OER_ON"] - jugados["DER_ON"]).round(2)
    jugados["%USO"] = np.where(jugados["POS_ON"] > 0, ((jugados["POS"] / jugados["POS_ON"]) * 100).round(1), 0.0)
    jugados["%STOPS"] = np.where(
        jugados["POS_ON"] > 0,
        (((jugados["RD"] + jugados["STL"] + jugados["BLKF"]) / jugados["POS_ON"]) * 100).round(1),
        0.0,
    )

    # 3. Acumulado ponderado inicial
    acum = calcular_acumulado_jugadores(jugados)

    return df_games, resumen_jornadas, jugados, acum