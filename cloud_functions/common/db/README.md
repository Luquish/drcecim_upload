# Base de Datos Cloud SQL - DrCecim

## 📋 Información General

Este documento describe la configuración y características de la base de datos PostgreSQL utilizada en el sistema DrCecim para almacenar vectores de embeddings y metadatos de documentos.

## 🏗️ Especificaciones Técnicas

### Instancia de Base de Datos
- **Nombre**: `drcecim-cloud-sql`
- **Versión**: PostgreSQL 15.13
- **Región**: `southamerica-east1`
- **Estado**: `RUNNABLE`
- **Tier**: `db-g1-small`
- **Disco**: 10GB PD_SSD

### Conexión
- **Connection Name**: `drcecim-465823:southamerica-east1:drcecim-cloud-sql`
- **IP Pública**: `34.95.166.187`
- **Puerto**: `5432`
- **SSL Requerido**: `False`

## 👥 Usuarios y Bases de Datos

### Usuarios
| Usuario | Tipo | Propósito |
|---------|------|-----------|
| `postgres` | BUILT_IN | Usuario administrador |
| `raguser` | BUILT_IN | Usuario de aplicación |

### Bases de Datos
| Base de Datos | Charset | Collation | Propósito |
|---------------|---------|-----------|-----------|
| `postgres` | UTF8 | en_US.UTF8 | Base de datos por defecto |
| `ragdb` | UTF8 | en_US.UTF8 | Base de datos de la aplicación |

## 🔐 Configuración de Seguridad

### Credenciales
- **Usuario de aplicación**: `raguser`
- **Contraseña**: `DrCecim2024@`
- **Base de datos**: `ragdb`

### Variables de Entorno
```bash
DB_USER=raguser
DB_PASS=DrCecim2024@
DB_NAME=ragdb
CLOUD_SQL_CONNECTION_NAME=drcecim-465823:southamerica-east1:drcecim-cloud-sql
DB_PRIVATE_IP=false
```

## 💾 Configuración de Backup

- **Backup habilitado**: `True`
- **Hora de backup**: `23:00` (11:00 PM)
- **Ubicación**: `us`
- **Retención**: `7` backups

## 🔧 Configuración de Mantenimiento

- **Día de mantenimiento**: `0` (Domingo)
- **Hora de mantenimiento**: `0` (12:00 AM)
- **Track de actualizaciones**: `canary`

## 📊 Estructura de Datos

### Tabla de Vectores (Pendiente de implementación)
```sql
CREATE TABLE vectors (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL,
    chunk_id VARCHAR(255) NOT NULL,
    embedding_vector REAL[] NOT NULL,
    text_content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices recomendados
CREATE INDEX idx_vectors_document_id ON vectors(document_id);
CREATE INDEX idx_vectors_chunk_id ON vectors(chunk_id);
CREATE INDEX idx_vectors_created_at ON vectors(created_at);
```

### Tabla de Metadatos (Opcional)
```sql
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) UNIQUE NOT NULL,
    filename VARCHAR(255) NOT NULL,
    file_size BIGINT,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_status VARCHAR(50) DEFAULT 'pending',
    num_chunks INTEGER DEFAULT 0,
    metadata JSONB
);
```

## 🔌 Conexión desde Aplicación

### Python con psycopg2
```python
import psycopg2
from google.cloud.sql.connector import Connector

# Usando Cloud SQL Connector (recomendado para Cloud Functions)
connector = Connector()

def get_connection():
    conn = connector.connect(
        instance_connection_name=os.getenv('CLOUD_SQL_CONNECTION_NAME'),
        driver='psycopg2',
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASS'),
        db=os.getenv('DB_NAME'),
    )
    return conn
```

### Python con SQLAlchemy
```python
from sqlalchemy import create_engine
from google.cloud.sql.connector import Connector

connector = Connector()

def get_engine():
    def getconn():
        conn = connector.connect(
            instance_connection_name=os.getenv('CLOUD_SQL_CONNECTION_NAME'),
            driver='psycopg2',
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASS'),
            db=os.getenv('DB_NAME'),
        )
        return conn

    engine = create_engine(
        "postgresql://",
        creator=getconn,
    )
    return engine
```

## 🚀 Comandos Útiles

### Conectar desde línea de comandos
```bash
# Conectar como postgres
PGPASSWORD=DrCecim2024@ psql -h 34.95.166.187 -U postgres -d postgres

# Conectar como raguser
PGPASSWORD=DrCecim2024@ psql -h 34.95.166.187 -U raguser -d ragdb
```

### Comandos de gcloud
```bash
# Ver información de la instancia
gcloud sql instances describe drcecim-cloud-sql

# Listar usuarios
gcloud sql users list --instance=drcecim-cloud-sql

# Listar bases de datos
gcloud sql databases list --instance=drcecim-cloud-sql

# Conectar (requiere psql instalado)
gcloud sql connect drcecim-cloud-sql --user=raguser
```

## 📈 Monitoreo y Métricas

### Métricas importantes a monitorear
- **CPU Usage**: Máximo 100% (db-g1-small)
- **Memory Usage**: Máximo 1.7GB
- **Disk Usage**: Máximo 10GB
- **Connections**: Máximo 100 conexiones simultáneas

### Logs
Los logs de la base de datos se pueden acceder desde:
- Google Cloud Console > SQL > Instancias > drcecim-cloud-sql > Logs
- Cloud Logging con filtro: `resource.type="cloudsql_database"`

## 🔄 Migración desde FAISS

### Ventajas de PostgreSQL sobre FAISS
1. **Persistencia**: Los datos se mantienen entre reinicios
2. **Escalabilidad**: Fácil escalado horizontal y vertical
3. **Consultas complejas**: SQL permite consultas avanzadas
4. **Backup automático**: Backups diarios automáticos
5. **Monitoreo**: Métricas integradas en Google Cloud

### Consideraciones de rendimiento
- **Índices vectoriales**: Considerar pgvector para búsquedas vectoriales eficientes
- **Particionamiento**: Para grandes volúmenes de datos
- **Conexiones**: Usar connection pooling en producción

## 🛠️ Mantenimiento

### Tareas periódicas
- **Revisar logs**: Semanalmente
- **Monitorear métricas**: Diariamente
- **Verificar backups**: Semanalmente
- **Actualizar índices**: Según necesidad

### Troubleshooting común
1. **Conexiones agotadas**: Revisar connection pooling
2. **Espacio en disco**: Monitorear uso de almacenamiento
3. **Lentitud en consultas**: Revisar índices y queries
4. **Errores de SSL**: Verificar configuración de conexión

## 📚 Referencias

- [Google Cloud SQL Documentation](https://cloud.google.com/sql/docs)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [pgvector Extension](https://github.com/pgvector/pgvector) (para búsquedas vectoriales)
- [Cloud SQL Connector](https://github.com/GoogleCloudPlatform/cloud-sql-python-connector)

---

**Última actualización**: 2025-08-01 12:11:04
**Responsable**: Equipo DrCecim
**Versión**: 1.0 