#!/bin/bash

echo "🔄 Rebuilding DriveShop Clip Docker container with latest changes..."

# Stop existing containers
echo "📦 Stopping existing containers..."
docker-compose down

# Remove old images to ensure fresh build
echo "🗑️ Removing old images..."
docker-compose rm -f

# Rebuild the container
echo "🏗️ Building new container..."
docker-compose build --no-cache

# Start the container
echo "🚀 Starting container..."
docker-compose up -d

# Show logs
echo "📋 Container logs (press Ctrl+C to exit):"
docker-compose logs -f app