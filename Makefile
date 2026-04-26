# Docker image for the web app (see Dockerfile).
IMAGE ?= analog-clock-worksheets

.PHONY: build
build:
	docker build -t $(IMAGE) .
