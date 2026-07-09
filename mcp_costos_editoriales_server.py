"""
Servidor MCP local para el PoC editorial.

Publica tools de solo lectura sobre SQLite para que LangChain las consuma
vía MCP, sin exponer SQL libre al modelo.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sqlite3
import uuid
from pathlib import Path

import pandas as pd
from fastmcp import FastMCP


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "Recursos y Contexto"
if not DATA_DIR.exists():
    DATA_DIR = ROOT
if not (DATA_DIR / "gastos_ficticios_poc.csv").exists():
    DATA_DIR = ROOT / "Recursos y Contexto"
CSV_PATH = DATA_DIR / "gastos_ficticios_poc.csv"
DB_PATH = DATA_DIR / "poc_gastos.sqlite"

mcp = FastMCP(
    name="PoC Costos Editoriales MCP",
    instructions=(
        "Servidor MCP para análisis editorial. "
        "Cada tool representa una pregunta de negocio concreta. "
        "Las tools de cálculo escriben automáticamente en logs de inferencia."
    ),
)


def abrir_db() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def a_json(df: pd.DataFrame) -> str:
    return df.to_json(orient="records", force_ascii=False)


def bootstrap_db() -> None:
    df = pd.read_csv(CSV_PATH)
    with abrir_db() as conn:
        df.to_sql("gastos_proyecto", conn, if_exists="replace", index=False)
        conn.execute("DROP VIEW IF EXISTS view_proyectos_resumen")
        conn.execute(
            """
            CREATE VIEW view_proyectos_resumen AS
            SELECT
                idproyecto,
                claveproducto,
                nombreproducto,
                fechaproyecto,
                COUNT(*) AS cantidad_gastos,
                ROUND(SUM(monto_gasto), 2) AS total_gastos,
                ROUND(AVG(monto_gasto), 2) AS gasto_promedio,
                MIN(fecha_gasto) AS primera_fecha_gasto,
                MAX(fecha_gasto) AS ultima_fecha_gasto
            FROM gastos_proyecto
            GROUP BY idproyecto, claveproducto, nombreproducto, fechaproyecto
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gastos_idproyecto ON gastos_proyecto(idproyecto)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gastos_nombreproducto ON gastos_proyecto(nombreproducto)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gastos_fechaproyecto ON gastos_proyecto(fechaproyecto)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gastos_tipo ON gastos_proyecto(tipo_gasto)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS logs_inferencia (
                id_log TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                idproyecto TEXT NOT NULL,
                modelo TEXT,
                input_usuario TEXT,
                output_agente TEXT,
                propuesta_costo REAL,
                propuesta_precio REAL,
                total_gastos REAL,
                score_global TEXT,
                campos_baja_confianza TEXT,
                latencia_ms REAL
            )
            """
        )


def ejecutar_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    with abrir_db() as conn:
        return pd.read_sql_query(sql, conn, params=params)


@mcp.tool()
def buscar_proyectos(texto: str, limite: int = 10) -> str:
    """
    Busca proyectos por idproyecto, claveproducto, nombreproducto, proveedor o tipo de gasto.

    Úsala cuando el usuario no recuerde el id exacto del proyecto o quiera encontrar
    proyectos relacionados con un término parcial.
    """
    limite = max(1, min(int(limite), 25))
    patron = f"%{texto.strip()}%"
    df = ejecutar_df(
        """
        SELECT
            idproyecto,
            claveproducto,
            nombreproducto,
            fechaproyecto,
            COUNT(*) AS cantidad_gastos,
            ROUND(SUM(monto_gasto), 2) AS total_gastos
        FROM gastos_proyecto
        WHERE idproyecto LIKE ?
           OR claveproducto LIKE ?
           OR nombreproducto LIKE ?
           OR proveedor LIKE ?
           OR tipo_gasto LIKE ?
        GROUP BY idproyecto, claveproducto, nombreproducto, fechaproyecto
        ORDER BY total_gastos DESC, fechaproyecto DESC
        LIMIT ?
        """,
        (patron, patron, patron, patron, patron, limite),
    )
    return a_json(df)


@mcp.tool()
def listar_proyectos_con_totales(limite: int = 10) -> str:
    """
    Devuelve un listado de proyectos con cantidad de gastos y gasto total.

    Úsala para ver rápidamente qué proyectos concentran más costo.
    """
    limite = max(1, min(int(limite), 50))
    df = ejecutar_df(
        """
        SELECT
            idproyecto,
            claveproducto,
            nombreproducto,
            fechaproyecto,
            COUNT(*) AS cantidad_gastos,
            ROUND(SUM(monto_gasto), 2) AS total_gastos,
            ROUND(AVG(monto_gasto), 2) AS gasto_promedio
        FROM gastos_proyecto
        GROUP BY idproyecto, claveproducto, nombreproducto, fechaproyecto
        ORDER BY total_gastos DESC, fechaproyecto DESC
        LIMIT ?
        """,
        (limite,),
    )
    return a_json(df)


@mcp.tool()
def top_proyectos_por_gasto(limite: int = 10) -> str:
    """
    Devuelve los proyectos con mayor gasto total.

    Úsala cuando el usuario quiera saber qué proyectos consumen más presupuesto.
    """
    limite = max(1, min(int(limite), 50))
    df = ejecutar_df(
        """
        SELECT
            idproyecto,
            claveproducto,
            nombreproducto,
            fechaproyecto,
            COUNT(*) AS cantidad_gastos,
            ROUND(SUM(monto_gasto), 2) AS total_gastos,
            ROUND(AVG(monto_gasto), 2) AS gasto_promedio
        FROM gastos_proyecto
        GROUP BY idproyecto, claveproducto, nombreproducto, fechaproyecto
        ORDER BY total_gastos DESC, cantidad_gastos DESC
        LIMIT ?
        """,
        (limite,),
    )
    return a_json(df)


@mcp.tool()
def proyectos_recientes(limite: int = 10) -> str:
    """
    Lista los proyectos más recientes según la fecha del proyecto.

    Úsala cuando la pregunta esté orientada a actividad reciente o últimos movimientos.
    """
    limite = max(1, min(int(limite), 25))
    df = ejecutar_df(
        """
        SELECT
            idproyecto,
            claveproducto,
            nombreproducto,
            fechaproyecto,
            COUNT(*) AS cantidad_gastos,
            ROUND(SUM(monto_gasto), 2) AS total_gastos
        FROM gastos_proyecto
        GROUP BY idproyecto, claveproducto, nombreproducto, fechaproyecto
        ORDER BY fechaproyecto DESC, total_gastos DESC
        LIMIT ?
        """,
        (limite,),
    )
    return a_json(df)


@mcp.tool()
def gastos_por_tipo_global(limite: int = 10) -> str:
    """
    Resume el gasto de todos los proyectos agrupado por tipo de gasto.

    Úsala para entender en qué categorías se concentra el presupuesto total.
    """
    limite = max(1, min(int(limite), 25))
    df = ejecutar_df(
        """
        SELECT
            tipo_gasto,
            COUNT(*) AS cantidad_items,
            ROUND(SUM(monto_gasto), 2) AS total_gasto,
            ROUND(AVG(monto_gasto), 2) AS gasto_promedio,
            COUNT(DISTINCT idproyecto) AS proyectos_distintos
        FROM gastos_proyecto
        GROUP BY tipo_gasto
        ORDER BY total_gasto DESC, cantidad_items DESC
        LIMIT ?
        """,
        (limite,),
    )
    return a_json(df)


@mcp.tool()
def gastos_por_proveedor(limite: int = 10) -> str:
    """
    Resume el gasto por proveedor.

    Úsala para identificar proveedores relevantes o concentraciones de gasto.
    """
    limite = max(1, min(int(limite), 25))
    df = ejecutar_df(
        """
        SELECT
            proveedor,
            COUNT(*) AS cantidad_items,
            ROUND(SUM(monto_gasto), 2) AS total_gasto,
            ROUND(AVG(monto_gasto), 2) AS gasto_promedio,
            COUNT(DISTINCT idproyecto) AS proyectos_distintos
        FROM gastos_proyecto
        GROUP BY proveedor
        ORDER BY total_gasto DESC, cantidad_items DESC
        LIMIT ?
        """,
        (limite,),
    )
    return a_json(df)


@mcp.tool()
def resumen_por_estado_registro() -> str:
    """
    Cuenta los registros por estado de registro.

    Úsala como apoyo de calidad o para entender el volumen por estado.
    """
    df = ejecutar_df(
        """
        SELECT
            estado_registro,
            COUNT(*) AS cantidad_registros,
            ROUND(SUM(monto_gasto), 2) AS total_gasto
        FROM gastos_proyecto
        GROUP BY estado_registro
        ORDER BY cantidad_registros DESC, total_gasto DESC
        """
    )
    return a_json(df)


@mcp.tool()
def resumen_proyecto_sql(idproyecto: str) -> str:
    """
    Resume un proyecto editorial con gasto total, fechas y número de gastos.

    Úsala cuando ya tengas el id exacto del proyecto y quieras un resumen ejecutivo.
    """
    resumen = ejecutar_df(
        """
        SELECT
            idproyecto,
            claveproducto,
            nombreproducto,
            fechaproyecto,
            COUNT(*) AS cantidad_gastos,
            ROUND(SUM(monto_gasto), 2) AS total_gastos,
            ROUND(AVG(monto_gasto), 2) AS gasto_promedio,
            MIN(fecha_gasto) AS primera_fecha_gasto,
            MAX(fecha_gasto) AS ultima_fecha_gasto,
            COUNT(DISTINCT proveedor) AS proveedores_distintos,
            COUNT(DISTINCT tipo_gasto) AS tipos_gasto_distintos
        FROM gastos_proyecto
        WHERE idproyecto = ?
        GROUP BY idproyecto, claveproducto, nombreproducto, fechaproyecto
        """,
        (idproyecto,),
    )

    if resumen.empty:
        return json.dumps(
            {
                "idproyecto": idproyecto,
                "encontrado": False,
                "mensaje": "No se encontró el proyecto solicitado.",
            },
            ensure_ascii=False,
        )

    detalle = ejecutar_df(
        """
        SELECT
            tipo_gasto,
            proveedor,
            fecha_gasto,
            descripcion_gasto,
            ROUND(monto_gasto, 2) AS monto_gasto
        FROM gastos_proyecto
        WHERE idproyecto = ?
        ORDER BY fecha_gasto ASC, monto_gasto DESC
        """,
        (idproyecto,),
    )
    desglose = ejecutar_df(
        """
        SELECT
            tipo_gasto,
            COUNT(*) AS cantidad_items,
            ROUND(SUM(monto_gasto), 2) AS total_gasto,
            ROUND(AVG(monto_gasto), 2) AS gasto_promedio
        FROM gastos_proyecto
        WHERE idproyecto = ?
        GROUP BY tipo_gasto
        ORDER BY total_gasto DESC
        """,
        (idproyecto,),
    )

    salida = resumen.iloc[0].to_dict()
    salida["detalle_gastos"] = json.loads(detalle.to_json(orient="records", force_ascii=False))
    salida["desglose_por_tipo"] = json.loads(desglose.to_json(orient="records", force_ascii=False))
    salida["encontrado"] = True
    return json.dumps(salida, ensure_ascii=False)


@mcp.tool()
def resumen_indicadores_globales() -> str:
    """
    Devuelve un resumen ejecutivo de toda la base.

    Úsala cuando el usuario pida una foto general del dataset.
    """
    df = ejecutar_df(
        """
        SELECT
            COUNT(*) AS filas,
            COUNT(DISTINCT idproyecto) AS proyectos_distintos,
            COUNT(DISTINCT proveedor) AS proveedores_distintos,
            COUNT(DISTINCT tipo_gasto) AS tipos_gasto_distintos,
            COUNT(DISTINCT estado_registro) AS estados_distintos,
            ROUND(SUM(monto_gasto), 2) AS total_gasto,
            ROUND(AVG(monto_gasto), 2) AS gasto_promedio,
            ROUND(MIN(monto_gasto), 2) AS gasto_minimo,
            ROUND(MAX(monto_gasto), 2) AS gasto_maximo
        FROM gastos_proyecto
        """
    )
    return a_json(df)


@mcp.tool()
def detalle_gastos_proyecto(idproyecto: str) -> str:
    """
    Devuelve el detalle línea por línea de los gastos de un proyecto.

    Úsala para revisar proveedores, fechas y descripciones exactas.
    """
    df = ejecutar_df(
        """
        SELECT
            idproyecto,
            claveproducto,
            nombreproducto,
            fecha_gasto,
            tipo_gasto,
            proveedor,
            descripcion_gasto,
            ROUND(monto_gasto, 2) AS monto_gasto,
            moneda
        FROM gastos_proyecto
        WHERE idproyecto = ?
        ORDER BY fecha_gasto ASC, monto_gasto DESC
        """,
        (idproyecto,),
    )
    return a_json(df)


@mcp.tool()
def desglose_gastos_por_tipo(idproyecto: str) -> str:
    """
    Agrupa los gastos de un proyecto por tipo de gasto.

    Úsala para entender en qué se concentra el costo del proyecto.
    """
    df = ejecutar_df(
        """
        SELECT
            tipo_gasto,
            COUNT(*) AS cantidad_items,
            ROUND(SUM(monto_gasto), 2) AS total_gasto,
            ROUND(AVG(monto_gasto), 2) AS gasto_promedio
        FROM gastos_proyecto
        WHERE idproyecto = ?
        GROUP BY tipo_gasto
        ORDER BY total_gasto DESC
        """,
        (idproyecto,),
    )
    return a_json(df)


@mcp.tool()
def proyectos_con_cantidad_inconsistente() -> str:
    """
    Detecta proyectos donde la cantidad reportada cambia entre registros.

    Úsala como herramienta de calidad de datos y control de incertidumbre.
    """
    df = ejecutar_df(
        """
        SELECT
            idproyecto,
            claveproducto,
            nombreproducto,
            COUNT(DISTINCT cantidad) AS cantidades_distintas,
            MIN(cantidad) AS cantidad_min,
            MAX(cantidad) AS cantidad_max,
            COUNT(*) AS gastos_registrados
        FROM gastos_proyecto
        GROUP BY idproyecto, claveproducto, nombreproducto
        HAVING COUNT(DISTINCT cantidad) > 1
        ORDER BY cantidades_distintas DESC, gastos_registrados DESC
        """
    )
    return a_json(df)


@mcp.tool()
def calcular_propuesta_costo_precio(
    idproyecto: str,
    margen_utilidad: float = 0.35,
) -> str:
    """
    Calcula la propuesta de costo y precio sugerido para un proyecto editorial.

    Úsala cuando el usuario pida calcular el costo o precio de venta de un proyecto.
    El costo propuesto es el gasto total del proyecto.
    El precio sugerido se calcula aplicando el margen de utilidad al costo total.
    """
    inicio = datetime.datetime.now()

    resumen = ejecutar_df(
        """
        SELECT
            idproyecto,
            claveproducto,
            nombreproducto,
            COUNT(*) AS cantidad_gastos,
            ROUND(SUM(monto_gasto), 2) AS total_gastos
        FROM gastos_proyecto
        WHERE idproyecto = ?
        GROUP BY idproyecto, claveproducto, nombreproducto
        """,
        (idproyecto,),
    )

    if resumen.empty:
        return json.dumps(
            {
                "idproyecto": idproyecto,
                "encontrado": False,
                "mensaje": "No se encontró el proyecto solicitado.",
            },
            ensure_ascii=False,
        )

    fila = resumen.iloc[0]
    idproyecto_val = str(fila["idproyecto"])
    claveproducto_val = int(fila["claveproducto"]) if pd.notna(fila["claveproducto"]) else None
    nombreproducto_val = str(fila["nombreproducto"])
    cantidad_gastos_val = int(fila["cantidad_gastos"])
    total_gastos_val = float(fila["total_gastos"])

    propuesta_costo = round(total_gastos_val, 2)
    propuesta_precio = round(propuesta_costo * (1 + margen_utilidad), 2)

    incosistencias = ejecutar_df(
        """
        SELECT COUNT(*) AS n FROM gastos_proyecto
        WHERE idproyecto = ?
        GROUP BY idproyecto
        HAVING COUNT(DISTINCT cantidad) > 1
        """,
        (idproyecto,),
    )
    hay_inconsistencias = not incosistencias.empty

    score = "alta" if not hay_inconsistencias and propuesta_costo > 0 else "media"
    campos_baja_confianza = []
    if hay_inconsistencias:
        campos_baja_confianza.append("cantidad")
    if total_gastos_val == 0:
        campos_baja_confianza.append("total_gastos")

    salida = {
        "idproyecto": idproyecto_val,
        "claveproducto": claveproducto_val,
        "nombreproducto": nombreproducto_val,
        "propuesta_costo": propuesta_costo,
        "propuesta_precio": propuesta_precio,
        "cantidad_gastos": cantidad_gastos_val,
        "total_gastos": total_gastos_val,
        "margen_utilidad_aplicado": margen_utilidad,
        "score_global": score,
        "campos_baja_confianza": campos_baja_confianza,
        "encontrado": True,
    }

    latencia_ms = round((datetime.datetime.now() - inicio).total_seconds() * 1000, 2)

    id_log = str(uuid.uuid4())
    timestamp = datetime.datetime.now().isoformat()
    try:
        with abrir_db() as conn:
            conn.execute(
                """
                INSERT INTO logs_inferencia
                    (id_log, timestamp, idproyecto, modelo, propuesta_costo, propuesta_precio,
                     total_gastos, score_global, campos_baja_confianza, latencia_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    id_log,
                    timestamp,
                    idproyecto_val,
                    "gemini-2.5-flash",
                    propuesta_costo,
                    propuesta_precio,
                    total_gastos_val,
                    score,
                    json.dumps(campos_baja_confianza, ensure_ascii=False),
                    latencia_ms,
                ),
            )
    except Exception:
        pass

    salida["id_log"] = id_log
    return json.dumps(salida, ensure_ascii=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor MCP local para costos editoriales")
    parser.add_argument("--host", default=os.getenv("MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MCP_PORT", "8010")))
    parser.add_argument("--path", default=os.getenv("MCP_PATH", "/mcp"))
    args = parser.parse_args()

    bootstrap_db()
    mcp.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        path=args.path,
        show_banner=False,
    )
