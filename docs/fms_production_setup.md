# FMS API Production Configuration

## Environment Variables

For production deployment, set the following environment variables:

### Staging Configuration (Testing)
```
FMS_API_TOKEN=12e5aaa75045279d6b336cad817a12d2
FMS_API_STAGING_URL=https://staging.driveshop.com/api/v1/clips
FMS_API_PRODUCTION_URL=https://fms.driveshop.com/api/v1/clips
FMS_API_ENVIRONMENT=staging
```

### Production Configuration (Live)
```
FMS_API_TOKEN=1359d1a466b03fa89891323061e61529
FMS_API_STAGING_URL=https://staging.driveshop.com/api/v1/clips
FMS_API_PRODUCTION_URL=https://fms.driveshop.com/api/v1/clips
FMS_API_ENVIRONMENT=production
```

## Deployment Instructions

### Render
1. Go to your Render dashboard
2. Navigate to your DriveShop_Clip service
3. Click on "Environment" in the left sidebar
4. Update/Add the environment variables listed above
5. Save changes (Render will automatically redeploy)

### Local Docker
1. Update your `.env` file with the appropriate configuration
2. Rebuild the container: `docker compose down && docker compose up -d --build`

## Visual Indicators

- **Staging**: Shows blue info message "🔧 FMS API Environment: STAGING (Testing)"
- **Production**: Shows red warning "🚨 FMS API Environment: PRODUCTION (Live System)"

## Important Notes

- The `.env` file is intentionally excluded from version control for security
- Always verify the environment indicator before sending clips
- Production sends to the live FMS system where clients can see the data
- Test thoroughly in staging before switching to production