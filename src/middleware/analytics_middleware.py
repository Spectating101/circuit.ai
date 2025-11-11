"""
Analytics Middleware

Automatically tracks:
- HTTP requests
- User sessions
- Page views
- API calls
- Feature usage
"""

import time
import uuid
from typing import Callable, Optional
from datetime import datetime
from fastapi import Request, Response
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from loguru import logger
import asyncio

from src.analytics.analytics_service_v2 import analytics_service_v2


class AnalyticsMiddleware(BaseHTTPMiddleware):
    """Middleware to track analytics events."""

    def __init__(self, app: ASGIApp, track_all_requests: bool = True):
        """
        Initialize analytics middleware.

        Args:
            app: ASGI application
            track_all_requests: Whether to track all HTTP requests
        """
        super().__init__(app)
        self.track_all_requests = track_all_requests
        logger.info("AnalyticsMiddleware initialized")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and track analytics.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            Response
        """
        start_time = time.time()

        # Extract user info from request
        user_id = self._get_user_id(request)
        session_id = self._get_session_id(request)

        # Process request
        response = await call_next(request)

        # Calculate processing time
        processing_time = time.time() - start_time

        # Track request asynchronously (don't block response)
        if self.track_all_requests and user_id:
            asyncio.create_task(
                self._track_request(
                    request=request,
                    response=response,
                    user_id=user_id,
                    session_id=session_id,
                    processing_time=processing_time
                )
            )

        # Add timing header
        response.headers["X-Process-Time"] = str(processing_time)

        return response

    async def _track_request(
        self,
        request: Request,
        response: Response,
        user_id: str,
        session_id: str,
        processing_time: float
    ):
        """
        Track request as analytics event.

        Args:
            request: HTTP request
            response: HTTP response
            user_id: User ID
            session_id: Session ID
            processing_time: Request processing time
        """
        try:
            # Determine event name from endpoint
            event_name = self._get_event_name(request)

            if event_name:
                properties = {
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": response.status_code,
                    "processing_time_ms": int(processing_time * 1000),
                    "query_params": dict(request.query_params),
                }

                # Track event
                await analytics_service_v2.track_event(
                    user_id=user_id,
                    event_name=event_name,
                    session_id=session_id,
                    properties=properties,
                    page_url=str(request.url),
                    referrer=request.headers.get("referer"),
                    user_agent=request.headers.get("user-agent"),
                    ip_address=self._get_client_ip(request)
                )

                logger.debug(f"Tracked event: {event_name} for user {user_id}")

        except Exception as e:
            logger.error(f"Error tracking analytics event: {e}")

    def _get_user_id(self, request: Request) -> Optional[str]:
        """
        Extract user ID from request.

        Args:
            request: HTTP request

        Returns:
            User ID or None
        """
        # Try to get from request state (set by auth middleware)
        if hasattr(request.state, "user_id"):
            return request.state.user_id

        # Try to get from headers (API key authentication)
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # TODO: Lookup user ID from API key
            return None

        # Try to get from cookie/session
        session_cookie = request.cookies.get("session_id")
        if session_cookie:
            # TODO: Lookup user ID from session
            return None

        return None

    def _get_session_id(self, request: Request) -> str:
        """
        Get or create session ID.

        Args:
            request: HTTP request

        Returns:
            Session ID
        """
        # Try to get from request state
        if hasattr(request.state, "session_id"):
            return request.state.session_id

        # Try to get from cookie
        session_id = request.cookies.get("session_id")
        if session_id:
            return session_id

        # Generate new session ID
        return str(uuid.uuid4())

    def _get_event_name(self, request: Request) -> Optional[str]:
        """
        Determine event name from request.

        Args:
            request: HTTP request

        Returns:
            Event name or None
        """
        path = request.url.path
        method = request.method

        # Map endpoints to event names
        event_mapping = {
            ("/api/analyze", "POST"): "analysis.started",
            ("/api/analyze/", "POST"): "analysis.started",
            ("/api/bom/generate", "POST"): "bom.generated",
            ("/api/bom/generate/", "POST"): "bom.generated",
            ("/api/schematic/generate", "POST"): "schematic.generated",
            ("/api/schematic/generate/", "POST"): "schematic.generated",
            ("/api/video/analyze", "POST"): "video.analyzed",
            ("/api/video/analyze/", "POST"): "video.analyzed",
            ("/api/auth/signup", "POST"): "user.signup",
            ("/api/auth/signup/", "POST"): "user.signup",
            ("/api/auth/login", "POST"): "user.login",
            ("/api/auth/login/", "POST"): "user.login",
            ("/api/auth/logout", "POST"): "user.logout",
            ("/api/auth/logout/", "POST"): "user.logout",
            ("/api/subscription/create", "POST"): "subscription.created",
            ("/api/subscription/create/", "POST"): "subscription.created",
            ("/api/subscription/upgrade", "POST"): "subscription.upgraded",
            ("/api/subscription/upgrade/", "POST"): "subscription.upgraded",
            ("/api/subscription/cancel", "POST"): "subscription.canceled",
            ("/api/subscription/cancel/", "POST"): "subscription.canceled",
        }

        event_name = event_mapping.get((path, method))

        # Generic page view tracking for GET requests
        if not event_name and method == "GET":
            if path.startswith("/api/"):
                event_name = f"api.{path.replace('/api/', '').replace('/', '.')}"
            else:
                event_name = "page.view"

        return event_name

    def _get_client_ip(self, request: Request) -> str:
        """
        Get client IP address.

        Args:
            request: HTTP request

        Returns:
            IP address
        """
        # Check for proxy headers
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to direct connection
        if request.client:
            return request.client.host

        return "unknown"


class FeatureTrackingRoute(APIRoute):
    """
    Custom route class to track feature usage.

    Use this for specific endpoints that need granular tracking.
    """

    def __init__(self, *args, feature_name: Optional[str] = None, **kwargs):
        """
        Initialize feature tracking route.

        Args:
            feature_name: Name of feature to track
        """
        super().__init__(*args, **kwargs)
        self.feature_name = feature_name

    def get_route_handler(self) -> Callable:
        """Get route handler with feature tracking."""
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            """Custom handler that tracks feature usage."""
            # Get user ID
            user_id = None
            if hasattr(request.state, "user_id"):
                user_id = request.state.user_id

            # Execute original handler
            start_time = time.time()
            response = await original_route_handler(request)
            processing_time = time.time() - start_time

            # Track feature usage
            if user_id and self.feature_name:
                asyncio.create_task(
                    self._track_feature(
                        user_id=user_id,
                        feature_name=self.feature_name,
                        request=request,
                        response=response,
                        processing_time=processing_time
                    )
                )

            return response

        return custom_route_handler

    async def _track_feature(
        self,
        user_id: str,
        feature_name: str,
        request: Request,
        response: Response,
        processing_time: float
    ):
        """Track feature usage."""
        try:
            session_id = str(uuid.uuid4())
            if hasattr(request.state, "session_id"):
                session_id = request.state.session_id

            await analytics_service_v2.track_event(
                user_id=user_id,
                event_name=f"feature.{feature_name}",
                session_id=session_id,
                properties={
                    "processing_time_ms": int(processing_time * 1000),
                    "status_code": response.status_code
                }
            )

            logger.debug(f"Tracked feature usage: {feature_name} for user {user_id}")

        except Exception as e:
            logger.error(f"Error tracking feature usage: {e}")


# Helper function to add analytics middleware to FastAPI app
def add_analytics_middleware(app, track_all_requests: bool = True):
    """
    Add analytics middleware to FastAPI app.

    Args:
        app: FastAPI application
        track_all_requests: Whether to track all requests

    Example:
        from fastapi import FastAPI
        from src.middleware.analytics_middleware import add_analytics_middleware

        app = FastAPI()
        add_analytics_middleware(app)
    """
    app.add_middleware(AnalyticsMiddleware, track_all_requests=track_all_requests)
    logger.info("Analytics middleware added to application")
