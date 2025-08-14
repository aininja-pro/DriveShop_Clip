#!/bin/bash

# Update Docker container with enhanced date filtering
echo "🚀 Updating DriveShop Clip Docker container with enhanced date filtering..."
echo "============================================================"

# Set variables
CONTAINER_NAME="driveshop-clip"
IMAGE_NAME="driveshop-clip"

# Stop the running container if it exists
echo "🛑 Stopping existing container..."
docker stop $CONTAINER_NAME 2>/dev/null || echo "Container not running"

# Remove the old container
echo "🗑️  Removing old container..."
docker rm $CONTAINER_NAME 2>/dev/null || echo "No container to remove"

# Build the new image
echo "🔨 Building new Docker image with enhanced date filtering..."
docker build -t $IMAGE_NAME . || {
    echo "❌ Docker build failed!"
    exit 1
}

# Run the new container
echo "🚀 Starting new container..."
docker run -d \
    --name $CONTAINER_NAME \
    -p 8501:8501 \
    -v $(pwd)/data:/app/data \
    -v $(pwd)/logs:/app/logs \
    -v $(pwd)/.env:/app/.env \
    --restart unless-stopped \
    $IMAGE_NAME || {
    echo "❌ Failed to start container!"
    exit 1
}

# Wait for container to be healthy
echo "⏳ Waiting for container to be ready..."
sleep 5

# Check if container is running
if docker ps | grep -q $CONTAINER_NAME; then
    echo "✅ Container is running!"
    echo ""
    echo "📊 Enhanced Date Filtering Features Added:"
    echo "  - YouTube relative date parser (e.g., '2 days ago')"
    echo "  - Platform-aware date filtering"
    echo "  - 18-month absolute age limit"
    echo "  - Smart URL pattern detection for old content"
    echo "  - Preserves good YouTube content without dates"
    echo ""
    echo "🌐 Access the dashboard at: http://localhost:8501"
    echo ""
    
    # Show container logs
    echo "📋 Recent container logs:"
    docker logs --tail 20 $CONTAINER_NAME
else
    echo "❌ Container failed to start!"
    echo "📋 Container logs:"
    docker logs $CONTAINER_NAME
    exit 1
fi

echo ""
echo "✅ Docker container update complete!"