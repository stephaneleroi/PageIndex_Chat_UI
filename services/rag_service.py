#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PageIndex service - handles PDF indexing and RAG operations.

Chat is now session-based: both agent and legacy flows take a session_id
and persist messages into models.session.SessionStore.
"""

import os
import re
import json
import base64
import logging
from typing import Dict, List, Optional, AsyncGenerator

from openai import AsyncOpenAI

from models.document import Document, DocumentStore, document_store
from models.session import Message, SessionStore, session_store
from config import config_manager, PLACEHOLDER_API_KEY

logger = logging.getLogger(__name__)


class PageIndexService:
    """Service for PageIndex operations"""
    
    def __init__(self, store: DocumentStore):
        self.store = store
    
    def _get_client(self, model_type: str = 'text') -> AsyncOpenAI:
        """Get OpenAI client with current configuration.

        Local OpenAI-compatible servers (Ollama, vLLM, LM Studio…) don't need a
        key, but the SDK requires a non-empty one — fall back to a placeholder
        so a base_url alone is enough to point at a local model.
        """
        config = config_manager.get_model_config(model_type)
        return AsyncOpenAI(
            api_key=config.get('api_key') or PLACEHOLDER_API_KEY,
            base_url=config.get('base_url') or None
        )
    
    def _get_model_name(self, model_type: str = 'text') -> str:
        """Get model name for the given type"""
        config = config_manager.get_model_config(model_type)
        return config.get('name', 'gpt-4o-mini')
    
    async def call_llm_stream(self, prompt: str, model_type: str = 'text',
                              messages: list = None) -> AsyncGenerator[str, None]:
        """Stream LLM response. ``messages`` (tours de dialogue bruts) prime
        sur ``prompt`` — utilisé par la conversation libre pour interroger le
        modèle NU, sans enrobage qui altérerait ses réponses."""
        client = self._get_client(model_type)
        model = self._get_model_name(model_type)

        try:
            # Mode brut (messages) : aucune température imposée — les réglages
            # du Modelfile s'appliquent (parité avec un chat Ollama direct).
            kwargs = {} if messages else {"temperature": 0}
            stream = await client.chat.completions.create(
                model=model,
                messages=messages or [{"role": "user", "content": prompt}],
                stream=True,
                **kwargs
            )
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"LLM call error: {e}")
            yield f"[Error: {str(e)}]"
    
    async def call_llm_tools(self, prompt: str, tools: list, model_type: str = 'light') -> dict:
        """Appel non-streamé avec function calling NATIF (paramètre `tools`),
        comme l'exemple officiel PageIndex (agentic_vectorless_rag_demo.py).
        Retourne {'content', 'reasoning', 'tool_calls': [{'name', 'arguments'}]}.
        Les exceptions remontent : l'appelant décide du repli (JSON texte)."""
        client = self._get_client(model_type)
        model = self._get_model_name(model_type)
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
            temperature=0,
        )
        msg = response.choices[0].message
        out = {
            "content": (msg.content or ""),
            "reasoning": (getattr(msg, 'reasoning', '') or ''),
            "tool_calls": [],
        }
        for tc in (msg.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments or '{}')
            except Exception:
                args = {}
            out["tool_calls"].append({"name": tc.function.name or "", "arguments": args})
        return out

    async def call_llm(self, prompt: str, model_type: str = 'text') -> str:
        """Non-streaming LLM call"""
        client = self._get_client(model_type)
        model = self._get_model_name(model_type)

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            if not (response.choices and len(response.choices) > 0):
                logger.error(f"LLM response has no choices")
                return "[Error: No response from model]"
            msg = response.choices[0].message
            content = (msg.content or '').strip()
            if content:
                return content
            # Certains modèles (gpt-oss via Ollama) répondent aux prompts de
            # type agent par un APPEL D'OUTIL NATIF (finish_reason=tool_calls,
            # content vide) au lieu du JSON texte demandé. On le re-sérialise
            # au format attendu par le planificateur ReAct.
            tool_calls = getattr(msg, 'tool_calls', None)
            if tool_calls:
                try:
                    fn = tool_calls[0].function
                    # Le modèle préfixe parfois le nom ("functions.tree_search",
                    # "tool_list_documents") — on normalise vers le registre.
                    name = (fn.name or '').split('.')[-1]
                    if name.startswith('tool_'):
                        name = name[5:]
                    return json.dumps({
                        "thought": (getattr(msg, 'reasoning', '') or '').strip()[:300],
                        "action": {"tool": name,
                                   "input": json.loads(fn.arguments or '{}')},
                    }, ensure_ascii=False)
                except Exception as e:
                    logger.warning(f"Native tool_call conversion failed: {e}")
            # Dernier recours : le canal de raisonnement, mieux que du vide.
            reasoning = (getattr(msg, 'reasoning', '') or '').strip()
            if reasoning:
                logger.warning("LLM returned empty content; falling back to reasoning channel")
                return reasoning
            return "[Error: empty response from model]"
        except Exception as e:
            logger.error(f"LLM call error: {e}")
            return f"[Error: {str(e)}]"
    
    async def call_vlm(self, prompt: str, image_paths: List[str], model_type: str = 'vision') -> str:
        """Call Vision Language Model with images (non-streaming)"""
        client = self._get_client(model_type)
        model = self._get_model_name(model_type)
        
        content = self._build_vlm_content(prompt, image_paths)
        
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": content}],
                temperature=0
            )
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content.strip()
            else:
                logger.error(f"VLM response has no choices")
                return "[Error: No response from model]"
        except Exception as e:
            logger.error(f"VLM call error: {e}")
            return f"[Error: {str(e)}]"

    async def call_vlm_stream(self, prompt: str, image_paths: List[str], model_type: str = 'vision'):
        """Stream Vision Language Model response with images"""
        client = self._get_client(model_type)
        model = self._get_model_name(model_type)

        content = self._build_vlm_content(prompt, image_paths)

        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": content}],
                temperature=0,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"VLM stream error: {e}")
            yield f"[Error: {str(e)}]"

    @staticmethod
    def _build_vlm_content(prompt: str, image_paths: List[str]) -> list:
        """Build multimodal content list for VLM calls"""
        content = [{"type": "text", "text": prompt}]
        for image_path in image_paths:
            if os.path.exists(image_path):
                with open(image_path, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_data}"
                    }
                })
        return content
    
    def load_tree_structure(self, tree_path: str) -> dict:
        """Load tree structure from JSON file"""
        with open(tree_path, 'r', encoding='utf-8') as f:
            tree_data = json.load(f)
            return tree_data.get('structure', tree_data)
    
    def create_node_mapping(self, tree: dict, include_page_ranges: bool = True, 
                           max_page: int = None) -> dict:
        """Create node mapping from tree structure"""
        def get_all_nodes(tree):
            if isinstance(tree, dict):
                return [tree] + [node for child in tree.get('nodes', []) for node in get_all_nodes(child)]
            elif isinstance(tree, list):
                return [node for item in tree for node in get_all_nodes(item)]
            return []
        
        all_nodes = get_all_nodes(tree)
        
        if not include_page_ranges:
            return {node["node_id"]: node for node in all_nodes if node.get("node_id")}
        
        mapping = {}
        for i, node in enumerate(all_nodes):
            if node.get("node_id"):
                start_page = node.get("start_index") or node.get("physical_index") or node.get("page_index")
                
                if i + 1 < len(all_nodes):
                    next_node = all_nodes[i + 1]
                    end_page = next_node.get("start_index") or next_node.get("physical_index") or next_node.get("page_index")
                else:
                    end_page = max_page
                
                mapping[node["node_id"]] = {
                    "node": node,
                    "start_index": start_page,
                    "end_index": end_page
                }
        
        return mapping
    
    def remove_fields(self, data, fields: List[str] = None):
        """Remove specified fields from data"""
        if fields is None:
            fields = ['text']
        if isinstance(data, dict):
            return {k: self.remove_fields(v, fields) for k, v in data.items() if k not in fields}
        elif isinstance(data, list):
            return [self.remove_fields(item, fields) for item in data]
        return data
    
    async def tree_search(self, query: str, tree: dict, model_type: str = 'text') -> dict:
        """Perform tree search to find relevant nodes (non-streaming)"""
        tree_without_text = self.remove_fields(tree.copy(), ['text'])
        
        search_prompt = f"""
You are given a question and a tree structure of a document.
Each node contains a node id, node title, and a corresponding summary.
Your task is to find all nodes that are likely to contain the answer to the question.

Question: {query}

Document tree structure:
{json.dumps(tree_without_text, indent=2, ensure_ascii=False)}

Important: You MUST respond in French (français). Your thinking process should be in French.

Please reply in the following JSON format:
{{
    "thinking": "<décris ton raisonnement en français>",
    "node_list": ["node_id_1", "node_id_2", ..., "node_id_n"]
}}
Directly return the final JSON structure. Do not output anything else.
"""
        
        result = await self.call_llm(search_prompt, 'light')
        
        try:
            if '```json' in result:
                start = result.find('```json') + 7
                end = result.rfind('```')
                result = result[start:end].strip()
            return json.loads(result)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse tree search result: {result}")
            return {"thinking": "Error parsing response", "node_list": []}
    
    async def tree_search_stream(self, query: str, tree: dict, model_type: str = 'text'):
        """Perform tree search with streaming thinking output"""
        tree_without_text = self.remove_fields(tree.copy(), ['text'])
        
        search_prompt = f"""You are given a question and a tree structure of a document.
Each node contains a node id, node title, and a corresponding summary.
Your task is to find all nodes that are likely to contain the answer to the question.

Question: {query}

Document tree structure:
{json.dumps(tree_without_text, indent=2, ensure_ascii=False)}

Important: You MUST respond in French (français). Your thinking process should be in French.

First, output your thinking process in French about which nodes are relevant to the question.
Then, at the very end, output the node list in this EXACT format on a new line:
[NODE_LIST]: ["node_id_1", "node_id_2", "node_id_n"]

Example output:
D'après la structure du document, je dois trouver les nœuds liés à la question...
Les nœuds les plus pertinents sont X et Y, car...
[NODE_LIST]: ["node_x", "node_y"]
"""
        
        full_response = ""
        buffer = ""
        node_list_str = ""
        
        async for chunk in self.call_llm_stream(search_prompt, 'light'):
            full_response += chunk
            buffer += chunk
            
            if len(buffer) > 20:
                yield ('thinking', buffer)
                buffer = ""
            
            if '[NODE_LIST]:' in buffer and not node_list_str:
                match = re.search(r'\[NODE_LIST\]:\s*(\[.*?\])', full_response, re.DOTALL)
                if match:
                    node_list_str = match.group(1)
                    try:
                        node_list = json.loads(node_list_str)
                        self._pending_node_list = node_list
                    except json.JSONDecodeError:
                        pass
        
        if buffer:
            yield ('thinking', buffer)
        
        if hasattr(self, '_pending_node_list') and self._pending_node_list:
            yield ('node_list', self._pending_node_list)
            delattr(self, '_pending_node_list')
            return
        
        match = re.search(r'\[NODE_LIST\]:\s*(\[.*?\])', full_response, re.DOTALL)
        if match:
            try:
                node_list = json.loads(match.group(1))
                yield ('node_list', node_list)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse node list: {match.group(1)}")
                yield ('node_list', [])
        else:
            match = re.search(r'\[("[^"]+"\s*,\s*)*"[^"]+"\s*\]', full_response)
            if match:
                try:
                    node_list = json.loads(match.group(0))
                    yield ('node_list', node_list)
                except Exception:
                    logger.error(f"Failed to parse any node list from response")
                    yield ('node_list', [])
            else:
                logger.error(f"No node list found in response: {full_response[:200]}")
                yield ('node_list', [])
    
    def get_relevant_content(self, node_list: List[str], node_map: dict) -> str:
        contents = []
        for node_id in node_list:
            if node_id in node_map:
                node_info = node_map[node_id]
                node = node_info.get('node', node_info)
                if isinstance(node, dict) and node.get('text'):
                    contents.append(node['text'])
        return "\n\n".join(contents)
    
    def get_page_images_for_nodes(self, node_list: List[str], node_map: dict, 
                                  page_images: dict) -> List[str]:
        image_paths = []
        seen_pages = set()
        
        for node_id in node_list:
            if node_id in node_map:
                node_info = node_map[node_id]
                start = node_info.get('start_index', 1)
                end = node_info.get('end_index', start)
                
                for page_num in range(start, end + 1):
                    if page_num not in seen_pages and page_num in page_images:
                        image_paths.append(page_images[page_num])
                        seen_pages.add(page_num)
        
        return image_paths
    
    async def extract_pdf_page_images(self, pdf_path: str, output_dir: str,
                                      on_progress=None) -> dict:
        """Render each PDF page to a JPEG under output_dir.

        on_progress(rendered:int, total:int) is called after each page so callers
        (e.g. the indexing pipeline) can surface "X/Y" page progress to the UI.
        """
        import fitz
        
        os.makedirs(output_dir, exist_ok=True)
        pdf_document = fitz.open(pdf_path)
        page_images = {}
        total = len(pdf_document)
        
        for page_number in range(total):
            page = pdf_document.load_page(page_number)
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("jpeg")
            image_path = os.path.join(output_dir, f"page_{page_number + 1}.jpg")
            with open(image_path, "wb") as f:
                f.write(img_data)
            page_images[page_number + 1] = image_path
            if on_progress is not None:
                try:
                    on_progress(page_number + 1, total)
                except Exception:
                    pass
        
        pdf_document.close()
        return page_images
    
    def get_pdf_page_count(self, pdf_path: str) -> int:
        import fitz
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count

    def extract_text_highlights(self, pdf_path: str, node_map: dict) -> dict:
        import fitz

        page_to_nodes: Dict[int, List[dict]] = {}
        for nid, info in node_map.items():
            s = info.get("start_index") or 1
            e = info.get("end_index") or s
            node_obj = info.get("node", info)
            node_text = node_obj.get("text", "") if isinstance(node_obj, dict) else ""
            for p in range(s, e + 1):
                page_to_nodes.setdefault(p, []).append({
                    "id": nid, "text": node_text, "start": s, "end": e,
                    # Comparaison insensible aux espaces : l'extraction par
                    # blocs (spans concaténés) et le texte des nœuds diffèrent
                    # par leurs blancs, ce qui faisait échouer l'attribution.
                    "norm": re.sub(r"\s+", "", node_text),
                })

        doc = fitz.open(pdf_path)
        result = {"scale": 2.0, "pages": {}}

        for page_number in range(len(doc)):
            page = doc.load_page(page_number)
            pnum = page_number + 1
            rect = page.rect
            page_data = {
                "width": rect.width,
                "height": rect.height,
                "blocks": [],
            }

            candidates = page_to_nodes.get(pnum, [])
            if not candidates:
                result["pages"][str(pnum)] = page_data
                continue

            text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                bbox = block.get("bbox")
                if not bbox:
                    continue

                block_text = ""
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        block_text += span.get("text", "")

                block_text_stripped = block_text.strip()
                if not block_text_stripped:
                    continue

                # Attribution stricte : un bloc n'est surligné que si son texte
                # (espaces ignorés) figure dans le texte d'un nœud candidat.
                # Un bloc inconnu (en-tête/pied retiré des nœuds, partie d'une
                # AUTRE pièce sur une page partagée) n'est PAS surligné — le
                # rabattre sur le premier candidat faisait surligner le début
                # de l'ordonnance comme s'il appartenait à la note.
                block_norm = re.sub(r"\s+", "", block_text_stripped)
                owner = None
                if block_norm:
                    for c in reversed(candidates):
                        if c["norm"] and block_norm in c["norm"]:
                            owner = c["id"]
                            break
                if not owner:
                    continue

                page_data["blocks"].append({
                    "bbox": [round(bbox[0], 1), round(bbox[1], 1),
                             round(bbox[2], 1), round(bbox[3], 1)],
                    "node_id": owner,
                })

            result["pages"][str(pnum)] = page_data

        doc.close()
        return result


class RAGService:
    """RAG service combining PageIndex with session-based chat."""

    def __init__(self, store: DocumentStore, sessions: SessionStore = session_store):
        self.store = store
        self.sessions = sessions
        self.pageindex = PageIndexService(store)
        self._agent = None

    @property
    def agent(self):
        if self._agent is None:
            from services.agent import DocumentAgent
            self._agent = DocumentAgent(self.pageindex, self.store, self.sessions)
        return self._agent
    
    async def prepare_document(self, doc_id: str, pdf_path: str, tree_path: str):
        """Prepare document for RAG - load tree and extract images"""
        doc = self.store.get_document(doc_id)
        if not doc:
            return False
        
        try:
            self.store.set_stage(doc_id, 'image_extract', 'Génération des images de pages (préparation)...')
            tree = self.pageindex.load_tree_structure(tree_path)
            self.store.cache_tree(doc_id, tree)
            
            page_count = self.pageindex.get_pdf_page_count(pdf_path)
            self.store.update_document(doc_id, page_count=page_count)
            
            node_map = self.pageindex.create_node_mapping(tree, include_page_ranges=True, max_page=page_count)
            self.store.cache_node_map(doc_id, node_map)

            # Throttle per-page messages so we don't hammer the metadata file.
            last_ts = [0.0]
            def _on_page(done: int, total: int):
                import time as _t
                now = _t.time()
                if done == total or now - last_ts[0] > 0.4:
                    self.store.set_stage(
                        doc_id, 'image_extract',
                        f'Génération des images de pages : page {done}/{total}',
                    )
                    last_ts[0] = now

            page_images = await self.pageindex.extract_pdf_page_images(
                pdf_path, doc.images_dir, on_progress=_on_page,
            )
            self.store.cache_page_images(doc_id, page_images)
            
            self.store.update_document(doc_id, status='ready')
            self.store.set_stage(doc_id, 'done', 'Indexation terminée')
            return True
        except Exception as e:
            logger.error(f"Error preparing document: {e}")
            self.store.update_document(
                doc_id, status='error', error_message=str(e),
                stage='error', stage_message=f'Échec de la phase de préparation : {e}'
            )
            return False

    # ---------------- Session-based chat ---------------- #

    async def chat_stream(self, session_id: str, query: str,
                          model_type: str = 'text',
                          use_memory: bool = True) -> AsyncGenerator[str, None]:
        """Legacy non-agent RAG stream. Operates on a session in single-doc mode only."""
        session = self.sessions.get_session(session_id)
        if not session:
            yield "[Error: Session not found]"
            return
        if session.mode != 'single':
            yield "[Error: Legacy chat only supports single-doc sessions. Use agent mode for KB.]"
            return
        if not session.doc_ids:
            yield "[Error: Session has no document]"
            return

        doc_id = session.doc_ids[0]
        doc = self.store.get_document(doc_id)
        if not doc or doc.status != 'ready':
            yield "[Error: Document not ready]"
            return

        tree = self.store.get_tree(doc_id)
        node_map = self.store.get_node_map(doc_id)
        page_images = self.store.get_page_images(doc_id)

        if tree and not node_map:
            yield "[PREPARING]\nPréparation des données du document...\n"
            try:
                page_count = self.pageindex.get_pdf_page_count(doc.file_path)
                self.store.update_document(doc_id, page_count=page_count)
                node_map = self.pageindex.create_node_mapping(tree, include_page_ranges=True, max_page=page_count)
                self.store.cache_node_map(doc_id, node_map)
                if not page_images:
                    page_images = await self.pageindex.extract_pdf_page_images(doc.file_path, doc.images_dir)
                    self.store.cache_page_images(doc_id, page_images)
                yield "[PREPARED]\nPréparation terminée !\n\n"
            except Exception as e:
                logger.error(f"Error preparing document: {e}")
                yield f"[Error: Failed to prepare document: {e}]"
                return

        if not tree:
            yield "[Error: Tree structure not loaded]"
            return
        if not node_map:
            yield "[Error: Node mapping not available]"
            return

        # Step 1: tree search streaming thinking
        yield "[SEARCHING]\n"

        thinking = ""
        node_list = []

        async for chunk_type, content in self.pageindex.tree_search_stream(query, tree, model_type):
            if chunk_type == 'thinking':
                thinking += content
                yield f"[THINKING_CHUNK]{content}"
            elif chunk_type == 'node_list':
                node_list = content

        if node_list:
            yield f"\n[NODES]{json.dumps(node_list)}\n"

        yield "[ANSWERING]\n"

        if model_type == 'text':
            relevant_content = self.pageindex.get_relevant_content(node_list, node_map)
            history_context = ""
            if use_memory:
                history = self.sessions.get_messages(session_id)
                # Skip reflection-superseded drafts (see agent._build_history_context).
                history = [m for m in history if not getattr(m, 'superseded', False)]
                if history:
                    history_context = "\n\nPrevious conversation:\n"
                    for msg in history[-5:]:
                        history_context += f"{msg.role}: {msg.content}\n"

            answer_prompt = f"""Answer the question based on the context. If the context is not sufficient, say so.

Question: {query}

Context: {relevant_content}
{history_context}

Important: You MUST respond in French (français). All your output should be in French.
When mentioning any mathematical symbol, variable, subscript, superscript, or formula, you MUST wrap them in LaTeX delimiters: use $...$ for inline math and \\[...\\] for display math.
Provide a clear, concise answer in French based only on the context provided. If you need to reference specific sections, mention the node IDs.
Use Markdown formatting for better readability.
"""
            full_answer = ""
            async for chunk in self.pageindex.call_llm_stream(answer_prompt, model_type):
                full_answer += chunk
                yield chunk

            self.sessions.add_message(session_id, Message(role='user', content=query))
            self.sessions.add_message(session_id, Message(
                role='assistant', content=full_answer,
                nodes=node_list, thinking=thinking,
            ))
        else:
            image_paths = self.pageindex.get_page_images_for_nodes(node_list, node_map, page_images)
            if not image_paths:
                yield "[Error: No relevant images found]"
                return

            answer_prompt = f"""Answer the question based on the images of the document pages as context.

Question: {query}

Important: You MUST respond in French (français). Use LaTeX for math symbols.
Use Markdown formatting for better readability.
"""
            full_answer = ""
            async for chunk in self.pageindex.call_vlm_stream(answer_prompt, image_paths, model_type):
                full_answer += chunk
                yield chunk

            self.sessions.add_message(session_id, Message(role='user', content=query))
            self.sessions.add_message(session_id, Message(
                role='assistant', content=full_answer,
                nodes=node_list, thinking=thinking,
            ))

    async def agent_chat_stream(self, session_id: str, query: str,
                                model_type: str = 'text',
                                use_memory: bool = True):
        """Agent-powered chat with ReAct loop, decomposition, and reflection."""
        async for chunk in self.agent.run_session(session_id, query, model_type, use_memory):
            yield chunk

    # ---------------- History helpers ---------------- #

    def get_session_history(self, session_id: str) -> List[dict]:
        return [m.to_dict() for m in self.sessions.get_messages(session_id)]

    def clear_session_history(self, session_id: str):
        self.sessions.clear_messages(session_id)

    async def auto_analyze_document(self, doc_id: str,
                                    model_type: str = 'text') -> dict:
        """Proactive document analysis after indexing"""
        self.store.set_stage(doc_id, 'analysis', 'Génération du résumé et des questions suggérées...')
        try:
            result = await self.agent.analyze_document(doc_id, model_type)
            self.store.set_stage(doc_id, 'done', 'Indexation terminée')
            return result
        except Exception as e:
            # Analysis is non-fatal — doc is already 'ready'. Just surface a hint.
            self.store.set_stage(doc_id, 'done', f'Échec de la génération du résumé (sans impact sur les questions) : {e}')
            raise


# Create singleton instance
rag_service = RAGService(document_store, session_store)
