# NG-HEADER: Nombre de archivo: test_drive_sync_worker.py
# NG-HEADER: Ubicación: tests/test_drive_sync_worker.py
# NG-HEADER: Descripción: Tests unitarios para worker de sincronización de Google Drive.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Tests unitarios para worker de sincronización de imágenes desde Google Drive."""

import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
import tempfile
import os

from workers.drive_sync import (
    extract_sku_from_filename,
    detect_mime_type,
    sync_drive_images,
)
from db.models import Product
from services.integrations.drive import GoogleDriveError


class TestExtractSkuFromFilename:
    """Tests para extracción de SKU desde nombres de archivo."""

    def test_extract_sku_valid_format(self):
        """Extrae SKU correctamente del formato 'SKU #'."""
        assert extract_sku_from_filename("ABC_1234_XYZ 1.jpg") == "ABC_1234_XYZ"
        assert extract_sku_from_filename("ROS_0123_RED 2.png") == "ROS_0123_RED"
        assert extract_sku_from_filename("SUP_0007_A1B 3.webp") == "SUP_0007_A1B"

    def test_extract_sku_direct_format(self):
        """Extrae SKU directamente si es canónico (sin número)."""
        # Ahora acepta SKU canónico directo sin espacio y número
        assert extract_sku_from_filename("ABC_1234_XYZ.jpg") == "ABC_1234_XYZ"
        assert extract_sku_from_filename("PAR_0032_PIC.jpg") == "PAR_0032_PIC"
        assert extract_sku_from_filename("ROS_0123_RED.png") == "ROS_0123_RED"

    def test_extract_sku_invalid_format(self):
        """Retorna None para formatos inválidos."""
        assert extract_sku_from_filename("imagen.jpg") is None
        assert extract_sku_from_filename("ABC123.jpg") is None
        assert extract_sku_from_filename("") is None

    def test_extract_sku_case_insensitive(self):
        """El patrón es case-insensitive pero el SKU debe ser canónico."""
        # El regex es case-insensitive, pero el SKU extraído debe validarse después
        result = extract_sku_from_filename("abc_1234_xyz 1.jpg")
        assert result == "abc_1234_xyz"  # Se extrae, pero luego se valida que sea canónico


class TestDetectMimeType:
    """Tests para detección de MIME type."""

    def test_detect_jpeg(self):
        """Detecta JPEG por magic bytes."""
        content = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        assert detect_mime_type(content, "test.jpg") == "image/jpeg"

    def test_detect_png(self):
        """Detecta PNG por magic bytes."""
        content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        assert detect_mime_type(content, "test.png") == "image/png"

    def test_detect_webp(self):
        """Detecta WebP por magic bytes."""
        content = b"RIFF\x00\x00\x00\x00WEBP"
        assert detect_mime_type(content, "test.webp") == "image/webp"

    def test_detect_gif(self):
        """Detecta GIF por magic bytes."""
        content = b"GIF87a\x00\x00\x00\x00"
        assert detect_mime_type(content, "test.gif") == "image/gif"

    def test_detect_by_extension_fallback(self):
        """Usa extensión como fallback si no detecta magic bytes."""
        content = b"fake content"
        assert detect_mime_type(content, "test.jpg") == "image/jpeg"
        assert detect_mime_type(content, "test.png") == "image/png"
        assert detect_mime_type(content, "test.webp") == "image/webp"
        assert detect_mime_type(content, "test.gif") == "image/gif"
        assert detect_mime_type(content, "test.unknown") == "application/octet-stream"


@pytest.mark.asyncio
class TestSyncDriveImages:
    """Tests para el flujo completo de sincronización."""

    @pytest_asyncio.fixture
    def mock_drive_sync(self):
        """Mock del cliente GoogleDriveSync."""
        mock = Mock()
        mock.authenticate = AsyncMock()
        mock.list_images_in_folder = AsyncMock()
        mock.download_file = AsyncMock()
        mock.move_file = AsyncMock()
        mock.find_or_create_folder = AsyncMock()
        mock.service = Mock()
        return mock

    @pytest_asyncio.fixture
    def sample_files(self):
        """Archivos de ejemplo para tests."""
        return [
            {"id": "file1", "name": "ABC_1234_XYZ 1.jpg", "mimeType": "image/jpeg"},
            {"id": "file2", "name": "ROS_0123_RED 2.png", "mimeType": "image/png"},
            {"id": "file3", "name": "invalid.jpg", "mimeType": "image/jpeg"},
            {"id": "file4", "name": "SUP_0007_A1B 1.webp", "mimeType": "image/webp"},
        ]

    @pytest_asyncio.fixture
    def product_with_canonical_sku(self, db_session):
        """Crea un producto con SKU canónico."""
        async def _create():
            product = Product(
                title="Producto Test",
                sku_root="ABC_1234_XYZ",
                canonical_sku="ABC_1234_XYZ",
                stock=10,
            )
            db_session.add(product)
            await db_session.commit()
            await db_session.refresh(product)
            return product
        return _create

    @patch("workers.drive_sync.GoogleDriveSync")
    @patch.dict(os.environ, {
        "GOOGLE_APPLICATION_CREDENTIALS": "./certs/test.json",
        "DRIVE_SOURCE_FOLDER_ID": "test_folder_id",
        "DRIVE_PROCESSED_FOLDER_NAME": "Procesados",
        "DRIVE_SIN_SKU_FOLDER_NAME": "SIN_SKU",
        "DRIVE_ERRORS_FOLDER_NAME": "Errores_SKU",
    })
    async def test_sync_no_files(self, mock_drive_class, db_session):
        """Test cuando no hay archivos para procesar."""
        mock_drive = Mock()
        mock_drive.authenticate = AsyncMock()
        mock_drive.list_images_in_folder = AsyncMock(return_value=[])
        mock_drive.find_or_create_folder = AsyncMock(return_value="folder_id")
        mock_drive.service = Mock()
        mock_drive.service.files.return_value.get.return_value.execute.return_value = {"parents": ["test_folder_id"]}
        mock_drive_class.return_value = mock_drive

        progress_calls = []

        def progress_callback(data):
            progress_calls.append(data)

        result = await sync_drive_images(progress_callback=progress_callback)

        assert result["total"] == 0
        assert result["processed"] == 0
        assert result["errors"] == 0
        assert result["no_sku"] == 0
        assert any(call["status"] == "completed" for call in progress_calls)

    @patch("workers.drive_sync.GoogleDriveSync")
    @patch("workers.drive_sync._process_image")
    @patch.dict(os.environ, {
        "GOOGLE_APPLICATION_CREDENTIALS": "./certs/test.json",
        "DRIVE_SOURCE_FOLDER_ID": "test_folder_id",
        "DRIVE_PROCESSED_FOLDER_NAME": "Procesados",
        "DRIVE_SIN_SKU_FOLDER_NAME": "SIN_SKU",
        "DRIVE_ERRORS_FOLDER_NAME": "Errores_SKU",
    })
    async def test_sync_file_no_sku_format(
        self, mock_process_image, mock_drive_class, db_session, sample_files
    ):
        """Test cuando un archivo no tiene formato SKU válido."""
        # Filtrar solo el archivo sin formato válido
        files = [f for f in sample_files if f["name"] == "invalid.jpg"]

        mock_drive = Mock()
        mock_drive.authenticate = AsyncMock()
        mock_drive.list_images_in_folder = AsyncMock(return_value=files)
        mock_drive.find_or_create_folder = AsyncMock(return_value="folder_id")
        mock_drive.move_file = AsyncMock()
        mock_drive.service = Mock()
        # Simular que el archivo está en la carpeta raíz
        mock_drive.service.files.return_value.get.return_value.execute.return_value = {
            "parents": ["test_folder_id"]
        }
        mock_drive_class.return_value = mock_drive

        progress_calls = []

        def progress_callback(data):
            progress_calls.append(data)

        result = await sync_drive_images(progress_callback=progress_callback)

        assert result["no_sku"] == 1
        assert result["processed"] == 0
        # Debe moverse a SIN_SKU
        mock_drive.move_file.assert_called_once()

    @patch("workers.drive_sync.GoogleDriveSync")
    @patch("workers.drive_sync._process_image")
    @patch.dict(os.environ, {
        "GOOGLE_APPLICATION_CREDENTIALS": "./certs/test.json",
        "DRIVE_SOURCE_FOLDER_ID": "test_folder_id",
        "DRIVE_PROCESSED_FOLDER_NAME": "Procesados",
        "DRIVE_SIN_SKU_FOLDER_NAME": "SIN_SKU",
        "DRIVE_ERRORS_FOLDER_NAME": "Errores_SKU",
    })
    async def test_sync_file_sku_not_canonical(
        self, mock_process_image, mock_drive_class, db_session
    ):
        """Test cuando un archivo tiene SKU pero no es canónico."""
        files = [{"id": "file1", "name": "abc_1234_xyz 1.jpg", "mimeType": "image/jpeg"}]

        mock_drive = Mock()
        mock_drive.authenticate = AsyncMock()
        mock_drive.list_images_in_folder = AsyncMock(return_value=files)
        mock_drive.find_or_create_folder = AsyncMock(return_value="folder_id")
        mock_drive.move_file = AsyncMock()
        mock_drive.service = Mock()
        mock_drive.service.files.return_value.get.return_value.execute.return_value = {
            "parents": ["test_folder_id"]
        }
        mock_drive_class.return_value = mock_drive

        progress_calls = []

        def progress_callback(data):
            progress_calls.append(data)

        result = await sync_drive_images(progress_callback=progress_callback)

        assert result["no_sku"] == 1  # SKU no canónico va a SIN_SKU
        assert result["processed"] == 0
        mock_drive.move_file.assert_called_once()

    @patch("workers.drive_sync.GoogleDriveSync")
    @patch("workers.drive_sync._process_image")
    @patch.dict(os.environ, {
        "GOOGLE_APPLICATION_CREDENTIALS": "./certs/test.json",
        "DRIVE_SOURCE_FOLDER_ID": "test_folder_id",
        "DRIVE_PROCESSED_FOLDER_NAME": "Procesados",
        "DRIVE_SIN_SKU_FOLDER_NAME": "SIN_SKU",
        "DRIVE_ERRORS_FOLDER_NAME": "Errores_SKU",
    })
    async def test_sync_file_product_not_found(
        self, mock_process_image, mock_drive_class, db_session
    ):
        """Test cuando el SKU es válido pero el producto no existe."""
        files = [{"id": "file1", "name": "ABC_1234_XYZ 1.jpg", "mimeType": "image/jpeg"}]

        mock_drive = Mock()
        mock_drive.authenticate = AsyncMock()
        mock_drive.list_images_in_folder = AsyncMock(return_value=files)
        mock_drive.find_or_create_folder = AsyncMock(return_value="folder_id")
        mock_drive.move_file = AsyncMock()
        mock_drive.service = Mock()
        mock_drive.service.files.return_value.get.return_value.execute.return_value = {
            "parents": ["test_folder_id"]
        }
        mock_drive_class.return_value = mock_drive

        progress_calls = []

        def progress_callback(data):
            progress_calls.append(data)

        result = await sync_drive_images(progress_callback=progress_callback)

        assert result["errors"] == 1
        assert result["processed"] == 0
        # Debe moverse a Errores_SKU
        mock_drive.move_file.assert_called_once()

    @patch("workers.drive_sync.GoogleDriveSync")
    @patch("workers.drive_sync._process_image")
    @patch.dict(os.environ, {
        "GOOGLE_APPLICATION_CREDENTIALS": "./certs/test.json",
        "DRIVE_SOURCE_FOLDER_ID": "test_folder_id",
        "DRIVE_PROCESSED_FOLDER_NAME": "Procesados",
        "DRIVE_SIN_SKU_FOLDER_NAME": "SIN_SKU",
        "DRIVE_ERRORS_FOLDER_NAME": "Errores_SKU",
    })
    async def test_sync_file_success(
        self, mock_process_image, mock_drive_class, db_session
    ):
        """Test cuando un archivo se procesa exitosamente."""
        # Crear producto primero
        product = Product(
            title="Producto Test",
            sku_root="ABC_1234_XYZ",
            canonical_sku="ABC_1234_XYZ",
            stock=10,
        )
        db_session.add(product)
        await db_session.commit()

        files = [{"id": "file1", "name": "ABC_1234_XYZ 1.jpg", "mimeType": "image/jpeg"}]

        mock_drive = Mock()
        mock_drive.authenticate = AsyncMock()
        mock_drive.list_images_in_folder = AsyncMock(return_value=files)
        mock_drive.find_or_create_folder = AsyncMock(return_value="folder_id")
        mock_drive.download_file = AsyncMock(return_value=b"fake image content")
        mock_drive.move_file = AsyncMock()
        mock_drive.service = Mock()
        mock_drive.service.files.return_value.get.return_value.execute.return_value = {
            "parents": ["test_folder_id"]
        }
        mock_drive_class.return_value = mock_drive

        # Mock _process_image para simular éxito
        mock_process_image.return_value = None

        progress_calls = []

        def progress_callback(data):
            progress_calls.append(data)

        result = await sync_drive_images(progress_callback=progress_callback)

        assert result["processed"] == 1
        assert result["errors"] == 0
        assert result["no_sku"] == 0
        # Debe llamarse _process_image
        mock_process_image.assert_called_once()
        # Debe moverse a Procesados
        assert mock_drive.move_file.call_count == 1

    @patch("workers.drive_sync.GoogleDriveSync")
    @patch.dict(os.environ, {
        "GOOGLE_APPLICATION_CREDENTIALS": "./certs/test.json",
        "DRIVE_SOURCE_FOLDER_ID": "test_folder_id",
    })
    async def test_sync_missing_credentials(self, mock_drive_class):
        """Test cuando faltan credenciales."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="GOOGLE_APPLICATION_CREDENTIALS"):
                await sync_drive_images()

    @patch("workers.drive_sync.GoogleDriveSync")
    @patch.dict(os.environ, {
        "GOOGLE_APPLICATION_CREDENTIALS": "./certs/test.json",
    })
    async def test_sync_missing_folder_id(self, mock_drive_class):
        """Test cuando falta DRIVE_SOURCE_FOLDER_ID."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./certs/test.json"
            with pytest.raises(ValueError, match="DRIVE_SOURCE_FOLDER_ID"):
                await sync_drive_images()

    @patch("workers.drive_sync.GoogleDriveSync")
    @patch.dict(os.environ, {
        "GOOGLE_APPLICATION_CREDENTIALS": "./certs/test.json",
        "DRIVE_SOURCE_FOLDER_ID": "test_folder_id",
        "DRIVE_PROCESSED_FOLDER_NAME": "Procesados",
        "DRIVE_SIN_SKU_FOLDER_NAME": "SIN_SKU",
        "DRIVE_ERRORS_FOLDER_NAME": "Errores_SKU",
    })
    async def test_sync_filters_subfolder_files(self, mock_drive_class, db_session):
        """Test que filtra archivos en subcarpetas (solo procesa archivos en raíz)."""
        # Archivos: uno en raíz, uno en subcarpeta
        files = [
            {"id": "file1", "name": "ABC_1234_XYZ 1.jpg", "mimeType": "image/jpeg"},
            {"id": "file2", "name": "ROS_0123_RED 1.jpg", "mimeType": "image/jpeg"},
        ]

        mock_drive = Mock()
        mock_drive.authenticate = AsyncMock()
        mock_drive.list_images_in_folder = AsyncMock(return_value=files)
        mock_drive.find_or_create_folder = AsyncMock(return_value="folder_id")
        mock_drive.service = Mock()
        
        # Simular que file1 está en raíz y file2 está en subcarpeta
        def mock_get_file(file_id):
            mock_file = Mock()
            if file_id == "file1":
                mock_file.execute.return_value = {"parents": ["test_folder_id"]}
            else:  # file2
                mock_file.execute.return_value = {"parents": ["test_folder_id", "subfolder_id"]}
            return mock_file
        
        mock_drive.service.files.return_value.get = mock_get_file
        mock_drive_class.return_value = mock_drive

        progress_calls = []

        def progress_callback(data):
            progress_calls.append(data)

        result = await sync_drive_images(progress_callback=progress_callback)

        # Solo debe procesar file1 (en raíz)
        # file2 está en subcarpeta, así que no se procesa
        assert result["total"] == 1

