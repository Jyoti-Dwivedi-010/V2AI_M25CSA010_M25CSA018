PYTHONPATH := src

.PHONY: install lint test api ui pipeline video eval register drift cleanup docker-up docker-gpu

install:
	python -m pip install --upgrade pip
	pip install -r requirements.txt

lint:
	ruff check src tests scripts

test:
	PYTHONPATH=$(PYTHONPATH) pytest -q

api:
	PYTHONPATH=$(PYTHONPATH) uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload

ui:
	PYTHONPATH=$(PYTHONPATH) streamlit run src/ui/streamlit_app.py

pipeline:
	PYTHONPATH=$(PYTHONPATH) python scripts/run_full_pipeline.py

video:
	PYTHONPATH=$(PYTHONPATH) python scripts/process_video_session.py $(VIDEO)

eval:
	PYTHONPATH=$(PYTHONPATH) python -m app.experiments.evaluate_rag

register:
	PYTHONPATH=$(PYTHONPATH) python -m app.experiments.register_model

drift:
	PYTHONPATH=$(PYTHONPATH) python -m app.monitoring.drift_check

cleanup:
	PYTHONPATH=$(PYTHONPATH) python scripts/cleanup_sessions.py --retention-days $(DAYS)

docker-up:
	docker compose up --build

docker-gpu:
	docker compose --profile gpu up --build
