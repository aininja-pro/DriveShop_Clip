#!/bin/bash

# Simplified local testing script for background jobs

echo "🚀 Local Background Jobs Testing"
echo "================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# First, integrate the Active Jobs tab into app.py
echo -e "${YELLOW}Step 1: Integrating Active Jobs into app.py...${NC}"
python3 integrate_active_jobs.py

echo ""
echo -e "${YELLOW}Step 2: Choose testing mode:${NC}"
echo "1) Test with Docker containers"
echo "2) Test directly with Python (no Docker)"
read -r -p "Enter choice (1 or 2): " choice

if [[ "$choice" == "1" ]]; then
    # Docker mode
    echo -e "${YELLOW}Starting Docker containers...${NC}"
    ./test_background_jobs_locally.sh
else
    # Direct Python mode
    echo -e "${YELLOW}Starting services directly...${NC}"
    
    # Kill any existing processes
    pkill -f "streamlit run" 2>/dev/null
    pkill -f "background_worker" 2>/dev/null
    
    # Start the dashboard
    echo -e "${GREEN}Starting dashboard...${NC}"
    streamlit run src/dashboard/app.py --server.port=8501 &
    DASHBOARD_PID=$!
    
    # Wait a moment for dashboard to start
    sleep 3
    
    # Ask about worker
    read -r -p "Start background worker? (y/n): " start_worker
    
    if [[ "$start_worker" == "y" ]]; then
        echo -e "${GREEN}Starting background worker...${NC}"
        WORKER_ID=local-worker-1 python -m src.worker.background_worker &
        WORKER_PID=$!
        
        echo ""
        echo -e "${GREEN}✅ Both services started!${NC}"
        echo "Dashboard: http://localhost:8501"
        echo "Worker PID: $WORKER_PID"
    else
        echo -e "${GREEN}✅ Dashboard started!${NC}"
        echo "Dashboard: http://localhost:8501"
        echo "Note: Jobs will be queued but not processed without a worker"
    fi
    
    echo ""
    echo "Dashboard PID: $DASHBOARD_PID"
    echo ""
    echo "Press Ctrl+C to stop all services..."
    
    # Wait for interrupt
    trap "kill $DASHBOARD_PID $WORKER_PID 2>/dev/null; exit" INT
    wait
fi