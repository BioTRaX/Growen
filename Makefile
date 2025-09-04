PY=python

.PHONY: crawl-doctor logs-clean

crawl-doctor:
	$(PY) -m tools.crawl_doctor

logs-clean:
	$(PY) -m tools.clean_crawl_logs
