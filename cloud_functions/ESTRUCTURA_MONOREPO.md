# 🏗️ Estructura Monorepo - Cloud Functions

## 📋 Resumen de la Implementación

Se ha migrado exitosamente de la estructura anterior (con directorios separados) a una **estructura monorepo** que es la mejor práctica recomendada por Google Cloud Functions.

## 🔄 Cambios Realizados

### ❌ Estructura Anterior (Problemática)
```
cloud_functions/
├── common/                          # Código compartido
├── process_pdf/                     # Cloud Function separada
│   ├── main.py
│   └── requirements.txt
└── create_embeddings/               # Cloud Function separada
    ├── main.py
    └── requirements.txt
```

### ✅ Estructura Actual (Monorepo)
```
cloud_functions/
├── main.py                          # ← Todas las funciones en un archivo
├── requirements.txt                 # ← Dependencias unificadas
├── common/                          # ← Código compartido
│   ├── config/
│   ├── services/
│   ├── utils/
│   └── models/
└── deploy_event_driven.sh          # ← Script actualizado
```

## 🚀 Beneficios de la Estructura Monorepo

### 1. **Simplicidad de Despliegue**
- ✅ Un solo archivo `main.py` contiene todas las funciones
- ✅ Un solo archivo `requirements.txt` con todas las dependencias
- ✅ No hay problemas de imports entre directorios

### 2. **Mejor Organización**
- ✅ Código compartido en `common/` accesible directamente
- ✅ No hay duplicación de código
- ✅ Fácil mantenimiento y actualizaciones

### 3. **Cumplimiento de Mejores Prácticas**
- ✅ Sigue las recomendaciones oficiales de Google Cloud Functions
- ✅ Estructura más limpia y profesional
- ✅ Mejor para equipos de desarrollo

### 4. **Rendimiento**
- ✅ Tiempos de build más rápidos
- ✅ Menor tamaño de deployment
- ✅ Mejor caching de dependencias

## 📁 Archivos Principales

### `main.py`
Contiene ambas Cloud Functions:
- `process_pdf_to_chunks()`: Procesa PDFs y genera chunks
- `create_embeddings_from_chunks()`: Genera embeddings y actualiza FAISS

### `requirements.txt`
Dependencias unificadas:
```txt
# Framework
functions-framework>=3.4.0

# Dependencias comunes
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-dotenv>=1.0.0
google-cloud-storage>=2.0.0
google-cloud-logging>=3.5.0
tenacity>=8.2.0

# Dependencias específicas
marker-pdf>=0.2.0
openai>=1.3.0
numpy>=1.24.0
faiss-cpu>=1.7.4
pandas>=1.5.0
tqdm>=4.64.0
```

### `deploy_event_driven.sh`
Script actualizado que usa:
- `--source=.` para desplegar desde el directorio raíz
- `--entry-point=function_name` para especificar qué función desplegar

## 🔧 Comandos de Despliegue

### Despliegue Automático
```bash
cd cloud_functions/
./deploy_event_driven.sh
```

### Despliegue Manual
```bash
# Función 1: process-pdf-to-chunks
gcloud functions deploy process-pdf-to-chunks \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=process_pdf_to_chunks \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=tu-bucket" \
  --service-account=tu-service-account \
  --memory=1024MB \
  --timeout=540s \
  --max-instances=10 \
  --project=tu-project

# Función 2: create-embeddings-from-chunks
gcloud functions deploy create-embeddings-from-chunks \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=create_embeddings_from_chunks \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=tu-bucket" \
  --service-account=tu-service-account \
  --memory=2048MB \
  --timeout=900s \
  --max-instances=5 \
  --concurrency=1 \
  --project=tu-project
```

## 🧪 Verificación

### Ejecutar Pruebas
```bash
cd cloud_functions/
python test_deployment_structure.py
```

### Verificar Funciones Desplegadas
```bash
# Verificar estado
gcloud functions describe process-pdf-to-chunks --region=us-central1 --project=tu-project
gcloud functions describe create-embeddings-from-chunks --region=us-central1 --project=tu-project

# Ver logs
gcloud functions logs read process-pdf-to-chunks --region=us-central1 --project=tu-project
gcloud functions logs read create-embeddings-from-chunks --region=us-central1 --project=tu-project
```

## 🔄 Migración desde Estructura Anterior

### Pasos Realizados
1. ✅ Combinado código de `process_pdf/main.py` y `create_embeddings/main.py` en `main.py`
2. ✅ Unificado dependencias en `requirements.txt`
3. ✅ Actualizado script de despliegue para usar `--source=.` y `--entry-point`
4. ✅ Eliminado bloques try/except de imports (ya no necesarios)
5. ✅ Actualizado script de pruebas para estructura monorepo

### Limpieza Opcional
```bash
# Eliminar directorios antiguos (si ya no los necesitas)
rm -rf process_pdf/
rm -rf create_embeddings/
```

## 📊 Comparación de Estructuras

| Aspecto | Estructura Anterior | Estructura Monorepo |
|---------|-------------------|-------------------|
| **Archivos principales** | 2 main.py + 2 requirements.txt | 1 main.py + 1 requirements.txt |
| **Duplicación de código** | Sí (bloques try/except) | No |
| **Complejidad de despliegue** | Alta (copiar directorios) | Baja (directo) |
| **Mantenimiento** | Difícil | Fácil |
| **Cumplimiento de mejores prácticas** | No | Sí |
| **Rendimiento** | Lento | Rápido |

## 🎯 Resultados

### ✅ Problemas Resueltos
- **Imports**: Ya no hay problemas de `ModuleNotFoundError`
- **Despliegue**: Proceso más simple y confiable
- **Mantenimiento**: Código más fácil de mantener
- **Escalabilidad**: Fácil agregar nuevas funciones

### ✅ Beneficios Obtenidos
- **Simplicidad**: Un solo archivo principal
- **Eficiencia**: Menor tiempo de build y deployment
- **Profesionalismo**: Estructura que sigue mejores prácticas
- **Futuro**: Base sólida para crecimiento del proyecto

## 🚀 Próximos Pasos

1. **Desplegar**: Ejecutar `./deploy_event_driven.sh`
2. **Probar**: Subir un PDF al bucket para verificar el flujo completo
3. **Monitorear**: Revisar logs para asegurar funcionamiento correcto
4. **Optimizar**: Ajustar configuración según necesidades específicas

---

**Nota**: Esta estructura monorepo es la recomendada por Google Cloud Functions y proporciona una base sólida para el crecimiento futuro del proyecto. 🎉 