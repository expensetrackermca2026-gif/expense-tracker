#!/usr/bin/env bash
# Exit on error
set -e

# Update pip
pip install --upgrade pip

# Install dependencies from the backend folder
pip install -r backend/requirements.txt
