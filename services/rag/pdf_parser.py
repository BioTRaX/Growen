# NG-HEADER: Nombre de archivo: pdf_parser.py
# NG-HEADER: Ubicación: services/rag/pdf_parser.py
# NG-HEADER: Descripción: Extracción de texto de archivos PDF usando PyMuPDF para Knowledge Base
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Parser de PDF para extracción de texto usando PyMuPDF (fitz)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PDFParseError(Exception):
    """Error al parsear un archivo PDF."""
    pass


def extract_text_from_pdf(file_path: Path | str) -> str:
    """
    Extraer texto de un archivo PDF.
    
    Args:
        file_path: Ruta al archivo PDF
        
    Returns:
        Texto extraído del PDF, con páginas separadas por doble salto de línea
        
    Raises:
        PDFParseError: Si el archivo no existe, está corrupto o protegido
        FileNotFoundError: Si el archivo no existe
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Archivo PDF no encontrado: {file_path}")
    
    if not file_path.suffix.lower() == '.pdf':
        raise PDFParseError(f"El archivo no tiene extensión PDF: {file_path}")
    
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise PDFParseError(
            "PyMuPDF no está instalado. Ejecutar: pip install PyMuPDF"
        ) from e
    
    try:
        doc = fitz.open(str(file_path))
    except Exception as e:
        raise PDFParseError(f"No se pudo abrir el PDF '{file_path.name}': {str(e)}") from e
    
    try:
        # Verificar si el PDF está protegido
        if doc.is_encrypted:
            raise PDFParseError(f"El PDF '{file_path.name}' está protegido con contraseña")
        
        pages_text = []
        total_pages = len(doc)
        
        for page_num in range(total_pages):
            try:
                page = doc[page_num]
                text = page.get_text("text")
                
                if text.strip():
                    pages_text.append(text.strip())
                    
            except Exception as e:
                logger.warning(
                    f"Error extrayendo texto de página {page_num + 1}/{total_pages} "
                    f"de '{file_path.name}': {str(e)}"
                )
                continue
        
        if not pages_text:
            logger.warning(
                f"No se extrajo texto del PDF '{file_path.name}'. "
                "Puede ser un PDF escaneado que requiere OCR."
            )
            return ""
        
        # Unir páginas con doble salto de línea para mejor separación de chunks
        full_text = "\n\n".join(pages_text)
        
        logger.info(
            f"Extraído texto de '{file_path.name}': "
            f"{total_pages} páginas, {len(full_text)} caracteres"
        )
        
        return full_text
        
    finally:
        doc.close()


def get_pdf_metadata(file_path: Path | str) -> dict:
    """
    Obtener metadatos de un archivo PDF.
    
    Args:
        file_path: Ruta al archivo PDF
        
    Returns:
        Dict con metadatos: title, author, subject, pages, creator, producer
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Archivo PDF no encontrado: {file_path}")
    
    try:
        import fitz
    except ImportError:
        return {"error": "PyMuPDF no instalado"}
    
    try:
        doc = fitz.open(str(file_path))
        metadata = doc.metadata or {}
        
        result = {
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "subject": metadata.get("subject", ""),
            "pages": len(doc),
            "creator": metadata.get("creator", ""),
            "producer": metadata.get("producer", ""),
            "encrypted": doc.is_encrypted,
        }
        
        doc.close()
        return result
        
    except Exception as e:
        return {"error": str(e)}


def is_pdf_readable(file_path: Path | str) -> tuple[bool, Optional[str]]:
    """
    Verificar si un PDF es legible (no corrupto ni protegido).
    
    Args:
        file_path: Ruta al archivo PDF
        
    Returns:
        Tuple (is_readable: bool, error_message: Optional[str])
    """
    try:
        text = extract_text_from_pdf(file_path)
        if not text:
            return False, "PDF sin texto extraíble (puede requerir OCR)"
        return True, None
    except FileNotFoundError as e:
        return False, str(e)
    except PDFParseError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error inesperado: {str(e)}"

