"""
Advanced Search with Elasticsearch

Features:
- Full-text search across components, analyses, designs
- Fuzzy matching for part numbers
- Aggregations and faceted search
- Auto-complete and suggestions
- Relevance scoring
- Search analytics
- Saved searches
- Search query DSL builder
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import asyncio
from elasticsearch import AsyncElasticsearch
from loguru import logger
import hashlib


class IndexName(Enum):
    """Elasticsearch index names."""
    COMPONENTS = "components"
    ANALYSES = "analyses"
    DESIGNS = "designs"
    BOM_ITEMS = "bom_items"
    USERS = "users"
    DOCUMENTS = "documents"


class SearchOperator(Enum):
    """Search operators."""
    AND = "AND"
    OR = "OR"
    NOT = "NOT"


@dataclass
class SearchQuery:
    """Search query specification."""
    query_text: str
    indices: List[IndexName]
    filters: Dict[str, Any]
    sort: Optional[List[Dict[str, str]]]
    page: int
    page_size: int
    include_aggregations: bool
    fuzzy: bool
    boost_fields: Optional[Dict[str, float]]


@dataclass
class SearchResult:
    """Search result."""
    id: str
    index: str
    score: float
    source: Dict[str, Any]
    highlight: Optional[Dict[str, List[str]]]


@dataclass
class SearchResponse:
    """Complete search response."""
    total_hits: int
    results: List[SearchResult]
    aggregations: Dict[str, Any]
    took_ms: int
    page: int
    page_size: int
    total_pages: int


class ElasticsearchService:
    """Elasticsearch search service."""

    def __init__(
        self,
        hosts: List[str] = None,
        username: str = "elastic",
        password: str = "changeme"
    ):
        """
        Initialize Elasticsearch service.

        Args:
            hosts: Elasticsearch hosts
            username: Username
            password: Password
        """
        self.hosts = hosts or ["http://localhost:9200"]
        self.username = username
        self.password = password
        self.client: Optional[AsyncElasticsearch] = None
        logger.info(f"ElasticsearchService initialized")

    async def connect(self):
        """Connect to Elasticsearch."""
        if not self.client:
            self.client = AsyncElasticsearch(
                hosts=self.hosts,
                basic_auth=(self.username, self.password),
                verify_certs=False
            )

            # Verify connection
            info = await self.client.info()
            logger.info(f"Connected to Elasticsearch: {info['version']['number']}")

    async def disconnect(self):
        """Disconnect from Elasticsearch."""
        if self.client:
            await self.client.close()
            self.client = None

    async def create_indices(self):
        """Create all indices with mappings."""
        await self.connect()

        # Component index
        await self._create_component_index()

        # Analysis index
        await self._create_analysis_index()

        # Design index
        await self._create_design_index()

        # BOM index
        await self._create_bom_index()

        logger.info("All indices created")

    async def _create_component_index(self):
        """Create component index."""
        mapping = {
            "properties": {
                "part_number": {
                    "type": "text",
                    "fields": {
                        "keyword": {"type": "keyword"},
                        "suggest": {"type": "completion"}
                    }
                },
                "manufacturer": {
                    "type": "text",
                    "fields": {"keyword": {"type": "keyword"}}
                },
                "description": {"type": "text"},
                "category": {"type": "keyword"},
                "package": {"type": "keyword"},
                "datasheet_url": {"type": "keyword"},
                "specifications": {
                    "type": "nested",
                    "properties": {
                        "name": {"type": "keyword"},
                        "value": {"type": "text"},
                        "unit": {"type": "keyword"}
                    }
                },
                "unit_price": {"type": "float"},
                "stock": {"type": "integer"},
                "created_at": {"type": "date"}
            }
        }

        index_name = IndexName.COMPONENTS.value

        if not await self.client.indices.exists(index=index_name):
            await self.client.indices.create(
                index=index_name,
                body={"mappings": mapping}
            )
            logger.info(f"Created index: {index_name}")

    async def _create_analysis_index(self):
        """Create analysis index."""
        mapping = {
            "properties": {
                "analysis_id": {"type": "keyword"},
                "user_id": {"type": "keyword"},
                "pcb_name": {"type": "text"},
                "component_count": {"type": "integer"},
                "defect_count": {"type": "integer"},
                "quality_score": {"type": "float"},
                "created_at": {"type": "date"},
                "components": {
                    "type": "nested",
                    "properties": {
                        "type": {"type": "keyword"},
                        "part_number": {"type": "keyword"},
                        "confidence": {"type": "float"}
                    }
                },
                "tags": {"type": "keyword"},
                "notes": {"type": "text"}
            }
        }

        index_name = IndexName.ANALYSES.value

        if not await self.client.indices.exists(index=index_name):
            await self.client.indices.create(
                index=index_name,
                body={"mappings": mapping}
            )
            logger.info(f"Created index: {index_name}")

    async def _create_design_index(self):
        """Create design index."""
        mapping = {
            "properties": {
                "design_id": {"type": "keyword"},
                "name": {"type": "text"},
                "description": {"type": "text"},
                "designer": {"type": "keyword"},
                "layer_count": {"type": "integer"},
                "board_size": {
                    "properties": {
                        "width": {"type": "float"},
                        "height": {"type": "float"}
                    }
                },
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"},
                "tags": {"type": "keyword"},
                "public": {"type": "boolean"}
            }
        }

        index_name = IndexName.DESIGNS.value

        if not await self.client.indices.exists(index=index_name):
            await self.client.indices.create(
                index=index_name,
                body={"mappings": mapping}
            )
            logger.info(f"Created index: {index_name}")

    async def _create_bom_index(self):
        """Create BOM index."""
        mapping = {
            "properties": {
                "bom_id": {"type": "keyword"},
                "project_name": {"type": "text"},
                "part_number": {"type": "keyword"},
                "quantity": {"type": "integer"},
                "unit_price": {"type": "float"},
                "total_price": {"type": "float"},
                "manufacturer": {"type": "keyword"},
                "supplier": {"type": "keyword"},
                "lead_time_weeks": {"type": "integer"},
                "created_at": {"type": "date"}
            }
        }

        index_name = IndexName.BOM_ITEMS.value

        if not await self.client.indices.exists(index=index_name):
            await self.client.indices.create(
                index=index_name,
                body={"mappings": mapping}
            )
            logger.info(f"Created index: {index_name}")

    async def index_document(
        self,
        index: IndexName,
        document_id: str,
        document: Dict[str, Any]
    ):
        """
        Index a document.

        Args:
            index: Index name
            document_id: Document ID
            document: Document data
        """
        await self.connect()

        await self.client.index(
            index=index.value,
            id=document_id,
            body=document
        )

    async def bulk_index(
        self,
        index: IndexName,
        documents: List[Dict[str, Any]]
    ):
        """
        Bulk index documents.

        Args:
            index: Index name
            documents: List of documents with 'id' and 'data' keys
        """
        await self.connect()

        # Prepare bulk operations
        operations = []
        for doc in documents:
            operations.append({
                "index": {
                    "_index": index.value,
                    "_id": doc.get('id')
                }
            })
            operations.append(doc.get('data'))

        if operations:
            await self.client.bulk(operations=operations)
            logger.info(f"Bulk indexed {len(documents)} documents to {index.value}")

    async def search(
        self,
        query: SearchQuery
    ) -> SearchResponse:
        """
        Perform search.

        Args:
            query: Search query

        Returns:
            Search response
        """
        await self.connect()

        # Build Elasticsearch query
        es_query = self._build_query(query)

        # Calculate pagination
        from_offset = (query.page - 1) * query.page_size

        # Execute search
        indices = [idx.value for idx in query.indices]

        response = await self.client.search(
            index=indices,
            body=es_query,
            from_=from_offset,
            size=query.page_size
        )

        # Parse results
        total_hits = response['hits']['total']['value']
        took_ms = response['took']

        results = []
        for hit in response['hits']['hits']:
            results.append(SearchResult(
                id=hit['_id'],
                index=hit['_index'],
                score=hit['_score'],
                source=hit['_source'],
                highlight=hit.get('highlight')
            ))

        # Parse aggregations
        aggregations = response.get('aggregations', {})

        total_pages = (total_hits + query.page_size - 1) // query.page_size

        return SearchResponse(
            total_hits=total_hits,
            results=results,
            aggregations=aggregations,
            took_ms=took_ms,
            page=query.page,
            page_size=query.page_size,
            total_pages=total_pages
        )

    def _build_query(self, query: SearchQuery) -> Dict[str, Any]:
        """Build Elasticsearch query DSL."""
        es_query: Dict[str, Any] = {
            "query": {
                "bool": {
                    "must": [],
                    "filter": []
                }
            }
        }

        # Main query
        if query.query_text:
            if query.fuzzy:
                # Fuzzy multi-match
                match_query = {
                    "multi_match": {
                        "query": query.query_text,
                        "fields": self._get_search_fields(query.boost_fields),
                        "fuzziness": "AUTO",
                        "type": "best_fields"
                    }
                }
            else:
                # Exact multi-match
                match_query = {
                    "multi_match": {
                        "query": query.query_text,
                        "fields": self._get_search_fields(query.boost_fields),
                        "type": "best_fields"
                    }
                }

            es_query["query"]["bool"]["must"].append(match_query)

        # Filters
        for field, value in query.filters.items():
            if isinstance(value, list):
                es_query["query"]["bool"]["filter"].append({
                    "terms": {field: value}
                })
            else:
                es_query["query"]["bool"]["filter"].append({
                    "term": {field: value}
                })

        # Highlighting
        es_query["highlight"] = {
            "fields": {
                "*": {}
            },
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"]
        }

        # Aggregations
        if query.include_aggregations:
            es_query["aggs"] = self._build_aggregations()

        # Sorting
        if query.sort:
            es_query["sort"] = query.sort
        else:
            es_query["sort"] = ["_score"]

        return es_query

    def _get_search_fields(
        self,
        boost_fields: Optional[Dict[str, float]] = None
    ) -> List[str]:
        """Get search fields with optional boosts."""
        if boost_fields:
            return [
                f"{field}^{boost}" if boost != 1.0 else field
                for field, boost in boost_fields.items()
            ]

        # Default fields
        return [
            "part_number^3",
            "manufacturer^2",
            "description",
            "category^1.5"
        ]

    def _build_aggregations(self) -> Dict[str, Any]:
        """Build common aggregations."""
        return {
            "by_category": {
                "terms": {"field": "category", "size": 20}
            },
            "by_manufacturer": {
                "terms": {"field": "manufacturer.keyword", "size": 20}
            },
            "price_stats": {
                "stats": {"field": "unit_price"}
            }
        }

    async def suggest_autocomplete(
        self,
        index: IndexName,
        field: str,
        prefix: str,
        size: int = 10
    ) -> List[str]:
        """
        Get autocomplete suggestions.

        Args:
            index: Index to search
            field: Field with completion mapping
            prefix: Prefix to match
            size: Number of suggestions

        Returns:
            List of suggestions
        """
        await self.connect()

        body = {
            "suggest": {
                "autocomplete": {
                    "prefix": prefix,
                    "completion": {
                        "field": field,
                        "size": size,
                        "skip_duplicates": True
                    }
                }
            }
        }

        response = await self.client.search(
            index=index.value,
            body=body
        )

        suggestions = []
        for option in response['suggest']['autocomplete'][0]['options']:
            suggestions.append(option['text'])

        return suggestions

    async def similar_components(
        self,
        component_id: str,
        min_score: float = 0.5,
        size: int = 10
    ) -> List[SearchResult]:
        """
        Find similar components using More Like This.

        Args:
            component_id: Component ID
            min_score: Minimum similarity score
            size: Number of results

        Returns:
            Similar components
        """
        await self.connect()

        query = {
            "query": {
                "more_like_this": {
                    "fields": ["description", "category", "specifications"],
                    "like": [
                        {
                            "_index": IndexName.COMPONENTS.value,
                            "_id": component_id
                        }
                    ],
                    "min_term_freq": 1,
                    "min_doc_freq": 1,
                    "min_score": min_score
                }
            }
        }

        response = await self.client.search(
            index=IndexName.COMPONENTS.value,
            body=query,
            size=size
        )

        results = []
        for hit in response['hits']['hits']:
            results.append(SearchResult(
                id=hit['_id'],
                index=hit['_index'],
                score=hit['_score'],
                source=hit['_source'],
                highlight=None
            ))

        return results

    async def delete_document(
        self,
        index: IndexName,
        document_id: str
    ):
        """Delete document."""
        await self.connect()

        await self.client.delete(
            index=index.value,
            id=document_id
        )

    async def update_document(
        self,
        index: IndexName,
        document_id: str,
        updates: Dict[str, Any]
    ):
        """Update document."""
        await self.connect()

        await self.client.update(
            index=index.value,
            id=document_id,
            body={"doc": updates}
        )


class SearchAnalytics:
    """Track search analytics."""

    def __init__(self, es_service: ElasticsearchService):
        """
        Initialize analytics.

        Args:
            es_service: Elasticsearch service
        """
        self.es_service = es_service
        self.analytics_index = "search_analytics"

    async def track_search(
        self,
        user_id: str,
        query: str,
        results_count: int,
        took_ms: int
    ):
        """Track search query."""
        document = {
            "user_id": user_id,
            "query": query,
            "results_count": results_count,
            "took_ms": took_ms,
            "timestamp": datetime.utcnow().isoformat()
        }

        doc_id = hashlib.md5(
            f"{user_id}:{query}:{datetime.utcnow().timestamp()}".encode()
        ).hexdigest()

        await self.es_service.client.index(
            index=self.analytics_index,
            id=doc_id,
            body=document
        )

    async def get_popular_searches(
        self,
        days: int = 7,
        size: int = 20
    ) -> List[Dict[str, Any]]:
        """Get popular search queries."""
        # Get searches from last N days
        query = {
            "size": 0,
            "query": {
                "range": {
                    "timestamp": {
                        "gte": f"now-{days}d/d"
                    }
                }
            },
            "aggs": {
                "popular_queries": {
                    "terms": {
                        "field": "query.keyword",
                        "size": size
                    }
                }
            }
        }

        response = await self.es_service.client.search(
            index=self.analytics_index,
            body=query
        )

        buckets = response['aggregations']['popular_queries']['buckets']

        return [
            {"query": bucket['key'], "count": bucket['doc_count']}
            for bucket in buckets
        ]


# Singleton instance
elasticsearch_service = ElasticsearchService()
search_analytics = SearchAnalytics(elasticsearch_service)
