#!/bin/bash

# Script to safely add Instagram integration to running container

echo "🔄 Adding Instagram integration to Docker container..."

# Get the new container ID
CONTAINER_ID=$(docker ps --filter "publish=8501" --format "{{.ID}}")

if [ -z "$CONTAINER_ID" ]; then
    echo "❌ No container found running on port 8501"
    exit 1
fi

echo "✅ Found container: $CONTAINER_ID"

# Wait for container to be fully ready
echo "⏳ Waiting for container to be ready..."
sleep 10

# Copy ONLY the Instagram handler
echo "📦 Copying Instagram handler..."
docker cp src/utils/instagram_handler.py $CONTAINER_ID:/app/src/utils/instagram_handler.py

# Install apify-client in the container
echo "📦 Installing apify-client..."
docker exec $CONTAINER_ID pip install apify-client

# Add Apify token to .env
echo "🔑 Adding Apify API token..."
docker exec $CONTAINER_ID sh -c "grep -q APIFY_API_TOKEN .env || echo 'APIFY_API_TOKEN=apify_api_5Qz8eDggL5YPKqezuOPOYXiD7IjCQS1gxC27r' >> .env"

echo "✅ Instagram integration added successfully!"
echo "🌐 The app should be working at http://localhost:8501"
echo ""
echo "📝 Note: The Instagram routing is already in your ingest.py from the main branch"