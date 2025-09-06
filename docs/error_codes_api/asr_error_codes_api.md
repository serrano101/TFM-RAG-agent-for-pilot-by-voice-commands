# Códigos de Error - Sistema ASR Service

## Códigos de Estado de Respuesta

### 1. Estados de Éxito (HTTP 200)
- **success**: Operación completada exitosamente (respuesta de /transcribe)
- **ok**: Servicio funcionando correctamente (respuesta de /)

### 2. Estados de Error de Validación (HTTP 400)
- **validation_error**: Error de validación de entrada
  - Descripción: El archivo de audio está vacío o la transcripción es vacía
  - Mensaje: "Audio file is empty or missing" o "Transcription is empty"

### 3. Estados de Error de Procesamiento (HTTP 500)
- **processing_error**: Error general de procesamiento
  - Descripción: Error inesperado durante la transcripción o notificación a microservicios
  - Mensaje: "Error processing audio: {error}"

## Estructura de Respuesta de Éxito y Error

### Éxito (HTTP 200)
```json
{
  "status": "success|ok",
  "transcription": "...texto transcrito..."
}
```

### Error (HTTP 400, 500)
```json
{
  "status": "validation_error|processing_error",
  "message": "Descripción del error",
  "transcription": null
}
```

## Códigos HTTP Utilizados

- **200**: Operación exitosa (todas las respuestas de éxito)
- **400**: Error de cliente (validación de archivo o transcripción)
- **500**: Error interno del servidor (errores de procesamiento)

## Logging Asociado

### Niveles de Log por Tipo de Error:
- **INFO**: Operaciones normales, inicio/fin de procesos
- **DEBUG**: Detalles técnicos, respuestas de microservicios
- **WARNING**: Errores recuperables, archivo o transcripción vacía
- **ERROR**: Errores críticos con exc_info=True para stack trace

### Ejemplo de Logs:
```
INFO - Notificando al microservicio Agentic ReAct...
DEBUG - Respuesta del microservicio Agentic ReAct: 200 - ...
WARNING - Archivo de audio vacío o no recibido
ERROR - Error en transcribe_endpoint: ...
```

## Recomendaciones de Manejo

1. **Para clientes HTTP**: Verificar siempre el campo "status" en la respuesta
2. **Para debugging**: Revisar logs con nivel DEBUG para detalles técnicos
3. **Para monitoreo**: Alertar en códigos 500 y alta frecuencia de 400
4. **Para usuarios**: Mostrar mensajes amigables basados en el campo "message"
