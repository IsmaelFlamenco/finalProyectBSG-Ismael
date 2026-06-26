# Blueprint del Proof of Concept

## Objetivo del PoC
Construir un prototipo simple de un agente que, a partir de los gastos de producción registrados en la base de datos, calcule el costo propuesto y sugiera un precio de venta con trazabilidad, validación básica e incertidumbre controlada.

Este blueprint se basa en:
- [Ficha 1 - Caso de Uso](./1%20-%20Caso%20de%20Uso.pdf)
- [Ficha 2 - Priorizacion y Arquitectura](./2%20-%20PriorizacionyArquitectura.pdf)
- [Ficha 3 - Capa de Datos y ETL](./3%20-%20GuiaCapadeDatosETL.pdf)
- [Guia Teorica PoC](./4%20-%20Guia%20Teorica%20PoC.pdf)

## 1. Resumen del caso de uso
El caso de uso consiste en apoyar al analista de costos y gastos en la determinacion dinamica del costo y del precio de venta de un material editorial.

### Problema principal
- Hoy el proceso es manual.
- Los gastos se revisan en contabilidad y se consolidan en Excel.
- Hay riesgo de omitir gastos.
- El calculo puede tardar demasiado.

### Resultado deseado
- Consolidar gastos y calcular costo en menos de 10 minutos.
- Obtener una propuesta de precio casi instantanea.
- Reducir errores y mantener trazabilidad.

## 2. Feature priorizada
La feature priorizada es:

**Agente inteligente para la determinacion dinamica de costos y precios de venta**

### Por que esta feature
- Resuelve directamente el problema central del caso.
- Es el nucleo del flujo de negocio.
- Permite transformar los gastos ya registrados en una salida util para toma de decisiones.
- Las otras capacidades quedan como futuras mejoras.

## 3. Alcance minimo del PoC
Para mantener el desarrollo simple, el PoC hara solo lo necesario:

1. Leer un CSV de prueba con gastos ficticios.
2. Cargar esos datos en SQLite.
3. Consultar los gastos por proyecto con SQL.
4. Calcular costo propuesto y precio sugerido.
5. Devolver una salida JSON estructurada.
6. Guardar el resultado en una tabla de logs de inferencia.

## 4. Elementos mas importantes de las fichas

### 4.1 Ficha 1: elementos clave
- Actor principal: analista de costos y gastos.
- Trigger: cierre del registro de costos y gastos.
- Dolor: proceso manual lento y con margen de error.
- Salida esperada: JSON con costo, precio, total de gastos y score.
- Politica de incertidumbre: si falta evidencia o hay baja confianza, no inventar.
- Medicion: tiempo total de ciclo, aceptacion del precio sugerido, calidad de la salida.

### 4.2 Ficha 2: elementos clave
- Feature priorizada: agente inteligente de costos y precios.
- Arquitectura simple por capas.
- Modelo via API.
- Exposicion del PoC por API REST o ejecucion local en notebook.
- Observabilidad basica con registro de entradas, salidas y latencia.

### 4.3 Ficha 3: elementos clave
- Fuente principal: base de datos relacional con gastos de produccion.
- Acceso: consulta SQL a una materialized view o vista consolidada.
- Transformacion: validacion de tipos y normalizacion de texto.
- Carga: logs de inferencia en base relacional.
- Idempotencia: usar `idproyecto` como identificador estable.
- Incertidumbre: si hay inconsistencia, marcar el campo como nulo o reportarlo.

## 5. Arquitectura propuesta

### Capa 1: Ingesta
**Que hace**
- Lee un archivo CSV de prueba.
- Carga la informacion en SQLite.

**Por que asi**
- Es la forma mas simple de simular la fuente real.
- Permite trabajar sin infraestructura adicional.

### Capa 2: Transformacion
**Que hace**
- Valida que montos y fechas tengan formato correcto.
- Normaliza cadenas como `claveproducto` y descripciones.
- Agrupa los datos por `idproyecto`.

**Por que asi**
- Los datos ya son estructurados.
- No se necesita OCR ni chunking semantico.

### Capa 3: Almacenamiento
**Que hace**
- Guarda los registros en SQLite.
- Guarda los resultados del agente en una tabla de logs.

**Por que asi**
- Es suficiente para un PoC.
- Mantiene la trazabilidad sin complejidad innecesaria.

### Capa 4: Inferencia
**Que hace**
- Usa un modelo de lenguaje para razonar sobre los gastos.
- Aplica reglas simples de negocio.
- Genera el JSON de salida.

**Por que asi**
- El flujo es lineal.
- No se justifica una orquestacion compleja.

### Capa 5: Serving
**Que hace**
- Expone la consulta como funcion dentro del notebook.
- Opcionalmente puede prepararse para API REST despues.

**Por que asi**
- Primero conviene validar el PoC.
- Luego se puede pasar a FastAPI si se aprueba el piloto.

### Capa 6: Observabilidad
**Que hace**
- Registra entrada, salida, latencia y modelo usado.
- Guarda el resultado para auditoria.

**Por que asi**
- Permite revisar errores.
- Ayuda a medir si el PoC realmente cumple el objetivo.

## 6. Estructura del dataset CSV de prueba
El dataset se generara con datos ficticios o de prueba.

### Nivel de granularidad
- Una fila por gasto.
- Un proyecto puede tener varias filas.

### Campos propuestos
- `idproyecto`
- `claveproducto`
- `nombreproducto`
- `fechaproyecto`
- `cantidad`
- `tipo_gasto`
- `descripcion_gasto`
- `monto_gasto`
- `moneda`
- `proveedor`
- `fecha_gasto`

### Por que estos campos
- Representan el caso de uso real.
- Permiten consultas SQL sencillas.
- Facilitan el calculo de costo total por proyecto.
- Dan soporte a pruebas de validacion e incertidumbre.

## 7. Salida esperada del sistema
El PoC devolvera un JSON con esta logica:

- `idproyecto`
- `claveproducto`
- `nombreproducto`
- `propuesta_costo`
- `propuesta_precio`
- `cantidad_gastos`
- `total_gastos`
- `score_global`
- `campos_baja_confianza`

## 8. Regla de incertidumbre
La regla sera simple:
- Si el dato esta claro, se usa.
- Si el dato es inconsistente o incompleto, no se inventa.
- Si la confianza es baja, el campo va como `null` o se reporta como dudoso.

## 9. Estructura del notebook a completar
El template se completara en este orden:

1. Configuracion del entorno.
2. Declaracion del modelo.
3. Conexion a SQLite.
4. Tool SQL.
5. System prompt.
6. Construccion del agente.
7. Pruebas con mini set.
8. Registro de resultados.

## 10. Criterio de simplicidad
Para este PoC se evita:
- RAG.
- Vector store.
- OCR.
- Multiples agentes.
- APIs externas.
- Chunking semantico.

Esto ayuda a concentrarse en el nucleo del caso: leer gastos, razonar sobre ellos y devolver una propuesta clara.

## 11. Proximo paso
Si este blueprint es aprobado, el siguiente paso sera:

1. Generar el CSV ficticio de prueba.
2. Crear la base SQLite.
3. Completar el notebook `PoCTemplateLangChain.ipynb`.
4. Dejar el flujo listo para ejecutar.
