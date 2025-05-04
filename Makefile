# Yuzito Makefile

# Detect OS
ifeq ($(OS),Windows_NT)
    DETECTED_OS := Windows
    PYTHON := python
    VENV_ACTIVATE := .venv\Scripts\activate
    RM_CMD := rd /s /q
    MKDIR_CMD := mkdir
    DAEMON_TOOL := nssm
else
    DETECTED_OS := $(shell uname -s)
    PYTHON := python3
    VENV_ACTIVATE := .venv/bin/activate
    RM_CMD := rm -rf
    MKDIR_CMD := mkdir -p
    DAEMON_TOOL := systemctl
endif

.PHONY: help init clean build install install-daemon

# Default target
help:
	@echo "Yuzito Makefile Help"
	@echo "===================="
	@echo "Available targets:"
	@echo "  help         - Show this help message"
	@echo "  init         - Initialize virtual environment"
	@echo "  clean        - Remove build artifacts"
	@echo "  build        - Build the package"
	@echo "  install      - Install the package"
	@echo "  install-daemon - Install as daemon/service"

# Initialize virtual environment
init:
	@echo "Initializing virtual environment (.venv)..."
	$(PYTHON) -m venv .venv
ifeq ($(DETECTED_OS),Windows)
	@echo "Activating virtual environment and installing dependencies..."
	.venv\Scripts\pip install -e .[dev]
else
	@echo "Activating virtual environment and installing dependencies..."
	. $(VENV_ACTIVATE) && pip install -e .[dev]
endif
	@echo "Virtual environment initialized successfully."

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
ifeq ($(DETECTED_OS),Windows)
	if exist build $(RM_CMD) build
	if exist dist $(RM_CMD) dist
	if exist *.egg-info $(RM_CMD) *.egg-info
	if exist .pytest_cache $(RM_CMD) .pytest_cache
	if exist __pycache__ $(RM_CMD) __pycache__
	for /d /r . %%d in (__pycache__) do @if exist "%%d" $(RM_CMD) "%%d"
else
	$(RM_CMD) build dist *.egg-info .pytest_cache __pycache__
	find . -name __pycache__ -exec $(RM_CMD) {} +
	find . -name "*.pyc" -delete
endif
	@echo "Clean completed."

# Build the package
build: clean
	@echo "Building the package..."
ifeq ($(DETECTED_OS),Windows)
	if not exist dist $(MKDIR_CMD) dist
	.venv\Scripts\pip install build
	.venv\Scripts\python -m build
else
	$(MKDIR_CMD) dist
	. $(VENV_ACTIVATE) && pip install build && python -m build
endif
	@echo "Build completed. Check the dist directory."

# Install the package
install:
	@echo "Installing the package..."
ifeq ($(DETECTED_OS),Windows)
	.venv\Scripts\pip install -e .
else
	. $(VENV_ACTIVATE) && pip install -e .
endif
	@echo "Installation completed."

# Install as daemon/service
install-daemon:
	@echo "Installing as daemon/service..."
ifeq ($(DETECTED_OS),Windows)
	@echo "Installing as Windows service using NSSM..."
	@echo "You may need to install NSSM first: https://nssm.cc/"
	@echo "Command (to run manually):"
	@echo "nssm install Yuzito \"$(CURDIR)\.venv\Scripts\yuzito.exe\" --self-hosted"
	@echo "nssm set Yuzito DisplayName \"Yuzito RTMP Streamer\""
	@echo "nssm set Yuzito Description \"Raspberry Pi Camera RTMP Streaming Service\""
	@echo "nssm set Yuzito Start SERVICE_AUTO_START"
else
	@echo "Installing as Linux systemd service..."
	@echo "[Unit]" > yuzito.service
	@echo "Description=Yuzito RTMP Streamer" >> yuzito.service
	@echo "After=network.target" >> yuzito.service
	@echo "" >> yuzito.service
	@echo "[Service]" >> yuzito.service
	@echo "Type=simple" >> yuzito.service
	@echo "User=$(USER)" >> yuzito.service
	@echo "WorkingDirectory=$(CURDIR)" >> yuzito.service
	@echo "ExecStart=$(CURDIR)/$(VENV_ACTIVATE) && yuzito --self-hosted" >> yuzito.service
	@echo "Restart=on-failure" >> yuzito.service
	@echo "RestartSec=5s" >> yuzito.service
	@echo "" >> yuzito.service
	@echo "[Install]" >> yuzito.service
	@echo "WantedBy=multi-user.target" >> yuzito.service
	@echo "Service file created at $(CURDIR)/yuzito.service"
	@echo "To install, run (requires sudo):"
	@echo "sudo cp $(CURDIR)/yuzito.service /etc/systemd/system/"
	@echo "sudo systemctl daemon-reload"
	@echo "sudo systemctl enable yuzito"
	@echo "sudo systemctl start yuzito"
endif
	@echo "Daemon installation instructions completed."