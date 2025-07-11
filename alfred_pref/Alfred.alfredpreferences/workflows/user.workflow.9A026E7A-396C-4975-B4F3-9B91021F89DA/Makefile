PROJECT_NAME := AlfredIsengard
WORKFLOW_NAMESPACE := "com.sanjams.alfred.isengard"
WORKFLOWS_DIR := $(if $(ALFRED_WORKFLOWS_DIR),$(ALFRED_WORKFLOWS_DIR),/Users/$(USER)/Library/Application\ Support/Alfred/Alfred.alfredpreferences/workflows)
CURRENT_WORKFLOW_DIRS := $(shell grep -l "$(WORKFLOW_NAMESPACE)" $(WORKFLOWS_DIR)/*/info.plist | sed -e 's/ /\\ /g')
WORKFLOW_OUTPUT_LOCATION := build/$(PROJECT_NAME).alfredworkflow
UUID := $(shell uuidgen)
PWD := $(shell pwd)

.PHONY: build

build:
	@echo "Building binary"
	@echo "Using go at path: $(shell which go)"
	@echo "GOROOT: $(GOROOT)"
	GOOS=darwin GOROOT=$(shell brazil-path \[GoLang\]run.libfarm)/lib GOCACHE=$(shell brazil-path package-build-root)/private/tmp/go-build go build -o out/alfred-isengard src/*.go

build-local:
	/usr/local/bin/go build -o out/alfred-isengard src/*.go

clean:
	rm -rf out/*
	rm -rf build

alfred: build-local
	mkdir -p build
	zip -r -X $(WORKFLOW_OUTPUT_LOCATION) * -x "build/*" -x "src/*" -x "*.alfredworkflow"
	cp $(WORKFLOW_OUTPUT_LOCATION) .

clear-current-workflows:
	for f in $(CURRENT_WORKFLOW_DIRS); do \
		echo $$f | sed -e 's/ /\\ /g' | xargs dirname | xargs -I {} rm -rf "{}" ; \
	done
	ls -l $(WORKFLOWS_DIR)

develop: clear-current-workflows build 
	ln -s $(PWD) $(WORKFLOWS_DIR)/user.workflow.$(UUID)

test: clear-current-workflows alfred
	open $(WORKFLOW_OUTPUT_LOCATION)

release: build
	mkdir -p build
	zip -r -X $(WORKFLOW_OUTPUT_LOCATION) * -x "build/*" -x "src/*" -x "*.alfredworkflow"

