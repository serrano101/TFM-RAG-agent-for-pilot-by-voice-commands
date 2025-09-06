 # Códigos de Error - Sistema RAG Agentic

## Códigos de Estado de Respuesta

### 1. Estados de Éxito (HTTP 200)
- **success**: Operación completada exitosamente (respuesta de /rag_result y /react_agent_result)
- **last_result**: Último resultado disponible devuelto (respuesta de /rag_last_result y /react_last_result)
- **empty**: No hay resultado previo disponible (respuesta de /rag_last_result y /react_last_result cuando no hay datos)
- **ok**: Servicio funcionando correctamente (respuesta de /health)

### 2. Estados de Error de Validación (HTTP 400)
- **json_error**: Error al parsear JSON del request
  - Descripción: El cuerpo de la petición no contiene JSON válido
  - Mensaje: "Invalid JSON in request body"

- **validation_error**: Error de validación de entrada
  - Descripción: La transcripción está vacía o es nula
  - Mensaje: "Transcription cannot be empty"

### 3. Estados de Error del RAG (HTTP 422)
- (Actualmente no implementados en app.py, pero previstos para lógica futura de RAG)
- **no_results**: No se encontraron documentos relevantes
  - Descripción: La búsqueda vectorial no devolvió resultados
  - Mensaje: "No relevant documents found"

- **low_relevance**: Puntuación de relevancia demasiado baja
  - Descripción: El mejor resultado tiene score < 0.7
  - Mensaje: "Best relevance score too low: {score}"

- **validation_error** (RAG): Error de validación en RAG
  - Descripción: Query vacío, k inválido, o prompt faltante
  - Mensaje: Variable según el error específico

### 4. Estados de Error de Conexión (HTTP 500)
- **connection_error**: Error de conexión a base de datos (previsto para lógica de dependencias)
  - Descripción: Fallo al conectar con ChromaDB
  - Mensaje: "Database connection failed: {error}"

### 5. Estados de Error de Ejecución (HTTP 500)
- **runtime_error**: Error durante la ejecución (previsto para lógica interna de RAG/Agente)
  - Descripción: Fallo en búsqueda, formateo de prompt, o invocación del LLM
  - Mensaje: Variable según el componente que falle

- **processing_error**: Error general de procesamiento
  - Descripción: RAG o React Agent execution devuelve resultado vacío o falla
  - Mensaje: "RAG execution failed", "React Agent execution failed" o "RAG execution failed: {error}"/"React Agent execution failed: {error}"

### 6. Estados de Error Inesperados (HTTP 500)
- **unexpected_error**: Error no anticipado
  - Descripción: Cualquier excepción no manejada específicamente (por ejemplo, errores inesperados en endpoints)
  - Mensaje: "An unexpected error occurred: {error}"

- **error**: Error genérico en endpoints simples
  - Descripción: Error en health check o recuperación de último resultado
  - Mensaje: Variable según el contexto

## Estructura de Respuesta de Éxito y Error

### Éxito (HTTP 200)
```json
{
  "status": "success|last_result|empty|ok",
  "response": "...respuesta generada..."
}
```

### Error (HTTP 400, 422, 500)
```json
{
  "status": "error_code",
  "message": "Descripción del error",
  "response": null
}
```

## Códigos HTTP Utilizados

- **200**: Operación exitosa (todas las respuestas de éxito)
- **400**: Error de cliente (JSON inválido, validación)
- **422**: Error de procesamiento (previsto para lógica avanzada de RAG)
- **500**: Error interno del servidor (errores de dependencias, ejecución, health check)

## Logging Asociado

### Niveles de Log por Tipo de Error:
- **INFO**: Operaciones normales, inicio/fin de procesos
- **DEBUG**: Detalles técnicos, configuración, previews
- **WARNING**: Errores recuperables, low relevance, no results
- **ERROR**: Errores críticos con exc_info=True para stack trace

### Ejemplo de Logs:
```
INFO - Esperando resultado de ASR para ser analizado por el RAG...
DEBUG - Datos recibidos de ASR: {...}
INFO - Procesando transcripción: ...
ERROR - Error al parsear el JSON de la solicitud: ...
ERROR - Error en la ejecución de RAG: ...
INFO - Devolviendo el último resultado RAG
```

## Códigos de Inicialización

### Errores durante el arranque:
- **FileNotFoundError**: Archivo de prompt no encontrado (al inicializar dependencias)
- **RuntimeError**: Fallo general en inicialización de dependencias
- **ConnectionError**: No se puede conectar a servicios externos (Ollama, ChromaDB)

## Recomendaciones de Manejo

1. **Para clientes HTTP**: Verificar siempre el campo "status" en la respuesta
2. **Para debugging**: Revisar logs con nivel DEBUG para detalles técnicos
3. **Para monitoreo**: Alertar en códigos 500 y alta frecuencia de 422
4. **Para usuarios**: Mostrar mensajes amigables basados en el "message" field
