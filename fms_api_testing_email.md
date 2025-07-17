# Email to FMS Engineer

**Subject: FMS API Testing - Getting 500 Error on Staging**

Hi [Engineer's Name],

I've been testing the FMS API integration on the staging environment, and I'm encountering a 500 Internal Server Error when sending clip data. I wanted to share my findings to help troubleshoot the issue.

## Testing Summary

**Environment Details:**
- API URL: `https://staging.driveshop.com/api/v1/clips`
- Token: `12e5aaa750...` (using the token you provided)
- Method: POST
- Header Format: `Authorization: Token {token}`

## Test Results

### Test 1: Minimal Data (Your Example)
When I send minimal data matching your example, I get a 422 error:

**Request:**
```json
{
  "clips": [{
    "activity_id": "12345",
    "link": "www.example.com"
  }]
}
```

**Response:** 
- Status: 422 Unprocessable Entity
- Body: `{"errors":"Invalid clip data"}`
- **This is good** - it shows the API is validating the data

### Test 2: Complete Data
When I send complete clip data with all fields, I get a 500 error:

**Request:**
```json
{
  "clips": [{
    "activity_id": "1181076",
    "brand_fit": "The 2024 Hyundai Sonata N Line delivers an impressive blend of performance and practicality, living up to Hyundai's reputation for value-packed vehicles. The turbocharged engine provides satisfying acceleration while maintaining reasonable fuel economy. The N Line's sport-tuned suspension strikes a good balance between handling prowess and daily comfort. Interior quality exceeds expectations for the price point, with a user-friendly infotainment system and ample passenger space. While not a full N model, this Sonata offers genuine driving enthusiasm without sacrificing the practicality that buyers expect from a midsize sedan.",
    "byline": "Matthew Dixon",
    "link": "https://www.youtube.com/watch?v=Qa3Gvj8r0cI",
    "cons": "Transmission can be hesitant during aggressive downshifts. Road noise is noticeable at highway speeds. Rear seat headroom may be tight for taller passengers.",
    "impressions": 245633,
    "publication_id": "youtube_001",
    "overall_score": "9",
    "sentiment": "positive",
    "pros": "Powerful and efficient turbocharged engine provides excellent acceleration. Well-tuned suspension balances sportiness with comfort. High-quality interior with intuitive technology features. Excellent value proposition in the sport sedan segment.",
    "date": "2025-03-15",
    "relevance_score": "10",
    "ai_summary": "Matthew Dixon's review of the 2024 Hyundai Sonata N Line praises its impressive performance-to-value ratio, highlighting the turbocharged engine's power, well-balanced suspension, and high-quality interior. While noting minor issues with transmission response and road noise, he concludes it's an excellent choice for buyers seeking driving excitement without sacrificing practicality."
  }]
}
```

**Response:**
- Status: 500 Internal Server Error
- Body: HTML error page "We're sorry, but something went wrong"

## What This Tells Us

1. **Authentication is working correctly** - I'm getting past the auth check
2. **The endpoint exists and is processing requests** - It returns 422 for invalid data
3. **There appears to be a server-side error** when processing complete clip data

## My Integration Details

I've implemented the integration exactly as specified:
- POST to the clips endpoint
- Authorization header with "Token {token}" format
- JSON payload with clips array
- All the fields from our export mapping

The same JSON data that causes the 500 error works perfectly when downloaded as a file, so I'm confident the data structure is correct.

## Questions

1. Is there a specific format or constraint for any of the fields that might be causing the error?
2. Are there any required fields I'm missing?
3. Can you check the server logs for the request ID `69415df3-5a2d-45be-8205-4934102f0b9f` to see what's causing the 500 error?
4. Is the staging API fully deployed and ready for testing?

I'm happy to test any adjustments or provide additional information. The JSON download feature is working great in the meantime, but I wanted to make sure the direct API integration is ready before we move to production.

Thanks for your help!

Best regards,
[Your name]

---

## Additional Technical Details (if needed)

**Full request headers:**
```
Authorization: Token 12e5aaa75045279d6b336cad817a12d2
Content-Type: application/json
```

**Testing was done using:**
- Python requests library
- Direct API calls (no proxy or additional middleware)
- Both from local environment and Docker container

**What I've verified:**
- ✅ Token is being sent correctly
- ✅ Content-Type is set to application/json
- ✅ JSON is valid and properly formatted
- ✅ All field names match the specification
- ✅ Network connectivity to staging server is working