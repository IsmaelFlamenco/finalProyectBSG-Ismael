# Agente Inteligente de Costos y Precios Editoriales (PoC)

Proof of Concept de un **agente de IA** que apoya al **analista de costos y gastos** de una editorial en la **determinación dinámica del costo y del precio de venta** de un material editorial, a partir de los gastos de producción registrados en la base de datos.

> Proyecto final del curso **AI Project** · Ismael Flamenco

## El problema (Need)

Hoy, al cierre del registro de costos y gastos, el proceso para fijar el precio de un producto editorial es manual:

- Los gastos se revisan en contabilidad y se consolidan **a mano en Excel**.
- Existe **riesgo de omitir gastos** al consolidar.
- El cálculo **puede tardar demasiado** y no queda trazabilidad de cómo se llegó al precio.

**Resultado deseado:** consolidar gastos y obtener una propuesta de costo y precio de venta en menos de 10 minutos, con validación básica, trazabilidad e incertidumbre controlada.

## La solución (Approach)

Un **agente conversacional** construido con **LangChain + Gemini 2.5 Flash** que consume la capa de datos a través de un **servidor MCP local** con tools de negocio concretas (sin SQL libre). El analista pregunta en lenguaje natural y el agente:

1. Interpreta la intención y elige la tool MCP adecuada.
2. Consulta los gastos consolidados en SQLite.
3. Calcula el **costo propuesto** (total de gastos) y el **precio sugerido** (margen de utilidad por defecto: 35 %).
4. Devuelve una salida estructurada con **score de confianza** y **campos de baja confianza**.
5. Registra cada cálculo en la tabla `logs_inferencia` (auditoría y observabilidad).

### Arquitectura por capas

```
CSV de gastos (fuente de prueba)
        │  ingesta idempotente
        ▼
SQLite  ·  tabla gastos_proyecto + view_proyectos_resumen + índices
        │
        ▼
Servidor MCP local (FastMCP · streamable-http)
        ·  13 tools de negocio de solo lectura
        ·  calcular_propuesta_costo_precio escribe en logs_inferencia
        │
        ▼
Agente LangChain (create_agent) + Gemini 2.5 Flash
        ·  system prompt con reglas de negocio y política de "nunca inventar"
        │
        ▼
Notebook / Playground interactivo  ·  trazas en LangSmith
```

### Tools MCP publicadas

| Tool | Pregunta de negocio que responde |
|---|---|
| `buscar_proyectos` | Ubicar proyectos por texto parcial (id, producto, proveedor, tipo de gasto) |
| `listar_proyectos_con_totales` | Listado de proyectos con cantidad y total de gastos |
| `top_proyectos_por_gasto` | Qué proyectos concentran más presupuesto |
| `proyectos_recientes` | Últimos proyectos según fecha |
| `gastos_por_tipo_global` | En qué categorías se concentra el gasto total |
| `gastos_por_proveedor` | Concentración de gasto por proveedor |
| `resumen_por_estado_registro` | Volumen de registros por estado |
| `resumen_proyecto_sql` | Resumen ejecutivo de un proyecto (totales, fechas, desglose) |
| `resumen_indicadores_globales` | Foto general del dataset |
| `detalle_gastos_proyecto` | Detalle línea por línea de los gastos de un proyecto |
| `desglose_gastos_por_tipo` | En qué se concentra el costo de un proyecto |
| `proyectos_con_cantidad_inconsistente` | Control de calidad: cantidades que cambian entre registros |
| `calcular_propuesta_costo_precio` | Propuesta de costo y precio sugerido (con log de inferencia) |

### Salida esperada

```json
{
  "idproyecto": "3232-0001",
  "claveproducto": 3232,
  "nombreproducto": "Crece Feliz - Nueva Edicion",
  "propuesta_costo": 220000.0,
  "propuesta_precio": 297000.0,
  "cantidad_gastos": 6,
  "total_gastos": 220000.0,
  "margen_utilidad_aplicado": 0.35,
  "score_global": "alta",
  "campos_baja_confianza": [],
  "encontrado": true
}
```

### Política de incertidumbre

- Si el dato está claro, se usa.
- Si el proyecto no existe o el dato es inconsistente, **no se inventa**: el campo va como `null` o se reporta en `campos_baja_confianza` (p. ej., cantidades que cambian entre registros).
- Si falta contexto, el agente lo dice con claridad y pide el dato faltante.

## Estructura del repositorio

```
├── PoCTemplateLangChain_completado.ipynb    # Notebook principal del PoC (entorno → datos → agente → pruebas)
├── mcp_costos_editoriales_server.py         # Servidor MCP local (FastMCP) con las 13 tools sobre SQLite
├── PitchFinalNABC_AgenteCostosEditoriales.pptx  # Presentación de pitch final (estructura NABC)
└── Recursos y Contexto/
    ├── gastos_ficticios_poc.csv             # Dataset de prueba (4 proyectos, 20 gastos, MXN)
    ├── blueprint_poc.md                     # Blueprint del PoC (alcance, arquitectura, criterios)
    ├── 1 - Caso de Uso.pdf                  # Ficha 1: caso de uso e incertidumbre
    ├── 2 - PriorizacionyArquitectura.pdf    # Ficha 2: feature priorizada y arquitectura
    ├── 3 - GuiaCapadeDatosETL.pdf           # Ficha 3: capa de datos y ETL
    ├── 4 - Guia Teorica PoC.pdf             # Guía teórica del PoC
    ├── GuiaNABCZerotoHeroProyectoFinal.pdf  # Guía del pitch final (NABC)
    └── Ejemplos y Templates/                # Laboratorios y templates de referencia
```

## Cómo ejecutarlo

### Requisitos

- Python 3.10+
- Claves de API en un archivo `.env` en la raíz del proyecto:

```env
GOOGLE_API_KEY=tu_clave_de_gemini
LANGSMITH_API_KEY=tu_clave_de_langsmith
```

### Pasos

1. Instalar dependencias:

   ```bash
   pip install -U langchain langchain-community langchain-google-genai \
                  langchain-mcp-adapters langsmith fastmcp pandas python-dotenv
   ```

2. Abrir y ejecutar el notebook `PoCTemplateLangChain_completado.ipynb` en orden. El notebook:
   - carga las claves desde `.env`;
   - **levanta automáticamente el servidor MCP** (`mcp_costos_editoriales_server.py`) en un puerto libre y crea la base SQLite desde el CSV;
   - descubre las tools MCP, construye el agente y corre un mini set de pruebas;
   - abre un **playground interactivo** para conversar con el agente.

3. (Opcional) Levantar el servidor MCP por separado:

   ```bash
   python mcp_costos_editoriales_server.py --host 127.0.0.1 --port 8010
   ```

### Ejemplos de preguntas

- `Calcula el costo y precio del proyecto 3232-0001`
- `¿Qué proyectos tienen mayor gasto?`
- `¿Hay proyectos con cantidades inconsistentes?`
- `¿Cuál es el resumen global de la base?`

## Observabilidad y trazabilidad

- **LangSmith:** cada corrida del agente queda trazada (tools llamadas, argumentos, latencia) en [smith.langchain.com](https://smith.langchain.com).
- **Logs de inferencia:** cada propuesta de costo/precio se registra en la tabla `logs_inferencia` de SQLite (id, timestamp, propuesta, score, latencia).

## Alcance y límites del PoC

Por diseño, este PoC **no** incluye RAG, vector stores, OCR, múltiples agentes ni APIs externas: el foco es validar el núcleo del caso (leer gastos, razonar sobre ellos y devolver una propuesta clara y trazable).

Límites reconocidos:

- Dataset **ficticio** de prueba (4 proyectos, 20 gastos); falta validar con datos reales.
- Margen de utilidad fijo por defecto (35 %), configurable por parámetro.
- El precio sugerido es una **propuesta**: la decisión final requiere validación humana.
- Interfaz en notebook; una UI (p. ej. Streamlit) queda como siguiente iteración.

## Próximos pasos

1. Validar el flujo con datos reales de la editorial y medir línea base vs. tiempo con el agente.
2. Medir tasa de aceptación del precio sugerido por el analista.
3. Exponer el agente vía interfaz web (Streamlit) o API REST (FastAPI).
4. Endurecer la capa de datos (manejo de errores, DLQ, idempotencia) según la Ficha 3.
