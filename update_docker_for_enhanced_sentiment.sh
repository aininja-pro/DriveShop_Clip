#!/bin/bash

echo "🚀 Updating Docker container with enhanced sentiment analysis..."

# Get the container ID for port 8501
CONTAINER_ID=$(docker ps -q --filter "publish=8501")

if [ -z "$CONTAINER_ID" ]; then
    echo "❌ No container found running on port 8501"
    exit 1
fi

echo "📦 Found container: $CONTAINER_ID"

# Copy the new enhanced sentiment analysis files
echo "📄 Copying enhanced sentiment analysis files..."

# Copy the main enhanced analysis module
docker cp src/analysis/gpt_analysis_enhanced.py $CONTAINER_ID:/app/src/analysis/gpt_analysis_enhanced.py

# Copy the OpenAI v1.x compatible version
docker cp src/analysis/gpt_analysis_enhanced_v1.py $CONTAINER_ID:/app/src/analysis/gpt_analysis_enhanced_v1.py

# Copy the updated sentiment analysis utility
docker cp src/utils/sentiment_analysis.py $CONTAINER_ID:/app/src/utils/sentiment_analysis.py

# Copy the sentiment manager for future use
docker cp src/analysis/sentiment_manager.py $CONTAINER_ID:/app/src/analysis/sentiment_manager.py

# Copy the updated database utility with enhanced sentiment storage
docker cp src/utils/database.py $CONTAINER_ID:/app/src/utils/database.py

echo "✅ Files copied successfully"

# Restart the Streamlit app inside the container
echo "🔄 Restarting Streamlit app..."
docker exec $CONTAINER_ID pkill -f streamlit
sleep 2

# The supervisor should automatically restart it, but let's make sure
docker exec -d $CONTAINER_ID streamlit run src/dashboard/app.py --server.port 8501 --server.address 0.0.0.0

echo "✅ Container updated successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Go to http://localhost:8501"
echo "2. Navigate to Bulk Review"
echo "3. Approve a clip"
echo "4. Check if sentiment analysis runs automatically"
echo "5. Look for enhanced extraction in the logs"
echo ""
echo "🔍 To monitor logs:"
echo "docker logs -f $CONTAINER_ID"