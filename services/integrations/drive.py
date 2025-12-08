# NG-HEADER: Nombre de archivo: drive.py
# NG-HEADER: Ubicación: services/integrations/drive.py
# NG-HEADER: Descripción: Servicio de sincronización con Google Drive API.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Servicio para interactuar con Google Drive API usando Service Account."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger(__name__)

# MIME types de imágenes permitidas
ALLOWED_IMAGE_MIMES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/heif",  # High Efficiency Image Format (iPhone, dispositivos modernos)
    "image/heic",  # Variante de HEIF
}


class GoogleDriveError(Exception):
    """Excepción base para errores de Google Drive."""

    pass


class GoogleDriveSync:
    """Cliente para sincronizar archivos desde Google Drive."""

    def __init__(self, credentials_path: str, source_folder_id: str):
        """Inicializa el cliente de Google Drive.

        Args:
            credentials_path: Ruta al archivo JSON de Service Account.
            source_folder_id: ID de la carpeta origen en Drive.
        """
        # Resolver ruta relativa desde el directorio raíz del proyecto
        creds_path = Path(credentials_path)
        if not creds_path.is_absolute():
            # Buscar el directorio raíz (donde está el .env o services/)
            project_root = Path(__file__).resolve().parent.parent.parent
            creds_path = project_root / creds_path
        self.credentials_path = creds_path
        self.source_folder_id = source_folder_id
        self.service: Optional[object] = None
        self._validate_credentials()

    def _validate_credentials(self) -> None:
        """Valida que el archivo de credenciales exista."""
        if not self.credentials_path.exists():
            raise GoogleDriveError(
                f"Archivo de credenciales no encontrado: {self.credentials_path}"
            )
        if not self.credentials_path.is_file():
            raise GoogleDriveError(
                f"La ruta de credenciales no es un archivo: {self.credentials_path}"
            )

    async def authenticate(self) -> None:
        """Autentica con Google Drive usando Service Account."""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                str(self.credentials_path),
                scopes=["https://www.googleapis.com/auth/drive"],
            )
            self.service = build("drive", "v3", credentials=credentials)
            logger.info("Autenticación con Google Drive exitosa")
        except Exception as e:
            logger.error(f"Error al autenticar con Google Drive: {e}")
            raise GoogleDriveError(f"Error de autenticación: {e}") from e

    async def list_images_in_folder(self) -> list[dict]:
        """Lista todos los archivos de imagen en la carpeta origen.

        Returns:
            Lista de diccionarios con metadata de archivos:
            [{"id": str, "name": str, "mimeType": str}, ...]
        """
        if not self.service:
            raise GoogleDriveError("No autenticado. Llame a authenticate() primero.")

        try:
            files = []
            page_token = None

            while True:
                # Construir query con condiciones OR para cada MIME type
                mime_conditions = " or ".join(
                    [f"mimeType='{mime}'" for mime in ALLOWED_IMAGE_MIMES]
                )
                query = (
                    f"'{self.source_folder_id}' in parents "
                    f"and ({mime_conditions}) "
                    "and trashed=false "
                    "and mimeType!='application/vnd.google-apps.folder'"
                )
                
                logger.debug(f"Query Drive: {query}")

                # Ejecutar en thread para no bloquear
                def execute_query():
                    return (
                        self.service.files()
                        .list(
                            q=query,
                            fields="nextPageToken, files(id, name, mimeType, size, parents)",
                            pageToken=page_token,
                            pageSize=100,
                        )
                        .execute()
                    )
                
                results = await asyncio.to_thread(execute_query)

                items = results.get("files", [])
                logger.debug(f"Página: {len(items)} archivos encontrados")
                files.extend(items)

                page_token = results.get("nextPageToken")
                if not page_token:
                    break

            logger.info(f"Encontrados {len(files)} archivos de imagen en carpeta origen (source_folder_id: {self.source_folder_id})")
            if len(files) > 0:
                logger.info(f"Primeros archivos: {[f.get('name') for f in files[:5]]}")
            elif len(files) == 0:
                # Si no hay archivos, listar TODOS los archivos (sin filtro de MIME) para diagnóstico
                logger.warning(f"No se encontraron archivos de imagen. Listando TODOS los archivos en la carpeta para diagnóstico...")
                try:
                    # Excluir carpetas explícitamente
                    all_files_query = (
                        f"'{self.source_folder_id}' in parents "
                        "and trashed=false "
                        "and mimeType!='application/vnd.google-apps.folder'"
                    )
                    all_results = await asyncio.to_thread(
                        lambda: self.service.files()
                        .list(q=all_files_query, fields="files(id, name, mimeType, size)", pageSize=20)
                        .execute()
                    )
                    all_items = all_results.get("files", [])
                    if all_items:
                        logger.info(f"Archivos encontrados en carpeta (sin filtro MIME, excluyendo carpetas):")
                        for item in all_items:
                            logger.info(
                                f"  - {item.get('name')}: "
                                f"mimeType={item.get('mimeType')}, "
                                f"size={item.get('size', 'N/A')} bytes"
                            )
                        # Verificar si hay archivos con MIME types de imagen que no están en nuestra lista
                        image_mimes_found = set()
                        for item in all_items:
                            mime = item.get('mimeType', '')
                            if mime.startswith('image/'):
                                image_mimes_found.add(mime)
                        if image_mimes_found:
                            logger.warning(
                                f"Se encontraron archivos con MIME types de imagen no incluidos en ALLOWED_IMAGE_MIMES: "
                                f"{image_mimes_found - ALLOWED_IMAGE_MIMES}"
                            )
                    else:
                        logger.warning(f"La carpeta está vacía o no se tienen permisos para listar archivos")
                except Exception as diag_err:
                    logger.warning(f"Error en diagnóstico de archivos: {diag_err}", exc_info=True)
            return files
        except HttpError as e:
            logger.error(f"Error al listar archivos en Drive: {e}")
            raise GoogleDriveError(f"Error al listar archivos: {e}") from e

    async def download_file(self, file_id: str) -> bytes:
        """Descarga un archivo desde Drive.

        Args:
            file_id: ID del archivo en Drive.

        Returns:
            Contenido del archivo como bytes.
        """
        if not self.service:
            raise GoogleDriveError("No autenticado. Llame a authenticate() primero.")

        try:
            import io

            request = self.service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.debug(
                        f"Descargando archivo {file_id}: {int(status.progress() * 100)}%"
                    )

            file_content.seek(0)
            content = file_content.read()
            logger.info(f"Archivo {file_id} descargado: {len(content)} bytes")
            return content
        except HttpError as e:
            logger.error(f"Error al descargar archivo {file_id}: {e}")
            raise GoogleDriveError(f"Error al descargar archivo: {e}") from e

    async def find_or_create_folder(
        self, parent_id: str, folder_name: str
    ) -> str:
        """Busca una carpeta por nombre dentro de un padre, o la crea si no existe.

        Args:
            parent_id: ID de la carpeta padre.
            folder_name: Nombre de la carpeta a buscar/crear.

        Returns:
            ID de la carpeta encontrada o creada.
        """
        if not self.service:
            raise GoogleDriveError("No autenticado. Llame a authenticate() primero.")

        try:
            # Buscar carpeta existente
            # Escapar comillas simples en el nombre de la carpeta para la query
            folder_name_escaped = folder_name.replace("'", "\\'")
            query = (
                f"'{parent_id}' in parents "
                f"and name='{folder_name_escaped}' "
                "and mimeType='application/vnd.google-apps.folder' "
                "and trashed=false"
            )
            
            logger.debug(f"Buscando carpeta '{folder_name}' en padre '{parent_id}' con query: {query}")

            # Ejecutar en thread para no bloquear
            def execute_query():
                return (
                    self.service.files()
                    .list(q=query, fields="files(id, name)", pageSize=1)
                    .execute()
                )
            
            results = await asyncio.to_thread(execute_query)

            folders = results.get("files", [])
            if folders:
                folder_id = folders[0]["id"]
                logger.info(f"Carpeta '{folder_name}' encontrada: {folder_id}")
                return folder_id

            # Crear carpeta si no existe
            logger.info(f"Carpeta '{folder_name}' no encontrada, creando en padre '{parent_id}'...")
            
            # Validar que parent_id es un ID válido (no un nombre)
            if not parent_id or len(parent_id) < 10:
                raise GoogleDriveError(
                    f"parent_id inválido: '{parent_id}'. Debe ser un ID de carpeta de Google Drive, no un nombre."
                )
            
            file_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
            }

            # Ejecutar en thread para no bloquear
            def create_folder():
                return (
                    self.service.files()
                    .create(body=file_metadata, fields="id")
                    .execute()
                )
            
            folder = await asyncio.to_thread(create_folder)

            folder_id = folder.get("id")
            logger.info(f"Carpeta '{folder_name}' creada: {folder_id}")
            return folder_id
        except HttpError as e:
            error_msg = str(e)
            # Detectar si los parámetros están invertidos
            if "File not found" in error_msg and parent_id and len(parent_id) < 20:
                logger.error(
                    f"Error al buscar/crear carpeta '{folder_name}' en padre '{parent_id}'. "
                    f"Posible error: los parámetros pueden estar invertidos. "
                    f"parent_id debe ser un ID de carpeta (ej: '1xznEbTmARfICOrT0pEDULBoHU6ZyEcx_'), "
                    f"no un nombre de carpeta."
                )
            else:
                logger.error(f"Error al buscar/crear carpeta '{folder_name}' en padre '{parent_id}': {e}")
            raise GoogleDriveError(
                f"Error al buscar/crear carpeta: {e}"
            ) from e

    async def move_file(self, file_id: str, target_folder_id: str) -> None:
        """Mueve un archivo a otra carpeta en Drive.

        Args:
            file_id: ID del archivo a mover.
            target_folder_id: ID de la carpeta destino.
        """
        if not self.service:
            raise GoogleDriveError("No autenticado. Llame a authenticate() primero.")

        try:
            # Obtener metadata del archivo para obtener padres actuales
            file = (
                self.service.files()
                .get(fileId=file_id, fields="parents")
                .execute()
            )

            previous_parents = ",".join(file.get("parents", []))

            # Mover archivo
            self.service.files().update(
                fileId=file_id,
                addParents=target_folder_id,
                removeParents=previous_parents,
                fields="id, parents",
            ).execute()

            logger.info(f"Archivo {file_id} movido a carpeta {target_folder_id}")
        except HttpError as e:
            logger.error(f"Error al mover archivo {file_id}: {e}")
            raise GoogleDriveError(f"Error al mover archivo: {e}") from e

