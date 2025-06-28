FROM python:3.11

WORKDIR /app

# Copy requirements file
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright chromium (without --with-deps to avoid system package issues)
RUN playwright install chromium

# Copy source code and assets
COPY . .

# Create directories
RUN mkdir -p data/fixtures logs

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Run Streamlit
CMD ["streamlit", "run", "src/dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"] 