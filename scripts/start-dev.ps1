# Start Backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'C:\Proyectos\NiceGrow\Growen'; .\.venv\Scripts\activate; python -m uvicorn services.api:app --reload --port 8000"

# Start Frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'C:\Proyectos\NiceGrow\Growen'; .\.venv\Scripts\activate; cd frontend; npm run dev"

Write-Host "Development environment started in two new separate terminals."
