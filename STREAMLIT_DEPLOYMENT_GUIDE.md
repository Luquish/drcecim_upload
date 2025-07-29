# 🚀 Guía de Despliegue en Streamlit Cloud

## 📋 Resumen del Proyecto

**Repositorio actual**: `drcecim_upload`
- ✅ **Streamlit App**: `streamlit_app.py`
- ✅ **Cloud Functions**: `cloud_functions/`
- ✅ **Dependencias**: `requirements.txt`

**Arquitectura**:
```
drcecim_upload (Streamlit) → Sube archivos → Google Cloud Storage
                                    ↓
chatbot_uba (Backend) ← Descarga embeddings ← Google Cloud Storage
```

## 🎯 ¿Puedes Desplegar en Streamlit Cloud?

**SÍ, absolutamente**. Este repositorio es perfecto para Streamlit Cloud porque:

1. ✅ Tiene `streamlit_app.py` (archivo principal)
2. ✅ Tiene `requirements.txt` (dependencias)
3. ✅ Es un repositorio de GitHub
4. ✅ Está bien estructurado

## 🚀 Pasos para Desplegar

### Paso 1: Preparar Credenciales

```bash
# Configurar credenciales en Google Cloud Secret Manager
cd cloud_functions/utils
python3 migrate_secrets.py --project-id drcecim-465823
```

### Paso 2: Desplegar en Streamlit Cloud

1. **Ve a Streamlit Cloud**:
   - https://share.streamlit.io/
   - Inicia sesión con GitHub

2. **Crear nueva app**:
   - Click en "New app"
   - Selecciona tu repositorio: `drcecim_upload`
   - Branch: `main` (o tu rama principal)
   - Main file path: `streamlit_app.py`

3. **Configurar variables de entorno**:
   - En la configuración de la app
   - Agrega: `GCS_BUCKET_NAME=drcecim-chatbot-storage`

### Paso 3: Verificar el Despliegue

- La app estará disponible en: `https://[tu-app].streamlit.app`
- Verifica que puede subir archivos
- Revisa los logs si hay errores

## 🔧 Configuración de Cloud Functions

**IMPORTANTE**: Las Cloud Functions se despliegan por separado:

```bash
# Desplegar Cloud Functions
cd cloud_functions
./deploy_event_driven.sh
```

**¿Por qué separado?**
- Streamlit Cloud = Frontend (interfaz de usuario)
- Cloud Functions = Backend (procesamiento)
- Se comunican a través de Google Cloud Storage

## 📁 Estructura del Repositorio

```
drcecim_upload/
├── streamlit_app.py          ← Archivo principal para Streamlit Cloud
├── requirements.txt          ← Dependencias
├── cloud_functions/         ← Backend (se despliega por separado)
│   ├── deploy_event_driven.sh
│   ├── utils/migrate_secrets.py
│   └── ...
├── ui/                      ← Componentes de Streamlit
├── services/                ← Servicios (GCS, etc.)
└── config/                  ← Configuraciones
```

## 🎯 Flujo Completo

1. **Usuario sube PDF** → Streamlit Cloud
2. **Streamlit sube al bucket** → Google Cloud Storage
3. **Cloud Functions detectan** → Procesan el archivo
4. **Generan embeddings** → Los suben al bucket
5. **Chatbot descarga** → Responde consultas

## 🔍 Troubleshooting

### Error: "No module named 'google.cloud'"
```bash
# Agregar a requirements.txt
google-cloud-storage>=2.12.0
google-cloud-secret-manager>=2.0.0
```

### Error: "Permission denied"
- Verifica que las credenciales tienen permisos para el bucket
- Ejecuta el script de migración de secretos

### Error: "Bucket not found"
- Verifica que `GCS_BUCKET_NAME` está configurado correctamente
- Asegúrate de que el bucket existe en Google Cloud

## 📞 URLs Útiles

- **Streamlit Cloud**: https://share.streamlit.io/
- **Google Cloud Console**: https://console.cloud.google.com/
- **Secret Manager**: https://console.cloud.google.com/security/secret-manager
- **Documentación Streamlit**: https://docs.streamlit.io/

## ✅ Checklist de Despliegue

- [ ] Credenciales configuradas en Secret Manager
- [ ] Repositorio subido a GitHub
- [ ] App creada en Streamlit Cloud
- [ ] Variables de entorno configuradas
- [ ] Cloud Functions desplegadas
- [ ] App funcionando correctamente

---

**¡Tu repositorio está listo para desplegar en Streamlit Cloud!** 🎉 