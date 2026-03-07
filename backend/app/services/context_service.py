"""
Context Extraction Service
───────────────────────────
Runs a background loop (every 60s) for each active session:
  1. Pulls the last ~5 minutes of transcript from the DB
  2. Sends it to Gemini extract_context()
  3. Saves the structured result (subtopic, key_terms, examples) to session_context table
  4. Broadcasts the update to the professor dashboard via WebSocket

This is the glue between Recall.ai transcripts and the Gemini AI pipeline.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from ..api import db
from ..api.recall_router import manager
from ..utils.gemini import extract_context

logger = logging.getLogger("qnai.context_service")

# How often to run extraction (seconds)
EXTRACTION_INTERVAL = 60

# How many minutes of transcript to feed Gemini
TRANSCRIPT_BUFFER_MINUTES = 5

# Track running tasks per session so we don't double-start
_running_tasks: dict[str, asyncio.Task] = {}


async def _extract_loop(session_id: str):
    """Runs forever (until cancelled) for one session."""
    logger.info(f"Context extraction started for session {session_id}")

    while True:
        try:
            await asyncio.sleep(EXTRACTION_INTERVAL)

            # 1. Check session is still active
            session = db.get_session(session_id)
            if not session or not session.get("is_active"):
                logger.info(f"Session {session_id} no longer active, stopping extraction")
                break

            # 2. Pull recent transcripts (last 5 min)
            all_transcripts = db.get_transcripts(session_id)
            if not all_transcripts:
                logger.debug(f"No transcripts yet for {session_id}, skipping")
                continue

            # Filter to last N minutes
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=TRANSCRIPT_BUFFER_MINUTES)
            cutoff_str = cutoff.isoformat()
            recent = [t for t in all_transcripts if t["created_at"] >= cutoff_str]

            # If nothing recent, use the last 20 chunks regardless of time
            if not recent:
                recent = all_transcripts[-20:]

            # 3. Build transcript text
            transcript_text = "\n".join(
                [f"{t['speaker']}: {t['text']}" for t in recent]
            )

            if not transcript_text.strip():
                continue

            # 4. Call Gemini extract_context (runs synchronously — it's fast enough)
            logger.info(f"Extracting context for {session_id} ({len(recent)} chunks)")
            context = await asyncio.to_thread(extract_context, transcript_text)

            # 5. Save to DB
            db.save_context(session_id, context, raw_buffer=transcript_text[-2000:])

            # 6. Broadcast to professor dashboard
            await manager.broadcast({
                "type": "context_update",
                "data": {
                    "current_subtopic": context.get("current_subtopic", "unknown"),
                    "key_terms": context.get("key_terms", []),
                    "examples": context.get("examples", []),
                }
            })

            logger.info(
                f"Context updated for {session_id}: "
                f"subtopic='{context.get('current_subtopic')}', "
                f"terms={context.get('key_terms')}"
            )

        except asyncio.CancelledError:
            logger.info(f"Context extraction cancelled for {session_id}")
            break
        except Exception as e:
            logger.error(f"Context extraction error for {session_id}: {e}", exc_info=True)
            # Don't crash the loop — wait and retry next cycle
            continue

    # Cleanup
    _running_tasks.pop(session_id, None)


def start_extraction(session_id: str):
    """Start the 60s context extraction loop for a session."""
    if session_id in _running_tasks:
        logger.warning(f"Extraction already running for {session_id}")
        return

    task = asyncio.create_task(_extract_loop(session_id))
    _running_tasks[session_id] = task
    logger.info(f"Extraction task created for {session_id}")


def stop_extraction(session_id: str):
    """Stop the extraction loop for a session."""
    task = _running_tasks.pop(session_id, None)
    if task:
        task.cancel()
        logger.info(f"Extraction task cancelled for {session_id}")


def stop_all():
    """Stop all running extraction loops (called on shutdown)."""
    for sid in list(_running_tasks.keys()):
        stop_extraction(sid)