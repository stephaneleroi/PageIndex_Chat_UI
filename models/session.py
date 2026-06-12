#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Chat session models for PageIndex Chat UI.

A ChatSession is a unit of conversation decoupled from Document:
  - mode='single'  : conversation bound to exactly one document
                     (doc_ids == [doc_id])
  - mode='kb'      : knowledge-base mode, conversation may reference any
                     subset of documents

    Sessions are persisted per mode so the two UIs never leak into each other:

        results/
          _index/
            sessions_single.json   # lightweight list of single-mode sessions
            sessions_kb.json       # lightweight list of kb-mode sessions
          _sessions/
            kb/<session_id>.json                   # kb sessions are flat
            single/<doc_dir_name>/<session_id>.json  # single sessions are
                                                    # grouped per document,
                                                    # mirroring results/documents/<doc_dir_name>/
            single/_unbound/<session_id>.json      # single session not yet
                                                    # bound to a document
"""

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(BASE_DIR, 'results')
INDEX_DIR = os.path.join(RESULTS_DIR, '_index')
SESSIONS_DIR = os.path.join(RESULTS_DIR, '_sessions')

# Per-mode locations
_MODES = ('single', 'kb')
INDEX_PATHS = {
    'single': os.path.join(INDEX_DIR, 'sessions_single.json'),
    'kb':     os.path.join(INDEX_DIR, 'sessions_kb.json'),
}
BODY_DIRS = {
    'single': os.path.join(SESSIONS_DIR, 'single'),
    'kb':     os.path.join(SESSIONS_DIR, 'kb'),
}
# Folder name used for single-mode sessions that have no document bound yet.
UNBOUND_SUBDIR = '_unbound'


@dataclass
class Message:
    """Chat message (also re-exported from models.document for backwards compat).

    ``superseded`` marks a message as "replaced by a later turn" — used when
    the agent's self-reflection triggers a retry that produces an improved
    answer. The original low-score draft stays visible in the UI history
    (so users can see the reasoning arc), but is skipped when assembling
    LLM history context so the model isn't confused by the stale draft.
    """
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: float = field(default_factory=time.time)
    nodes: List[str] = field(default_factory=list)
    thinking: str = ''
    superseded: bool = False
    # Résultat de l'auto-évaluation ou d'une vérification à la demande :
    # {score, issues, missing_info, auto, verified_at} — None = non vérifiée.
    verification: Optional[dict] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class ChatSession:
    """A chat session, independent from any Document lifecycle."""
    session_id: str
    mode: str  # 'single' | 'kb'
    title: str = ''
    doc_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    messages: List[Message] = field(default_factory=list)

    def to_summary(self) -> dict:
        """Compact representation used by the per-mode index files."""
        return {
            'session_id': self.session_id,
            'mode': self.mode,
            'title': self.title,
            'doc_ids': list(self.doc_ids),
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'message_count': len(self.messages),
        }

    def to_dict(self) -> dict:
        return {
            'session_id': self.session_id,
            'mode': self.mode,
            'title': self.title,
            'doc_ids': list(self.doc_ids),
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'messages': [m.to_dict() for m in self.messages],
        }

    @staticmethod
    def from_dict(data: dict) -> 'ChatSession':
        msgs = [
            Message(
                role=m.get('role', 'user'),
                content=m.get('content', ''),
                timestamp=m.get('timestamp', time.time()),
                nodes=m.get('nodes', []) or [],
                thinking=m.get('thinking', '') or '',
                superseded=bool(m.get('superseded', False)),
                verification=m.get('verification'),
            )
            for m in data.get('messages', [])
        ]
        return ChatSession(
            session_id=data['session_id'],
            mode=data.get('mode', 'single'),
            title=data.get('title', ''),
            doc_ids=data.get('doc_ids', []) or [],
            created_at=data.get('created_at', time.time()),
            updated_at=data.get('updated_at', time.time()),
            messages=msgs,
        )


class SessionStore:
    """File-based session persistence with per-mode isolation.

    Directory layout (see module docstring)::

        results/_index/sessions_single.json
        results/_index/sessions_kb.json
        results/_sessions/kb/<id>.json
        results/_sessions/single/<doc_dir_name>/<id>.json
        results/_sessions/single/_unbound/<id>.json   # no document bound yet

    Single-mode sessions live under a per-document subfolder whose name
    matches ``Document.result_dir_name`` (so it also matches the folder used
    under ``results/documents/``). The summary cached in the index file
    remembers that subfolder via the ``body_subdir`` field so body lookups
    don't have to reverse-resolve the document every time.

    Session ids are still globally unique (prefixed with mode at creation
    time, e.g. ``sess_single_...`` / ``sess_kb_...``) so lookups remain
    cheap even without knowing the mode upfront.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        os.makedirs(INDEX_DIR, exist_ok=True)
        for d in BODY_DIRS.values():
            os.makedirs(d, exist_ok=True)
        # index: mode -> {session_id: summary}
        self._index: Dict[str, Dict[str, dict]] = {m: {} for m in _MODES}
        self._body_cache: Dict[str, ChatSession] = {}
        self._load_indexes()

    # -------------------- index persistence -------------------- #

    def _load_indexes(self):
        for mode in _MODES:
            path = INDEX_PATHS[mode]
            if not os.path.exists(path):
                self._index[mode] = {}
                continue
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self._index[mode] = {
                        s['session_id']: s for s in data if 'session_id' in s
                    }
                elif isinstance(data, dict):
                    self._index[mode] = data
                else:
                    self._index[mode] = {}
            except Exception as e:
                print(f"[SessionStore] Failed to load {mode} index: {e}")
                self._index[mode] = {}

    def _save_index(self, mode: str):
        try:
            with open(INDEX_PATHS[mode], 'w', encoding='utf-8') as f:
                json.dump(
                    list(self._index[mode].values()),
                    f, indent=2, ensure_ascii=False,
                )
        except Exception as e:
            print(f"[SessionStore] Failed to save {mode} index: {e}")

    # -------------------- body persistence -------------------- #

    def _resolve_doc_subdir(self, doc_id: str) -> Optional[str]:
        """Best-effort lookup of the on-disk folder name for a document.

        Imported lazily to avoid a circular import at module load time.
        Returns None if the document is unknown (e.g. already deleted).
        """
        if not doc_id:
            return None
        try:
            from .document import document_store
        except Exception:
            return None
        doc = document_store.get_document(doc_id)
        return doc.result_dir_name if doc else None

    def _single_subdir_for(self, session: 'ChatSession') -> str:
        """Pick the per-document subfolder for a single-mode session body."""
        if session.mode != 'single':
            return ''
        doc_id = session.doc_ids[0] if session.doc_ids else ''
        subdir = self._resolve_doc_subdir(doc_id) if doc_id else ''
        return subdir or UNBOUND_SUBDIR

    def _body_path(self, mode: str, session_id: str,
                   subdir: str = '') -> str:
        if mode == 'single':
            # ``subdir`` should always be provided for single sessions once
            # the caller has a ChatSession in hand, but we fall back to the
            # unbound folder if it's missing (e.g. legacy code paths).
            sub = subdir or UNBOUND_SUBDIR
            return os.path.join(BODY_DIRS['single'], sub, f'{session_id}.json')
        return os.path.join(BODY_DIRS[mode], f'{session_id}.json')

    def _locate(self, session_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Return (mode, body_path) for a session id, or (None, None).

        Fast path: consult the in-memory per-mode index (which remembers
        ``body_subdir`` for single sessions). Slow path: scan the filesystem
        (covers corrupt / missing indexes).
        """
        # Fast path via index.
        for mode in _MODES:
            entry = self._index[mode].get(session_id)
            if entry is None:
                continue
            if mode == 'single':
                subdir = entry.get('body_subdir') or ''
                if not subdir:
                    doc_ids = entry.get('doc_ids') or []
                    subdir = (self._resolve_doc_subdir(doc_ids[0])
                              if doc_ids else '') or UNBOUND_SUBDIR
                return mode, self._body_path('single', session_id, subdir)
            return mode, self._body_path(mode, session_id)

        # Slow path: filesystem scan.
        kb_path = os.path.join(BODY_DIRS['kb'], f'{session_id}.json')
        if os.path.exists(kb_path):
            return 'kb', kb_path
        single_root = BODY_DIRS['single']
        if os.path.isdir(single_root):
            for sub in os.listdir(single_root):
                candidate = os.path.join(single_root, sub, f'{session_id}.json')
                if os.path.exists(candidate):
                    return 'single', candidate
        return None, None

    def _load_body(self, session_id: str) -> Optional[ChatSession]:
        mode, path = self._locate(session_id)
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return ChatSession.from_dict(json.load(f))
        except Exception as e:
            print(f"[SessionStore] Failed to load session {session_id}: {e}")
            return None

    def _save_body(self, session: ChatSession):
        try:
            if session.mode == 'single':
                subdir = self._single_subdir_for(session)
                body_dir = os.path.join(BODY_DIRS['single'], subdir)
                os.makedirs(body_dir, exist_ok=True)
                path = os.path.join(body_dir, f'{session.session_id}.json')
            else:
                path = self._body_path(session.mode, session.session_id)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[SessionStore] Failed to save session {session.session_id}: {e}")

    def _relocate_single_body_if_needed(self, session: ChatSession):
        """Move a single-mode session file if its bound document changed.

        Called after ``doc_ids`` updates so the on-disk folder stays in sync
        with the (possibly new) document. No-op for kb sessions.
        """
        if session.mode != 'single':
            return
        target_subdir = self._single_subdir_for(session)
        target_path = os.path.join(
            BODY_DIRS['single'], target_subdir, f'{session.session_id}.json')
        # Find where the body currently lives.
        current_path = None
        single_root = BODY_DIRS['single']
        if os.path.isdir(single_root):
            for sub in os.listdir(single_root):
                cand = os.path.join(single_root, sub, f'{session.session_id}.json')
                if os.path.exists(cand):
                    current_path = cand
                    break
        if current_path and os.path.abspath(current_path) != os.path.abspath(target_path):
            try:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                os.replace(current_path, target_path)
                # Remove the old folder if it's now empty (but never the
                # _unbound folder, which is a long-lived bucket).
                old_dir = os.path.dirname(current_path)
                if (os.path.basename(old_dir) != UNBOUND_SUBDIR
                        and os.path.isdir(old_dir)
                        and not os.listdir(old_dir)):
                    os.rmdir(old_dir)
            except Exception as e:
                print(f"[SessionStore] Failed to relocate session {session.session_id}: {e}")

    def _write_index_for(self, session: 'ChatSession'):
        """Refresh the per-mode index entry for ``session``.

        For single sessions the summary carries an extra ``body_subdir`` so
        the next ``_locate`` can go straight to the file without consulting
        ``document_store`` again.
        """
        summary = session.to_summary()
        if session.mode == 'single':
            summary['body_subdir'] = self._single_subdir_for(session)
        self._index[session.mode][session.session_id] = summary

    # -------------------- public API -------------------- #

    @staticmethod
    def _new_id(mode: str) -> str:
        return f"sess_{mode}_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    def create_session(self, mode: str, doc_ids: Optional[List[str]] = None,
                       title: str = '') -> ChatSession:
        assert mode in _MODES, f"mode must be one of {_MODES}"
        session = ChatSession(
            session_id=self._new_id(mode),
            mode=mode,
            title=title,
            doc_ids=list(doc_ids or []),
        )
        self._body_cache[session.session_id] = session
        self._save_body(session)
        self._write_index_for(session)
        self._save_index(mode)
        return session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        if session_id in self._body_cache:
            return self._body_cache[session_id]
        s = self._load_body(session_id)
        if s:
            self._body_cache[session_id] = s
        return s

    def list_sessions(self, mode: Optional[str] = None,
                      doc_id: Optional[str] = None) -> List[dict]:
        """Return summary list (newest first), optionally filtered.

        ``mode`` is the primary filter (cheap: reads only one index).
        ``doc_id`` is applied on top.
        """
        if mode and mode in _MODES:
            items = list(self._index[mode].values())
        else:
            items = []
            for m in _MODES:
                items.extend(self._index[m].values())
        if doc_id:
            items = [s for s in items if doc_id in (s.get('doc_ids') or [])]
        items.sort(key=lambda s: s.get('updated_at', 0), reverse=True)
        return items

    def update_session(self, session_id: str, **kwargs) -> Optional[ChatSession]:
        session = self.get_session(session_id)
        if not session:
            return None
        doc_ids_changed = (
            'doc_ids' in kwargs and kwargs['doc_ids'] is not None
            and list(kwargs['doc_ids']) != list(session.doc_ids)
        )
        for k in ('title', 'doc_ids'):
            if k in kwargs and kwargs[k] is not None:
                setattr(session, k, kwargs[k])
        session.updated_at = time.time()
        # If the single session changed its document binding, move its body
        # file into the new per-document folder before rewriting it.
        if doc_ids_changed:
            self._relocate_single_body_if_needed(session)
        self._save_body(session)
        self._write_index_for(session)
        self._save_index(session.mode)
        return session

    def delete_session(self, session_id: str) -> bool:
        mode, path = self._locate(session_id)
        self._body_cache.pop(session_id, None)
        removed = False
        if mode and session_id in self._index[mode]:
            self._index[mode].pop(session_id, None)
            self._save_index(mode)
            removed = True
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                print(f"[SessionStore] Failed to remove session file: {e}")
            # For single sessions, drop the per-document subfolder if it's
            # now empty (but never the long-lived _unbound bucket).
            if mode == 'single':
                parent = os.path.dirname(path)
                if (os.path.basename(parent) != UNBOUND_SUBDIR
                        and os.path.isdir(parent)
                        and not os.listdir(parent)):
                    try:
                        os.rmdir(parent)
                    except OSError:
                        pass
        return removed

    def drop_document_bindings(self, doc_id: str,
                               doc_dir_name: str = '') -> int:
        """Delete every single-mode session tied to ``doc_id``.

        Called from ``DocumentStore.delete_document`` so that removing a
        document also cleans up its dedicated sessions folder under
        ``_sessions/single/<doc_dir_name>/``.

        Returns the number of sessions removed.
        """
        victims = [
            sid for sid, summary in self._index['single'].items()
            if doc_id in (summary.get('doc_ids') or [])
        ]
        for sid in victims:
            self.delete_session(sid)
        # If the per-document folder still exists (e.g. stray files), wipe it.
        if doc_dir_name:
            folder = os.path.join(BODY_DIRS['single'], doc_dir_name)
            if os.path.isdir(folder):
                try:
                    import shutil
                    shutil.rmtree(folder)
                except Exception as e:
                    print(f"[SessionStore] Failed to remove folder {folder}: {e}")
        return len(victims)

    def add_message(self, session_id: str, message: Message) -> bool:
        session = self.get_session(session_id)
        if not session:
            return False
        session.messages.append(message)
        session.updated_at = time.time()
        # First user message becomes default title if not set.
        if not session.title and message.role == 'user' and message.content:
            session.title = (message.content[:40] + '…') if len(message.content) > 40 else message.content
        self._save_body(session)
        self._write_index_for(session)
        self._save_index(session.mode)
        return True

    def update_last_message(self, session_id: str, role: str,
                            **fields) -> bool:
        """Overwrite the last message with ``role`` in a session.

        Used by the agent's retry path: after a reflection-triggered retry
        produces a better answer, we replace the previously-saved assistant
        message instead of appending a second one.
        """
        session = self.get_session(session_id)
        if not session:
            return False
        for msg in reversed(session.messages):
            if msg.role == role:
                for k, v in fields.items():
                    if hasattr(msg, k):
                        setattr(msg, k, v)
                msg.timestamp = time.time()
                session.updated_at = time.time()
                self._save_body(session)
                self._write_index_for(session)
                self._save_index(session.mode)
                return True
        return False

    def update_message_at(self, session_id: str, index: int, **fields) -> bool:
        """Met à jour un message par son index (vérification à la demande)."""
        session = self.get_session(session_id)
        if not session or not (0 <= index < len(session.messages)):
            return False
        msg = session.messages[index]
        for k, v in fields.items():
            if hasattr(msg, k):
                setattr(msg, k, v)
        session.updated_at = time.time()
        self._save_body(session)
        self._write_index_for(session)
        self._save_index(session.mode)
        return True

    def mark_superseded_before_last(self, session_id: str, role: str) -> bool:
        """Mark the SECOND-to-last message with ``role`` as superseded.

        Used by the agent's reflection-retry path: after appending the
        improved answer as a new assistant turn, we flag the original
        low-score draft so ``_build_history_context`` skips it when
        assembling LLM history for subsequent turns. The draft remains
        visible in the UI — only LLM context treats it as replaced.
        """
        session = self.get_session(session_id)
        if not session:
            return False
        seen = 0
        for msg in reversed(session.messages):
            if msg.role == role:
                seen += 1
                if seen == 2:
                    msg.superseded = True
                    session.updated_at = time.time()
                    self._save_body(session)
                    self._write_index_for(session)
                    self._save_index(session.mode)
                    return True
        return False

    def clear_messages(self, session_id: str) -> bool:
        session = self.get_session(session_id)
        if not session:
            return False
        session.messages = []
        session.updated_at = time.time()
        self._save_body(session)
        self._write_index_for(session)
        self._save_index(session.mode)
        return True

    def truncate_messages(self, session_id: str, index: int) -> bool:
        """Drop every message at position ``index`` and beyond.

        Used by the "edit & resend" / "regenerate" flows: the user wants to
        rewrite history starting from a specific turn, so we discard the
        tail (old answers, reflection drafts, superseded turns, etc.) before
        the fresh ``agent_chat`` call re-reads the session's message list.

        ``index`` is clamped to ``[0, len(messages)]``. Returns True if the
        session exists; whether any messages were actually removed can be
        inferred from the caller's prior knowledge of the length.
        """
        session = self.get_session(session_id)
        if session is None:
            return False
        if index < 0:
            index = 0
        if index > len(session.messages):
            index = len(session.messages)
        if index == len(session.messages):
            # Nothing to do, but still touch updated_at? No — leave it alone
            # so we don't bump the session for a no-op.
            return True
        session.messages = session.messages[:index]
        session.updated_at = time.time()
        self._save_body(session)
        self._write_index_for(session)
        self._save_index(session.mode)
        return True

    def get_messages(self, session_id: str) -> List[Message]:
        session = self.get_session(session_id)
        return session.messages if session else []


session_store = SessionStore()
