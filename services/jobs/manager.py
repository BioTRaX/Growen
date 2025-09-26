# NG-HEADER: Nombre de archivo: manager.py
# NG-HEADER: Ubicación: services/jobs/manager.py
# NG-HEADER: Descripción: Administrador y scheduler de jobs backend.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Administrador muy básico de jobs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional
import uuid


@dataclass
class Job:
    id: str
    type: str
    status: str = "pending"
    result: Optional[dict] = None


class JobManager:
    """Almacena jobs en memoria."""

    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}

    def create(self, type_: str) -> Job:
        job_id = uuid.uuid4().hex
        job = Job(id=job_id, type=type_)
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)
