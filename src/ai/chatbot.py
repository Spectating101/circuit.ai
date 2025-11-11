"""
AI-Powered Chatbot Assistant for PCB Help

Features:
- Natural language PCB queries
- Component recommendations
- Design troubleshooting
- Best practices guidance
- Code generation for Arduino/ESP32
- Real-time context awareness
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import openai
import anthropic
from loguru import logger
import json


@dataclass
class ChatMessage:
    """Chat message."""
    role: str  # user, assistant, system
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ChatContext:
    """Chat conversation context."""
    session_id: str
    user_id: str
    pcb_context: Optional[Dict[str, Any]]  # Current PCB being discussed
    messages: List[ChatMessage]
    created_at: datetime


class PCBChatbot:
    """AI-powered chatbot for PCB assistance."""

    def __init__(self, api_key: str, model: str = "gpt-4"):
        """
        Initialize chatbot.

        Args:
            api_key: OpenAI/Anthropic API key
            model: Model to use
        """
        self.api_key = api_key
        self.model = model
        self.system_prompt = self._build_system_prompt()
        self.sessions: Dict[str, ChatContext] = {}
        logger.info(f"PCBChatbot initialized with model {model}")

    def _build_system_prompt(self) -> str:
        """Build system prompt with PCB expertise."""
        return """You are an expert PCB design assistant with deep knowledge of:
- Electronic circuit design and analysis
- Component selection and specifications
- PCB layout best practices
- Signal integrity and power distribution
- EMI/EMC considerations
- Manufacturing processes (SMT, through-hole)
- Common design mistakes and how to avoid them
- Arduino, ESP32, Raspberry Pi integration
- Debugging techniques

You provide:
1. Clear, actionable advice
2. Specific component recommendations with part numbers
3. Code examples when helpful
4. Links to datasheets and resources
5. Warning about potential issues

Always be concise but thorough. Use technical terminology when appropriate,
but explain complex concepts clearly."""

    async def chat(
        self,
        session_id: str,
        user_id: str,
        message: str,
        pcb_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Send message to chatbot and get response.

        Args:
            session_id: Chat session ID
            user_id: User ID
            message: User message
            pcb_context: Current PCB context (components, analysis, etc.)

        Returns:
            Assistant response
        """
        # Get or create session
        if session_id not in self.sessions:
            self.sessions[session_id] = ChatContext(
                session_id=session_id,
                user_id=user_id,
                pcb_context=pcb_context,
                messages=[],
                created_at=datetime.utcnow()
            )

        session = self.sessions[session_id]

        # Update PCB context if provided
        if pcb_context:
            session.pcb_context = pcb_context

        # Add user message
        session.messages.append(ChatMessage(
            role="user",
            content=message,
            timestamp=datetime.utcnow()
        ))

        # Build context-aware prompt
        enhanced_message = self._enhance_with_context(message, session)

        # Get response from LLM
        response = await self._get_llm_response(session, enhanced_message)

        # Add assistant response
        session.messages.append(ChatMessage(
            role="assistant",
            content=response,
            timestamp=datetime.utcnow()
        ))

        return response

    def _enhance_with_context(self, message: str, session: ChatContext) -> str:
        """Enhance message with PCB context."""
        if not session.pcb_context:
            return message

        context_info = []

        # Add component info
        if 'components' in session.pcb_context:
            component_count = len(session.pcb_context['components'])
            component_types = {}
            for comp in session.pcb_context['components']:
                comp_type = comp.get('type', 'unknown')
                component_types[comp_type] = component_types.get(comp_type, 0) + 1

            context_info.append(f"Current PCB has {component_count} components:")
            for comp_type, count in component_types.items():
                context_info.append(f"  - {count}x {comp_type}")

        # Add analysis results
        if 'anomalies' in session.pcb_context:
            anomaly_count = len(session.pcb_context['anomalies'])
            if anomaly_count > 0:
                context_info.append(f"\nDetected {anomaly_count} potential issues:")
                for i, anomaly in enumerate(session.pcb_context['anomalies'][:3]):
                    context_info.append(f"  {i+1}. {anomaly.get('title', 'Unknown issue')}")

        if context_info:
            context_str = "\n".join(context_info)
            return f"[PCB Context:\n{context_str}]\n\nUser question: {message}"

        return message

    async def _get_llm_response(
        self,
        session: ChatContext,
        message: str
    ) -> str:
        """Get response from LLM."""
        try:
            if self.model.startswith("gpt"):
                return await self._get_openai_response(session, message)
            elif self.model.startswith("claude"):
                return await self._get_anthropic_response(session, message)
            else:
                raise ValueError(f"Unsupported model: {self.model}")
        except Exception as e:
            logger.error(f"Error getting LLM response: {e}")
            return "I apologize, but I encountered an error. Please try again."

    async def _get_openai_response(
        self,
        session: ChatContext,
        message: str
    ) -> str:
        """Get response from OpenAI."""
        messages = [{"role": "system", "content": self.system_prompt}]

        # Add conversation history (last 10 messages)
        for msg in session.messages[-10:]:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })

        # Add current message
        messages.append({"role": "user", "content": message})

        # Call OpenAI API
        client = openai.AsyncOpenAI(api_key=self.api_key)
        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )

        return response.choices[0].message.content

    async def _get_anthropic_response(
        self,
        session: ChatContext,
        message: str
    ) -> str:
        """Get response from Anthropic Claude."""
        messages = []

        # Add conversation history
        for msg in session.messages[-10:]:
            messages.append({
                "role": msg.role if msg.role != "system" else "user",
                "content": msg.content
            })

        messages.append({"role": "user", "content": message})

        # Call Anthropic API
        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        response = await client.messages.create(
            model=self.model,
            system=self.system_prompt,
            messages=messages,
            max_tokens=1000
        )

        return response.content[0].text

    async def suggest_components(
        self,
        session_id: str,
        requirements: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Get AI-powered component suggestions.

        Args:
            session_id: Session ID
            requirements: Component requirements

        Returns:
            List of component suggestions
        """
        prompt = f"""Suggest components for these requirements:
{json.dumps(requirements, indent=2)}

Provide specific part numbers, manufacturers, and reasoning for each suggestion.
Format as JSON array."""

        response = await self.chat(
            session_id=session_id,
            user_id="system",
            message=prompt
        )

        # Parse JSON response
        try:
            suggestions = json.loads(response)
            return suggestions
        except json.JSONDecodeError:
            logger.error("Failed to parse component suggestions")
            return []

    async def debug_circuit(
        self,
        session_id: str,
        problem_description: str,
        circuit_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Help debug circuit issues.

        Args:
            session_id: Session ID
            problem_description: Description of the problem
            circuit_data: Circuit information

        Returns:
            Debugging suggestions
        """
        prompt = f"""Help debug this circuit issue:

Problem: {problem_description}

Circuit info:
{json.dumps(circuit_data, indent=2)}

Provide:
1. Likely causes
2. Troubleshooting steps
3. Measurements to take
4. Potential fixes"""

        response = await self.chat(
            session_id=session_id,
            user_id="system",
            message=prompt
        )

        return {
            "analysis": response,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def generate_code(
        self,
        session_id: str,
        platform: str,  # arduino, esp32, raspberry_pi
        task_description: str
    ) -> str:
        """
        Generate code for microcontroller.

        Args:
            session_id: Session ID
            platform: Target platform
            task_description: What the code should do

        Returns:
            Generated code
        """
        prompt = f"""Generate {platform} code for: {task_description}

Include:
- Complete, working code
- Pin definitions
- Library includes
- Comments explaining key sections
- Setup and loop functions"""

        response = await self.chat(
            session_id=session_id,
            user_id="system",
            message=prompt
        )

        return response

    async def explain_component(
        self,
        session_id: str,
        component_type: str,
        specific_part: Optional[str] = None
    ) -> str:
        """
        Explain component type or specific part.

        Args:
            session_id: Session ID
            component_type: Type of component
            specific_part: Specific part number (optional)

        Returns:
            Explanation
        """
        if specific_part:
            prompt = f"Explain the {specific_part} ({component_type}) in detail. Include specs, typical uses, and alternatives."
        else:
            prompt = f"Explain {component_type} components. Include types, key specs, selection criteria, and common applications."

        response = await self.chat(
            session_id=session_id,
            user_id="system",
            message=prompt
        )

        return response

    async def quick_tip(self, topic: str) -> str:
        """
        Get quick PCB design tip.

        Args:
            topic: Topic area

        Returns:
            Design tip
        """
        tips_db = {
            "power": [
                "Always add bulk capacitors (10-100µF) near voltage regulators",
                "Use star grounding for power distribution",
                "Calculate trace width for current capacity: 1A needs ~10mil for 1oz copper"
            ],
            "signal_integrity": [
                "Keep high-speed traces short and direct",
                "Use differential pairs for USB, Ethernet, HDMI",
                "Add termination resistors for transmission lines"
            ],
            "thermal": [
                "Add thermal vias under QFN/BGA packages",
                "Keep high-power components away from temperature-sensitive parts",
                "Consider heatsinks for components >1W"
            ],
            "layout": [
                "Place decoupling caps as close to IC pins as possible",
                "Route critical signals first, then power, then ground",
                "Use ground plane for better EMI performance"
            ]
        }

        topic_lower = topic.lower()
        for key, tips in tips_db.items():
            if key in topic_lower:
                import random
                return random.choice(tips)

        return "General tip: Always review your PCB design checklist before sending to fabrication!"


class ChatbotIntegration:
    """Integration layer for chatbot in application."""

    def __init__(self, chatbot: PCBChatbot):
        """Initialize integration."""
        self.chatbot = chatbot

    async def handle_analysis_question(
        self,
        user_id: str,
        analysis_id: str,
        question: str
    ) -> str:
        """
        Answer question about specific analysis.

        Args:
            user_id: User ID
            analysis_id: Analysis ID
            question: User question

        Returns:
            Answer
        """
        # Load analysis data
        # TODO: Get from database
        analysis_data = {
            "components": [],
            "anomalies": []
        }

        session_id = f"analysis_{analysis_id}"

        response = await self.chatbot.chat(
            session_id=session_id,
            user_id=user_id,
            message=question,
            pcb_context=analysis_data
        )

        return response

    async def provide_design_review(
        self,
        user_id: str,
        pcb_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Provide AI-powered design review.

        Args:
            user_id: User ID
            pcb_data: PCB design data

        Returns:
            Design review
        """
        session_id = f"review_{user_id}_{datetime.utcnow().timestamp()}"

        prompt = """Review this PCB design and provide:
1. Overall assessment
2. Potential issues
3. Improvement suggestions
4. Best practice violations
5. Rating (1-10)

Be thorough but concise."""

        response = await self.chatbot.chat(
            session_id=session_id,
            user_id=user_id,
            message=prompt,
            pcb_context=pcb_data
        )

        return {
            "review": response,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def interactive_troubleshooting(
        self,
        user_id: str,
        initial_problem: str
    ) -> str:
        """
        Start interactive troubleshooting session.

        Args:
            user_id: User ID
            initial_problem: Problem description

        Returns:
            First troubleshooting question/suggestion
        """
        session_id = f"troubleshoot_{user_id}_{datetime.utcnow().timestamp()}"

        prompt = f"""User reported this problem: {initial_problem}

Start troubleshooting by:
1. Asking clarifying questions
2. Suggesting initial diagnostic steps
3. Identifying most likely causes

Be methodical and guide them through the process."""

        response = await self.chatbot.chat(
            session_id=session_id,
            user_id=user_id,
            message=prompt
        )

        return response


# Singleton instance
chatbot = PCBChatbot(
    api_key="sk-placeholder",  # Set from environment
    model="gpt-4"
)
chatbot_integration = ChatbotIntegration(chatbot)
