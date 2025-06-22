"""
CreatorIQ Hybrid Authentication GraphQL Client

Supports both API key and browser session authentication.
Automatically prefers API key when available.
"""

import asyncio
import json
import ssl
from typing import List, Dict, Optional, Any
import aiohttp
from src.utils.logger import setup_logger

# Import both authentication methods
from src.creatoriq.api_key_auth import get_api_key_headers, is_api_key_authenticated
from src.creatoriq.auth_headers import get_auth_headers, is_authenticated

logger = setup_logger(__name__)

class CreatorIQHybridClient:
    """
    Hybrid GraphQL client that supports both API key and browser authentication.
    
    Automatically chooses the best available authentication method.
    """
    
    def __init__(self, prefer_api_key: bool = True):
        self.base_url = "https://app.creatoriq.com/api/reporting/graphql"
        self.session = None
        self.prefer_api_key = prefer_api_key
        self.auth_method = None
        
        # Determine which authentication method to use
        self._choose_auth_method()
        
    def _choose_auth_method(self):
        """Choose the best available authentication method."""
        
        if self.prefer_api_key and is_api_key_authenticated():
            self.auth_method = 'api_key'
            logger.info("🔑 Using API Key authentication (preferred)")
        elif is_authenticated():
            self.auth_method = 'browser'
            logger.info("🌐 Using Browser session authentication")
        elif is_api_key_authenticated():
            self.auth_method = 'api_key'
            logger.info("🔑 Using API Key authentication (fallback)")
        else:
            self.auth_method = None
            logger.error("❌ No valid authentication method available")
            raise ValueError("No authentication configured. Need either API key or browser credentials.")
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers based on chosen authentication method."""
        
        if self.auth_method == 'api_key':
            headers = get_api_key_headers()
            logger.info("🔑 Using API Key headers")
        elif self.auth_method == 'browser':
            headers = get_auth_headers()
            logger.info("🌐 Using Browser session headers")
        else:
            raise ValueError("No authentication method available")
        
        return headers
    
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
    
    async def execute_query(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute GraphQL query using the chosen authentication method.
        
        Args:
            query_data: GraphQL query and variables
            
        Returns:
            GraphQL response data
            
        Raises:
            Exception: If query fails
        """
        headers = self.get_headers()
        
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
                        if self.auth_method == 'api_key':
                            error_msg = f"❌ API Key authentication failed (401). Please check your CREATORIQ_API_KEY."
                        else:
                            error_msg = f"❌ Browser authentication failed (401). Please refresh your credentials."
                    elif response.status == 403:
                        error_msg = f"❌ Access forbidden (403). Check permissions for this resource."
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

    def _build_posts_query(self, campaign_id: int, cursor: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """Build GraphQL query for campaign posts."""
        
        cursor_part = f', after: "{cursor}"' if cursor else ""
        
        query = f"""
        query {{
            campaign(id: "{campaign_id}") {{
                id
                name
                posts(first: {limit}{cursor_part}) {{
                    pageInfo {{
                        hasNextPage
                        endCursor
                    }}
                    edges {{
                        node {{
                            id
                            contentUrl
                            text
                            publishedAt
                            network
                            creator {{
                                id
                                fullName
                                primarySocialUsername
                            }}
                            combinedMetrics {{
                                combinedImpressions {{
                                    value
                                }}
                                combinedEngagements {{
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
        }}
        """
        
        return {
            "query": query.strip(),
            "variables": {}
        }

# Convenience functions for backward compatibility
async def get_campaign_posts_hybrid(campaign_id: int, max_posts: Optional[int] = None, prefer_api_key: bool = True) -> List[Dict[str, Any]]:
    """
    Get all posts for a campaign using hybrid authentication.
    
    Args:
        campaign_id: Campaign ID to fetch posts for
        max_posts: Maximum number of posts to retrieve (None for all)
        prefer_api_key: Whether to prefer API key over browser auth
        
    Returns:
        List of post dictionaries
    """
    logger.info(f"🎯 Starting hybrid GraphQL extraction for campaign {campaign_id}")
    
    posts = []
    cursor = None
    page = 1
    
    async with CreatorIQHybridClient(prefer_api_key=prefer_api_key) as client:
        
        while True:
            logger.info(f"📄 Fetching page {page} (cursor: {cursor})")
            
            query_data = client._build_posts_query(campaign_id, cursor, limit=50)
            
            try:
                result = await client.execute_query(query_data)
                
                # Extract posts from response
                campaign_data = result.get('data', {}).get('campaign')
                if not campaign_data:
                    logger.warning("No campaign data in response")
                    break
                
                posts_data = campaign_data.get('posts', {})
                edges = posts_data.get('edges', [])
                
                if not edges:
                    logger.info("No more posts found")
                    break
                
                # Process posts
                for edge in edges:
                    node = edge.get('node', {})
                    
                    # Extract metrics safely
                    combined_metrics = node.get('combinedMetrics', {})
                    organic_metrics = node.get('organicMetrics', {})
                    creator = node.get('creator', {})
                    
                    post_data = {
                        'post_id': node.get('id'),
                        'post_url': node.get('contentUrl'),
                        'platform': node.get('network'),
                        'caption': node.get('text', ''),
                        'published_date': node.get('publishedAt'),
                        'creator_name': creator.get('fullName'),
                        'creator_username': creator.get('primarySocialUsername'),
                        'impressions': combined_metrics.get('combinedImpressions', {}).get('value', 0),
                        'engagements': combined_metrics.get('combinedEngagements', {}).get('value', 0),
                        'likes': organic_metrics.get('likes', 0),
                        'comments': organic_metrics.get('comments', 0),
                        'shares': organic_metrics.get('shares', 0),
                        'video_views': organic_metrics.get('videoViews', 0)
                    }
                    
                    posts.append(post_data)
                
                logger.info(f"📊 Page {page}: Retrieved {len(edges)} posts (total: {len(posts)})")
                
                # Check for more pages
                page_info = posts_data.get('pageInfo', {})
                if not page_info.get('hasNextPage', False):
                    logger.info("🏁 No more pages available")
                    break
                
                cursor = page_info.get('endCursor')
                page += 1
                
                # Check max posts limit
                if max_posts and len(posts) >= max_posts:
                    posts = posts[:max_posts]
                    logger.info(f"📊 Reached max posts limit: {max_posts}")
                    break
                
            except Exception as e:
                logger.error(f"❌ Error on page {page}: {e}")
                raise
    
    logger.info(f"✅ Extraction complete: {len(posts)} total posts")
    return posts

def get_campaign_posts_hybrid_sync(campaign_id: int, max_posts: Optional[int] = None, prefer_api_key: bool = True) -> List[Dict[str, Any]]:
    """
    Synchronous wrapper for hybrid authentication post retrieval.
    
    Args:
        campaign_id: Campaign ID to fetch posts for
        max_posts: Maximum number of posts to retrieve (None for all)
        prefer_api_key: Whether to prefer API key over browser auth
        
    Returns:
        List of post dictionaries
    """
    return asyncio.run(get_campaign_posts_hybrid(campaign_id, max_posts, prefer_api_key))

# Test function
async def test_hybrid_client():
    """Test the hybrid client with both authentication methods."""
    logger.info("🧪 Testing CreatorIQ Hybrid Authentication Client")
    
    try:
        # Test with API key preference
        posts = await get_campaign_posts_hybrid(695483, max_posts=5, prefer_api_key=True)
        
        logger.info(f"✅ Hybrid client test successful: Retrieved {len(posts)} posts")
        
        if posts:
            sample_post = posts[0]
            logger.info("📋 Sample post data:")
            for key, value in sample_post.items():
                logger.info(f"   {key}: {value}")
        
        return posts
        
    except Exception as e:
        logger.error(f"❌ Hybrid client test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_hybrid_client()) 