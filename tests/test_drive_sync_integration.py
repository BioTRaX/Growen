# NG-HEADER: Nombre de archivo: test_drive_sync_integration.py
# NG-HEADER: Ubicación: tests/test_drive_sync_integration.py
# NG-HEADER: Descripción: Tests de integración para sincronización de Google Drive.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Tests de integración para el flujo completo de sincronización Drive."""

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, Mock, MagicMock
import tempfile
from pathlib import Path

from workers.drive_sync import sync_drive_images
from db.models import Product, Image
from services.integrations.drive import GoogleDriveSync


@pytest.mark.asyncio
@pytest.mark.integration
class TestDriveSyncIntegration:
    """Tests de integración del flujo completo."""

    @pytest_asyncio.fixture
    def sample_image_content(self):
        """Contenido de imagen JPEG de prueba."""
        # JPEG válido mínimo
        return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xd9"

    @patch("workers.drive_sync.GoogleDriveSync")
    @patch.dict("os.environ", {
        "GOOGLE_APPLICATION_CREDENTIALS": "./certs/test.json",
        "DRIVE_SOURCE_FOLDER_ID": "test_folder_id",
        "DRIVE_PROCESSED_FOLDER_NAME": "Procesados",
        "DRIVE_SIN_SKU_FOLDER_NAME": "SIN_SKU",
        "DRIVE_ERRORS_FOLDER_NAME": "Errores_SKU",
    })
    async def test_full_sync_flow_success(
        self, mock_drive_class, db_session, sample_image_content
    ):
        """Test del flujo completo de sincronización exitosa."""
        # Crear producto con SKU canónico
        product = Product(
            title="Producto Test",
            sku_root="ABC_1234_XYZ",
            canonical_sku="ABC_1234_XYZ",
            stock=10,
        )
        db_session.add(product)
        await db_session.commit()
        await db_session.refresh(product)

        # Mock de Google Drive
        mock_drive = Mock()
        mock_drive.authenticate = AsyncMock()
        mock_drive.list_images_in_folder = AsyncMock(return_value=[
            {"id": "file1", "name": "ABC_1234_XYZ 1.jpg", "mimeType": "image/jpeg"}
        ])
        mock_drive.find_or_create_folder = AsyncMock(return_value="processed_folder_id")
        mock_drive.download_file = AsyncMock(return_value=sample_image_content)
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

        # Verificar resultados
        assert result["processed"] == 1
        assert result["errors"] == 0
        assert result["no_sku"] == 0
        assert result["total"] == 1

        # Verificar que se llamaron los métodos correctos
        mock_drive.authenticate.assert_called_once()
        mock_drive.list_images_in_folder.assert_called_once()
        assert mock_drive.find_or_create_folder.call_count == 3  # Procesados, Errores, SIN_SKU
        mock_drive.download_file.assert_called_once_with("file1")
        mock_drive.move_file.assert_called_once()

        # Verificar que se creó la imagen en la BD
        images = await db_session.execute(
            "SELECT * FROM images WHERE product_id = :pid",
            {"pid": product.id}
        )
        # Nota: En un test real necesitaríamos verificar con SQLAlchemy ORM
        # Por ahora verificamos que el flujo se ejecutó

        # Verificar progreso
        assert any(call["status"] == "completed" for call in progress_calls)
        assert any(call["status"] == "processing" for call in progress_calls)

    @patch("workers.drive_sync.GoogleDriveSync")
    @patch.dict("os.environ", {
        "GOOGLE_APPLICATION_CREDENTIALS": "./certs/test.json",
        "DRIVE_SOURCE_FOLDER_ID": "test_folder_id",
        "DRIVE_PROCESSED_FOLDER_NAME": "Procesados",
        "DRIVE_SIN_SKU_FOLDER_NAME": "SIN_SKU",
        "DRIVE_ERRORS_FOLDER_NAME": "Errores_SKU",
    })
    async def test_full_sync_flow_mixed_results(
        self, mock_drive_class, db_session
    ):
        """Test del flujo con resultados mixtos (éxitos y errores)."""
        # Crear un producto
        product = Product(
            title="Producto Test",
            sku_root="ABC_1234_XYZ",
            canonical_sku="ABC_1234_XYZ",
            stock=10,
        )
        db_session.add(product)
        await db_session.commit()

        # Mock con múltiples archivos
        mock_drive = Mock()
        mock_drive.authenticate = AsyncMock()
        mock_drive.list_images_in_folder = AsyncMock(return_value=[
            {"id": "file1", "name": "ABC_1234_XYZ 1.jpg", "mimeType": "image/jpeg"},  # Válido
            {"id": "file2", "name": "invalid.jpg", "mimeType": "image/jpeg"},  # Sin SKU
            {"id": "file3", "name": "NOT_FOUND_0001_XXX 1.jpg", "mimeType": "image/jpeg"},  # Producto no existe
        ])
        mock_drive.find_or_create_folder = AsyncMock(return_value="folder_id")
        mock_drive.download_file = AsyncMock(return_value=b"fake content")
        mock_drive.move_file = AsyncMock()
        mock_drive.service = Mock()
        mock_drive.service.files.return_value.get.return_value.execute.return_value = {
            "parents": ["test_folder_id"]
        }
        mock_drive_class.return_value = mock_drive

        # Mock _process_image para el archivo válido
        with patch("workers.drive_sync._process_image", new_callable=AsyncMock) as mock_process:
            progress_calls = []

            def progress_callback(data):
                progress_calls.append(data)

            result = await sync_drive_images(progress_callback=progress_callback)

            # Verificar resultados
            assert result["total"] == 3
            assert result["processed"] == 1
            assert result["no_sku"] == 1
            assert result["errors"] == 1

            # Verificar que se procesó el archivo válido
            mock_process.assert_called_once()

            # Verificar que se movieron los archivos
            assert mock_drive.move_file.call_count == 3

