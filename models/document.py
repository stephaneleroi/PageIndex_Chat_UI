#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Document models for PageIndex Chat UI.

A Document represents a persisted, indexed PDF plus its derived artifacts
(structure, images, analysis). It is no longer tied to a single chat history —
chat state lives in models.session.SessionStore.
"""

import os
import json
import shutil
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

# Re-export Message from session module so legacy imports keep working.
from .session import Message  # noqa: F401

# Base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
RESULTS_DIR = os.path.join(BASE_DIR, 'results')
# All per-document artifacts (metadata/structure/images/analysis) live under
# results/documents/<doc_dir_name>/ so the results root only contains a small
# number of well-known subdirectories (documents/, _index/, _sessions/).
DOCUMENTS_DIR = os.path.join(RESULTS_DIR, 'documents')

@dataclass
class Document:
    """Document representation."""
    doc_id: str
    filename: str  # original filename without doc_id prefix
    file_path: str  # path to PDF in uploads/
    result_dir_name: str = ''  # directory name in results/documents/ (defaults to {doc_id}_{filename})
    status: str = 'pending'  # pending, indexing, indexed, ready, error
    created_at: float = field(default_factory=time.time)
    page_count: int = 0
    error_message: str = ''
    # Fine-grained indexing progress — only meaningful while status != 'ready'.
    # stage: queued | parsing | toc_detect | tree_build | image_extract | analysis | done | error
    stage: str = ''
    stage_message: str = ''        # Short Chinese description for the UI.
    stage_started_at: float = 0.0  # When the current stage began (unix ts).

    def __post_init__(self):
        if not self.result_dir_name:
            self.result_dir_name = f"{self.doc_id}_{self.filename}"

    @property
    def result_dir(self) -> str:
        return os.path.join(DOCUMENTS_DIR, self.result_dir_name)

    @property
    def metadata_path(self) -> str:
        return os.path.join(self.result_dir, 'metadata.json')

    @property
    def structure_path(self) -> str:
        return os.path.join(self.result_dir, 'structure.json')

    @property
    def images_dir(self) -> str:
        return os.path.join(self.result_dir, 'images')

    @property
    def analysis_path(self) -> str:
        return os.path.join(self.result_dir, 'analysis.json')

    def to_dict(self):
        d = asdict(self)
        # Attach short analysis summary (best-effort) so library cards can show it.
        try:
            if os.path.exists(self.analysis_path):
                with open(self.analysis_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                summary = (data.get('summary') or '').strip()
                if summary:
                    d['analysis_summary'] = summary[:240]
        except Exception:
            pass
        return d


class DocumentStore:
    """In-memory document registry with lazy disk persistence.

    Chat history has been removed — see models.session.SessionStore.
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
        self.documents: Dict[str, Document] = {}
        self.tree_cache: Dict[str, dict] = {}
        self.node_map_cache: Dict[str, dict] = {}
        self.page_images_cache: Dict[str, dict] = {}

        os.makedirs(UPLOADS_DIR, exist_ok=True)
        os.makedirs(RESULTS_DIR, exist_ok=True)
        os.makedirs(DOCUMENTS_DIR, exist_ok=True)

        # One-shot migration: any <doc_dir>/ still sitting directly under
        # results/ (from older versions) is moved into results/documents/.
        self._migrate_legacy_layout()

        self._load_from_disk()

    # -------------------- discovery & metadata -------------------- #

    def _migrate_legacy_layout(self):
        """Move legacy results/<doc_dir>/ folders into results/documents/.

        Only directories that look like a document artifact folder (i.e. they
        contain a metadata.json) are migrated. System directories (_index,
        _sessions, documents itself, dotfiles) are skipped.
        """
        if not os.path.exists(RESULTS_DIR):
            return
        moved = 0
        for dir_name in os.listdir(RESULTS_DIR):
            if dir_name.startswith('_') or dir_name.startswith('.'):
                continue
            if dir_name == 'documents':
                continue
            src = os.path.join(RESULTS_DIR, dir_name)
            if not os.path.isdir(src):
                continue
            if not os.path.exists(os.path.join(src, 'metadata.json')):
                continue
            dst = os.path.join(DOCUMENTS_DIR, dir_name)
            if os.path.exists(dst):
                print(f"[DocumentStore] Skip migration, destination exists: {dst}")
                continue
            try:
                shutil.move(src, dst)
                moved += 1
                print(f"[DocumentStore] Migrated legacy document dir: {dir_name}")
            except Exception as e:
                print(f"[DocumentStore] Failed to migrate {dir_name}: {e}")
        if moved:
            print(f"[DocumentStore] Legacy layout migration complete ({moved} dir(s)).")

    def _load_from_disk(self):
        """Recover documents by scanning results/documents/* for metadata.json files."""
        if not os.path.exists(DOCUMENTS_DIR):
            return

        print("Scanning results/documents directory to recover documents...")
        for dir_name in os.listdir(DOCUMENTS_DIR):
            if dir_name.startswith('.'):
                continue

            doc_dir = os.path.join(DOCUMENTS_DIR, dir_name)
            if not os.path.isdir(doc_dir):
                continue

            metadata_path = os.path.join(doc_dir, 'metadata.json')
            if not os.path.exists(metadata_path):
                continue

            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                doc_id = data['doc_id']
                filename = data['filename']
                result_dir_name = data.get('result_dir_name', dir_name)

                pdf_path = os.path.join(UPLOADS_DIR, f"{doc_id}_{filename}")
                if not os.path.exists(pdf_path):
                    print(f"Skipping document with missing PDF: {dir_name}")
                    continue

                status = data.get('status', 'ready')
                error_message = data.get('error_message', '')
                stage = data.get('stage', '') if status != 'ready' else ''
                stage_message = data.get('stage_message', '') if status != 'ready' else ''
                # An indexing run cannot survive a server restart (its thread
                # died with the old process) — recover such documents as
                # failed so the UI offers Retry/Delete instead of a card
                # stuck on "indexation en cours" forever.
                if status in ('pending', 'indexing', 'indexed'):
                    status = 'error'
                    stage = 'error'
                    error_message = 'Indexation interrompue par un redémarrage du serveur'
                    stage_message = error_message

                doc = Document(
                    doc_id=doc_id,
                    filename=filename,
                    file_path=pdf_path,
                    result_dir_name=result_dir_name,
                    status=status,
                    created_at=data.get('created_at', os.path.getctime(doc_dir)),
                    page_count=data.get('page_count', 0),
                    error_message=error_message,
                    stage=stage,
                    stage_message=stage_message,
                    stage_started_at=data.get('stage_started_at', 0.0),
                )
                self.documents[doc.doc_id] = doc
                print(f"Recovered document: {filename} (id: {doc_id}, status: {doc.status})")
            except Exception as e:
                print(f"Error loading metadata for {dir_name}: {e}")
        print(f"Total documents recovered: {len(self.documents)}")

    def _save_document_metadata(self, doc: Document):
        os.makedirs(doc.result_dir, exist_ok=True)
        metadata = {
            'doc_id': doc.doc_id,
            'filename': doc.filename,
            'result_dir_name': doc.result_dir_name,
            'status': doc.status,
            'created_at': doc.created_at,
            'page_count': doc.page_count,
            'error_message': doc.error_message,
            'stage': doc.stage,
            'stage_message': doc.stage_message,
            'stage_started_at': doc.stage_started_at,
        }
        try:
            with open(doc.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving document metadata: {e}")

    # -------------------- CRUD -------------------- #

    def add_document(self, doc: Document):
        self.documents[doc.doc_id] = doc
        os.makedirs(doc.result_dir, exist_ok=True)
        self._save_document_metadata(doc)

    def get_document(self, doc_id: str) -> Optional[Document]:
        return self.documents.get(doc_id)

    def get_document_by_name(self, filename: str) -> Optional[Document]:
        for doc in self.documents.values():
            if doc.filename == filename:
                return doc
        return None

    def update_document(self, doc_id: str, **kwargs):
        if doc_id in self.documents:
            doc = self.documents[doc_id]
            for key, value in kwargs.items():
                if hasattr(doc, key):
                    setattr(doc, key, value)
            self._save_document_metadata(doc)

    def set_stage(self, doc_id: str, stage: str, message: str = ''):
        """Update fine-grained indexing progress for a not-yet-ready document."""
        if doc_id not in self.documents:
            return
        doc = self.documents[doc_id]
        doc.stage = stage
        doc.stage_message = message
        doc.stage_started_at = time.time()
        # Keep the metadata file in sync so the next list_documents call reflects it.
        self._save_document_metadata(doc)

    def get_all_documents(self) -> List[Document]:
        return list(self.documents.values())

    def delete_document(self, doc_id: str):
        """Delete a document's index artifacts. Does NOT affect any chat session."""
        if doc_id not in self.documents:
            return
        doc = self.documents[doc_id]

        if doc.file_path and os.path.exists(doc.file_path):
            try:
                os.remove(doc.file_path)
            except Exception as e:
                print(f"Error removing PDF: {e}")

        if os.path.exists(doc.result_dir):
            try:
                shutil.rmtree(doc.result_dir)
            except Exception as e:
                print(f"Error removing result dir: {e}")

        # Also drop any single-mode chat sessions that were bound to this
        # document, plus their per-document folder under _sessions/single/.
        try:
            from .session import session_store
            session_store.drop_document_bindings(doc_id, doc.result_dir_name)
        except Exception as e:
            print(f"Error cleaning sessions for doc {doc_id}: {e}")

        del self.documents[doc_id]
        self.tree_cache.pop(doc_id, None)
        self.node_map_cache.pop(doc_id, None)
        self.page_images_cache.pop(doc_id, None)

    # -------------------- derived artifact caches -------------------- #

    def cache_tree(self, doc_id: str, tree: dict):
        self.tree_cache[doc_id] = tree

    def get_tree(self, doc_id: str) -> Optional[dict]:
        if doc_id in self.tree_cache:
            return self.tree_cache[doc_id]
        doc = self.get_document(doc_id)
        if doc and os.path.exists(doc.structure_path):
            try:
                with open(doc.structure_path, 'r', encoding='utf-8') as f:
                    tree_data = json.load(f)
                tree = tree_data.get('structure', tree_data)
                self.tree_cache[doc_id] = tree
                return tree
            except Exception as e:
                print(f"Error loading tree from disk: {e}")
        return None

    def update_node(self, doc_id: str, node_id: str,
                    title: Optional[str] = None,
                    summary: Optional[str] = None) -> bool:
        """Met à jour le titre et/ou le résumé d'un nœud de l'arbre, sur
        disque (structure.json) et en cache. L'arbre étant l'index de
        recherche, c'est le levier d'intervention humaine le plus rentable
        (corriger « Document 2 » en « Note d'information UEHC du 07/08 »
        améliore directement le retrieval par raisonnement)."""
        doc = self.get_document(doc_id)
        if not doc or not os.path.exists(doc.structure_path):
            return False
        with open(doc.structure_path, 'r', encoding='utf-8') as f:
            tree_data = json.load(f)
        structure = tree_data.get('structure', tree_data)

        def find(n):
            if isinstance(n, list):
                for x in n:
                    r = find(x)
                    if r:
                        return r
                return None
            if n.get('node_id') == node_id:
                return n
            return find(n.get('nodes', []))

        node = find(structure)
        if not node:
            return False
        if title is not None and title.strip():
            node['title'] = title.strip()
        if summary is not None:
            node['summary'] = summary.strip()
        with open(doc.structure_path, 'w', encoding='utf-8') as f:
            json.dump(tree_data, f, indent=2, ensure_ascii=False)
        # Invalider les dérivés : l'arbre sera relu du disque, le node_map
        # (et donc les infos de la visionneuse) reconstruit à la demande.
        self.tree_cache.pop(doc_id, None)
        self.node_map_cache.pop(doc_id, None)
        return True

    def cache_node_map(self, doc_id: str, node_map: dict):
        self.node_map_cache[doc_id] = node_map

    def get_node_map(self, doc_id: str) -> Optional[dict]:
        return self.node_map_cache.get(doc_id)

    def cache_page_images(self, doc_id: str, page_images: dict):
        self.page_images_cache[doc_id] = page_images

    def get_page_images(self, doc_id: str) -> Optional[dict]:
        if doc_id in self.page_images_cache:
            return self.page_images_cache[doc_id]

        doc = self.get_document(doc_id)
        if doc and os.path.exists(doc.images_dir):
            try:
                page_images = {}
                for filename in os.listdir(doc.images_dir):
                    if filename.endswith(('.png', '.jpg', '.jpeg')):
                        try:
                            page_num = int(filename.replace('page_', '').split('.')[0])
                            page_images[page_num] = os.path.join(doc.images_dir, filename)
                        except ValueError:
                            continue
                if page_images:
                    self.page_images_cache[doc_id] = page_images
                    return page_images
            except Exception as e:
                print(f"Error loading page images from disk: {e}")
        return None

    def get_analysis(self, doc_id: str) -> Optional[dict]:
        doc = self.get_document(doc_id)
        if not doc:
            return None
        if os.path.exists(doc.analysis_path):
            try:
                with open(doc.analysis_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading analysis: {e}")
        return None


# Global store instance
document_store = DocumentStore()
