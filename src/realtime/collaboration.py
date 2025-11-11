"""
Real-Time Collaboration System

Features:
- Multi-user PCB viewing/editing
- Shared cursors and selections
- Live annotations and comments
- Change synchronization
- Conflict resolution
- Presence awareness
"""

from typing import Dict, List, Set, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import json
import uuid
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger


class MessageType(Enum):
    """WebSocket message types."""
    # Presence
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    USER_UPDATE = "user_update"
    PRESENCE_SYNC = "presence_sync"

    # Cursor and selection
    CURSOR_MOVE = "cursor_move"
    SELECTION_CHANGE = "selection_change"

    # Annotations
    ANNOTATION_ADD = "annotation_add"
    ANNOTATION_UPDATE = "annotation_update"
    ANNOTATION_DELETE = "annotation_delete"

    # Components
    COMPONENT_SELECT = "component_select"
    COMPONENT_HIGHLIGHT = "component_highlight"
    COMPONENT_COMMENT = "component_comment"

    # Analysis
    ANALYSIS_START = "analysis_start"
    ANALYSIS_PROGRESS = "analysis_progress"
    ANALYSIS_COMPLETE = "analysis_complete"

    # Chat
    CHAT_MESSAGE = "chat_message"
    CHAT_TYPING = "chat_typing"

    # Document changes
    CHANGE_APPLY = "change_apply"
    CHANGE_UNDO = "change_undo"
    CHANGE_REDO = "change_redo"

    # System
    ERROR = "error"
    ACK = "ack"


@dataclass
class User:
    """Connected user."""
    user_id: str
    username: str
    email: str
    avatar_url: Optional[str]
    color: str  # Hex color for cursor/selections
    role: str  # viewer, editor, admin
    joined_at: datetime


@dataclass
class CursorPosition:
    """User cursor position."""
    user_id: str
    x: float
    y: float
    timestamp: datetime


@dataclass
class Selection:
    """User selection."""
    user_id: str
    component_ids: List[str]
    bounds: Optional[Dict[str, float]]  # x, y, width, height
    timestamp: datetime


@dataclass
class Annotation:
    """PCB annotation."""
    annotation_id: str
    user_id: str
    x: float
    y: float
    text: str
    type: str  # comment, measurement, arrow, highlight
    color: str
    created_at: datetime
    updated_at: datetime
    resolved: bool


@dataclass
class ChatMessage:
    """Chat message."""
    message_id: str
    user_id: str
    username: str
    text: str
    mentions: List[str]  # User IDs mentioned
    reply_to: Optional[str]  # Message ID this replies to
    timestamp: datetime


class CollaborationSession:
    """Manages a collaborative PCB editing session."""

    def __init__(self, session_id: str, pcb_id: str):
        """
        Initialize collaboration session.

        Args:
            session_id: Unique session identifier
            pcb_id: PCB being collaborated on
        """
        self.session_id = session_id
        self.pcb_id = pcb_id

        # Connected users
        self.users: Dict[str, User] = {}
        self.connections: Dict[str, WebSocket] = {}

        # Collaboration state
        self.cursors: Dict[str, CursorPosition] = {}
        self.selections: Dict[str, Selection] = {}
        self.annotations: Dict[str, Annotation] = {}
        self.chat_messages: List[ChatMessage] = []

        # Operational transformation state
        self.revision = 0
        self.pending_changes: List[Dict[str, Any]] = []

        # Typing indicators
        self.typing_users: Set[str] = set()

        logger.info(f"Collaboration session created: {session_id} for PCB {pcb_id}")

    async def add_user(self, user: User, websocket: WebSocket):
        """
        Add user to session.

        Args:
            user: User to add
            websocket: User's WebSocket connection
        """
        self.users[user.user_id] = user
        self.connections[user.user_id] = websocket

        # Initialize cursor and selection
        self.cursors[user.user_id] = CursorPosition(
            user_id=user.user_id,
            x=0,
            y=0,
            timestamp=datetime.utcnow()
        )

        # Broadcast user joined to all others
        await self.broadcast_message(
            message_type=MessageType.USER_JOINED,
            data={'user': asdict(user)},
            exclude_user=user.user_id
        )

        # Send current state to new user
        await self.send_presence_sync(user.user_id)

        logger.info(f"User {user.username} joined session {self.session_id}")

    async def remove_user(self, user_id: str):
        """
        Remove user from session.

        Args:
            user_id: User to remove
        """
        if user_id in self.users:
            username = self.users[user_id].username
            del self.users[user_id]

        if user_id in self.connections:
            del self.connections[user_id]

        # Clean up user state
        if user_id in self.cursors:
            del self.cursors[user_id]
        if user_id in self.selections:
            del self.selections[user_id]
        if user_id in self.typing_users:
            self.typing_users.remove(user_id)

        # Broadcast user left
        await self.broadcast_message(
            message_type=MessageType.USER_LEFT,
            data={'user_id': user_id, 'username': username}
        )

        logger.info(f"User {username} left session {self.session_id}")

    async def send_presence_sync(self, user_id: str):
        """
        Send current session state to user.

        Args:
            user_id: User to sync
        """
        if user_id not in self.connections:
            return

        state = {
            'users': [asdict(u) for u in self.users.values() if u.user_id != user_id],
            'cursors': {uid: asdict(c) for uid, c in self.cursors.items() if uid != user_id},
            'selections': {uid: asdict(s) for uid, s in self.selections.items() if uid != user_id},
            'annotations': [asdict(a) for a in self.annotations.values()],
            'revision': self.revision
        }

        await self.send_message(
            user_id=user_id,
            message_type=MessageType.PRESENCE_SYNC,
            data=state
        )

    async def handle_cursor_move(self, user_id: str, x: float, y: float):
        """
        Handle cursor movement.

        Args:
            user_id: User moving cursor
            x: X coordinate
            y: Y coordinate
        """
        self.cursors[user_id] = CursorPosition(
            user_id=user_id,
            x=x,
            y=y,
            timestamp=datetime.utcnow()
        )

        # Broadcast to all except sender
        await self.broadcast_message(
            message_type=MessageType.CURSOR_MOVE,
            data={
                'user_id': user_id,
                'x': x,
                'y': y
            },
            exclude_user=user_id
        )

    async def handle_selection_change(
        self,
        user_id: str,
        component_ids: List[str],
        bounds: Optional[Dict[str, float]] = None
    ):
        """
        Handle selection change.

        Args:
            user_id: User making selection
            component_ids: Selected component IDs
            bounds: Selection bounding box
        """
        self.selections[user_id] = Selection(
            user_id=user_id,
            component_ids=component_ids,
            bounds=bounds,
            timestamp=datetime.utcnow()
        )

        await self.broadcast_message(
            message_type=MessageType.SELECTION_CHANGE,
            data={
                'user_id': user_id,
                'component_ids': component_ids,
                'bounds': bounds
            },
            exclude_user=user_id
        )

    async def add_annotation(
        self,
        user_id: str,
        x: float,
        y: float,
        text: str,
        annotation_type: str = "comment"
    ) -> str:
        """
        Add annotation.

        Args:
            user_id: User adding annotation
            x: X coordinate
            y: Y coordinate
            text: Annotation text
            annotation_type: Type of annotation

        Returns:
            Annotation ID
        """
        annotation_id = str(uuid.uuid4())
        user = self.users.get(user_id)

        annotation = Annotation(
            annotation_id=annotation_id,
            user_id=user_id,
            x=x,
            y=y,
            text=text,
            type=annotation_type,
            color=user.color if user else "#FF0000",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            resolved=False
        )

        self.annotations[annotation_id] = annotation

        await self.broadcast_message(
            message_type=MessageType.ANNOTATION_ADD,
            data=asdict(annotation)
        )

        return annotation_id

    async def update_annotation(
        self,
        annotation_id: str,
        updates: Dict[str, Any]
    ):
        """
        Update annotation.

        Args:
            annotation_id: Annotation to update
            updates: Fields to update
        """
        if annotation_id not in self.annotations:
            return

        annotation = self.annotations[annotation_id]

        # Update fields
        if 'text' in updates:
            annotation.text = updates['text']
        if 'resolved' in updates:
            annotation.resolved = updates['resolved']

        annotation.updated_at = datetime.utcnow()

        await self.broadcast_message(
            message_type=MessageType.ANNOTATION_UPDATE,
            data=asdict(annotation)
        )

    async def delete_annotation(self, annotation_id: str):
        """
        Delete annotation.

        Args:
            annotation_id: Annotation to delete
        """
        if annotation_id in self.annotations:
            del self.annotations[annotation_id]

            await self.broadcast_message(
                message_type=MessageType.ANNOTATION_DELETE,
                data={'annotation_id': annotation_id}
            )

    async def send_chat_message(
        self,
        user_id: str,
        text: str,
        mentions: Optional[List[str]] = None,
        reply_to: Optional[str] = None
    ) -> str:
        """
        Send chat message.

        Args:
            user_id: User sending message
            text: Message text
            mentions: User IDs mentioned
            reply_to: Message ID being replied to

        Returns:
            Message ID
        """
        message_id = str(uuid.uuid4())
        user = self.users.get(user_id)

        message = ChatMessage(
            message_id=message_id,
            user_id=user_id,
            username=user.username if user else "Unknown",
            text=text,
            mentions=mentions or [],
            reply_to=reply_to,
            timestamp=datetime.utcnow()
        )

        self.chat_messages.append(message)

        # Remove from typing users
        self.typing_users.discard(user_id)

        await self.broadcast_message(
            message_type=MessageType.CHAT_MESSAGE,
            data=asdict(message)
        )

        return message_id

    async def set_typing_indicator(self, user_id: str, is_typing: bool):
        """
        Set typing indicator.

        Args:
            user_id: User typing
            is_typing: Whether user is typing
        """
        if is_typing:
            self.typing_users.add(user_id)
        else:
            self.typing_users.discard(user_id)

        await self.broadcast_message(
            message_type=MessageType.CHAT_TYPING,
            data={
                'user_id': user_id,
                'is_typing': is_typing,
                'typing_users': list(self.typing_users)
            },
            exclude_user=user_id
        )

    async def broadcast_analysis_progress(
        self,
        progress: float,
        status: str
    ):
        """
        Broadcast analysis progress to all users.

        Args:
            progress: Progress percentage (0-100)
            status: Status message
        """
        await self.broadcast_message(
            message_type=MessageType.ANALYSIS_PROGRESS,
            data={
                'progress': progress,
                'status': status
            }
        )

    async def broadcast_message(
        self,
        message_type: MessageType,
        data: Any,
        exclude_user: Optional[str] = None
    ):
        """
        Broadcast message to all connected users.

        Args:
            message_type: Type of message
            data: Message payload
            exclude_user: User ID to exclude (optional)
        """
        message = {
            'type': message_type.value,
            'session_id': self.session_id,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }

        message_json = json.dumps(message)

        # Send to all connected users
        disconnected_users = []

        for user_id, websocket in self.connections.items():
            if exclude_user and user_id == exclude_user:
                continue

            try:
                await websocket.send_text(message_json)
            except WebSocketDisconnect:
                disconnected_users.append(user_id)
                logger.warning(f"User {user_id} disconnected during broadcast")
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {e}")
                disconnected_users.append(user_id)

        # Clean up disconnected users
        for user_id in disconnected_users:
            await self.remove_user(user_id)

    async def send_message(
        self,
        user_id: str,
        message_type: MessageType,
        data: Any
    ):
        """
        Send message to specific user.

        Args:
            user_id: Target user
            message_type: Type of message
            data: Message payload
        """
        if user_id not in self.connections:
            return

        message = {
            'type': message_type.value,
            'session_id': self.session_id,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }

        try:
            await self.connections[user_id].send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message to user {user_id}: {e}")


class CollaborationManager:
    """Manages all collaboration sessions."""

    def __init__(self):
        """Initialize collaboration manager."""
        self.sessions: Dict[str, CollaborationSession] = {}
        self.user_sessions: Dict[str, str] = {}  # user_id -> session_id
        logger.info("CollaborationManager initialized")

    def create_session(self, pcb_id: str) -> str:
        """
        Create new collaboration session.

        Args:
            pcb_id: PCB to collaborate on

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        session = CollaborationSession(session_id, pcb_id)
        self.sessions[session_id] = session

        logger.info(f"Created collaboration session {session_id} for PCB {pcb_id}")
        return session_id

    def get_session(self, session_id: str) -> Optional[CollaborationSession]:
        """
        Get collaboration session.

        Args:
            session_id: Session ID

        Returns:
            Session or None
        """
        return self.sessions.get(session_id)

    def get_or_create_session(self, pcb_id: str) -> Tuple[str, CollaborationSession]:
        """
        Get existing session for PCB or create new one.

        Args:
            pcb_id: PCB ID

        Returns:
            (session_id, session)
        """
        # Look for existing session for this PCB
        for session_id, session in self.sessions.items():
            if session.pcb_id == pcb_id:
                return session_id, session

        # Create new session
        session_id = self.create_session(pcb_id)
        return session_id, self.sessions[session_id]

    async def join_session(
        self,
        session_id: str,
        user: User,
        websocket: WebSocket
    ):
        """
        Join collaboration session.

        Args:
            session_id: Session to join
            user: User joining
            websocket: WebSocket connection
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        await session.add_user(user, websocket)
        self.user_sessions[user.user_id] = session_id

    async def leave_session(self, user_id: str):
        """
        Leave collaboration session.

        Args:
            user_id: User leaving
        """
        if user_id not in self.user_sessions:
            return

        session_id = self.user_sessions[user_id]
        session = self.get_session(session_id)

        if session:
            await session.remove_user(user_id)

        del self.user_sessions[user_id]

        # Clean up empty sessions
        if session and len(session.users) == 0:
            del self.sessions[session_id]
            logger.info(f"Removed empty session {session_id}")

    def cleanup_stale_sessions(self, max_age_hours: int = 24):
        """
        Clean up stale sessions.

        Args:
            max_age_hours: Maximum session age in hours
        """
        now = datetime.utcnow()
        stale_sessions = []

        for session_id, session in self.sessions.items():
            # Check if session has any users
            if len(session.users) == 0:
                # Check last activity
                if session.users:
                    latest_activity = max(
                        u.joined_at for u in session.users.values()
                    )
                    age_hours = (now - latest_activity).total_seconds() / 3600

                    if age_hours > max_age_hours:
                        stale_sessions.append(session_id)

        # Remove stale sessions
        for session_id in stale_sessions:
            del self.sessions[session_id]
            logger.info(f"Cleaned up stale session {session_id}")


# Singleton instance
collaboration_manager = CollaborationManager()


# Background task to clean up stale sessions
async def cleanup_stale_sessions_task():
    """Background task to clean up stale sessions."""
    while True:
        await asyncio.sleep(3600)  # Run every hour
        collaboration_manager.cleanup_stale_sessions()
        logger.info("Ran stale session cleanup")
