# FMS API Integration

## Overview

The DriveShop Clip system now includes automatic FMS (Fleet Management System) API integration for exporting approved clips. This allows clips to be sent directly to the FMS system without manual file handling.

## Configuration

### Environment Variables

Add the following to your `.env` file:

```bash
# FMS API configuration
FMS_API_TOKEN=your_api_token_here
FMS_API_STAGING_URL=https://staging.driveshop.com/api/v1/clips
FMS_API_PRODUCTION_URL=https://fms.driveshop.com/api/v1/clips
FMS_API_ENVIRONMENT=staging  # or 'production' for live system
```

**Current Staging Token**: `12e5aaa75045279d6b336cad817a12d2`

## Usage

### Dashboard Export

1. Navigate to the **Approved Queue** tab
2. Filter for "Ready to Export" clips
3. Select the clips you want to export
4. Click the **📤 FMS Export** button
5. Choose one of three options:
   - **📥 Download JSON**: Download the export file to your computer
   - **🚀 Send to FMS API**: Send clips directly to the FMS system
   - **❌ Cancel Export**: Cancel without exporting

### API Data Format

The FMS API expects clips in the following JSON format:

```json
{
  "clips": [
    {
      "activity_id": "1133103",
      "brand_fit": "brand narrative text",
      "byline": "Author Name",
      "link": "https://clip-url.com",
      "cons": "negative points",
      "impressions": 12345,
      "publication_id": "media_outlet_id",
      "overall_score": "8",
      "sentiment": "positive",
      "pros": "positive points",
      "date": "2025-06-20",
      "relevance_score": "10",
      "ai_summary": "summary text"
    }
  ]
}
```

## Testing

### Test Script

Use the provided test script to verify API connectivity:

```bash
python test_fms_api.py
```

The test script will:
1. Test the connection to the FMS API
2. Validate sample data (dry run)
3. Optionally send a test clip to the staging API

### API Environments

- **Staging**: `https://staging.driveshop.com/api/v1/clips` (for testing)
- **Production**: `https://fms.driveshop.com/api/v1/clips` (live system)

Always test with staging before switching to production.

## Error Handling

The system includes comprehensive error handling:

- **Validation Errors**: Checks required fields before sending
- **Network Errors**: Handles timeouts and connection issues
- **API Errors**: Displays detailed error messages from the FMS API
- **Logging**: All API interactions are logged for debugging

## Security

- API tokens are stored in environment variables
- HTTPS is enforced for all API communications
- Tokens are never logged or displayed in full
- Environment settings clearly indicate staging vs production

## Workflow

1. Clips are approved in Bulk Review
2. Sentiment analysis runs automatically
3. Clips appear in "Ready to Export" queue
4. User selects and exports clips via API or download
5. Exported clips move to "Recent Complete"
6. Database tracks export timestamp and status

## Troubleshooting

### Common Issues

1. **Connection Failed**: Check API token and network connectivity
2. **Validation Errors**: Ensure all required fields are present
3. **405 Method Not Allowed**: Normal response for GET test on POST-only endpoint
4. **Authentication Failed**: Verify API token is correct

### Debug Mode

Enable debug logging in the FMS API client:

```python
import logging
logging.getLogger('src.utils.fms_api').setLevel(logging.DEBUG)
```

## Future Enhancements

- Batch retry for failed clips
- Webhook notifications on successful export
- Export scheduling and automation
- Detailed export history and analytics