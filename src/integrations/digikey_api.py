"""
Digi-Key API Integration

Provides:
- Part search
- Pricing and availability
- Datasheet links
- Alternative parts
"""

import os
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import aiohttp
from loguru import logger

@dataclass
class DigiKeyPart:
    """Digi-Key part information."""
    part_number: str
    manufacturer: str
    description: str
    category: str

    # Pricing
    unit_price: float
    price_breaks: List[Dict[str, Any]]
    currency: str = "USD"

    # Availability
    quantity_available: int
    minimum_order_quantity: int
    lead_time_days: Optional[int] = None

    # Links
    datasheet_url: Optional[str] = None
    product_url: Optional[str] = None

    # Specifications
    specifications: Dict[str, str] = None

    # Alternatives
    alternatives: List[str] = None


class DigiKeyAPI:
    """
    Digi-Key API client.

    Requires:
    - DIGIKEY_CLIENT_ID
    - DIGIKEY_CLIENT_SECRET
    - DIGIKEY_API_URL (default: https://api.digikey.com/v1)
    """

    BASE_URL = "https://api.digikey.com/v1"

    def __init__(self):
        """Initialize Digi-Key API client."""
        self.client_id = os.getenv("DIGIKEY_CLIENT_ID")
        self.client_secret = os.getenv("DIGIKEY_CLIENT_SECRET")
        self.api_url = os.getenv("DIGIKEY_API_URL", self.BASE_URL)

        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None

        if not self.client_id or not self.client_secret:
            logger.warning("⚠️ Digi-Key API credentials not configured")

    async def _get_access_token(self) -> str:
        """Get OAuth access token."""
        if self._access_token and self._token_expires_at:
            import time
            if time.time() < self._token_expires_at - 60:  # 1 minute buffer
                return self._access_token

        # Request new token
        token_url = "https://api.digikey.com/v1/oauth2/token"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials"
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self._access_token = data["access_token"]

                    import time
                    self._token_expires_at = time.time() + data["expires_in"]

                    logger.info("Obtained Digi-Key access token")
                    return self._access_token
                else:
                    error = await response.text()
                    logger.error(f"Failed to get Digi-Key token: {error}")
                    raise Exception(f"Digi-Key authentication failed: {error}")

    async def search_parts(self,
                          keyword: str,
                          category: Optional[str] = None,
                          limit: int = 10) -> List[DigiKeyPart]:
        """
        Search for parts by keyword.

        Args:
            keyword: Search keyword (e.g., "resistor 10k")
            category: Optional category filter
            limit: Max results

        Returns:
            List of DigiKeyPart objects
        """
        if not self.client_id:
            logger.warning("Digi-Key API not configured, returning mock data")
            return self._mock_search_parts(keyword)

        try:
            token = await self._get_access_token()

            search_url = f"{self.api_url}/Search/v3/Products/Keyword"

            headers = {
                "Authorization": f"Bearer {token}",
                "X-DIGIKEY-Client-Id": self.client_id,
                "Content-Type": "application/json"
            }

            payload = {
                "Keywords": keyword,
                "RecordCount": limit,
                "RecordStartPosition": 0,
                "Filters": {}
            }

            if category:
                payload["Filters"]["CategoryIds"] = [category]

            async with aiohttp.ClientSession() as session:
                async with session.post(search_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_search_results(data)
                    else:
                        error = await response.text()
                        logger.error(f"Digi-Key search failed: {error}")
                        return []

        except Exception as e:
            logger.error(f"Digi-Key API error: {e}")
            return []

    async def get_part_details(self, part_number: str) -> Optional[DigiKeyPart]:
        """
        Get detailed information for a specific part.

        Args:
            part_number: Digi-Key part number

        Returns:
            DigiKeyPart object or None
        """
        if not self.client_id:
            logger.warning("Digi-Key API not configured")
            return None

        try:
            token = await self._get_access_token()

            details_url = f"{self.api_url}/Search/v3/Products/{part_number}"

            headers = {
                "Authorization": f"Bearer {token}",
                "X-DIGIKEY-Client-Id": self.client_id
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(details_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_part_details(data)
                    else:
                        logger.error(f"Failed to get part details for {part_number}")
                        return None

        except Exception as e:
            logger.error(f"Digi-Key API error: {e}")
            return None

    def _parse_search_results(self, data: Dict[str, Any]) -> List[DigiKeyPart]:
        """Parse search results from API response."""
        parts = []

        for product in data.get("Products", []):
            try:
                part = DigiKeyPart(
                    part_number=product.get("DigiKeyPartNumber", ""),
                    manufacturer=product.get("Manufacturer", {}).get("Name", ""),
                    description=product.get("ProductDescription", ""),
                    category=product.get("Category", {}).get("Name", ""),
                    unit_price=product.get("UnitPrice", 0.0),
                    price_breaks=self._parse_price_breaks(product.get("StandardPricing", [])),
                    quantity_available=product.get("QuantityAvailable", 0),
                    minimum_order_quantity=product.get("MinimumOrderQuantity", 1),
                    datasheet_url=product.get("DatasheetUrl"),
                    product_url=product.get("ProductUrl"),
                    specifications=self._parse_specifications(product.get("Parameters", []))
                )
                parts.append(part)
            except Exception as e:
                logger.warning(f"Failed to parse part: {e}")
                continue

        return parts

    def _parse_part_details(self, data: Dict[str, Any]) -> DigiKeyPart:
        """Parse part details from API response."""
        return DigiKeyPart(
            part_number=data.get("DigiKeyPartNumber", ""),
            manufacturer=data.get("Manufacturer", {}).get("Name", ""),
            description=data.get("ProductDescription", ""),
            category=data.get("Category", {}).get("Name", ""),
            unit_price=data.get("UnitPrice", 0.0),
            price_breaks=self._parse_price_breaks(data.get("StandardPricing", [])),
            quantity_available=data.get("QuantityAvailable", 0),
            minimum_order_quantity=data.get("MinimumOrderQuantity", 1),
            lead_time_days=data.get("LeadTimeDays"),
            datasheet_url=data.get("DatasheetUrl"),
            product_url=data.get("ProductUrl"),
            specifications=self._parse_specifications(data.get("Parameters", [])),
            alternatives=self._parse_alternatives(data.get("AlternateParts", []))
        )

    def _parse_price_breaks(self, pricing: List[Dict]) -> List[Dict[str, Any]]:
        """Parse price breaks."""
        return [
            {
                "quantity": p.get("BreakQuantity", 0),
                "unit_price": p.get("UnitPrice", 0.0),
                "total_price": p.get("TotalPrice", 0.0)
            }
            for p in pricing
        ]

    def _parse_specifications(self, params: List[Dict]) -> Dict[str, str]:
        """Parse product specifications."""
        specs = {}
        for param in params:
            name = param.get("Parameter", "")
            value = param.get("Value", "")
            if name and value:
                specs[name] = value
        return specs

    def _parse_alternatives(self, alternatives: List[Dict]) -> List[str]:
        """Parse alternative part numbers."""
        return [alt.get("DigiKeyPartNumber", "") for alt in alternatives]

    def _mock_search_parts(self, keyword: str) -> List[DigiKeyPart]:
        """Return mock data for development."""
        logger.info(f"Returning mock Digi-Key results for: {keyword}")

        return [
            DigiKeyPart(
                part_number="311-10.0KHRCT-ND",
                manufacturer="Yageo",
                description="RES 10K OHM 5% 1/4W 1206",
                category="Resistors",
                unit_price=0.10,
                price_breaks=[
                    {"quantity": 1, "unit_price": 0.10, "total_price": 0.10},
                    {"quantity": 10, "unit_price": 0.08, "total_price": 0.80},
                    {"quantity": 100, "unit_price": 0.05, "total_price": 5.00}
                ],
                quantity_available=50000,
                minimum_order_quantity=1,
                datasheet_url="https://www.yageo.com/datasheet.pdf",
                specifications={
                    "Resistance": "10 kOhms",
                    "Tolerance": "±5%",
                    "Power": "0.25W",
                    "Package": "1206"
                }
            )
        ]


# Singleton instance
digikey_api = DigiKeyAPI()
