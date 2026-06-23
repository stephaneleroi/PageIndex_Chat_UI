#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API routes for PageIndex Chat UI
"""

import os
import uuid
import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

from models.document import Document, document_store, UPLOADS_DIR, RESULTS_DIR
from models.session import session_store
from services.rag_service import rag_service
from services.indexing_service import indexing_service
from services.skill_manager import skill_manager, Skill
from config import config_manager

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

# Les indexations d'un import par lot (ex. 50 pièces d'un dossier de
# procédure) s'exécutaient toutes en parallèle en se disputant le serveur
# LLM local. File séquentielle : un document à la fois, les autres restent
# « En file d'attente d'indexation… » (statut déjà affiché par l'IHM).
from threading import Semaphore
_INDEXING_GATE = Semaphore(1)

# Cache de réimportation : l'arbre PageIndex est sauvegardé en JSON à côté du
# document source (<nom>.pageindex.json) dans le répertoire de données. À la
# réimportation du même PDF (empreinte SHA-256 identique), l'arbre est
# réutilisé : aucun appel LLM, le document est prêt en quelques secondes.
SOURCE_DATA_DIR = os.environ.get(
    'SOURCE_DATA_DIR',
    os.path.abspath(os.path.join(os.path.dirname(UPLOADS_DIR), '..', 'data')),
)


def _sha256_file(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _source_dir(folder: str) -> str:
    return os.path.join(SOURCE_DATA_DIR, folder) if folder else SOURCE_DATA_DIR


def _find_cached_index(folder: str, sha: str):
    """Cherche un <nom>.pageindex.json dont l'empreinte correspond au PDF."""
    d = _source_dir(folder)
    if not os.path.isdir(d):
        return None
    for fn in sorted(os.listdir(d)):
        if not fn.endswith('.pageindex.json'):
            continue
        try:
            with open(os.path.join(d, fn), 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get('pdf_sha256') == sha and data.get('structure'):
                logger.info(f"Cache d'index trouvé : {fn}")
                return data
        except Exception as e:
            logger.warning(f"Cache d'index illisible ({fn}) : {e}")
    return None


def _write_index_cache(doc, sha: str):
    """Écrit l'arbre indexé à côté du PDF source (retrouvé par empreinte).
    Source absent du répertoire de données → on n'écrit rien, sans erreur."""
    d = _source_dir(doc.folder)
    if not os.path.isdir(d):
        return
    for fn in sorted(os.listdir(d)):
        if not fn.lower().endswith('.pdf'):
            continue
        src = os.path.join(d, fn)
        try:
            if _sha256_file(src) != sha:
                continue
        except Exception:
            continue
        with open(doc.structure_path, 'r', encoding='utf-8') as f:
            structure = json.load(f)
        analysis = None
        if os.path.exists(doc.analysis_path):
            with open(doc.analysis_path, 'r', encoding='utf-8') as f:
                analysis = json.load(f)
        cache = {'pdf_sha256': sha, 'page_count': doc.page_count,
                 'structure': structure, 'analysis': analysis}
        cache_path = src + '.pageindex.json'
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=1, ensure_ascii=False)
        logger.info(f"Cache d'index écrit : {cache_path}")
        return


def _launch_indexing(doc_id: str, file_path: str, filename: str):
    """Fil d'indexation d'un document : cache de réimportation, deux
    tentatives, préparation locale, analyse, écriture du cache. Utilisé par
    l'upload et par la relance manuelle (retry)."""
    from threading import Thread

    def run_indexing():
        import asyncio
        with _INDEXING_GATE:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                doc = document_store.get_document(doc_id)
                sha = _sha256_file(file_path)

                cached = _find_cached_index(doc.folder if doc else '', sha)
                if cached:
                    # Réimportation : arbre restauré, aucun appel LLM.
                    os.makedirs(doc.result_dir, exist_ok=True)
                    with open(doc.structure_path, 'w', encoding='utf-8') as f:
                        json.dump(cached['structure'], f, indent=2, ensure_ascii=False)
                    if cached.get('analysis'):
                        with open(doc.analysis_path, 'w', encoding='utf-8') as f:
                            json.dump(cached['analysis'], f, indent=2, ensure_ascii=False)
                    document_store.update_document(doc_id, status='indexed')
                    document_store.set_stage(doc_id, 'image_extract',
                                             'Index réutilisé depuis le cache — préparation locale...')
                    loop.run_until_complete(
                        rag_service.prepare_document(doc_id, file_path, doc.structure_path)
                    )
                    return

                # Indexation non déterministe : un échec transitoire se
                # résout souvent par une simple seconde tentative.
                success = False
                for attempt in (1, 2):
                    success = loop.run_until_complete(
                        indexing_service.index_pdf(doc_id, file_path, filename)
                    )
                    if success:
                        break
                    if attempt == 1:
                        logger.warning(f"Indexation échouée pour {filename} — nouvelle tentative")
                        document_store.set_stage(doc_id, 'tree_build',
                                                 'Échec de la première tentative — nouvelle tentative...')
                if success:
                    doc = document_store.get_document(doc_id)
                    if doc and os.path.exists(doc.structure_path):
                        loop.run_until_complete(
                            rag_service.prepare_document(doc_id, file_path, doc.structure_path)
                        )
                        try:
                            loop.run_until_complete(rag_service.auto_analyze_document(doc_id))
                        except Exception as e:
                            logger.warning(f"Auto-analysis failed (non-fatal): {e}")
                        try:
                            _write_index_cache(document_store.get_document(doc_id), sha)
                        except Exception as e:
                            logger.warning(f"Écriture du cache d'index échouée (non-fatal): {e}")
            finally:
                loop.close()

    Thread(target=run_indexing).start()


# ============= Configuration Routes =============

@api_bp.route('/config/models', methods=['GET'])
def get_models():
    return jsonify({
        'models': config_manager.get_all_models(),
        'default_type': config_manager.get_default_model_type()
    })


@api_bp.route('/config/models/<model_type>', methods=['GET', 'PUT'])
def model_config(model_type):
    if request.method == 'GET':
        return jsonify(config_manager.get_model_config(model_type))
    data = request.json
    config_manager.set_model_config(model_type, data)
    return jsonify({'success': True, 'message': f'{model_type} model config updated'})


# ============= Document Routes =============

@api_bp.route('/documents', methods=['GET'])
def list_documents():
    docs = [doc.to_dict() for doc in document_store.get_all_documents()]
    # Sort: ready first, then by created_at desc
    docs.sort(key=lambda d: (0 if d['status'] == 'ready' else 1, -d.get('created_at', 0)))
    return jsonify({'documents': docs})


def _convert_to_pdf_with_libreoffice(src_path: str) -> str:
    """Convertit un document bureautique (.docx…) en PDF via LibreOffice
    headless. Une conversion interne contrôlée vaut mieux que les exports
    manuels approximatifs (sommaire/pagination faussés). Retourne le chemin
    du PDF produit (même dossier, même nom)."""
    import shutil
    import subprocess
    soffice = shutil.which('soffice') or '/Applications/LibreOffice.app/Contents/MacOS/soffice'
    if not os.path.exists(soffice):
        raise RuntimeError("LibreOffice (soffice) introuvable — nécessaire pour convertir le .docx")
    subprocess.run(
        [soffice, '--headless', '--convert-to', 'pdf', '--outdir',
         os.path.dirname(src_path), src_path],
        check=True, capture_output=True, timeout=180,
    )
    pdf_path = os.path.splitext(src_path)[0] + '.pdf'
    if not os.path.exists(pdf_path):
        raise RuntimeError('Conversion LibreOffice échouée (pas de PDF produit)')
    return pdf_path


@api_bp.route('/documents/upload', methods=['POST'])
def upload_document():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    lower = file.filename.lower()
    if not lower.endswith(('.pdf', '.docx')):
        return jsonify({'error': 'Formats pris en charge : PDF et DOCX'}), 400

    # Répertoire logique d'appartenance (import de dossier) — simple
    # étiquette d'organisation, assainie (pas de traversée de chemin).
    folder = (request.form.get('folder') or '').strip().strip('/')
    folder = '/'.join(seg for seg in folder.split('/') if seg and seg != '..')[:120]

    try:
        filename = secure_filename(file.filename)
        os.makedirs(UPLOADS_DIR, exist_ok=True)

        # Sauvegarde TEMPORAIRE d'abord : le doc_id est DÉRIVÉ de l'empreinte
        # SHA-256 du contenu (pas d'un horodatage aléatoire). Conséquence clé :
        # réimporter le MÊME PDF redonne le MÊME doc_id → les conversations qui le
        # citent (doc_id::node) ne deviennent jamais orphelines après un
        # supprimer/réimporter.
        tmp_path = os.path.join(UPLOADS_DIR, f"_tmp_{uuid.uuid4().hex}_{filename}")
        file.save(tmp_path)

        if lower.endswith('.docx'):
            try:
                pdf_path = _convert_to_pdf_with_libreoffice(tmp_path)
            except Exception as e:
                os.remove(tmp_path)
                logger.error(f"Conversion .docx échouée: {e}")
                return jsonify({'error': f'Conversion du .docx en PDF échouée : {e}'}), 500
            os.remove(tmp_path)
            tmp_path = pdf_path
            filename = os.path.splitext(filename)[0] + '.pdf'
            logger.info(f"Document .docx converti en PDF : {filename}")

        doc_id = _sha256_file(tmp_path)[:16]   # empreinte du CONTENU → identifiant stable

        # Réimport idempotent : même contenu déjà présent → on réutilise (ni
        # doublon, ni réindexation), on jette le fichier temporaire.
        existing = document_store.get_document(doc_id)
        if existing:
            os.remove(tmp_path)
            return jsonify({'success': True, 'document': existing.to_dict(),
                            'message': 'Document déjà importé (même contenu)'})

        file_path = os.path.join(UPLOADS_DIR, f"{doc_id}_{filename}")
        os.replace(tmp_path, file_path)

        doc = Document(doc_id=doc_id, filename=filename, file_path=file_path, folder=folder, status='pending')
        document_store.add_document(doc)
        document_store.set_stage(doc_id, 'queued', 'En file d\'attente d\'indexation...')

        _launch_indexing(doc_id, file_path, filename)

        return jsonify({
            'success': True,
            'document': doc.to_dict(),
            'message': 'Document uploaded, indexing started'
        })
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/documents/<doc_id>/retry', methods=['POST'])
def retry_document(doc_id):
    """Relance l'indexation d'un document en erreur (PDF déjà dans uploads/,
    pas besoin de réimporter)."""
    doc = document_store.get_document(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    if doc.status != 'error':
        return jsonify({'error': 'Seul un document en erreur peut être relancé'}), 400
    if not doc.file_path or not os.path.exists(doc.file_path):
        return jsonify({'error': 'PDF source absent — supprimez le document et réimportez-le'}), 400
    document_store.update_document(doc_id, status='pending', error_message='')
    document_store.set_stage(doc_id, 'queued', 'En file d\'attente d\'indexation...')
    _launch_indexing(doc_id, doc.file_path, doc.filename)
    return jsonify({'success': True, 'document': doc.to_dict(),
                    'message': 'Indexation relancée'})


@api_bp.route('/documents/<doc_id>', methods=['GET'])
def get_document(doc_id):
    doc = document_store.get_document(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    return jsonify({'document': doc.to_dict()})


@api_bp.route('/documents/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """Delete a document's index. Sessions that referenced it keep their history."""
    try:
        document_store.delete_document(doc_id)
        return jsonify({'success': True, 'message': 'Document deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/documents/<doc_id>/status', methods=['GET'])
def get_document_status(doc_id):
    doc = document_store.get_document(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    return jsonify({
        'status': doc.status,
        'error_message': doc.error_message,
        'stage': doc.stage,
        'stage_message': doc.stage_message,
        'stage_started_at': doc.stage_started_at,
        'page_count': doc.page_count,
    })


# ============= Session Routes =============

@api_bp.route('/sessions', methods=['GET'])
def list_sessions():
    """List sessions, optionally filtered by mode and/or doc_id."""
    mode = request.args.get('mode')
    doc_id = request.args.get('doc_id')
    items = session_store.list_sessions(mode=mode, doc_id=doc_id)
    return jsonify({'sessions': items})


@api_bp.route('/sessions', methods=['POST'])
def create_session():
    data = request.json or {}
    mode = data.get('mode')
    if mode not in ('single', 'kb'):
        return jsonify({'error': "mode must be 'single' or 'kb'"}), 400
    doc_ids = data.get('doc_ids') or []
    title = data.get('title', '')
    if mode == 'single' and len(doc_ids) != 1:
        return jsonify({'error': 'single-mode session requires exactly one doc_id'}), 400
    # kb sans document = conversation LIBRE (dialogue direct, sans sources).

    # Validate all docs exist.
    for did in doc_ids:
        if not document_store.get_document(did):
            return jsonify({'error': f'Document {did} not found'}), 404

    session = session_store.create_session(mode=mode, doc_ids=doc_ids, title=title)
    return jsonify({'success': True, 'session': session.to_summary()})


@api_bp.route('/sessions/<session_id>', methods=['GET'])
def get_session(session_id):
    session = session_store.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    return jsonify({'session': session.to_dict()})


@api_bp.route('/sessions/<session_id>', methods=['PUT'])
def update_session(session_id):
    data = request.json or {}
    kwargs = {}
    if 'title' in data:
        kwargs['title'] = data['title']
    if 'doc_ids' in data:
        kwargs['doc_ids'] = data['doc_ids']
    session = session_store.update_session(session_id, **kwargs)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    return jsonify({'success': True, 'session': session.to_summary()})


@api_bp.route('/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    ok = session_store.delete_session(session_id)
    if not ok:
        return jsonify({'error': 'Session not found'}), 404
    return jsonify({'success': True})


@api_bp.route('/sessions/<session_id>/messages/<int:index>', methods=['PUT'])
def update_message(session_id, index):
    """Édition du texte d'une réponse (persistée dans la session). Réservée
    aux messages assistant ; l'édition invalide le verdict de vérification."""
    session = session_store.get_session(session_id)
    if not session or not (0 <= index < len(session.messages)):
        return jsonify({'error': 'Message introuvable'}), 404
    if session.messages[index].role != 'assistant':
        return jsonify({'error': 'Seules les réponses sont éditables ici'}), 400
    data = request.json or {}
    content = (data.get('content') or '').strip()
    if not content:
        return jsonify({'error': 'content requis'}), 400
    session_store.update_message_at(session_id, index, content=content, verification=None)
    return jsonify({'success': True})


@api_bp.route('/sessions/<session_id>/messages/<int:index>/verify', methods=['POST'])
def verify_message(session_id, index):
    """Vérification À LA DEMANDE d'une réponse : rejoue l'auto-évaluation
    (juge LLM) sur le message, avec le texte de ses nœuds sources comme
    pièces. Le verdict est persisté dans le message (badge dans l'IHM)."""
    session = session_store.get_session(session_id)
    if not session or not (0 <= index < len(session.messages)):
        return jsonify({'error': 'Message introuvable'}), 404
    msg = session.messages[index]
    if msg.role != 'assistant':
        return jsonify({'error': 'Seules les réponses peuvent être vérifiées'}), 400

    # La question = le dernier message utilisateur qui précède.
    question = next((m.content for m in reversed(session.messages[:index])
                     if m.role == 'user'), '')

    # Contexte de vérification : les nœuds CITÉS d'abord (preuve directe), puis le
    # texte des AUTRES pièces de la session pour combler (borné). Sans cela, le juge
    # prend un fait venant d'une pièce NON citée pour une hallucination (faux positif).
    cited = set()
    for ref in (msg.nodes or []):
        d, _, n = ref.partition('::')
        cited.add((d or (session.doc_ids[0] if session.doc_ids else ''), n or ref))

    def _walk(doc_id):
        tree = document_store.get_tree(doc_id)
        out, stack = [], ([tree] if tree else [])
        while stack:
            n = stack.pop()
            if isinstance(n, list):
                stack.extend(n)
                continue
            if n.get('text'):
                out.append((doc_id, n.get('node_id'), n['text']))
            stack.extend(n.get('nodes', []))
        return out

    all_nodes = []
    for did in (session.doc_ids or []):
        all_nodes.extend(_walk(did))
    ordered = ([x for x in all_nodes if (x[0], x[1]) in cited]
               + [x for x in all_nodes if (x[0], x[1]) not in cited])
    parts, total = [], 0
    for did, nid, txt in ordered:
        block = f"=== {did} node_{nid} ===\n{txt}"
        if total + len(block) > 60000:
            break
        parts.append(block)
        total += len(block)
    context = "\n\n".join(parts)

    # Vérification CIBLÉE PAR SCOPE. La pré-détection a déjà tranché le déterministe
    # (citations/verbatim, affichés en alertes) ; ici on exécute les vérificateurs LLM
    # du `scope` recommandé. `complete` = tout vérifier (présupposé sur toute la réponse)
    # avec plus de votes (sinon ciblé). Les contrôles déterministes sont rejoués pour
    # alimenter la réponse corrigée.
    data = request.json or {}
    scope = data.get('scope') or []
    complete = bool(data.get('complete'))
    agent = rag_service.agent
    import asyncio
    import time as _time

    async def _verify():
        issues = []
        # --- Contrôles DÉTERMINISTES (toujours, gratuits) ---
        for s in agent._verbatim_issues(msg.content, context):
            issues.append(f"Citation entre guillemets introuvable dans les sources : « {s} »")
        if isinstance(msg.quality, dict):
            issues += [f"Citation : {p}" for p in (msg.quality.get('problems') or [])]
        det_issues = list(issues)
        # --- Vérificateurs LLM (ciblés par scope, ou tout si `complete`) ---
        votes = 5 if complete else 3
        corr = None
        if complete or 'presupposition' in scope or agent._question_presupposes(question):
            corr = await agent._presupposition_violation(question, msg.content, context, 'text', votes=votes)
        reflection = await agent.reflect(question, msg.content, context, 'text', False)
        if corr:
            issues = [f"Présupposé non établi par les pièces : {corr}"] + issues
        issues += list(reflection.get('issues') or [])
        corrected = None
        needs_fix = bool(corr) or bool(det_issues) or (reflection.get('action') == 'retry'
                                                       and (reflection.get('score') or 10) < 6)
        if needs_fix:
            fix = corr or "; ".join(str(i) for i in issues) or "Corriger les défauts signalés."
            rewrite = (
                "Corrige la réponse ci-dessous en te fondant UNIQUEMENT sur les sources, "
                f"sans rien inventer. Problème(s) à corriger : {fix}\n\n"
                f"Question : {question}\n\nSources :\n{context[:30000]}\n\n"
                f"Réponse à corriger :\n{msg.content}\n\n"
                "Réécris la réponse en français en intégrant la correction (dis explicitement "
                "si une entité présupposée n'est pas établie par les pièces ; supprime toute "
                "citation entre guillemets absente des sources), en conservant les faits "
                "corrects et les citations (doc / node / page). Renvoie UNIQUEMENT la réponse réécrite."
            )
            corrected = await agent.pageindex.call_llm(rewrite, 'text')
        return {'score': reflection.get('score'), 'issues': issues,
                'missing_info': reflection.get('missing_info') or [], 'corrected': corrected}

    try:
        result = asyncio.run(_verify())
    except Exception as e:
        logger.error(f"Vérification à la demande échouée: {e}")
        return jsonify({'error': str(e)}), 500

    verification = {**result, 'scope': scope, 'complete': complete, 'auto': False, 'verified_at': _time.time()}
    session_store.update_message_at(session_id, index, verification=verification)
    return jsonify({'success': True, 'verification': verification})


@api_bp.route('/sessions/<session_id>/truncate', methods=['POST'])
def truncate_session_messages(session_id):
    """Drop messages at ``index`` and beyond.

    Powers the frontend's "edit & resend" / "regenerate" flows: the client
    tells us where the fresh turn should start, we cut the tail, then the
    subsequent ``agent_chat`` socket event replays from that point with the
    already-trimmed history as LLM context.
    """
    session = session_store.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    data = request.json or {}
    try:
        index = int(data.get('index'))
    except (TypeError, ValueError):
        return jsonify({'error': 'index (int) required'}), 400
    session_store.truncate_messages(session_id, index)
    return jsonify({
        'success': True,
        'message_count': len(session_store.get_messages(session_id)),
    })


# ============= Tree Structure Routes =============

@api_bp.route('/documents/<doc_id>/tree', methods=['GET'])
def get_tree_structure(doc_id):
    tree = document_store.get_tree(doc_id)
    if not tree:
        return jsonify({'error': 'Tree structure not found'}), 404
    from services.rag_service import PageIndexService
    service = PageIndexService(document_store)
    clean_tree = service.remove_fields(tree, ['text'])
    return jsonify({'tree': clean_tree})


@api_bp.route('/documents/<doc_id>/nodes/<node_id>', methods=['PUT'])
def update_tree_node(doc_id, node_id):
    """Édition humaine de l'arbre (titre/résumé d'un nœud) — l'arbre est
    l'index de recherche, le corriger améliore directement le retrieval."""
    data = request.json or {}
    if 'title' not in data and 'summary' not in data:
        return jsonify({'error': 'title ou summary requis'}), 400
    ok = document_store.update_node(
        doc_id, node_id,
        title=data.get('title'), summary=data.get('summary'),
    )
    if not ok:
        return jsonify({'error': 'Document ou nœud introuvable'}), 404
    return jsonify({'success': True})


@api_bp.route('/documents/<doc_id>/focused-fiches', methods=['GET'])
def list_focused_fiches(doc_id):
    """Fiches à chaud (map-reduce), persistées comme les notes
    (focused_fiches.json à côté de la structure), regroupées par pièce (head node)."""
    return jsonify({'fiches': document_store.get_focused_fiches(doc_id)})


@api_bp.route('/folders/<path:folder>/structure', methods=['GET'])
def get_folder_structure(folder):
    """Structure CONSOLIDÉE d'un répertoire. Conceptuellement, un dossier de N
    pièces ≡ un document concaténant N pièces (c'est déjà ainsi qu'il est traité
    au retrieval, cf. la voie corpus). On agrège ici, pour l'IHM, les pièces de
    niveau 1 (détection canonique `piece_head_nodes`) de TOUS ses fichiers PRÊTS.
    Lecture seule, aucun appel LLM, aucun impact indexation/retrieval."""
    from pageindex.utils import piece_head_nodes

    def _span(head):
        starts, ends, stack = [], [], [head]
        while stack:
            n = stack.pop()
            if n.get('start_index'):
                starts.append(n['start_index'])
            if n.get('end_index'):
                ends.append(n['end_index'])
            stack.extend(n.get('nodes') or [])
        return (min(starts) if starts else None, max(ends) if ends else None)

    docs = [d for d in document_store.get_all_documents() if (d.folder or '') == folder]
    ready = [d for d in docs if d.status == 'ready']
    pieces = []
    for d in sorted(ready, key=lambda x: (x.filename or '').lower()):
        tree = document_store.get_tree(d.doc_id)
        if not tree:
            continue
        heads = piece_head_nodes(tree)
        single = len(heads) <= 1
        for h in heads:
            start, end = _span(h)
            pieces.append({
                'doc_id': d.doc_id,
                'filename': d.filename,
                'node_id': h.get('node_id'),
                'title': d.filename if single else ((h.get('title') or '').strip() or d.filename),
                'summary': (h.get('summary') or '').strip(),
                'start_index': start,
                'end_index': end,
            })
    return jsonify({'folder': folder, 'total_docs': len(docs),
                    'ready_docs': len(ready), 'pieces': pieces})


@api_bp.route('/documents/<doc_id>/notes', methods=['GET'])
def list_doc_notes(doc_id):
    """Notes utilisateur (annotations) du document, par node_id."""
    return jsonify({'notes': document_store.get_notes(doc_id)})


@api_bp.route('/documents/<doc_id>/nodes/<node_id>/notes', methods=['POST'])
def add_doc_note(doc_id, node_id):
    data = request.json or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'text requis'}), 400
    kind = data.get('kind') or 'desc'
    page = data.get('page')
    page = int(page) if str(page).isdigit() else None
    quote = data.get('quote')
    # rects = liste de {x, y, w, h} en fractions 0-1 de la page (surlignage jaune)
    rects = data.get('rects') if isinstance(data.get('rects'), list) else None
    note = document_store.add_note(doc_id, node_id, text, kind, page, quote, rects)
    if note is None:
        return jsonify({'error': 'Document introuvable'}), 404
    return jsonify({'success': True, 'note': note})


@api_bp.route('/documents/<doc_id>/nodes/<node_id>/notes/<note_id>', methods=['DELETE'])
def delete_doc_note(doc_id, node_id, note_id):
    ok = document_store.delete_note(doc_id, node_id, note_id)
    return jsonify({'success': ok}), (200 if ok else 404)


@api_bp.route('/documents/<doc_id>/analysis', methods=['GET'])
def get_document_analysis(doc_id):
    doc = document_store.get_document(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    analysis = document_store.get_analysis(doc_id)
    if not analysis:
        return jsonify({'error': 'Analysis not available yet'}), 404
    return jsonify({'analysis': analysis})


@api_bp.route('/documents/<doc_id>/node-info', methods=['GET'])
def get_node_info(doc_id):
    doc = document_store.get_document(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    
    tree = document_store.get_tree(doc_id)
    node_map = document_store.get_node_map(doc_id)
    
    if tree and not node_map:
        from services.rag_service import PageIndexService
        service = PageIndexService(document_store)
        page_count = doc.page_count or 0
        if not page_count:
            def count_pages(node):
                max_page = 0
                if isinstance(node, dict):
                    if 'page' in node:
                        max_page = max(max_page, node.get('page', 0))
                    for child in node.get('children', []):
                        max_page = max(max_page, count_pages(child))
                elif isinstance(node, list):
                    for item in node:
                        max_page = max(max_page, count_pages(item))
                return max_page
            page_count = count_pages(tree)
        
        node_map = service.create_node_mapping(tree, include_page_ranges=True, max_page=page_count)
        document_store.cache_node_map(doc_id, node_map)
    
    if not node_map:
        return jsonify({'error': 'Node mapping not available'}), 404
    
    node_info = {}
    for node_id, info in node_map.items():
        node = info.get('node', {})
        node_info[node_id] = {
            'title': node.get('title', ''),
            'summary': node.get('summary', ''),
            'start_index': info.get('start_index'),
            'end_index': info.get('end_index'),
        }
    
    all_pages = []
    page_count = doc.page_count or 0
    for page_num in range(1, page_count + 1):
        page_url = f"/api/results/{doc_id}_{doc.filename}/images/page_{page_num}.jpg"
        all_pages.append({'page': page_num, 'url': page_url})
    
    return jsonify({'node_map': node_info, 'page_count': page_count, 'all_pages': all_pages})


@api_bp.route('/documents/<doc_id>/text-highlights', methods=['GET'])
def get_text_highlights(doc_id):
    doc = document_store.get_document(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    if doc.status != 'ready':
        return jsonify({'error': 'Document not ready'}), 400

    cache_path = os.path.join(doc.result_dir, 'text_highlights.json')
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))

    node_map = document_store.get_node_map(doc_id)
    if not node_map:
        # Cache mémoire perdu au redémarrage du serveur : l'arbre se recharge
        # depuis le disque, la cartographie se recalcule.
        tree = document_store.get_tree(doc_id)
        if tree:
            try:
                page_count = rag_service.pageindex.get_pdf_page_count(doc.file_path)
                node_map = rag_service.pageindex.create_node_mapping(
                    tree, include_page_ranges=True, max_page=page_count)
                document_store.cache_node_map(doc_id, node_map)
            except Exception as e:
                logger.error(f"Node map rebuild error: {e}")
    if not node_map:
        return jsonify({'error': 'Node mapping not available'}), 404

    from services.rag_service import PageIndexService
    service = PageIndexService(document_store)
    try:
        highlights = service.extract_text_highlights(doc.file_path, node_map)
    except Exception as e:
        logger.error(f"Text highlight extraction error: {e}")
        return jsonify({'error': str(e)}), 500

    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(highlights, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to cache highlights: {e}")

    return jsonify(highlights)


@api_bp.route('/documents/<doc_id>/page-words', methods=['GET'])
def get_page_words(doc_id):
    """Mots positionnés de chaque page (PyMuPDF get_text('words')), en FRACTIONS
    0-1 de la page → couche de texte sélectionnable par-dessus l'image (la
    sélection souris donne le passage exact + ses rectangles). Mis en cache."""
    doc = document_store.get_document(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    if doc.status != 'ready':
        return jsonify({'error': 'Document not ready'}), 400

    cache_path = os.path.join(doc.result_dir, 'page_words.json')
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))

    try:
        import fitz
        pdf = fitz.open(doc.file_path)
        pages = {}
        for i in range(len(pdf)):
            page = pdf.load_page(i)
            w, h = page.rect.width or 1, page.rect.height or 1
            words = []
            for x0, y0, x1, y1, word, *_ in page.get_text("words"):
                if not word.strip():
                    continue
                words.append([round(x0 / w, 4), round(y0 / h, 4),
                              round((x1 - x0) / w, 4), round((y1 - y0) / h, 4), word])
            pages[str(i + 1)] = words
        result = {'pages': pages}
    except Exception as e:
        logger.error(f"page-words extraction error: {e}")
        return jsonify({'error': str(e)}), 500

    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to cache page-words: {e}")
    return jsonify(result)


# ============= Skill Routes =============

@api_bp.route('/skills', methods=['GET'])
def list_skills():
    skills = skill_manager.list_skills()
    return jsonify({'skills': [s.to_dict() for s in skills]})


@api_bp.route('/skills', methods=['POST'])
def create_skill():
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Skill name is required'}), 400
    skill = skill_manager.create_skill(
        name=name,
        description=data.get('description', ''),
        content=data.get('content', ''),
        enabled=data.get('enabled', True),
    )
    return jsonify({'success': True, 'skill': skill.to_dict()})


@api_bp.route('/skills/<skill_id>', methods=['GET'])
def get_skill(skill_id):
    skill = skill_manager.get_skill(skill_id)
    if not skill:
        return jsonify({'error': 'Skill not found'}), 404
    return jsonify({'skill': skill.to_dict()})


@api_bp.route('/skills/<skill_id>', methods=['PUT'])
def update_skill(skill_id):
    data = request.json or {}
    skill = skill_manager.update_skill(skill_id, **data)
    if not skill:
        return jsonify({'error': 'Skill not found'}), 404
    return jsonify({'success': True, 'skill': skill.to_dict()})


@api_bp.route('/skills/<skill_id>', methods=['DELETE'])
def delete_skill(skill_id):
    if skill_manager.delete_skill(skill_id):
        return jsonify({'success': True})
    return jsonify({'error': 'Skill not found'}), 404


@api_bp.route('/skills/upload', methods=['POST'])
def upload_skill():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if not file.filename or not file.filename.endswith('.md'):
        return jsonify({'error': 'Only .md files are supported'}), 400

    content = file.read().decode('utf-8')
    skill_id = secure_filename(file.filename)[:-3]
    skill = Skill.from_markdown(content, skill_id)
    skill_manager.save_skill(skill)
    return jsonify({'success': True, 'skill': skill.to_dict()})
