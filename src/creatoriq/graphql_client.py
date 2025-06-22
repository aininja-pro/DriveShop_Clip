"""
CreatorIQ GraphQL Client

Direct API client for CreatorIQ reporting GraphQL endpoint.
Bypasses DOM parsing by querying the API directly.
"""

import asyncio
import json
import ssl
from typing import List, Dict, Optional, Any
import aiohttp
from src.utils.logger import setup_logger
from src.creatoriq.auth_headers import get_auth_headers, is_authenticated, validate_auth_setup

logger = setup_logger(__name__)

class CreatorIQGraphQLClient:
    """
    Direct GraphQL client for CreatorIQ reporting API.
    
    Handles pagination and data extraction from the GraphQL endpoint.
    """
    
    def __init__(self, require_auth: bool = True):
        self.base_url = "https://app.creatoriq.com/api/reporting/graphql"
        self.session = None
        self.require_auth = require_auth
        
        # Validate authentication if required
        if self.require_auth:
            try:
                validate_auth_setup()
            except ValueError as e:
                logger.warning(f"⚠️ Authentication validation failed: {e}")
                logger.warning("🔧 Set require_auth=False to use without authentication (demo mode)")
                raise
        
    async def __aenter__(self):
        """Async context manager entry."""
        # Create SSL context that handles certificate verification
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Create connector with SSL context
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(connector=connector)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    def _build_posts_query(self, campaign_id: int, cursor: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """
        Build GraphQL query for fetching posts.
        
        Args:
            campaign_id: Campaign ID to query
            cursor: Pagination cursor (None for first page)
            limit: Number of posts per page
            
        Returns:
            GraphQL query dictionary
        """
        # Build the pagination arguments
        pagination_args = f'first: {limit}'
        if cursor:
            pagination_args += f', after: "{cursor}"'
        
        query = f"""
        query GetPosts {{
            getPosts(campaignId: {campaign_id}, {pagination_args}) {{
                pageInfo {{
                    hasNextPage
                    endCursor
                }}
                edges {{
                    node {{
                        id
                        publishedAt
                        text
                        contentUrl
                        thumbnailURL
                        network
                        contentType
                        creator {{
                            id
                            fullName
                            primarySocialUsername
                        }}
                        account {{
                            socialUsername
                        }}
                        combinedMetrics {{
                            combinedImpressions {{
                                value
                            }}
                            combinedEngagements {{
                                value
                            }}
                            combinedLikes: combinedEngagements {{
                                value
                            }}
                        }}
                        organicMetrics {{
                            likes
                            comments
                            shares
                            videoViews
                        }}
                    }}
                }}
            }}
        }}
        """
        
        return {
            "query": query.strip(),
            "variables": {}
        }
    
    async def _execute_query(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute GraphQL query against CreatorIQ API.
        
        Args:
            query_data: GraphQL query and variables
            
        Returns:
            GraphQL response data
            
        Raises:
            Exception: If query fails
        """
        # Get authentication headers
        if self.require_auth:
            headers = get_auth_headers()
            logger.info("🔐 Using authenticated headers for GraphQL request")
        else:
            # Fallback headers for demo mode
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/91.0.4472.124 Safari/537.36',
                'Origin': 'https://report.driveshop.com',
                'Referer': 'https://report.driveshop.com/'
            }
            logger.info("🔓 Using demo mode headers (no authentication)")
        
        try:
            async with self.session.post(
                self.base_url,
                json=query_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    
                    # Provide helpful error messages for common issues
                    if response.status == 401:
                        error_msg = f"❌ Authentication failed (401). Please check your credentials in .env file."
                        if not self.require_auth:
                            error_msg += "\n💡 Try setting require_auth=True and configuring authentication."
                    elif response.status == 403:
                        error_msg = f"❌ Access forbidden (403). Your credentials may be expired or insufficient."
                    else:
                        error_msg = f"❌ GraphQL request failed with status {response.status}"
                    
                    logger.error(f"{error_msg}\nResponse: {error_text}")
                    raise Exception(f"{error_msg}: {error_text}")
                
                result = await response.json()
                
                # Check for GraphQL errors
                if 'errors' in result:
                    errors = result['errors']
                    error_messages = [error.get('message', str(error)) for error in errors]
                    error_msg = f"GraphQL errors: {', '.join(error_messages)}"
                    logger.error(f"❌ {error_msg}")
                    raise Exception(error_msg)
                
                return result
                
        except asyncio.TimeoutError:
            raise Exception("GraphQL request timed out")
        except Exception as e:
            logger.error(f"GraphQL query failed: {e}")
            raise
    
    def _extract_post_data(self, post_node: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract required fields from a post node.
        
        Args:
            post_node: Raw post data from GraphQL response
            
        Returns:
            Cleaned post data dictionary
        """
        # Helper function to safely get nested values
        def safe_get(obj, *keys, default=None):
            for key in keys:
                if isinstance(obj, dict) and key in obj:
                    obj = obj[key]
                else:
                    return default
            return obj
        
        # Extract creator information
        creator_name = safe_get(post_node, 'creator', 'fullName', default='Unknown')
        creator_username = (
            safe_get(post_node, 'creator', 'primarySocialUsername') or
            safe_get(post_node, 'account', 'socialUsername') or
            'unknown'
        )
        
        # Extract metrics
        impressions = safe_get(post_node, 'combinedMetrics', 'combinedImpressions', 'value', default=0)
        engagements = safe_get(post_node, 'combinedMetrics', 'combinedEngagements', 'value', default=0)
        
        # Try to get likes and comments from organic metrics, fallback to combined
        likes = (
            safe_get(post_node, 'organicMetrics', 'likes', default=0) or
            safe_get(post_node, 'combinedMetrics', 'combinedLikes', 'value', default=0)
        )
        comments = safe_get(post_node, 'organicMetrics', 'comments', default=0)
        
        return {
            'post_id': safe_get(post_node, 'id', default=''),
            'post_url': safe_get(post_node, 'contentUrl', default=''),
            'platform': safe_get(post_node, 'network', default='UNKNOWN'),
            'content_type': safe_get(post_node, 'contentType', default='UNKNOWN'),
            'creator_name': creator_name,
            'username': creator_username,
            'date': safe_get(post_node, 'publishedAt', default=''),
            'caption': safe_get(post_node, 'text', default=''),
            'impressions': int(impressions) if impressions else 0,
            'engagements': int(engagements) if engagements else 0,
            'likes': int(likes) if likes else 0,
            'comments': int(comments) if comments else 0,
            'thumbnail_url': safe_get(post_node, 'thumbnailURL', default=''),
        }
    
    async def get_all_posts(self, campaign_id: int, max_posts: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve all posts for a campaign using pagination.
        
        Args:
            campaign_id: Campaign ID to query
            max_posts: Maximum number of posts to retrieve (None for all)
            
        Returns:
            List of post dictionaries with extracted data
        """
        logger.info(f"🎯 Starting GraphQL extraction for campaign {campaign_id}")
        
        all_posts = []
        cursor = None
        page = 1
        
        while True:
            logger.info(f"📄 Fetching page {page} (cursor: {cursor[:20] + '...' if cursor else 'None'})")
            
            # Build and execute query
            query_data = self._build_posts_query(campaign_id, cursor)
            response = await self._execute_query(query_data)
            
            # Extract posts data
            posts_data = response.get('data', {}).get('getPosts', {})
            edges = posts_data.get('edges', [])
            page_info = posts_data.get('pageInfo', {})
            
            if not edges:
                logger.info("📄 No more posts found")
                break
            
            # Process posts from this page
            page_posts = []
            for edge in edges:
                post_node = edge.get('node', {})
                extracted_post = self._extract_post_data(post_node)
                page_posts.append(extracted_post)
            
            all_posts.extend(page_posts)
            logger.info(f"✅ Page {page}: Retrieved {len(page_posts)} posts (total: {len(all_posts)})")
            
            # Check if we should continue
            has_next_page = page_info.get('hasNextPage', False)
            cursor = page_info.get('endCursor')
            
            if not has_next_page:
                logger.info("📄 Reached last page")
                break
            
            if max_posts and len(all_posts) >= max_posts:
                logger.info(f"📄 Reached max posts limit ({max_posts})")
                all_posts = all_posts[:max_posts]
                break
            
            page += 1
        
        logger.info(f"🎯 GraphQL extraction complete: {len(all_posts)} posts retrieved")
        return all_posts

# Convenience functions for easy usage
async def get_campaign_posts(campaign_id: int, max_posts: Optional[int] = None, require_auth: bool = True) -> List[Dict[str, Any]]:
    """
    Convenience function to get all posts for a campaign.
    
    Args:
        campaign_id: Campaign ID to query
        max_posts: Maximum number of posts to retrieve (None for all)
        require_auth: Whether to require authentication (True for live API, False for demo)
        
    Returns:
        List of post dictionaries
    """
    async with CreatorIQGraphQLClient(require_auth=require_auth) as client:
        return await client.get_all_posts(campaign_id, max_posts)

def get_campaign_posts_sync(campaign_id: int, max_posts: Optional[int] = None, require_auth: bool = True) -> List[Dict[str, Any]]:
    """
    Synchronous wrapper for getting campaign posts.
    
    Args:
        campaign_id: Campaign ID to query
        max_posts: Maximum number of posts to retrieve (None for all)
        require_auth: Whether to require authentication (True for live API, False for demo)
        
    Returns:
        List of post dictionaries
    """
    return asyncio.run(get_campaign_posts(campaign_id, max_posts, require_auth))

# Test function
async def test_graphql_client_with_auth():
    """Test the GraphQL client with authentication."""
    logger.info("🧪 Testing GraphQL client with authentication for Audi campaign (695483)")
    
    try:
        # Test with authentication
        posts = await get_campaign_posts(695483, max_posts=10, require_auth=True)
        
        logger.info(f"✅ Authenticated test successful: Retrieved {len(posts)} posts")
        
        if posts:
            sample_post = posts[0]
            logger.info("📋 Sample post data:")
            for key, value in sample_post.items():
                logger.info(f"   {key}: {value}")
        
        return posts
        
    except Exception as e:
        logger.error(f"❌ Authenticated test failed: {e}")
        logger.info("💡 Make sure your .env file has valid CreatorIQ credentials")
        raise

async def test_graphql_client_demo():
    """Test the GraphQL client in demo mode (no auth)."""
    logger.info("🧪 Testing GraphQL client in demo mode (no authentication)")
    
    try:
        # Test without authentication (will likely fail but shows the flow)
        posts = await get_campaign_posts(695483, max_posts=10, require_auth=False)
        
        logger.info(f"✅ Demo test successful: Retrieved {len(posts)} posts")
        return posts
        
    except Exception as e:
        logger.error(f"❌ Demo test failed (expected): {e}")
        logger.info("💡 This is expected without valid authentication")
        return []

if __name__ == "__main__":
    # Test authentication first
    asyncio.run(test_graphql_client_with_auth()) 