VENV := venv
PYTHON := $(shell test -x $(VENV)/bin/python && echo $(VENV)/bin/python || echo python3)
PIP := $(shell test -x $(VENV)/bin/pip && echo $(VENV)/bin/pip || echo pip3)

install:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt

api:
	$(PYTHON) -m backend.main

run:
	$(PYTHON) -m bot.main

dev:
	$(PYTHON) -m bot.main

cities:
	$(PYTHON) -m scout.city_loader

scout:
	$(PYTHON) -m scout.main $(CITY)

tg-auth:
	$(PYTHON) -m scout.tg_auth $(if $(SESSION),--session $(SESSION),)

tg-scout:
	$(PYTHON) -m scout.main --tg $(CITY)

clean:
	rm -rf $(VENV)
	rm -f data/news.db
