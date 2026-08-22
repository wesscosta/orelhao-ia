.PHONY: install install-stt test lint run audio-devices audio-loopback stt-test

install:
	pip install -e '.[dev,audio]'

install-stt:
	pip install -e '.[dev,audio,stt]'

test:
	pytest -q

lint:
	ruff check src tests

run:
	orelhao

audio-devices:
	orelhao --list-audio-devices

audio-loopback:
	orelhao --audio-loopback

stt-test:
	orelhao --stt-test
