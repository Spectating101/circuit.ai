"""
WebSocket Routes for Real-Time Collaboration

Provides WebSocket endpoints for:
- Real-time collaboration
- Live analysis progress
- Notifications
- Presence awareness
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from loguru import logger
import json
from datetime import datetime

from src.realtime.collaboration import (
    collaboration_manager,
    User,
    MessageType
)


router = APIRouter()


@router.websocket("/ws/collaborate/{pcb_id}")
async def websocket_collaborate(
    websocket: WebSocket,
    pcb_id: str,
    user_id: str = Query(...),
    username: str = Query(...),
    email: str = Query(...),
    role: str = Query(default="editor"),
    color: Optional[str] = Query(default=None)
):
    """
    WebSocket endpoint for real-time PCB collaboration.

    Args:
        pcb_id: PCB to collaborate on
        user_id: User ID
        username: Username
        email: User email
        role: User role (viewer, editor, admin)
        color: User color for cursor/selections

    Example:
        ws://localhost:8000/ws/collaborate/pcb123?user_id=user1&username=John&email=john@example.com
    """
    await websocket.accept()

    # Generate random color if not provided
    if not color:
        import random
        color = f"#{random.randint(0, 0xFFFFFF):06x}"

    # Create user object
    user = User(
        user_id=user_id,
        username=username,
        email=email,
        avatar_url=None,
        color=color,
        role=role,
        joined_at=datetime.utcnow()
    )

    # Get or create session
    session_id, session = collaboration_manager.get_or_create_session(pcb_id)

    try:
        # Join session
        await collaboration_manager.join_session(session_id, user, websocket)

        # Handle messages
        while True:
            try:
                # Receive message
                data = await websocket.receive_text()
                message = json.loads(data)

                message_type = message.get('type')
                payload = message.get('data', {})

                # Route message to appropriate handler
                await handle_websocket_message(
                    session=session,
                    user_id=user_id,
                    message_type=message_type,
                    payload=payload
                )

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for user {username}")
                break
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from user {username}: {e}")
                await websocket.send_text(json.dumps({
                    'type': MessageType.ERROR.value,
                    'data': {'error': 'Invalid JSON'}
                }))
            except Exception as e:
                logger.error(f"Error handling message from user {username}: {e}")
                await websocket.send_text(json.dumps({
                    'type': MessageType.ERROR.value,
                    'data': {'error': str(e)}
                }))

    except Exception as e:
        logger.error(f"Error in WebSocket collaboration for user {username}: {e}")

    finally:
        # Clean up
        await collaboration_manager.leave_session(user_id)
        try:
            await websocket.close()
        except:
            pass


async def handle_websocket_message(
    session,
    user_id: str,
    message_type: str,
    payload: Dict[str, Any]
):
    """
    Handle incoming WebSocket message.

    Args:
        session: Collaboration session
        user_id: User ID
        message_type: Message type
        payload: Message payload
    """
    try:
        msg_type = MessageType(message_type)
    except ValueError:
        logger.warning(f"Unknown message type: {message_type}")
        return

    # Cursor movement
    if msg_type == MessageType.CURSOR_MOVE:
        x = payload.get('x', 0)
        y = payload.get('y', 0)
        await session.handle_cursor_move(user_id, x, y)

    # Selection change
    elif msg_type == MessageType.SELECTION_CHANGE:
        component_ids = payload.get('component_ids', [])
        bounds = payload.get('bounds')
        await session.handle_selection_change(user_id, component_ids, bounds)

    # Add annotation
    elif msg_type == MessageType.ANNOTATION_ADD:
        x = payload.get('x', 0)
        y = payload.get('y', 0)
        text = payload.get('text', '')
        annotation_type = payload.get('annotation_type', 'comment')
        annotation_id = await session.add_annotation(user_id, x, y, text, annotation_type)

        # Send ACK with annotation ID
        await session.send_message(
            user_id,
            MessageType.ACK,
            {'annotation_id': annotation_id}
        )

    # Update annotation
    elif msg_type == MessageType.ANNOTATION_UPDATE:
        annotation_id = payload.get('annotation_id')
        updates = payload.get('updates', {})
        await session.update_annotation(annotation_id, updates)

    # Delete annotation
    elif msg_type == MessageType.ANNOTATION_DELETE:
        annotation_id = payload.get('annotation_id')
        await session.delete_annotation(annotation_id)

    # Chat message
    elif msg_type == MessageType.CHAT_MESSAGE:
        text = payload.get('text', '')
        mentions = payload.get('mentions', [])
        reply_to = payload.get('reply_to')
        message_id = await session.send_chat_message(user_id, text, mentions, reply_to)

        # Send ACK
        await session.send_message(
            user_id,
            MessageType.ACK,
            {'message_id': message_id}
        )

    # Typing indicator
    elif msg_type == MessageType.CHAT_TYPING:
        is_typing = payload.get('is_typing', False)
        await session.set_typing_indicator(user_id, is_typing)

    # Component highlight
    elif msg_type == MessageType.COMPONENT_HIGHLIGHT:
        component_id = payload.get('component_id')
        await session.broadcast_message(
            message_type=MessageType.COMPONENT_HIGHLIGHT,
            data={
                'user_id': user_id,
                'component_id': component_id
            },
            exclude_user=user_id
        )

    # Component comment
    elif msg_type == MessageType.COMPONENT_COMMENT:
        component_id = payload.get('component_id')
        comment = payload.get('comment', '')
        # Store comment as annotation on component
        await session.add_annotation(
            user_id=user_id,
            x=0,  # Would get from component position
            y=0,
            text=f"Component {component_id}: {comment}",
            annotation_type="component_comment"
        )


@router.websocket("/ws/analysis/{analysis_id}")
async def websocket_analysis_progress(
    websocket: WebSocket,
    analysis_id: str,
    user_id: str = Query(...)
):
    """
    WebSocket endpoint for live analysis progress.

    Streams real-time progress updates during PCB analysis.

    Args:
        analysis_id: Analysis job ID
        user_id: User ID

    Example:
        ws://localhost:8000/ws/analysis/abc123?user_id=user1
    """
    await websocket.accept()

    try:
        logger.info(f"Analysis progress WebSocket connected: {analysis_id}")

        # Send initial status
        await websocket.send_text(json.dumps({
            'type': 'analysis_start',
            'analysis_id': analysis_id,
            'status': 'connected'
        }))

        # In production, this would subscribe to analysis progress events
        # For now, simulate progress updates
        import asyncio

        progress_steps = [
            (10, "Uploading image"),
            (25, "Pre-processing image"),
            (40, "Running component detection"),
            (60, "Analyzing traces"),
            (75, "Generating BOM"),
            (90, "Creating report"),
            (100, "Complete")
        ]

        for progress, status in progress_steps:
            await asyncio.sleep(1)  # Simulate work

            await websocket.send_text(json.dumps({
                'type': 'analysis_progress',
                'analysis_id': analysis_id,
                'progress': progress,
                'status': status,
                'timestamp': datetime.utcnow().isoformat()
            }))

        # Send completion
        await websocket.send_text(json.dumps({
            'type': 'analysis_complete',
            'analysis_id': analysis_id,
            'result_url': f'/api/analysis/{analysis_id}/results'
        }))

    except WebSocketDisconnect:
        logger.info(f"Analysis progress WebSocket disconnected: {analysis_id}")
    except Exception as e:
        logger.error(f"Error in analysis progress WebSocket: {e}")
        try:
            await websocket.send_text(json.dumps({
                'type': 'error',
                'error': str(e)
            }))
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass


@router.websocket("/ws/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    user_id: str = Query(...)
):
    """
    WebSocket endpoint for real-time notifications.

    Receives system notifications, mentions, alerts, etc.

    Args:
        user_id: User ID

    Example:
        ws://localhost:8000/ws/notifications?user_id=user1
    """
    await websocket.accept()

    try:
        logger.info(f"Notifications WebSocket connected for user {user_id}")

        # Send welcome message
        await websocket.send_text(json.dumps({
            'type': 'connected',
            'message': 'Notifications stream connected'
        }))

        # In production, this would subscribe to notification events
        # Keep connection alive and send notifications as they arrive
        while True:
            try:
                # Keep alive ping every 30 seconds
                import asyncio
                await asyncio.sleep(30)

                await websocket.send_text(json.dumps({
                    'type': 'ping',
                    'timestamp': datetime.utcnow().isoformat()
                }))

            except WebSocketDisconnect:
                break

    except Exception as e:
        logger.error(f"Error in notifications WebSocket: {e}")
    finally:
        logger.info(f"Notifications WebSocket disconnected for user {user_id}")
        try:
            await websocket.close()
        except:
            pass


@router.get("/api/v2/collaboration/sessions")
async def list_collaboration_sessions():
    """
    List all active collaboration sessions.

    Returns:
        List of active sessions with user counts
    """
    sessions_info = []

    for session_id, session in collaboration_manager.sessions.items():
        sessions_info.append({
            'session_id': session_id,
            'pcb_id': session.pcb_id,
            'user_count': len(session.users),
            'users': [
                {
                    'user_id': user.user_id,
                    'username': user.username,
                    'role': user.role,
                    'joined_at': user.joined_at.isoformat()
                }
                for user in session.users.values()
            ],
            'annotation_count': len(session.annotations),
            'message_count': len(session.chat_messages)
        })

    return sessions_info


@router.get("/api/v2/collaboration/sessions/{session_id}")
async def get_collaboration_session(session_id: str):
    """
    Get collaboration session details.

    Args:
        session_id: Session ID

    Returns:
        Session details
    """
    session = collaboration_manager.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    return {
        'session_id': session.session_id,
        'pcb_id': session.pcb_id,
        'users': [
            {
                'user_id': user.user_id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'color': user.color,
                'joined_at': user.joined_at.isoformat()
            }
            for user in session.users.values()
        ],
        'annotations': [
            {
                'annotation_id': a.annotation_id,
                'user_id': a.user_id,
                'x': a.x,
                'y': a.y,
                'text': a.text,
                'type': a.type,
                'resolved': a.resolved,
                'created_at': a.created_at.isoformat()
            }
            for a in session.annotations.values()
        ],
        'chat_messages': [
            {
                'message_id': m.message_id,
                'user_id': m.user_id,
                'username': m.username,
                'text': m.text,
                'timestamp': m.timestamp.isoformat()
            }
            for m in session.chat_messages[-50:]  # Last 50 messages
        ]
    }


@router.delete("/api/v2/collaboration/sessions/{session_id}")
async def end_collaboration_session(session_id: str):
    """
    End collaboration session.

    Args:
        session_id: Session to end

    Returns:
        Success message
    """
    session = collaboration_manager.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    # Disconnect all users
    for user_id in list(session.users.keys()):
        await collaboration_manager.leave_session(user_id)

    # Remove session
    del collaboration_manager.sessions[session_id]

    return {'message': f'Session {session_id} ended successfully'}
