#!/bin/sh

# Nightly job for DriveShop Clip Tracking

# Set working directory
cd /app

# Log start time
echo "Starting nightly run at $(date)"

# Run the ingest script
python -m src.ingest.ingest

# Log completion
echo "Completed nightly run at $(date)" 