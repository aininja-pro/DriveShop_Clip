#!/bin/bash

# Script to test background jobs locally with Docker

echo "🚀 Testing Background Jobs System Locally"
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Stop any running processes
echo -e "${YELLOW}Stopping current Docker container if running...${NC}"
docker stop driveshop-clip 2>/dev/null || true

# Rebuild the container with new code
echo -e "${YELLOW}Rebuilding Docker container with new code...${NC}"
docker build -t driveshop-clip-app . || {
    echo -e "${RED}Failed to build Docker image${NC}"
    exit 1
}

# Start the main app container
echo -e "${GREEN}Starting main application container...${NC}"
docker run -d \
    --name driveshop-clip \
    -p 8501:8501 \
    -v $(pwd):/app \
    --env-file .env \
    driveshop-clip-app || {
    echo -e "${RED}Failed to start main container${NC}"
    exit 1
}

echo -e "${GREEN}✅ Main app started on http://localhost:8501${NC}"

# Option to run worker in a separate container
echo ""
echo -e "${YELLOW}Do you want to run a background worker locally? (y/n)${NC}"
read -r response

if [[ "$response" == "y" ]]; then
    echo -e "${YELLOW}Starting background worker container...${NC}"
    
    # Run worker in a separate container
    docker run -d \
        --name driveshop-worker \
        -v $(pwd):/app \
        --env-file .env \
        -e WORKER_ID=local-worker-1 \
        driveshop-clip-app \
        python -m src.worker.background_worker || {
        echo -e "${RED}Failed to start worker container${NC}"
        echo "You can still test job submission, but jobs won't be processed"
    }
    
    echo -e "${GREEN}✅ Worker started${NC}"
    echo ""
    echo "To view worker logs: docker logs -f driveshop-worker"
fi

echo ""
echo "========================================="
echo -e "${GREEN}🎉 Local test environment ready!${NC}"
echo ""
echo "1. Open http://localhost:8501 in your browser"
echo "2. You should see the new '🚀 Active Jobs' tab"
echo "3. Try submitting a job from the sidebar"
echo "4. Monitor progress in the Active Jobs tab"
echo ""
echo "Useful commands:"
echo "  View app logs:    docker logs -f driveshop-clip"
echo "  View worker logs: docker logs -f driveshop-worker"
echo "  Stop everything:  docker stop driveshop-clip driveshop-worker"
echo ""
echo "Press Ctrl+C to stop watching logs..."

# Tail the logs
docker logs -f driveshop-clip