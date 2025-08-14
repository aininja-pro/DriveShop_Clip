#!/bin/bash

# Script to update running Docker container with Instagram integration code

echo "🔄 Updating Docker container with Instagram integration..."

# Find the container ID running on port 8501
CONTAINER_ID=$(docker ps --filter "publish=8501" --format "{{.ID}}")

if [ -z "$CONTAINER_ID" ]; then
    echo "❌ No container found running on port 8501"
    exit 1
fi

echo "✅ Found container: $CONTAINER_ID"

# Copy the Instagram handler
echo "📦 Copying Instagram handler..."
docker cp src/utils/instagram_handler.py $CONTAINER_ID:/app/src/utils/instagram_handler.py

# Copy updated ingest files
echo "📦 Copying updated ingest files..."
docker cp src/ingest/ingest.py $CONTAINER_ID:/app/src/ingest/ingest.py
docker cp src/ingest/ingest_database.py $CONTAINER_ID:/app/src/ingest/ingest_database.py

# Install apify-client in the container
echo "📦 Installing apify-client in container..."
docker exec $CONTAINER_ID pip install apify-client

# Restart the Streamlit app to pick up changes
echo "🔄 Restarting Streamlit app..."
docker exec $CONTAINER_ID pkill -f streamlit || true
sleep 2

# The container should auto-restart streamlit, but if not:
docker exec -d $CONTAINER_ID streamlit run Home.py --server.port=8501 --server.address=0.0.0.0

echo "✅ Container updated successfully!"
echo "🌐 Access the app at http://localhost:8501"
echo ""
echo "⚠️  Make sure to add APIFY_API_TOKEN to your .env file inside the container:"
echo "   docker exec -it $CONTAINER_ID sh"
echo "   echo 'APIFY_API_TOKEN=your_token_here' >> .env"