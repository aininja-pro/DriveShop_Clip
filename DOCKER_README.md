# DriveShop Clip - Docker Setup

## Quick Start

1. **Ensure your `.env` file is configured** with all required environment variables:
   ```
   OPENAI_API_KEY=your_key_here
   SUPABASE_URL=your_supabase_url
   SUPABASE_ANON_KEY=your_supabase_key
   GOOGLE_API_KEY=your_google_api_key
   GOOGLE_CX=your_google_cx
   SCRAPFLY_API_KEY=your_scrapfly_key
   ```

2. **Build and run the container:**
   ```bash
   docker-compose up -d
   ```

3. **Access the application:**
   - Open http://localhost:8501 in your browser

## Database Migrations

Before running the application with the new sentiment analysis features, apply the database migrations:

```sql
-- Run this in your Supabase SQL editor:
-- Add sentiment_completed flag to track when sentiment analysis has been completed
ALTER TABLE clips
ADD COLUMN IF NOT EXISTS sentiment_completed BOOLEAN DEFAULT FALSE;

-- Add additional sentiment analysis fields if they don't exist
ALTER TABLE clips
ADD COLUMN IF NOT EXISTS overall_score INTEGER,
ADD COLUMN IF NOT EXISTS aspects JSONB,
ADD COLUMN IF NOT EXISTS pros TEXT[],
ADD COLUMN IF NOT EXISTS cons TEXT[],
ADD COLUMN IF NOT EXISTS recommendation TEXT,
ADD COLUMN IF NOT EXISTS key_mentions TEXT[];

-- Update existing clips with sentiment data to have sentiment_completed = true
UPDATE clips
SET sentiment_completed = TRUE
WHERE overall_sentiment IS NOT NULL
AND workflow_stage = 'complete';

-- Create index for faster queries on sentiment_completed
CREATE INDEX IF NOT EXISTS idx_clips_sentiment_completed 
ON clips(sentiment_completed, status, workflow_stage);
```

## Rebuilding After Changes

To rebuild the container after code changes:

```bash
./rebuild-docker.sh
```

Or manually:
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Viewing Logs

```bash
# View all logs
docker-compose logs

# Follow logs in real-time
docker-compose logs -f

# View specific service logs
docker-compose logs app
```

## Volumes

The following directories are mounted as volumes:
- `./data` → `/app/data` - Data files and CSVs
- `./logs` → `/app/logs` - Application logs
- `./src` → `/app/src` - Source code (for development)
- `./migrations` → `/app/migrations` - Database migrations

## Troubleshooting

1. **Port 8501 already in use:**
   ```bash
   # Find process using port 8501
   lsof -i :8501
   # Kill the process or change the port in docker-compose.yml
   ```

2. **Container won't start:**
   ```bash
   # Check logs for errors
   docker-compose logs app
   ```

3. **Permission issues:**
   ```bash
   # Ensure directories exist and have proper permissions
   mkdir -p data logs
   chmod -R 755 data logs
   ```

## New Workflow Features

The updated container includes:
- Simplified Approved Queue workflow
- Batch sentiment analysis processing
- Enhanced export functionality with sentiment data
- Visual indicators for sentiment completion status
- Integration with existing advanced GPT analysis

## Environment Variables

All environment variables are loaded from the `.env` file. Ensure you have:
- `OPENAI_API_KEY` - Required for sentiment analysis
- `SUPABASE_URL` & `SUPABASE_ANON_KEY` - Database connection
- `GOOGLE_API_KEY` & `GOOGLE_CX` - Google search functionality
- `SCRAPFLY_API_KEY` - Web scraping functionality