"""
Mouser API Integration

Provides:
- Part search
- Pricing and availability
- Alternative parts
- Stock checking
"""

import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import aiohttp
from loguru import logger


@dataclass
class MouserPart:
    """Mouser part information."""
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
    lead_time_days: Optional[int] = None

    # Links
    datasheet_url: Optional[str] = None
    product_url: Optional[str] = None

    # Lifecycle
    lifecycle_status: Optional[str] = None
    rohs_status: Optional[str] = None


class MouserAPI:
    """
    Mouser API client.

    Requires:
    - MOUSER_API_KEY
    """

    BASE_URL = "https://api.mouser.com/api/v1"

    def __init__(self):
        """Initialize Mouser API client."""
        self.api_key = os.getenv("MOUSER_API_KEY")

        if not self.api_key:
            logger.warning("⚠️ Mouser API key not configured")

    async def search_parts(self, keyword: str, limit: int = 10) -> List[MouserPart]:
        """
        Search for parts by keyword.

        Args:
            keyword: Search keyword
            limit: Max results

        Returns:
            List of MouserPart objects
        """
        if not self.api_key:
            logger.warning("Mouser API not configured, returning mock data")
            return self._mock_search_parts(keyword)

        try:
            search_url = f"{self.BASE_URL}/search/keyword"

            params = {
                "apiKey": self.api_key
            }

            payload = {
                "SearchByKeywordRequest": {
                    "keyword": keyword,
                    "records": limit,
                    "startingRecord": 0
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(search_url, params=params, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_search_results(data)
                    else:
                        error = await response.text()
                        logger.error(f"Mouser search failed: {error}")
                        return []

        except Exception as e:
            logger.error(f"Mouser API error: {e}")
            return []

    async def get_part_details(self, part_number: str) -> Optional[MouserPart]:
        """
        Get detailed information for a specific part.

        Args:
            part_number: Mouser part number

        Returns:
            MouserPart object or None
        """
        if not self.api_key:
            logger.warning("Mouser API not configured")
            return None

        try:
            details_url = f"{self.BASE_URL}/search/partnumber"

            params = {
                "apiKey": self.api_key
            }

            payload = {
                "SearchByPartRequest": {
                    "mouserPartNumber": part_number
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(details_url, params=params, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        parts = self._parse_search_results(data)
                        return parts[0] if parts else None
                    else:
                        logger.error(f"Failed to get part details for {part_number}")
                        return None

        except Exception as e:
            logger.error(f"Mouser API error: {e}")
            return None

    def _parse_search_results(self, data: Dict[str, Any]) -> List[MouserPart]:
        """Parse search results from API response."""
        parts = []

        search_results = data.get("SearchResults", {})
        for part in search_results.get("Parts", []):
            try:
                mouser_part = MouserPart(
                    part_number=part.get("MouserPartNumber", ""),
                    manufacturer=part.get("Manufacturer", ""),
                    description=part.get("Description", ""),
                    category=part.get("Category", ""),
                    unit_price=self._parse_price(part.get("PriceBreaks", [])),
                    price_breaks=self._parse_price_breaks(part.get("PriceBreaks", [])),
                    quantity_available=part.get("AvailabilityInStock", 0),
                    lead_time_days=self._parse_lead_time(part.get("LeadTime", "")),
                    datasheet_url=part.get("DataSheetUrl"),
                    product_url=part.get("ProductDetailUrl"),
                    lifecycle_status=part.get("LifecycleStatus"),
                    rohs_status=part.get("ROHSStatus")
                )
                parts.append(mouser_part)
            except Exception as e:
                logger.warning(f"Failed to parse part: {e}")
                continue

        return parts

    def _parse_price(self, price_breaks: List[Dict]) -> float:
        """Get unit price from price breaks."""
        if not price_breaks:
            return 0.0

        # Return price for quantity 1
        for pb in price_breaks:
            if pb.get("Quantity", 0) == 1:
                price_str = pb.get("Price", "0")
                # Remove currency symbol and convert
                price_str = price_str.replace("$", "").replace(",", "")
                try:
                    return float(price_str)
                except ValueError:
                    return 0.0

        return 0.0

    def _parse_price_breaks(self, price_breaks: List[Dict]) -> List[Dict[str, Any]]:
        """Parse price breaks."""
        parsed = []

        for pb in price_breaks:
            try:
                price_str = pb.get("Price", "0").replace("$", "").replace(",", "")
                quantity = pb.get("Quantity", 0)
                unit_price = float(price_str)

                parsed.append({
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_price": unit_price * quantity
                })
            except (ValueError, TypeError):
                continue

        return parsed

    def _parse_lead_time(self, lead_time_str: str) -> Optional[int]:
        """Parse lead time string to days."""
        if not lead_time_str:
            return None

        # Parse strings like "10 Days", "2 Weeks", etc.
        try:
            parts = lead_time_str.split()
            number = int(parts[0])

            if "week" in lead_time_str.lower():
                return number * 7
            elif "day" in lead_time_str.lower():
                return number
            else:
                return number
        except (ValueError, IndexError):
            return None

    def _mock_search_parts(self, keyword: str) -> List[MouserPart]:
        """Return mock data for development."""
        logger.info(f"Returning mock Mouser results for: {keyword}")

        return [
            MouserPart(
                part_number="603-RC0805FR-0710KL",
                manufacturer="Yageo",
                description="RES 10K OHM 1% 1/8W 0805",
                category="Resistors",
                unit_price=0.08,
                price_breaks=[
                    {"quantity": 1, "unit_price": 0.08, "total_price": 0.08},
                    {"quantity": 10, "unit_price": 0.06, "total_price": 0.60},
                    {"quantity": 100, "unit_price": 0.04, "total_price": 4.00}
                ],
                quantity_available=75000,
                lead_time_days=5,
                datasheet_url="https://www.yageo.com/datasheet.pdf",
                lifecycle_status="Active",
                rohs_status="RoHS Compliant"
            )
        ]


# Singleton instance
mouser_api = MouserAPI()
