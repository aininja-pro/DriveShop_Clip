#!/bin/bash
echo "Starting Streamlit debug wrapper..."
exec streamlit run src/dashboard/app.py --server.port=8501 --server.address=0.0.0.0 2>&1