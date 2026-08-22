.PHONY: install install-audio test lint run audio devices

install:
	python -m pip install -e '.[dev]'

install-audio:
	python -m pip install -e '.[dev,audio]'

test:
	pytest

lint:
	ruff check src tests

run:
	orelhao

audio:
	orelhao --audio-loopback

devices:
	orelhao --list-audio-devices
