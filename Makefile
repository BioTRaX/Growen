PY=python

.PHONY: crawl-doctor logs-clean admin-dev admin-logs-clean

crawl-doctor:
	$(PY) -m tools.crawl_doctor

logs-clean:
	$(PY) -m tools.clean_crawl_logs

# Convenience targets for admin work
admin-dev:
	@echo "Start backend + frontend (see README for details)"
	@echo "- Backend: use scripts/start_stack.ps1 or scripts/run_api.cmd on Windows"
	@echo "- Frontend: cd frontend && npm run dev"

admin-logs-clean:
	$(PY) scripts/clear_logs.py
