PNPM := $(shell which pnpm 2>/dev/null || echo "$$HOME/.local/bin/pnpm")
PLUGIN_NAME := NewSuspendMode
ZIP_NAME := $(PLUGIN_NAME).zip
DEST_DIR := $(HOME)/homebrew/plugins/$(PLUGIN_NAME)

.PHONY: all build package install clean

all: build

build:
	$(PNPM) run build

package: build
	$(PNPM) run package

install: build
	@echo "Installing to $(DEST_DIR)..."
	@mkdir -p $(DEST_DIR)
	@cp -rf dist $(DEST_DIR)/
	@cp -f plugin.json $(DEST_DIR)/
	@cp -f main.py $(DEST_DIR)/
	@cp -rf py_modules $(DEST_DIR)/
	@cp -f package.json $(DEST_DIR)/
	@if [ -d "assets" ]; then cp -rf assets $(DEST_DIR)/; fi
	@echo "Installed successfully!"
	@echo "Restart Decky service if needed: sudo systemctl restart plugin_loader"

clean:
	rm -rf dist build $(ZIP_NAME)
