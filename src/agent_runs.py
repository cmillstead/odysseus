"""Detached agent-run manager.

Keeps an agent/chat stream running server-side after the SSE client disconnects
(tab close, navigate away, refresh). The streaming generator is drained by a
background asyncio task into a per-session replay buffer; SSE clients SUBSCRIBE
to that buffer (replay everything so far, then live). Closing the SSE only drops
the subscriber — the drain task keeps going.

The wrapped generator already persists the assistant message to the session on
completion, so reopening the session shows the finished result even if nobody
was connected when it finished. Reconnecting mid-run replays the buffer + streams
live (pick up where it is).

Durability scope: in-memory, survives as long as the server process runs (tab
close / navigation / refresh). It does NOT survive a server restart.
"""
import asyncio
import json
import logging
import uuid
from typing import AsyncGenerator, Dict, Optional

logger = logging.getLogger(__name__)


class _Run:
    __slots__ = ("buffer", "subscribers", "status", "task", "evict_task", "run_id", "event_count")

    def __init__(self) -> None:
        self.buffer: list = []          # ordered SSE event strings (replay log)
        self.subscribers: set = set()   # one asyncio.Queue per connected client
        self.status: str = "running"    # running | done | error | stopped
        self.task: Optional[asyncio.Task] = None
        self.evict_task: Optional[asyncio.Task] = None
        self.run_id: Optional[str] = None
        self.event_count: int = 0


_RUNS: Dict[str, _Run] = {}

# How long a FINISHED run (and its full replay buffer) is retained after the
# last subscriber disconnects, so a reconnect within the window can still
# replay the result. After this, the run is evicted to bound memory — without
# it, every session that ever streamed kept its entire event log forever.
_EVICT_GRACE_S = 180


def _publish(run: _Run, ev: str) -> None:
    """Append one SSE event and fan it out to every live subscriber."""
    run.buffer.append(ev)
    seq = len(run.buffer) - 1
    run.event_count += 1
    for q in list(run.subscribers):
        try:
            q.put_nowait((seq, ev))
        except Exception:
            pass
    _persist_stream_sample(run, seq, ev)


def _persist_stream_sample(run: _Run, seq: int, ev: str) -> None:
    """Persist sampled stream telemetry without writing every token to SQLite."""
    if not run.run_id:
        return
    terminal = "[DONE]" in ev or "event: error" in ev
    if not terminal and seq % 25 != 0:
        return
    try:
        from services.runs import get_run_registry

        get_run_registry().append_event(
            run.run_id,
            "stream_event",
            "Agent stream event persisted",
            payload={
                "seq": seq,
                "bytes": len(ev),
                "terminal": terminal,
                "preview": ev[:500],
            },
        )
    except Exception:
        logger.debug("Run registry stream event sync failed", exc_info=True)


def _schedule_evict(session_id: str) -> None:
    """(Re)arm a grace-period eviction for a terminal run with no subscribers.
    Identity-checked so a run that gets replaced/reused is never evicted by a
    stale timer."""
    run = _RUNS.get(session_id)
    if run is None:
        return
    if run.evict_task and not run.evict_task.done():
        run.evict_task.cancel()

    async def _evict(run_ref: _Run) -> None:
        try:
            await asyncio.sleep(_EVICT_GRACE_S)
        except asyncio.CancelledError:
            return
        cur = _RUNS.get(session_id)
        if cur is run_ref and cur.status != "running" and not cur.subscribers:
            _RUNS.pop(session_id, None)

    run.evict_task = asyncio.create_task(_evict(run))


def is_active(session_id: str) -> bool:
    r = _RUNS.get(session_id)
    return bool(r and r.status == "running")


def get_status(session_id: str) -> Optional[str]:
    r = _RUNS.get(session_id)
    return r.status if r else None


def _create_registry_run(session_id: str) -> Optional[str]:
    try:
        import os
        import time

        from core.database import Session as DbSession, SessionLocal
        from services.runs import get_run_registry
        db = SessionLocal()
        try:
            sess = db.query(DbSession).filter(DbSession.id == session_id).first()
            owner = getattr(sess, "owner", None) if sess else None
            title = f"Agent: {getattr(sess, 'name', None) or session_id[:8]}"
            model = getattr(sess, "model", None) if sess else None
        finally:
            db.close()
        registry = get_run_registry()
        run = registry.create_run(
            run_type="agent",
            title=title,
            owner=owner,
            objective=f"Detached chat stream for session {session_id}",
            origin="chat_stream",
            executor="local_agent",
            backend="local",
            model=model,
            session_id=session_id,
            external_type="agent_stream",
            external_id=f"{session_id}:{uuid.uuid4().hex[:8]}",
            status="running",
            current_step="Streaming response",
            metadata={
                "executor": "local_agent",
                "durability_scope": "local_process_with_registry_recovery",
                "restart_recovery": "block_if_worker_missing",
                "last_heartbeat_at": time.time(),
                "pid": os.getpid(),
                "capabilities": {
                    "cancel": True,
                    "pause": True,
                    "resume": True,
                    "inputs": True,
                    "approvals": True,
                    "artifacts": True,
                    "subruns": True,
                    "restart_recovery": "truthful_blocked",
                    "durability": "registry_events",
                },
            },
        )
        registry.append_event(run["id"], "status", "Agent stream started", payload={"session_id": session_id}, owner=owner)
        registry.append_event(
            run["id"],
            "checkpoint",
            "Stream checkpoint created",
            payload={"checkpoint": "start", "session_id": session_id},
            owner=owner,
        )
        return run["id"]
    except Exception:
        logger.debug("Run registry agent stream start sync failed for %s", session_id, exc_info=True)
        return None


def _update_registry_run(run: _Run, session_id: str, status: str, message: str) -> None:
    if not getattr(run, "run_id", None):
        return
    try:
        from services.runs import get_run_registry
        normalized = {
            "done": "succeeded",
            "error": "failed",
            "stopped": "cancelled",
        }.get(status, status)
        registry = get_run_registry()
        registry.update_run(
            run.run_id,
            status=normalized,
            current_step=message,
            summary=message if normalized == "succeeded" else None,
            error=message if normalized == "failed" else None,
            metadata={"final_event_count": getattr(run, "event_count", 0)},
            event_type="complete" if normalized == "succeeded" else ("cancel" if normalized == "cancelled" else "error"),
            event_message=message,
        )
        if normalized == "succeeded":
            registry.append_event(
                run.run_id,
                "checkpoint",
                "Final output checkpoint saved",
                payload={"event_count": getattr(run, "event_count", 0)},
            )
    except Exception:
        logger.debug("Run registry agent stream finish sync failed for %s", session_id, exc_info=True)


async def _drain(session_id: str, agen: AsyncGenerator[str, None],
                 prev_task: Optional[asyncio.Task] = None) -> None:
    """Pull every event from the wrapped generator into the run buffer, fanning
    each out to live subscribers. Runs to completion regardless of subscribers."""
    run = _RUNS.get(session_id)
    if run is None:
        return
    # If this run replaced an in-flight one (rapid double-send), wait for that
    # one to fully finish first. Its CancelledError handler calls aclose(), which
    # persists its partial response — letting it complete before we start writing
    # keeps the two runs' session saves sequential instead of interleaved.
    if prev_task is not None and not prev_task.done():
        try:
            await asyncio.wait({prev_task})
        except asyncio.CancelledError:
            raise            # our own cancellation — propagate
        except Exception:
            pass
    try:
        async for ev in agen:
            _publish(run, ev)
        if run.status == "running":
            run.status = "done"
            _update_registry_run(run, session_id, "done", "Agent stream completed")
    except asyncio.CancelledError:
        run.status = "stopped"
        # Let the wrapped generator's own CancelledError handler run (it saves
        # the partial response to the session).
        try:
            await agen.aclose()
        except Exception:
            pass
        _update_registry_run(run, session_id, "stopped", "Agent stream stopped")
    except Exception as e:
        logger.error("[agent-run] %s failed: %s", session_id, e, exc_info=True)
        run.status = "error"
        _update_registry_run(run, session_id, "error", "Agent stream failed")
        _publish(
            run,
            "event: error\n"
            f"data: {json.dumps({'error': 'Agent run failed before completion.', 'status': 500})}\n\n",
        )
        _publish(run, "data: [DONE]\n\n")
    finally:
        # Wake every subscriber with the end sentinel so their SSE closes.
        for q in list(run.subscribers):
            try:
                q.put_nowait((None, None))
            except Exception:
                pass
        # Run is terminal — arm the grace timer so it (and its buffer) is
        # eventually freed even if nobody ever reconnects. subscribe() cancels
        # this on connect and re-arms on disconnect.
        _schedule_evict(session_id)


def start(session_id: str, agen: AsyncGenerator[str, None]) -> _Run:
    """Start a detached run draining `agen` for a session. If a run is already in
    flight for this session (e.g. a rapid double-send), it's cancelled first."""
    prev = _RUNS.get(session_id)
    prev_task: Optional[asyncio.Task] = None
    if prev:
        if prev.task and not prev.task.done():
            prev.task.cancel()
            prev_task = prev.task   # new run awaits this before it starts writing
        if prev.evict_task and not prev.evict_task.done():
            prev.evict_task.cancel()
    run = _Run()
    run.run_id = _create_registry_run(session_id)
    _RUNS[session_id] = run
    run.task = asyncio.create_task(_drain(session_id, agen, prev_task))
    return run


async def subscribe(session_id: str) -> AsyncGenerator[str, None]:
    """Replay the run's buffer from the start, then stream live until it ends.
    Safe to call repeatedly (reconnect) and from multiple clients at once."""
    run = _RUNS.get(session_id)
    if run is None:
        return
    q: asyncio.Queue = asyncio.Queue()
    run.subscribers.add(q)            # register BEFORE replaying so nothing is missed
    # A live subscriber is connected — don't let a pending grace timer evict
    # the run out from under it mid-replay.
    if run.evict_task and not run.evict_task.done():
        run.evict_task.cancel()
    try:
        next_seq = 0
        while next_seq < len(run.buffer):
            yield run.buffer[next_seq]
            next_seq += 1
        if run.status != "running":
            return
        heartbeat_idx = 0
        while True:
            try:
                seq, ev = await asyncio.wait_for(q.get(), timeout=10.0)
            except asyncio.TimeoutError:
                # Keep slow local models/proxies alive while they prefill before
                # the first token. SSE comments are ignored by the UI but reset
                # browser/proxy idle timers, which prevents "empty response"
                # disconnects on llama.cpp first-token latencies of 30s+.
                if run.status == "running":
                    heartbeat_idx += 1
                    yield f": heartbeat {heartbeat_idx}\n\n"
                    continue
                seq, ev = (None, None)
            if seq is None:            # end sentinel
                while next_seq < len(run.buffer):   # flush any tail the sentinel raced
                    yield run.buffer[next_seq]
                    next_seq += 1
                break
            if seq >= next_seq:        # skip events already replayed from the buffer
                yield ev
                next_seq = seq + 1
    finally:
        run.subscribers.discard(q)
        # Last subscriber gone on a finished run — (re)arm eviction so the
        # buffer doesn't linger indefinitely.
        if not run.subscribers and run.status != "running":
            _schedule_evict(session_id)


def stop(session_id: str) -> bool:
    """Cancel an in-flight run (the wrapped generator saves its partial)."""
    run = _RUNS.get(session_id)
    if run and run.task and not run.task.done():
        try:
            if run.run_id:
                from services.runs import get_run_registry
                get_run_registry().update_run(
                    run.run_id,
                    status="cancelled",
                    current_step="Stop requested",
                    event_type="cancel",
                    event_message="Agent stream stop requested",
                )
        except Exception:
            pass
        run.task.cancel()
        return True
    return False
