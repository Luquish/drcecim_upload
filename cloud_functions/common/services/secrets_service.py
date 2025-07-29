"""
Servicio para gestión de secretos usando Google Secret Manager.
"""
import os
import logging
from typing import Optional, Dict, Any
from google.cloud import secretmanager
from config.settings import GCF_PROJECT_ID

logger = logging.getLogger(__name__)


class SecretsService:
    """
    Servicio para gestionar secretos usando Google Secret Manager.
    """
    
    def __init__(self, project_id: str = None):
        """
        Inicializa el servicio de secretos.
        
        Args:
            project_id (str): ID del proyecto de Google Cloud
        """
        self.project_id = project_id or GCF_PROJECT_ID
        if not self.project_id:
            raise ValueError("PROJECT_ID es requerido para usar Secret Manager")
        
        try:
            self.client = secretmanager.SecretManagerServiceClient()
            logger.info(f"Cliente de Secret Manager inicializado para proyecto: {self.project_id}")
        except ImportError as e:
            logger.error(f"Error importando Secret Manager client: {str(e)}")
            raise ImportError("Google Cloud Secret Manager no está disponible")
        except Exception as e:
            logger.error(f"Error de conectividad inicializando Secret Manager: {str(e)}")
            raise ConnectionError(f"No se pudo conectar con Secret Manager: {str(e)}")
    
    def get_secret(self, secret_name: str, version: str = "latest") -> Optional[str]:
        """
        Obtiene un secreto de Google Secret Manager.
        
        Args:
            secret_name (str): Nombre del secreto
            version (str): Versión del secreto (por defecto "latest")
            
        Returns:
            str: Valor del secreto o None si no existe
        """
        try:
            # Construir el nombre completo del secreto
            secret_path = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
            
            # Obtener el secreto
            response = self.client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode("UTF-8")
            
            logger.info(f"Secreto '{secret_name}' obtenido exitosamente")
            return secret_value
            
        except ValueError as e:
            logger.error(f"Nombre de secreto inválido '{secret_name}': {str(e)}")
            return None
        except UnicodeDecodeError as e:
            logger.error(f"Error decodificando secreto '{secret_name}': {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error de conectividad obteniendo secreto '{secret_name}': {str(e)}")
            return None
    
    def create_secret(self, secret_name: str, secret_value: str) -> bool:
        """
        Crea un nuevo secreto en Google Secret Manager.
        
        Args:
            secret_name (str): Nombre del secreto
            secret_value (str): Valor del secreto
            
        Returns:
            bool: True si se creó exitosamente
        """
        try:
            parent = f"projects/{self.project_id}"
            
            # Crear el secreto
            secret = self.client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_name,
                    "secret": {"replication": {"automatic": {}}},
                }
            )
            
            # Agregar la versión con el valor
            self.client.add_secret_version(
                request={
                    "parent": secret.name,
                    "payload": {"data": secret_value.encode("UTF-8")},
                }
            )
            
            logger.info(f"Secreto '{secret_name}' creado exitosamente")
            return True
            
        except ValueError as e:
            logger.error(f"Nombre o valor de secreto inválido '{secret_name}': {str(e)}")
            return False
        except UnicodeEncodeError as e:
            logger.error(f"Error codificando valor del secreto '{secret_name}': {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error de conectividad creando secreto '{secret_name}': {str(e)}")
            return False
    
    def update_secret(self, secret_name: str, secret_value: str) -> bool:
        """
        Actualiza un secreto existente con un nuevo valor.
        
        Args:
            secret_name (str): Nombre del secreto
            secret_value (str): Nuevo valor del secreto
            
        Returns:
            bool: True si se actualizó exitosamente
        """
        try:
            parent = f"projects/{self.project_id}/secrets/{secret_name}"
            
            # Agregar nueva versión
            self.client.add_secret_version(
                request={
                    "parent": parent,
                    "payload": {"data": secret_value.encode("UTF-8")},
                }
            )
            
            logger.info(f"Secreto '{secret_name}' actualizado exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"Error actualizando secreto '{secret_name}': {str(e)}")
            return False
    
    def delete_secret(self, secret_name: str) -> bool:
        """
        Elimina un secreto de Google Secret Manager.
        
        Args:
            secret_name (str): Nombre del secreto
            
        Returns:
            bool: True si se eliminó exitosamente
        """
        try:
            secret_path = f"projects/{self.project_id}/secrets/{secret_name}"
            
            self.client.delete_secret(request={"name": secret_path})
            
            logger.info(f"Secreto '{secret_name}' eliminado exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"Error eliminando secreto '{secret_name}': {str(e)}")
            return False
    
    def list_secrets(self) -> Dict[str, Any]:
        """
        Lista todos los secretos del proyecto.
        
        Returns:
            Dict: Información de los secretos
        """
        try:
            parent = f"projects/{self.project_id}"
            
            secrets = []
            for secret in self.client.list_secrets(request={"parent": parent}):
                secrets.append({
                    "name": secret.name.split("/")[-1],
                    "created": secret.create_time,
                    "labels": dict(secret.labels) if secret.labels else {}
                })
            
            logger.info(f"Se encontraron {len(secrets)} secretos")
            return {"secrets": secrets, "count": len(secrets)}
            
        except Exception as e:
            logger.error(f"Error listando secretos: {str(e)}")
            return {"secrets": [], "count": 0}


class SecureConfigManager:
    """
    Gestor de configuración que prioriza Secret Manager sobre variables de entorno.
    """
    
    def __init__(self, project_id: str = None):
        """
        Inicializa el gestor de configuración segura.
        
        Args:
            project_id (str): ID del proyecto de Google Cloud
        """
        self.secrets_service = None
        try:
            self.secrets_service = SecretsService(project_id)
        except Exception as e:
            logger.warning(f"No se pudo inicializar Secret Manager: {str(e)}")
            logger.info("Usando solo variables de entorno")
    
    def get_config_value(self, key: str, default: str = None, env_fallback: bool = True) -> Optional[str]:
        """
        Obtiene un valor de configuración, priorizando Secret Manager.
        
        Args:
            key (str): Nombre de la configuración/secreto
            default (str): Valor por defecto
            env_fallback (bool): Si usar variables de entorno como fallback
            
        Returns:
            str: Valor de la configuración
        """
        # 1. Intentar obtener de Secret Manager
        if self.secrets_service:
            secret_value = self.secrets_service.get_secret(key)
            if secret_value:
                logger.info(f"Configuración '{key}' obtenida de Secret Manager")
                return secret_value
        
        # 2. Fallback a variables de entorno
        if env_fallback:
            env_value = os.getenv(key, default)
            if env_value:
                logger.info(f"Configuración '{key}' obtenida de variables de entorno")
                return env_value
        
        # 3. Valor por defecto
        if default:
            logger.info(f"Usando valor por defecto para '{key}'")
            return default
        
        logger.warning(f"No se encontró configuración para '{key}'")
        return None
    
    def get_openai_api_key(self) -> Optional[str]:
        """
        Obtiene la API key de OpenAI de forma segura.
        
        Returns:
            str: API key de OpenAI
        """
        return self.get_config_value("openai-api-key", env_fallback=True)
    
    def get_database_url(self) -> Optional[str]:
        """
        Obtiene la URL de base de datos de forma segura.
        
        Returns:
            str: URL de base de datos
        """
        return self.get_config_value("database-url", env_fallback=True)
    
    def get_jwt_secret(self) -> Optional[str]:
        """
        Obtiene el secreto JWT de forma segura.
        
        Returns:
            str: Secreto JWT
        """
        return self.get_config_value("jwt-secret", env_fallback=False)
    
    def migrate_env_to_secrets(self, env_vars: list) -> Dict[str, bool]:
        """
        Migra variables de entorno a Secret Manager.
        
        Args:
            env_vars (list): Lista de nombres de variables de entorno
            
        Returns:
            Dict: Resultado de la migración para cada variable
        """
        results = {}
        
        if not self.secrets_service:
            logger.error("Secret Manager no está disponible para migración")
            return results
        
        for env_var in env_vars:
            env_value = os.getenv(env_var)
            if env_value:
                # Convertir nombre de variable de entorno a formato de Secret Manager
                secret_name = env_var.lower().replace("_", "-")
                
                success = self.secrets_service.create_secret(secret_name, env_value)
                results[env_var] = success
                
                if success:
                    logger.info(f"Variable '{env_var}' migrada a secreto '{secret_name}'")
                else:
                    logger.error(f"Error migrando variable '{env_var}'")
            else:
                logger.warning(f"Variable de entorno '{env_var}' no encontrada")
                results[env_var] = False
        
        return results


# Instancia global del gestor de configuración
config_manager = SecureConfigManager() 