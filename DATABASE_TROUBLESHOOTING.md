# 🔧 Solución de Problemas de Conexión a Cloud SQL

## 🚨 Problema Identificado

El error `"connection already closed"` indica que Cloud SQL está cerrando las conexiones por inactividad, y la aplicación no tiene mecanismos de reconexión automática.

## ✅ Soluciones Implementadas

### 1. **Reconexión Automática**
- ✅ Verificación de estado de conexión antes de cada consulta
- ✅ Reconexión automática con reintentos y backoff exponencial
- ✅ Decorador `@_with_retry` para métodos de base de datos

### 2. **Configuración de Keepalives**
```python
# Nuevos parámetros de conexión PostgreSQL
keepalives_idle=600      # 10 minutos antes del primer keepalive
keepalives_interval=30   # 30 segundos entre keepalives
keepalives_count=3       # 3 keepalives fallidos = conexión muerta
```

### 3. **Variables de Entorno Configurables**
```bash
# En docker-compose.yml o .env
DB_CONNECTION_TIMEOUT=3600    # 1 hora
DB_KEEPALIVES_IDLE=600        # 10 minutos
DB_KEEPALIVES_INTERVAL=30     # 30 segundos
DB_KEEPALIVES_COUNT=3         # 3 intentos
DB_MAX_RETRIES=3              # 3 reintentos de reconexión
```

## 🚀 Deploy en Streamlit Cloud

### Paso 1: Configurar Secrets
En Streamlit Cloud, ve a **Settings > Secrets** y agrega:

```toml
# Configuración básica
DB_HOST = "tu-ip-cloud-sql"
DB_PORT = 5432
DB_NAME = "ragdb"
DB_USER = "raguser"
DB_PASS = "tu_password_seguro"

# Configuración anti-timeout (CRÍTICO)
DB_CONNECTION_TIMEOUT = 3600
DB_KEEPALIVES_IDLE = 600
DB_KEEPALIVES_INTERVAL = 30
DB_KEEPALIVES_COUNT = 3
DB_MAX_RETRIES = 3

# Google Cloud
GCS_BUCKET_NAME = "tu-bucket"
GCF_PROJECT_ID = "tu-proyecto"
```

### Paso 2: Configurar Cloud SQL para Streamlit Cloud
```sql
-- Permitir conexiones desde IPs de Streamlit Cloud
-- En Cloud SQL > Connections > Authorized networks
-- Agregar: 0.0.0.0/0 (solo para desarrollo)
-- Para producción, usar IPs específicas de Streamlit Cloud
```

### Paso 3: Verificar Configuración
```python
# La aplicación ahora incluye verificación automática
# Revisa logs en Streamlit Cloud para confirmar conexiones exitosas
```

## 🔍 Monitoreo y Debugging

### Logs a Revisar
```bash
# En Docker
docker-compose logs -f drcecim-upload

# Buscar estos mensajes:
✅ Conexión a Cloud SQL inicializada exitosamente
🔄 Reconectando a Cloud SQL...
✅ Reconexión exitosa en intento X
```

### Comandos de Diagnóstico
```bash
# Probar conectividad a Cloud SQL
telnet 34.95.166.187 5432

# Verificar configuración de Docker
docker-compose config

# Reiniciar servicios
docker-compose down && docker-compose up -d
```

## ⚠️ Puntos Críticos para Producción

1. **NO usar IP pública en producción**
   - Usa Cloud SQL Proxy o conexión privada
   - Configura VPC peering si es necesario

2. **Rotar credenciales regularmente**
   - Cambia passwords cada 90 días
   - Usa IAM authentication cuando sea posible

3. **Monitorear métricas de Cloud SQL**
   - Conexiones activas
   - CPU y memoria
   - Logs de conexión

4. **Configurar alertas**
   - Conexiones fallidas
   - Timeouts de consulta
   - Uso de recursos

## 🏥 Health Checks

La aplicación ahora incluye:
- ✅ Verificación automática de conexión
- ✅ Reconexión transparente
- ✅ Manejo graceful de errores
- ✅ Logs detallados para debugging

## 📞 Soporte

Si persisten los problemas:
1. Revisa los logs completos
2. Verifica configuración de Cloud SQL
3. Confirma que las IPs están autorizadas
4. Contacta: drcecim@gmail.com