"""
AI-Powered Component Recommendation Engine

Uses ML to recommend:
- Alternative components (cheaper, better specs)
- Missing components (design suggestions)
- Obsolete component replacements
- Power optimization suggestions
- Cost optimization paths
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.ensemble import RandomForestClassifier
from loguru import logger
import asyncio
import aiohttp


@dataclass
class ComponentRecommendation:
    """Component recommendation with reasoning."""
    component_id: str
    component_name: str
    manufacturer: str
    part_number: str
    confidence: float  # 0-1
    reasoning: str
    savings_potential: float  # USD
    availability_score: float  # 0-1
    specifications: Dict[str, Any]
    datasheet_url: str

    # Comparison with current component
    price_difference: float  # Negative = cheaper
    performance_difference: float  # Positive = better
    compatibility_score: float  # 0-1


@dataclass
class DesignSuggestion:
    """Design improvement suggestion."""
    suggestion_type: str  # missing_component, power_issue, thermal_issue
    severity: str  # critical, high, medium, low
    title: str
    description: str
    recommended_components: List[ComponentRecommendation]
    potential_savings: float
    implementation_difficulty: str  # easy, medium, hard


class ComponentEmbeddings:
    """Component embeddings for similarity search."""

    def __init__(self):
        """Initialize embedding model."""
        self.embedding_dim = 128
        self.component_vectors = {}  # Cache
        logger.info("ComponentEmbeddings initialized")

    def create_embedding(self, component: Dict[str, Any]) -> np.ndarray:
        """
        Create embedding vector for component.

        Args:
            component: Component specifications

        Returns:
            Embedding vector
        """
        features = []

        # Numeric features
        features.append(component.get('voltage_rating', 0) / 100.0)
        features.append(component.get('current_rating', 0) / 10.0)
        features.append(component.get('power_rating', 0) / 10.0)
        features.append(component.get('tolerance', 0) / 100.0)
        features.append(component.get('temperature_rating', 0) / 200.0)
        features.append(component.get('package_size_mm', 0) / 50.0)
        features.append(component.get('price_usd', 0) / 100.0)

        # Categorical features (one-hot encoded)
        component_type = component.get('type', 'unknown')
        type_encoding = self._encode_component_type(component_type)
        features.extend(type_encoding)

        # Pad or truncate to fixed dimension
        embedding = np.array(features)
        if len(embedding) < self.embedding_dim:
            embedding = np.pad(embedding, (0, self.embedding_dim - len(embedding)))
        else:
            embedding = embedding[:self.embedding_dim]

        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding

    def _encode_component_type(self, component_type: str) -> List[float]:
        """One-hot encode component type."""
        types = ['resistor', 'capacitor', 'inductor', 'ic', 'transistor',
                'diode', 'led', 'connector', 'switch', 'crystal']
        encoding = [1.0 if component_type == t else 0.0 for t in types]
        return encoding

    def find_similar(
        self,
        target_component: Dict[str, Any],
        candidate_pool: List[Dict[str, Any]],
        top_k: int = 10
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Find similar components using embedding similarity.

        Args:
            target_component: Component to find alternatives for
            candidate_pool: Pool of candidate components
            top_k: Number of results to return

        Returns:
            List of (component, similarity_score) tuples
        """
        target_embedding = self.create_embedding(target_component)

        similarities = []
        for candidate in candidate_pool:
            candidate_embedding = self.create_embedding(candidate)
            similarity = cosine_similarity(
                target_embedding.reshape(1, -1),
                candidate_embedding.reshape(1, -1)
            )[0][0]
            similarities.append((candidate, float(similarity)))

        # Sort by similarity and return top k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]


class RecommendationEngine:
    """AI-powered component recommendation engine."""

    def __init__(self):
        """Initialize recommendation engine."""
        self.embeddings = ComponentEmbeddings()
        self.component_database = self._load_component_database()
        self.obsolescence_db = self._load_obsolescence_database()
        logger.info("RecommendationEngine initialized")

    def _load_component_database(self) -> List[Dict[str, Any]]:
        """
        Load component database.

        In production, this would query from:
        - Digi-Key API
        - Mouser API
        - Octopart API
        - Internal component library
        """
        # Mock database with common components
        return [
            {
                'id': 'RES-001',
                'type': 'resistor',
                'name': '10K Resistor 0603',
                'manufacturer': 'Yageo',
                'part_number': 'RC0603FR-0710KL',
                'voltage_rating': 75,
                'power_rating': 0.1,
                'tolerance': 1.0,
                'temperature_rating': 155,
                'package_size_mm': 1.6,
                'price_usd': 0.01,
                'stock': 100000,
                'lifecycle_status': 'active'
            },
            {
                'id': 'CAP-001',
                'type': 'capacitor',
                'name': '10uF Ceramic 16V X7R 0805',
                'manufacturer': 'Samsung',
                'part_number': 'CL21B106KOQNNNE',
                'voltage_rating': 16,
                'capacitance': 10.0,
                'tolerance': 10.0,
                'temperature_rating': 125,
                'package_size_mm': 2.0,
                'price_usd': 0.15,
                'stock': 50000,
                'lifecycle_status': 'active'
            },
            # Add more components...
        ]

    def _load_obsolescence_database(self) -> Dict[str, Dict[str, Any]]:
        """Load database of obsolete components and replacements."""
        return {
            'LM78L05': {
                'status': 'obsolete',
                'reason': 'Discontinued by manufacturer',
                'recommended_replacement': 'LM78L05ACZ',
                'alternative_modern': 'TPS7A0550PDQNR'
            }
        }

    async def recommend_alternatives(
        self,
        component: Dict[str, Any],
        optimization_goal: str = 'cost'  # cost, performance, availability
    ) -> List[ComponentRecommendation]:
        """
        Recommend alternative components.

        Args:
            component: Current component
            optimization_goal: What to optimize for

        Returns:
            List of recommendations
        """
        # Find similar components using embeddings
        similar_components = self.embeddings.find_similar(
            component,
            self.component_database,
            top_k=20
        )

        recommendations = []

        for candidate, similarity in similar_components:
            # Skip if same component
            if candidate.get('part_number') == component.get('part_number'):
                continue

            # Calculate metrics
            price_diff = candidate.get('price_usd', 0) - component.get('price_usd', 0)

            # Performance comparison (simplified)
            performance_diff = self._calculate_performance_difference(
                component, candidate
            )

            # Availability score
            availability_score = min(1.0, candidate.get('stock', 0) / 10000.0)

            # Compatibility score (based on specs)
            compatibility_score = self._calculate_compatibility(component, candidate)

            # Calculate confidence based on similarity and compatibility
            confidence = (similarity * 0.6 + compatibility_score * 0.4)

            # Generate reasoning
            reasoning = self._generate_reasoning(
                component, candidate, optimization_goal, price_diff, performance_diff
            )

            # Calculate savings
            savings = abs(price_diff) if price_diff < 0 else 0

            recommendation = ComponentRecommendation(
                component_id=candidate['id'],
                component_name=candidate['name'],
                manufacturer=candidate.get('manufacturer', 'Unknown'),
                part_number=candidate.get('part_number', ''),
                confidence=confidence,
                reasoning=reasoning,
                savings_potential=savings,
                availability_score=availability_score,
                specifications=candidate,
                datasheet_url=f"https://datasheets.example.com/{candidate.get('part_number', '')}",
                price_difference=price_diff,
                performance_difference=performance_diff,
                compatibility_score=compatibility_score
            )

            recommendations.append(recommendation)

        # Sort based on optimization goal
        if optimization_goal == 'cost':
            recommendations.sort(key=lambda r: (
                -r.savings_potential,
                r.compatibility_score
            ), reverse=True)
        elif optimization_goal == 'performance':
            recommendations.sort(key=lambda r: r.performance_difference, reverse=True)
        elif optimization_goal == 'availability':
            recommendations.sort(key=lambda r: r.availability_score, reverse=True)

        return recommendations[:10]

    def _calculate_performance_difference(
        self,
        current: Dict[str, Any],
        candidate: Dict[str, Any]
    ) -> float:
        """Calculate normalized performance difference."""
        score = 0.0

        # Higher ratings are better
        if candidate.get('power_rating', 0) > current.get('power_rating', 0):
            score += 0.3
        if candidate.get('voltage_rating', 0) > current.get('voltage_rating', 0):
            score += 0.3
        if candidate.get('temperature_rating', 0) > current.get('temperature_rating', 0):
            score += 0.2

        # Lower tolerance is better
        if candidate.get('tolerance', 100) < current.get('tolerance', 100):
            score += 0.2

        return score

    def _calculate_compatibility(
        self,
        current: Dict[str, Any],
        candidate: Dict[str, Any]
    ) -> float:
        """
        Calculate compatibility score.

        Checks if candidate can be a drop-in replacement.
        """
        score = 1.0

        # Must be same component type
        if current.get('type') != candidate.get('type'):
            return 0.0

        # Voltage rating must be >= current
        if candidate.get('voltage_rating', 0) < current.get('voltage_rating', 0):
            score *= 0.5

        # Power rating must be >= current
        if candidate.get('power_rating', 0) < current.get('power_rating', 0):
            score *= 0.5

        # Package size should be similar (within 50%)
        current_size = current.get('package_size_mm', 0)
        candidate_size = candidate.get('package_size_mm', 0)
        if current_size > 0:
            size_ratio = candidate_size / current_size
            if size_ratio < 0.5 or size_ratio > 1.5:
                score *= 0.7

        return score

    def _generate_reasoning(
        self,
        current: Dict[str, Any],
        candidate: Dict[str, Any],
        goal: str,
        price_diff: float,
        perf_diff: float
    ) -> str:
        """Generate human-readable reasoning for recommendation."""
        reasons = []

        if price_diff < -0.01:
            savings_pct = abs(price_diff / current.get('price_usd', 1.0)) * 100
            reasons.append(f"${abs(price_diff):.2f} cheaper ({savings_pct:.0f}% savings)")

        if perf_diff > 0.2:
            reasons.append("Better specifications")

        if candidate.get('stock', 0) > current.get('stock', 0):
            reasons.append("Better availability")

        if candidate.get('manufacturer') == current.get('manufacturer'):
            reasons.append("Same manufacturer (easier transition)")

        if not reasons:
            reasons.append("Similar specifications with comparable pricing")

        return "; ".join(reasons)

    async def check_obsolescence(
        self,
        components: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Check components for obsolescence issues.

        Args:
            components: List of components to check

        Returns:
            List of obsolescence warnings with recommended replacements
        """
        warnings = []

        for component in components:
            part_number = component.get('part_number', '')

            # Check obsolescence database
            if part_number in self.obsolescence_db:
                obs_info = self.obsolescence_db[part_number]

                # Get recommended replacement
                replacement_pn = obs_info.get('recommended_replacement')
                replacement = next(
                    (c for c in self.component_database
                     if c.get('part_number') == replacement_pn),
                    None
                )

                warnings.append({
                    'component': component,
                    'status': obs_info['status'],
                    'reason': obs_info['reason'],
                    'recommended_replacement': replacement,
                    'severity': 'high'
                })

        return warnings

    async def suggest_design_improvements(
        self,
        pcb_analysis: Dict[str, Any]
    ) -> List[DesignSuggestion]:
        """
        Suggest design improvements based on PCB analysis.

        Args:
            pcb_analysis: PCB analysis results

        Returns:
            List of design suggestions
        """
        suggestions = []

        components = pcb_analysis.get('components', [])

        # Check for missing decoupling capacitors
        ics = [c for c in components if c.get('type') == 'ic']
        capacitors = [c for c in components if c.get('type') == 'capacitor']

        if len(ics) > 0 and len(capacitors) < len(ics):
            suggestions.append(DesignSuggestion(
                suggestion_type='missing_component',
                severity='high',
                title='Missing Decoupling Capacitors',
                description=f'Detected {len(ics)} ICs but only {len(capacitors)} capacitors. Each IC should have dedicated decoupling capacitors for stable operation.',
                recommended_components=await self._recommend_decoupling_caps(ics),
                potential_savings=0,
                implementation_difficulty='easy'
            ))

        # Check for power optimization opportunities
        power_components = [c for c in components if c.get('type') in ['resistor', 'led']]
        if power_components:
            total_power = sum(c.get('power_rating', 0) for c in power_components)
            if total_power > 5.0:  # Watts
                suggestions.append(DesignSuggestion(
                    suggestion_type='power_issue',
                    severity='medium',
                    title='High Power Consumption Detected',
                    description=f'Total power consumption: {total_power:.1f}W. Consider using lower-power alternatives to reduce heat and extend battery life.',
                    recommended_components=[],
                    potential_savings=total_power * 0.2,  # Estimate 20% savings
                    implementation_difficulty='medium'
                ))

        # Check for cost optimization
        expensive_components = [c for c in components if c.get('price_usd', 0) > 1.0]
        if expensive_components:
            total_savings = 0
            alternative_recommendations = []

            for comp in expensive_components[:5]:  # Top 5 expensive
                alternatives = await self.recommend_alternatives(comp, 'cost')
                if alternatives:
                    best = alternatives[0]
                    total_savings += best.savings_potential
                    alternative_recommendations.append(best)

            if total_savings > 0.5:
                suggestions.append(DesignSuggestion(
                    suggestion_type='cost_optimization',
                    severity='low',
                    title='Cost Optimization Opportunities',
                    description=f'Found alternative components that could save ${total_savings:.2f} per unit without compromising performance.',
                    recommended_components=alternative_recommendations,
                    potential_savings=total_savings,
                    implementation_difficulty='easy'
                ))

        return suggestions

    async def _recommend_decoupling_caps(
        self,
        ics: List[Dict[str, Any]]
    ) -> List[ComponentRecommendation]:
        """Recommend appropriate decoupling capacitors for ICs."""
        recommendations = []

        # Standard decoupling cap: 100nF ceramic
        standard_cap = {
            'id': 'CAP-DECOUPLING',
            'type': 'capacitor',
            'name': '100nF Ceramic 50V X7R 0603',
            'manufacturer': 'Murata',
            'part_number': 'GRM188R71H104KA93D',
            'voltage_rating': 50,
            'capacitance': 0.1,
            'price_usd': 0.05,
            'stock': 200000
        }

        for ic in ics:
            rec = ComponentRecommendation(
                component_id='CAP-DECOUPLING',
                component_name=standard_cap['name'],
                manufacturer=standard_cap['manufacturer'],
                part_number=standard_cap['part_number'],
                confidence=0.95,
                reasoning='Standard 100nF ceramic capacitor for IC power supply decoupling',
                savings_potential=0,
                availability_score=1.0,
                specifications=standard_cap,
                datasheet_url='https://datasheets.example.com/GRM188R71H104KA93D',
                price_difference=0,
                performance_difference=0,
                compatibility_score=1.0
            )
            recommendations.append(rec)

        return recommendations


# Singleton instance
recommendation_engine = RecommendationEngine()
