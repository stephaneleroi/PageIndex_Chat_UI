/**
 * PageIndex Agent — Frontend Application
 * Three-page architecture: Library / Doc-Chat / KB-Chat
 */

// ========================================================================
// Global State
// ========================================================================
const State = {
    socket: null,
    currentPage: 'library',           // 'library' | 'doc-chat' | 'kb-chat'
    modelType: 'text',

    // Library
    documents: [],

    // Doc-chat (single document, potentially multiple sessions)
    docChat: {
        docId: null,
        docInfo: null,
        analysis: null,
        sessions: [],
        activeSessionId: null,
        useMemory: true,
    },

    // KB-chat (multi-doc, multiple sessions)
    kbChat: {
        selectedDocIds: new Set(),
        sessions: [],
        activeSessionId: null,
        docSearchKeyword: '',
        useMemory: true,
    },

    // Streaming
    isStreaming: false,
    streamingRawText: '',
    streamingNodes: [],               // qualified node refs for the answer in progress

    // Caches
    nodeMapCache: {},
    allPagesCache: {},
    highlightsCache: {},
    activeHighlightNodeId: null,
    _highlightObserver: null,
};

const NODE_COLORS = [
    {bg:'#eef2ff',text:'#4338ca'},{bg:'#ecfdf5',text:'#065f46'},{bg:'#fef3c7',text:'#92400e'},
    {bg:'#fce7f3',text:'#9d174d'},{bg:'#e0f2fe',text:'#075985'},{bg:'#f3e8ff',text:'#6b21a8'},
    {bg:'#fef2f2',text:'#991b1b'},{bg:'#f0fdf4',text:'#166534'},{bg:'#fff7ed',text:'#9a3412'},
    {bg:'#f5f3ff',text:'#5b21b6'},{bg:'#ecfeff',text:'#155e75'},{bg:'#fdf2f8',text:'#831843'},
];

// ========================================================================
// Markdown / KaTeX helpers (unchanged from v1)
// ========================================================================
if (typeof marked !== 'undefined') {
    marked.setOptions({ breaks: true, gfm: true });
}

let _mathStore = [];
function normalizeMathDelimiters(text) {
    if (!text) return '';
    return text.replace(/(^|\n)\[\s*\n([\s\S]*?)\n\](?=\n|$)/g, '$1\\\\[\n$2\n\\\\]');
}
function protectMathDelimiters(text) {
    if (!text) return text;
    _mathStore = [];
    let idx = 0;
    text = text.replace(/\$\$([\s\S]*?)\$\$/g, (m) => { _mathStore.push(m); return `@@MATH_PLACEHOLDER_${idx++}@@`; });
    text = text.replace(/\\\[([\s\S]*?)\\\]/g, (m) => { _mathStore.push(m); return `@@MATH_PLACEHOLDER_${idx++}@@`; });
    text = text.replace(/\\\(([\s\S]*?)\\\)/g, (m) => { _mathStore.push(m); return `@@MATH_PLACEHOLDER_${idx++}@@`; });
    text = text.replace(/(?<![\\$])\$(?!\$)((?:[^$\\]|\\.)+?)\$/g, (m) => { _mathStore.push(m); return `@@MATH_PLACEHOLDER_${idx++}@@`; });
    return text;
}
function restoreMathDelimiters(html) {
    if (!html) return html;
    return html.replace(/@@MATH_PLACEHOLDER_(\d+)@@/g, (_, i) => {
        const original = _mathStore[parseInt(i)] || '';
        const d = document.createElement('div'); d.textContent = original; return d.innerHTML;
    });
}
function renderMarkdown(text) {
    if (!text) return '';
    const normalized = normalizeMathDelimiters(text);
    const protectedText = protectMathDelimiters(normalized);
    if (typeof marked !== 'undefined') {
        let html = marked.parse(protectedText);
        html = restoreMathDelimiters(html);
        html = html.replace(/<table([\s\S]*?<\/table>)/g, '<div class="table-wrapper"><table$1</div>');
        return html;
    }
    return esc(normalized);
}
function renderMathInContainer(container) {
    if (!container || typeof renderMathInElement === 'undefined') return;
    renderMathInElement(container, {
        throwOnError: false,
        delimiters: [
            { left: '$$', right: '$$', display: true },
            { left: '\\[', right: '\\]', display: true },
            { left: '$', right: '$', display: false },
            { left: '\\(', right: '\\)', display: false }
        ]
    });
}
function esc(t) { const d = document.createElement('div'); d.textContent = t == null ? '' : String(t); return d.innerHTML; }

function showNotification(msg, kind = 'success') {
    const n = document.createElement('div');
    const bg = kind === 'error' ? '#ef4444' : '#22c55e';
    n.style.cssText = `position:fixed;top:20px;right:20px;background:${bg};color:white;padding:12px 24px;border-radius:10px;box-shadow:0 4px 15px rgba(0,0,0,0.2);z-index:99999;animation:slideIn .3s ease`;
    n.textContent = msg; document.body.appendChild(n);
    setTimeout(() => { n.style.animation = 'slideOut .3s ease'; setTimeout(() => n.remove(), 300); }, 2500);
}

function fmtTime(ts) {
    if (!ts) return '';
    const d = new Date(ts * 1000);
    const now = new Date();
    const sameDay = d.toDateString() === now.toDateString();
    if (sameDay) return d.toTimeString().slice(0, 5);
    const diff = Math.floor((now - d) / 86400000);
    if (diff < 7) return `il y a ${diff} j`;
    return `${d.getMonth() + 1}/${d.getDate()}`;
}

// ========================================================================
// Bootstrap
// ========================================================================
function safeRun(label, fn) {
    try {
        fn();
        console.log(`%c[boot] ✓ ${label}`, 'color:#10b981');
    } catch (e) {
        console.error(`%c[boot] ✗ ${label}`, 'color:#ef4444;font-weight:bold', e);
    }
}

function bootApp() {
    console.log('%c[PageIndex Agent] booting...', 'color:#6366f1;font-weight:bold;font-size:14px');
    safeRun('initSocket', initSocket);
    safeRun('setupNavTabs', setupNavTabs);
    safeRun('setupLibraryPage', setupLibraryPage);
    safeRun('setupDocChatPage', setupDocChatPage);
    safeRun('setupKbChatPage', setupKbChatPage);
    safeRun('setupModelToggle', setupModelToggle);
    safeRun('setupSettings', setupSettings);
    safeRun('setupSkills', setupSkills);
    safeRun('loadConfig', loadConfig);
    safeRun('loadLibrary', loadLibrary);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const preview = document.getElementById('pagePreviewModal');
            if (preview && preview.classList.contains('active')) closePagePreviewModal();
        }
    });
    console.log('%c[PageIndex Agent] boot complete.', 'color:#10b981;font-weight:bold');
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootApp);
} else {
    // Script ran after DOM is already ready (defensive).
    bootApp();
}

// ========================================================================
// Top Nav Tabs
// ========================================================================
function setupNavTabs() {
    document.querySelectorAll('.nav-tab').forEach(btn => {
        btn.addEventListener('click', () => goToPage(btn.dataset.page));
    });
}

function goToPage(page, opts = {}) {
    State.currentPage = page;
    document.querySelectorAll('.nav-tab').forEach(t =>
        t.classList.toggle('active', t.dataset.page === page));
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const el = document.getElementById({
        'library': 'pageLibrary',
        'doc-chat': 'pageDocChat',
        'kb-chat': 'pageKbChat',
    }[page]);
    if (el) el.classList.add('active');

    if (page === 'library') {
        loadLibrary();
    } else if (page === 'kb-chat') {
        onEnterKbChat(opts);
    } else if (page === 'doc-chat') {
        onEnterDocChat(opts);
    }
}

// ========================================================================
// Model Toggle
// ========================================================================
function setupModelToggle() {
    document.getElementById('textModelBtn')?.addEventListener('click', () => switchModel('text'));
    document.getElementById('visionModelBtn')?.addEventListener('click', () => switchModel('vision'));
}
function switchModel(t) {
    State.modelType = t;
    document.getElementById('textModelBtn')?.classList.toggle('active', t === 'text');
    document.getElementById('visionModelBtn')?.classList.toggle('active', t === 'vision');
}

// ========================================================================
// Socket
// ========================================================================
function initSocket() {
    if (typeof io === 'undefined') {
        console.warn('[initSocket] socket.io not loaded — CDN blocked? Chat streaming will be unavailable, but UI should still work.');
        return;
    }
    try {
        State.socket = io();
    } catch (e) {
        console.error('[initSocket] io() threw:', e);
        return;
    }
    State.socket.on('connect', () => console.log('Socket connected'));
    State.socket.on('status', d => onStreamStatus(d.status));
    State.socket.on('thinking_chunk', d => onStreamThinking(d.content));
    State.socket.on('nodes', d => onStreamNodes(d.nodes));
    State.socket.on('chunk', d => onStreamChunk(d.content));
    State.socket.on('response', d => onStreamFullResponse(d.content));
    State.socket.on('done', () => onStreamDone(false));
    State.socket.on('stopped', () => onStreamDone(true));
    State.socket.on('error', d => onStreamError(d.message));
    State.socket.on('agent_step', d => onAgentStep(d));
    State.socket.on('agent_decompose', d => onAgentDecompose(d));
    State.socket.on('agent_reflect', d => onAgentReflect(d));
    State.socket.on('history', d => onHistoryReceived(d));
    State.socket.on('history_cleared', d => onHistoryCleared(d));
}

function activeChatUI() {
    if (State.currentPage === 'doc-chat') {
        return {
            messages: document.getElementById('docChatMessages'),
            container: document.getElementById('docChatContainer'),
            input: document.getElementById('docChatInput'),
            sendBtn: document.getElementById('docSendBtn'),
        };
    }
    if (State.currentPage === 'kb-chat') {
        return {
            messages: document.getElementById('kbChatMessages'),
            container: document.getElementById('kbChatContainer'),
            input: document.getElementById('kbChatInput'),
            sendBtn: document.getElementById('kbSendBtn'),
        };
    }
    return null;
}

function scrollChatToBottom() {
    const ui = activeChatUI();
    if (ui?.container) ui.container.scrollTop = ui.container.scrollHeight;
}

// ========================================================================
//  LIBRARY PAGE
// ========================================================================
function setupLibraryPage() {
    const fileInput = document.getElementById('libraryFileInput');
    const pickFiles = () => fileInput?.click();

    document.getElementById('libraryUploadBtn')?.addEventListener('click', pickFiles);
    document.getElementById('heroUploadBtn')?.addEventListener('click', pickFiles);
    document.getElementById('heroKbBtn')?.addEventListener('click', () => goToPage('kb-chat'));

    fileInput?.addEventListener('change', e => {
        const files = [...(e.target.files || [])];
        files.forEach(f => uploadDocument(f));
        e.target.value = '';
    });

    // Drag & drop anywhere on the library page
    const libraryPage = document.getElementById('pageLibrary');
    if (libraryPage) {
        let dragDepth = 0;
        libraryPage.addEventListener('dragenter', e => {
            if (!e.dataTransfer?.types?.includes('Files')) return;
            e.preventDefault();
            dragDepth++;
            document.querySelector('.lib-dropzone')?.classList.add('dragover');
        });
        libraryPage.addEventListener('dragleave', e => {
            if (!e.dataTransfer?.types?.includes('Files')) return;
            dragDepth = Math.max(0, dragDepth - 1);
            if (dragDepth === 0) {
                document.querySelector('.lib-dropzone')?.classList.remove('dragover');
            }
        });
        libraryPage.addEventListener('dragover', e => {
            if (e.dataTransfer?.types?.includes('Files')) e.preventDefault();
        });
        libraryPage.addEventListener('drop', e => {
            if (!e.dataTransfer?.types?.includes('Files')) return;
            e.preventDefault();
            dragDepth = 0;
            document.querySelector('.lib-dropzone')?.classList.remove('dragover');
            const files = [...(e.dataTransfer.files || [])].filter(f => f.name.toLowerCase().endsWith('.pdf'));
            if (!files.length) { showNotification('Seuls les fichiers PDF sont pris en charge', 'error'); return; }
            files.forEach(f => uploadDocument(f));
        });
    }
}

async function loadLibrary() {
    try {
        const [docsRes, sessRes] = await Promise.all([
            fetch('/api/documents').then(r => r.json()).catch(() => ({ documents: [] })),
            fetch('/api/sessions').then(r => r.json()).catch(() => ({ sessions: [] })),
        ]);
        State.documents = docsRes.documents || [];
        renderLibrary(sessRes.sessions || []);
        // Resume polling for any doc that is still indexing — e.g. after a
        // page refresh or when switching back to the library tab.
        for (const d of State.documents) {
            if (d.status !== 'ready' && d.status !== 'error') {
                ensurePolling(d.doc_id);
            }
        }
    } catch (e) { console.error('Load library error:', e); }
}

// De-dup concurrent pollers for the same doc.
const _activePollers = new Set();
function ensurePolling(docId) {
    if (_activePollers.has(docId)) return;
    _activePollers.add(docId);
    startProgressTick();
    pollDocumentStatus(docId);
}

function renderLibrary(allSessions = []) {
    // --- Update hero stats ---
    const docs = State.documents || [];
    const readyCount = docs.filter(d => d.status === 'ready').length;
    const pageCount = docs.reduce((s, d) => s + (d.page_count || 0), 0);
    const sessionCount = allSessions.length;

    const setStat = (id, v) => {
        const el = document.getElementById(id);
        if (el) {
            // Preserve <span class="unit"> if present
            const unit = el.querySelector('.unit');
            if (unit) {
                el.firstChild.textContent = v;
            } else {
                el.textContent = v;
            }
        }
    };
    setStat('statTotalDocs', docs.length);
    setStat('statReadyDocs', readyCount);
    setStat('statTotalPages', pageCount);
    setStat('statTotalSessions', sessionCount);

    const badge = document.getElementById('docsCountBadge');
    if (badge) badge.textContent = docs.length;

    // --- Render grid ---
    const grid = document.getElementById('libraryGrid');
    if (!grid) return;
    if (docs.length === 0) {
        grid.innerHTML = `
            <div class="lib-dropzone" id="libDropzone">
                <div class="dz-icon"><i class="bi bi-cloud-arrow-up"></i></div>
                <h3>Glissez un PDF ici / cliquez pour importer</h3>
                <p>L'Agent analyse la structure et génère un résumé ; la conversation est possible après quelques dizaines de secondes</p>
                <div class="dz-hint">Import par lots pris en charge · 50 Mo max recommandé par fichier</div>
            </div>`;
        grid.querySelector('#libDropzone')?.addEventListener('click', () => {
            document.getElementById('libraryFileInput')?.click();
        });
        return;
    }
    grid.innerHTML = docs.map(d => renderDocCard(d)).join('');
    grid.querySelectorAll('[data-action="chat"]').forEach(el => {
        el.addEventListener('click', e => {
            e.stopPropagation();
            enterDocChat(el.dataset.docId);
        });
    });
    grid.querySelectorAll('[data-action="delete"]').forEach(el => {
        el.addEventListener('click', e => {
            e.stopPropagation();
            deleteDocument(el.dataset.docId, el.dataset.filename);
        });
    });
    grid.querySelectorAll('[data-action="retry"]').forEach(el => {
        el.addEventListener('click', e => {
            e.stopPropagation();
            retryDocument(el.dataset.docId);
        });
    });
    grid.querySelectorAll('[data-action="tree"]').forEach(el => {
        el.addEventListener('click', e => {
            e.stopPropagation();
            showDocTree(el.dataset.docId);
        });
    });
    grid.querySelectorAll('[data-action="preview"]').forEach(el => {
        el.addEventListener('click', e => {
            e.stopPropagation();
            showDocPreview(el.dataset.docId);
        });
    });
}

function renderDocCard(d) {
    const statusLabel = { pending: 'En attente', indexing: 'Indexation en cours', indexed: 'Indexation terminée', ready: 'Prêt', error: 'Échec' }[d.status] || d.status;
    const summary = d.status === 'ready' && d.analysis_summary ?
        `<div class="doc-card-summary">${esc(d.analysis_summary)}</div>` : '';
    const errorMsg = d.status === 'error' && d.error_message ?
        `<div class="doc-card-error-msg">${esc(d.error_message)}</div>` : '';
    const meta = d.page_count ? `<span>· ${d.page_count} pages</span>` : '';

    // Progress block — only shown while indexing.
    const progressBlock = (d.status !== 'ready' && d.status !== 'error')
        ? renderDocProgress(d) : '';

    let footer = '';
    if (d.status === 'ready') {
        footer = `
            <button class="doc-card-btn chat-btn" data-action="chat" data-doc-id="${d.doc_id}">
                <i class="bi bi-chat-square-text"></i> Discuter
            </button>
            <button class="doc-card-btn" data-action="tree" data-doc-id="${d.doc_id}" title="Voir la structure PageIndex">
                <i class="bi bi-diagram-3"></i> Structure
            </button>
            <button class="doc-card-btn" data-action="preview" data-doc-id="${d.doc_id}" title="Feuilleter le document">
                <i class="bi bi-eye"></i>
            </button>
            <button class="doc-card-btn delete-btn" data-action="delete" data-doc-id="${d.doc_id}" data-filename="${esc(d.filename)}">
                <i class="bi bi-trash3"></i>
            </button>`;
    } else if (d.status === 'error') {
        footer = `
            <button class="doc-card-btn" data-action="retry" data-doc-id="${d.doc_id}">
                <i class="bi bi-arrow-clockwise"></i> Réessayer
            </button>
            <button class="doc-card-btn delete-btn" data-action="delete" data-doc-id="${d.doc_id}" data-filename="${esc(d.filename)}">
                <i class="bi bi-trash3"></i>
            </button>`;
    } else {
        const stageShort = STAGE_LABEL[d.stage] || 'Traitement en cours';
        footer = `
            <button class="doc-card-btn" disabled style="opacity:.6;cursor:not-allowed">
                <i class="bi bi-hourglass-split"></i> ${esc(stageShort)}…
            </button>`;
    }

    // Cover thumbnail (page 1 render) — produced during indexing; falls back
    // to a neutral PDF glyph while pending or if the image is missing.
    const coverUrl = d.result_dir_name
        ? `/api/results/${encodeURIComponent(d.result_dir_name)}/images/page_1.jpg` : '';
    const cover = `
        <div class="doc-card-cover">
            ${coverUrl ? `<img src="${coverUrl}" alt="" loading="lazy"
                 onerror="this.style.display='none'">` : ''}
            <div class="doc-card-cover-fallback" style="z-index:-1"><i class="bi bi-file-earmark-pdf"></i></div>
        </div>`;

    return `
        <div class="doc-card ${d.status === 'error' ? 'status-error' : ''}">
            ${cover}
            <div class="doc-card-main">
                <div class="doc-card-top">
                    <div class="doc-card-name">${esc(d.filename)}</div>
                </div>
                <div class="doc-card-meta">
                    <span class="status-badge status-${d.status}"></span>
                    <span>${statusLabel}</span>
                    ${meta}
                </div>
                ${summary}
                ${progressBlock}
                ${errorMsg}
                <div class="doc-card-footer">${footer}</div>
            </div>
        </div>`;
}

// Ordered stages + their display labels (French) and nominal progress %.
// Progress % is a rough visual guide — it's intentionally not exposed by the
// backend since we can't measure LLM latency precisely.
const STAGE_ORDER = ['queued', 'parsing', 'toc_detect', 'tree_build', 'image_extract', 'analysis', 'done'];
const STAGE_LABEL = {
    queued:        'En file d\'attente',
    parsing:       'Analyse du PDF',
    toc_detect:    'Détection du sommaire',
    tree_build:    'Construction de l\'arbre',
    image_extract: 'Rendu des pages',
    analysis:      'Génération du résumé',
    done:          'Terminé',
    error:         'Échec',
};
// Each stage occupies a [from, to] % band. Within a band we interpolate based
// on elapsed time so the bar visibly creeps forward even while the backend is
// blocked inside an LLM call (never reaches the band's upper bound — that only
// happens when the backend flips to the next stage).
const STAGE_BAND = {
    queued:        [0,  5],
    parsing:       [5, 12],
    toc_detect:    [12, 28],
    tree_build:    [28, 70],   // widest band — usually the longest phase
    image_extract: [70, 90],
    analysis:      [90, 97],
    done:          [100, 100],
};
// How long (seconds) a stage typically takes — used to turn elapsed → progress.
// We use asymptotic easing so it always feels alive but never hits the ceiling.
const STAGE_EXPECTED_SEC = {
    queued: 2, parsing: 5, toc_detect: 15,
    tree_build: 120, image_extract: 30, analysis: 15, done: 1,
};

function stagePercent(stage, startedAt, stageMessage) {
    const band = STAGE_BAND[stage] || [0, 5];
    const [from, to] = band;
    // image_extract / tree_build embed an "X/Y" counter in the message — parse
    // for exact progress. tree_build's "X" counts node summaries, image_extract's
    // counts pages; either way the fraction is real.
    if ((stage === 'image_extract' || stage === 'tree_build') && stageMessage) {
        const m = /(\d+)\s*\/\s*(\d+)/.exec(stageMessage);
        if (m) {
            const done = parseInt(m[1], 10), total = parseInt(m[2], 10);
            if (total > 0) return from + (to - from) * (done / total);
        }
    }
    if (!startedAt) return from;
    const elapsed = Math.max(0, Date.now() / 1000 - startedAt);
    const expected = STAGE_EXPECTED_SEC[stage] || 30;
    // Ease out: reaches ~86% of the band at `expected` sec, ~95% at 2× expected.
    const ratio = 1 - Math.exp(-elapsed / expected);
    return from + (to - from) * ratio;
}

function renderDocProgress(d) {
    const stage = d.stage || (d.status === 'indexed' ? 'image_extract' : 'queued');
    const msg = d.stage_message || STAGE_LABEL[stage] || 'Traitement en cours...';
    const pct = stagePercent(stage, d.stage_started_at, d.stage_message);
    const elapsedTxt = formatElapsed(d.stage_started_at);
    return `
        <div class="doc-card-progress" data-stage="${esc(stage)}" data-started-at="${d.stage_started_at || 0}" data-stage-message="${esc(msg)}">
            <div class="doc-card-progress-text">
                <span class="stage-msg">${esc(msg)}</span>
                <span class="stage-elapsed">${elapsedTxt}</span>
            </div>
            <div class="doc-card-progress-bar">
                <div class="fill" style="width:${pct.toFixed(1)}%"></div>
            </div>
        </div>`;
}

function formatElapsed(startedAt) {
    if (!startedAt) return '';
    const secs = Math.max(0, Math.floor(Date.now() / 1000 - startedAt));
    if (secs < 60) return `${secs}s`;
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}m${s.toString().padStart(2, '0')}s`;
}

// Local-only tick: every 500ms, refresh elapsed text and progress bar width for
// every visible in-flight card. This lets the UI feel alive even when the
// backend hasn't pushed a new stage update (e.g. long LLM calls).
let _progressTickTimer = null;
function startProgressTick() {
    if (_progressTickTimer) return;
    _progressTickTimer = setInterval(() => {
        const nodes = document.querySelectorAll('.doc-card-progress');
        if (!nodes.length) {
            clearInterval(_progressTickTimer);
            _progressTickTimer = null;
            return;
        }
        for (const node of nodes) {
            const stage = node.dataset.stage;
            const startedAt = parseFloat(node.dataset.startedAt || '0');
            const msg = node.dataset.stageMessage || '';
            const elapsedEl = node.querySelector('.stage-elapsed');
            const fillEl = node.querySelector('.doc-card-progress-bar .fill');
            if (elapsedEl) elapsedEl.textContent = formatElapsed(startedAt);
            if (fillEl) {
                const pct = stagePercent(stage, startedAt, msg);
                fillEl.style.width = pct.toFixed(1) + '%';
            }
        }
    }, 500);
}

async function uploadDocument(file) {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
        showNotification('Veuillez choisir un fichier PDF', 'error'); return;
    }
    const fd = new FormData();
    fd.append('file', file);
    try {
        const r = await fetch('/api/documents/upload', { method: 'POST', body: fd });
        const d = await r.json();
        if (d.success) {
            showNotification(`"${file.name}" importé, indexation en cours...`);
            await loadLibrary();
            ensurePolling(d.document.doc_id);
        } else {
            showNotification('Échec de l\'import : ' + d.error, 'error');
        }
    } catch (e) {
        console.error('Upload error:', e);
        showNotification('Échec de l\'import', 'error');
    }
}

async function pollDocumentStatus(docId) {
    // Poll at 1s cadence while indexing. Refresh the full library only when
    // the document flips to a terminal state — otherwise just patch the card.
    const poll = async () => {
        try {
            const r = await fetch(`/api/documents/${docId}/status`);
            const d = await r.json();
            if (d.error) { _activePollers.delete(docId); return; }

            const terminal = (d.status === 'ready' || d.status === 'error');
            if (State.currentPage === 'library') {
                if (terminal) {
                    await loadLibrary();
                } else {
                    patchDocCardStatus(docId, d);
                }
            }
            if (terminal) { _activePollers.delete(docId); return; }
            setTimeout(poll, 1000);
        } catch { setTimeout(poll, 2500); }
    };
    setTimeout(poll, 800);
}

// Replace a single doc card's meta + progress in-place so the grid doesn't flicker.
function patchDocCardStatus(docId, statusData) {
    const grid = document.getElementById('libraryGrid');
    if (!grid) return;
    const cards = grid.querySelectorAll('.doc-card');
    for (const card of cards) {
        const chatBtn = card.querySelector(`[data-doc-id="${docId}"]`);
        if (!chatBtn) continue;
        // Rebuild just the progress block.
        const filenameEl = card.querySelector('.doc-card-name');
        const filename = filenameEl ? filenameEl.textContent : '';
        const fake = {
            doc_id: docId,
            filename,
            status: statusData.status,
            stage: statusData.stage,
            stage_message: statusData.stage_message,
            stage_started_at: statusData.stage_started_at,
            page_count: statusData.page_count,
        };
        const oldProgress = card.querySelector('.doc-card-progress');
        const newHtml = renderDocProgress(fake);
        if (oldProgress) {
            oldProgress.outerHTML = newHtml;
        } else {
            const footer = card.querySelector('.doc-card-footer');
            if (footer) footer.insertAdjacentHTML('beforebegin', newHtml);
        }
        break;
    }
}

async function deleteDocument(docId, filename) {
    if (!confirm(`Supprimer l'index de « ${filename} » ? Les conversations associées seront conservées mais vous ne pourrez plus poser de questions.`)) return;
    try {
        const r = await fetch(`/api/documents/${docId}`, { method: 'DELETE' });
        const d = await r.json();
        if (d.success) {
            showNotification('Document supprimé');
            State.kbChat.selectedDocIds.delete(docId);
            await loadLibrary();
        } else {
            showNotification('Échec de la suppression : ' + d.error, 'error');
        }
    } catch (e) { showNotification('Échec de la suppression', 'error'); }
}

async function retryDocument(docId) {
    await deleteDocument(docId, State.documents.find(d => d.doc_id === docId)?.filename || '');
    document.getElementById('libraryFileInput')?.click();
}

// ========================================================================
//  DOC-CHAT PAGE  (single document, multi-session)
// ========================================================================
function setupDocChatPage() {
    document.getElementById('docBackBtn')?.addEventListener('click', () => goToPage('library'));
    document.getElementById('docNewSessionBtn')?.addEventListener('click', () => startNewDocSession());
    document.getElementById('docMemoryToggle')?.addEventListener('change', e => {
        State.docChat.useMemory = e.target.checked;
    });
    document.getElementById('docChatInput')?.addEventListener('keydown', e => handleChatKeydown(e, 'doc-chat'));
    document.getElementById('docSendBtn')?.addEventListener('click', () => sendChatMessage('doc-chat'));
}

async function enterDocChat(docId) {
    State.docChat.docId = docId;
    State.docChat.activeSessionId = null;
    goToPage('doc-chat');
}

async function onEnterDocChat() {
    const docId = State.docChat.docId;
    if (!docId) { goToPage('library'); return; }

    // Load doc info
    try {
        const r = await fetch(`/api/documents/${docId}`);
        const data = await r.json();
        State.docChat.docInfo = data.document;
    } catch (e) {
        showNotification('Impossible de charger les informations du document', 'error');
        goToPage('library'); return;
    }

    // Header
    document.getElementById('docChatFilename').textContent = State.docChat.docInfo.filename;
    document.getElementById('docChatMeta').textContent =
        State.docChat.docInfo.page_count ? `${State.docChat.docInfo.page_count} pages` : '';

    // Load analysis (non-blocking)
    loadDocAnalysis(docId);

    // Load sessions
    await loadDocSessions();

    // Clear chat area, show landing (analysis)
    renderDocChatLandingOrMessages();
}

async function loadDocAnalysis(docId) {
    try {
        const r = await fetch(`/api/documents/${docId}/analysis`);
        if (r.ok) {
            const d = await r.json();
            State.docChat.analysis = d.analysis;
        } else {
            State.docChat.analysis = null;
        }
    } catch { State.docChat.analysis = null; }
    renderDocChatLandingOrMessages();
}

async function loadDocSessions() {
    const docId = State.docChat.docId;
    try {
        const r = await fetch(`/api/sessions?mode=single&doc_id=${encodeURIComponent(docId)}`);
        const data = await r.json();
        State.docChat.sessions = data.sessions || [];
    } catch { State.docChat.sessions = []; }
    renderDocSessionsList();
}

function renderDocSessionsList() {
    const list = document.getElementById('docSessionsList');
    if (!list) return;
    const sessions = State.docChat.sessions;
    if (!sessions.length) {
        list.innerHTML = '<div class="sessions-empty">Aucune conversation<br>créée automatiquement à l\'envoi d\'un message</div>';
        return;
    }
    list.innerHTML = sessions.map(s => `
        <div class="session-item ${s.session_id === State.docChat.activeSessionId ? 'active' : ''}" data-session-id="${s.session_id}">
            <div class="session-item-body">
                <div class="session-item-title">${esc(s.title || 'Nouvelle conversation')}</div>
                <div class="session-item-meta">${s.message_count || 0} msg · ${fmtTime(s.updated_at)}</div>
            </div>
            <button class="session-item-del" data-session-id="${s.session_id}" title="Supprimer">
                <i class="bi bi-trash3"></i>
            </button>
        </div>`).join('');
    list.querySelectorAll('.session-item').forEach(el => {
        el.addEventListener('click', (e) => {
            if (e.target.closest('.session-item-del')) return;
            openDocSession(el.dataset.sessionId);
        });
    });
    list.querySelectorAll('.session-item-del').forEach(el => {
        el.addEventListener('click', async (e) => {
            e.stopPropagation();
            await deleteSession(el.dataset.sessionId, 'doc');
        });
    });
}

function renderDocChatLandingOrMessages() {
    const landing = document.getElementById('docAnalysisLanding');
    const messages = document.getElementById('docChatMessages');
    if (!landing || !messages) return;
    if (State.docChat.activeSessionId) {
        landing.classList.add('hidden');
        messages.style.display = '';
    } else {
        landing.classList.remove('hidden');
        messages.innerHTML = '';
        messages.style.display = 'none';
        renderDocAnalysisLanding();
    }
}

function renderDocAnalysisLanding() {
    const el = document.getElementById('docAnalysisLanding');
    if (!el) return;
    const a = State.docChat.analysis;
    if (!a) {
        el.innerHTML = `
            <div class="analysis-landing-empty">
                <i class="bi bi-hourglass-split"></i>
                <div>Analyse intelligente du document en cours, actualisez plus tard…</div>
                <div style="margin-top:20px">
                    <button class="btn btn-sm btn-outline-primary" onclick="startNewDocSession()">
                        <i class="bi bi-chat-square-dots"></i> Démarrer la conversation
                    </button>
                </div>
            </div>`;
        return;
    }
    const findings = (a.key_findings || []).map(f => `<li>${esc(f)}</li>`).join('');
    const topics = (a.main_topics || []).map(t => `<li>${esc(t)}</li>`).join('');
    const questions = (a.suggested_questions || []).map(q =>
        `<button class="suggest-btn" data-q="${esc(q)}">${esc(q)}</button>`
    ).join('');
    el.innerHTML = `
        <div class="analysis-card-block">
            <div class="analysis-card-title-big">
                <i class="bi bi-stars"></i> Analyse intelligente du document
            </div>
            <div class="analysis-summary-text">${esc(a.summary || '')}</div>
            <div class="analysis-grid">
                ${findings ? `<div class="analysis-card"><div class="analysis-card-title"><i class="bi bi-bookmark-star"></i> Constats clés</div><ul>${findings}</ul></div>` : ''}
                ${topics ? `<div class="analysis-card"><div class="analysis-card-title"><i class="bi bi-tags"></i> Thèmes principaux</div><ul>${topics}</ul></div>` : ''}
            </div>
        </div>
        ${questions ? `
        <div class="suggest-questions-block">
            <div class="suggest-questions-title"><i class="bi bi-chat-left-quote"></i> Questions suggérées</div>
            <div class="suggest-questions">${questions}</div>
        </div>` : ''}`;
    el.querySelectorAll('.suggest-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const q = btn.dataset.q;
            const input = document.getElementById('docChatInput');
            if (input) input.value = q;
            sendChatMessage('doc-chat');
        });
    });
}

async function startNewDocSession() {
    State.docChat.activeSessionId = null;
    renderDocSessionsList();
    renderDocChatLandingOrMessages();
    document.getElementById('docChatInput')?.focus();
}

async function openDocSession(sessionId) {
    State.docChat.activeSessionId = sessionId;
    renderDocSessionsList();
    document.getElementById('docAnalysisLanding').classList.add('hidden');
    const messages = document.getElementById('docChatMessages');
    messages.style.display = '';
    messages.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-secondary)">Chargement de la conversation...</div>';
    State.socket.emit('get_history', { session_id: sessionId });
}

// ========================================================================
//  KB-CHAT PAGE
// ========================================================================
function setupKbChatPage() {
    document.getElementById('kbNewSessionBtn')?.addEventListener('click', () => startNewKbSession());
    document.getElementById('kbMemoryToggle')?.addEventListener('change', e => {
        State.kbChat.useMemory = e.target.checked;
    });
    document.getElementById('kbChatInput')?.addEventListener('keydown', e => handleChatKeydown(e, 'kb-chat'));
    document.getElementById('kbSendBtn')?.addEventListener('click', () => sendChatMessage('kb-chat'));
    document.getElementById('kbSelectAllBtn')?.addEventListener('click', () => {
        if (State.kbChat.activeSessionId) return;   // locked when session is active
        const list = State.documents.filter(d => d.status === 'ready').map(d => d.doc_id);
        State.kbChat.selectedDocIds = new Set(list);
        renderKbDocList();
        updateKbTopbar();
    });
    document.getElementById('kbClearAllBtn')?.addEventListener('click', () => {
        if (State.kbChat.activeSessionId) return;
        State.kbChat.selectedDocIds.clear();
        renderKbDocList();
        updateKbTopbar();
    });
    document.getElementById('kbDocSearch')?.addEventListener('input', e => {
        State.kbChat.docSearchKeyword = (e.target.value || '').toLowerCase();
        renderKbDocList();
    });
}

async function onEnterKbChat() {
    await loadLibrary();
    await loadKbSessions();
    renderKbDocList();
    updateKbTopbar();
    // default: nothing selected, no session
    renderKbMessagesEmpty();
}

async function loadKbSessions() {
    try {
        const r = await fetch('/api/sessions?mode=kb');
        const data = await r.json();
        State.kbChat.sessions = data.sessions || [];
    } catch { State.kbChat.sessions = []; }
    renderKbSessionsList();
}

function renderKbDocList() {
    const list = document.getElementById('kbDocList');
    if (!list) return;
    const kw = State.kbChat.docSearchKeyword;
    const readyDocs = State.documents.filter(d => d.status === 'ready');
    const shown = kw ? readyDocs.filter(d => d.filename.toLowerCase().includes(kw)) : readyDocs;

    const sessionActive = !!State.kbChat.activeSessionId;

    if (!readyDocs.length) {
        list.innerHTML = '<div style="padding:16px;text-align:center;color:rgba(255,255,255,0.4);font-size:12px">Aucun document prêt<br>Importez-en d\'abord dans la base de connaissances</div>';
        return;
    }
    if (!shown.length) {
        list.innerHTML = '<div style="padding:16px;text-align:center;color:rgba(255,255,255,0.4);font-size:12px">Aucun résultat correspondant</div>';
        return;
    }
    list.innerHTML = shown.map(d => {
        const checked = State.kbChat.selectedDocIds.has(d.doc_id);
        const pc = d.page_count ? `${d.page_count} p.` : '';
        return `
            <label class="kb-doc-item ${sessionActive ? 'disabled' : ''}" data-doc-id="${d.doc_id}">
                <input type="checkbox" ${checked ? 'checked' : ''} ${sessionActive ? 'disabled' : ''} data-doc-id="${d.doc_id}">
                <span class="kb-doc-item-name" title="${esc(d.filename)}">${esc(d.filename)}</span>
                <span class="kb-doc-item-meta">${pc}</span>
            </label>`;
    }).join('');
    list.querySelectorAll('input[type="checkbox"]').forEach(cb => {
        cb.addEventListener('change', e => {
            const id = cb.dataset.docId;
            if (cb.checked) State.kbChat.selectedDocIds.add(id);
            else State.kbChat.selectedDocIds.delete(id);
            updateKbTopbar();
        });
    });

    const totalReady = readyDocs.length;
    document.getElementById('kbSelectInfo').textContent =
        `${State.kbChat.selectedDocIds.size} / ${totalReady}`;
}

function renderKbSessionsList() {
    const list = document.getElementById('kbSessionsList');
    if (!list) return;
    if (!State.kbChat.sessions.length) {
        list.innerHTML = '<div class="sessions-empty">Aucune conversation</div>';
        return;
    }
    list.innerHTML = State.kbChat.sessions.map(s => `
        <div class="session-item ${s.session_id === State.kbChat.activeSessionId ? 'active' : ''}" data-session-id="${s.session_id}">
            <div class="session-item-body">
                <div class="session-item-title">${esc(s.title || 'Nouvelle conversation')}</div>
                <div class="session-item-meta">${(s.doc_ids || []).length} doc · ${s.message_count || 0} msg · ${fmtTime(s.updated_at)}</div>
            </div>
            <button class="session-item-del" data-session-id="${s.session_id}" title="Supprimer">
                <i class="bi bi-trash3"></i>
            </button>
        </div>`).join('');
    list.querySelectorAll('.session-item').forEach(el => {
        el.addEventListener('click', (e) => {
            if (e.target.closest('.session-item-del')) return;
            openKbSession(el.dataset.sessionId);
        });
    });
    list.querySelectorAll('.session-item-del').forEach(el => {
        el.addEventListener('click', async (e) => {
            e.stopPropagation();
            await deleteSession(el.dataset.sessionId, 'kb');
        });
    });
}

function updateKbTopbar() {
    const bar = document.getElementById('kbChatTopbar');
    if (!bar) return;
    if (State.kbChat.activeSessionId) {
        const sess = State.kbChat.sessions.find(s => s.session_id === State.kbChat.activeSessionId);
        if (!sess) { bar.innerHTML = ''; return; }
        const docNames = (sess.doc_ids || []).map(did => {
            const d = State.documents.find(x => x.doc_id === did);
            return d ? { name: d.filename, ok: d.status === 'ready' } : { name: did, ok: false };
        });
        const chips = docNames.map(x =>
            `<span class="active-chip ${x.ok ? '' : 'disabled'}" title="${x.ok ? '' : 'Document supprimé'}">
                <i class="bi bi-file-earmark-pdf"></i>${esc(x.name)}
            </span>`).join('');
        bar.innerHTML = `<i class="bi bi-chat-square-dots"></i> Conversation en cours : ${chips}`;
    } else {
        const count = State.kbChat.selectedDocIds.size;
        if (count === 0) {
            bar.innerHTML = `<i class="bi bi-info-circle"></i> Sélectionnez au moins un document à gauche, ou cliquez sur « Nouvelle conversation »`;
        } else {
            bar.innerHTML = `<i class="bi bi-check-circle"></i> <strong style="margin:0 4px;color:var(--primary)">${count}</strong> document(s) sélectionné(s) ; envoyez un message pour démarrer une nouvelle conversation`;
        }
    }
}

function startNewKbSession() {
    State.kbChat.activeSessionId = null;
    renderKbSessionsList();
    renderKbDocList();
    renderKbMessagesEmpty();
    updateKbTopbar();
    document.getElementById('kbChatInput')?.focus();
}

function renderKbMessagesEmpty() {
    const mc = document.getElementById('kbChatMessages');
    if (!mc) return;
    mc.innerHTML = `
        <div class="empty-landing">
            <div class="empty-hero-icon"><i class="bi bi-chat-square-dots"></i></div>
            <h4>Questions-réponses</h4>
            <p>Cochez à gauche les documents à inclure : l'Agent recherche, compare et synthétise sa réponse à partir de plusieurs documents.</p>
        </div>`;
}

async function openKbSession(sessionId) {
    State.kbChat.activeSessionId = sessionId;
    const sess = State.kbChat.sessions.find(s => s.session_id === sessionId);
    if (sess) {
        State.kbChat.selectedDocIds = new Set(sess.doc_ids || []);
    }
    renderKbSessionsList();
    renderKbDocList();
    updateKbTopbar();
    const mc = document.getElementById('kbChatMessages');
    mc.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-secondary)">Chargement de la conversation...</div>';
    State.socket.emit('get_history', { session_id: sessionId });
}

// ========================================================================
//  Session CRUD
// ========================================================================
async function createSession(mode, docIds, title) {
    const r = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, doc_ids: docIds, title })
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || 'Session create failed');
    return d.session;
}

async function updateSessionTitle(sessionId, title) {
    try {
        await fetch(`/api/sessions/${sessionId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title })
        });
    } catch (e) { console.warn('update session title failed', e); }
}

async function deleteSession(sessionId, scope) {
    if (!confirm('Supprimer cette conversation ?')) return;
    try {
        const r = await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' });
        const d = await r.json();
        if (!d.success) throw new Error(d.error || 'delete failed');
        if (scope === 'doc') {
            if (State.docChat.activeSessionId === sessionId) {
                State.docChat.activeSessionId = null;
                renderDocChatLandingOrMessages();
            }
            await loadDocSessions();
        } else {
            if (State.kbChat.activeSessionId === sessionId) {
                State.kbChat.activeSessionId = null;
                renderKbMessagesEmpty();
                updateKbTopbar();
            }
            await loadKbSessions();
            renderKbDocList();
        }
        showNotification('Conversation supprimée');
    } catch (e) {
        showNotification('Échec de la suppression : ' + e.message, 'error');
    }
}

// ========================================================================
//  Chat sending (unified for both doc-chat & kb-chat)
// ========================================================================
function handleChatKeydown(e, page) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!State.isStreaming) sendChatMessage(page);
    }
}

async function sendChatMessage(page) {
    const ui = page === 'doc-chat' ? {
        input: document.getElementById('docChatInput'),
        messages: document.getElementById('docChatMessages'),
    } : {
        input: document.getElementById('kbChatInput'),
        messages: document.getElementById('kbChatMessages'),
    };

    const text = (ui.input?.value || '').trim();
    if (!text || State.isStreaming) return;

    // Ensure a session exists (lazy-create)
    let sessionId;
    if (page === 'doc-chat') {
        if (!State.docChat.activeSessionId) {
            try {
                const s = await createSession('single', [State.docChat.docId], truncateTitle(text));
                State.docChat.activeSessionId = s.session_id;
                await loadDocSessions();
            } catch (e) {
                showNotification('Échec de la création de la conversation : ' + e.message, 'error'); return;
            }
        }
        sessionId = State.docChat.activeSessionId;
        // First-time: hide landing, show messages area
        document.getElementById('docAnalysisLanding').classList.add('hidden');
        ui.messages.style.display = '';
        if (ui.messages.innerHTML.trim() === '') ui.messages.innerHTML = '';
    } else {
        if (!State.kbChat.activeSessionId) {
            const docIds = [...State.kbChat.selectedDocIds];
            if (!docIds.length) {
                showNotification('Veuillez sélectionner au moins un document', 'error'); return;
            }
            try {
                const s = await createSession('kb', docIds, truncateTitle(text));
                State.kbChat.activeSessionId = s.session_id;
                await loadKbSessions();
                renderKbDocList();
                updateKbTopbar();
            } catch (e) {
                showNotification('Échec de la création de la conversation : ' + e.message, 'error'); return;
            }
        }
        sessionId = State.kbChat.activeSessionId;
        if (ui.messages.innerHTML.includes('empty-landing')) ui.messages.innerHTML = '';
    }

    ui.input.value = '';
    sendChatQuery(page, sessionId, text, { appendUserBubble: true });
}

/**
 * Low-level send: fires the agent_chat socket event for ``text`` against
 * ``sessionId`` and wires up the streaming UI. Does NOT create a session
 * or validate document selection — callers are responsible for that.
 *
 * ``appendUserBubble`` controls whether a user bubble is added to the DOM
 * before streaming starts:
 *   - true  (normal send): yes, as always.
 *   - false (regenerate / edit-resend): no — the user bubble is already
 *     in the DOM (or will be restored by a subsequent history refresh).
 */
function sendChatQuery(page, sessionId, text, opts) {
    opts = opts || {};
    const ui = page === 'doc-chat' ? {
        messages: document.getElementById('docChatMessages'),
    } : {
        messages: document.getElementById('kbChatMessages'),
    };
    if (!ui.messages) return;

    if (opts.appendUserBubble !== false) {
        addUserMessage(ui.messages, text);
    }
    showTypingIndicator(ui.messages);
    State.isStreaming = true;
    State.streamingNodes = [];
    updateSendButton();

    const payload = {
        session_id: sessionId,
        query: text,
        model_type: State.modelType,
        use_memory: page === 'doc-chat' ? State.docChat.useMemory : State.kbChat.useMemory,
    };

    // All modes (text & vision) use the same streaming agent path.
    State.socket.emit('agent_chat', payload);
}

/**
 * Regenerate the latest assistant answer.
 *
 * Strategy: truncate the session to just before the last non-superseded
 * assistant turn (which keeps the user's question at the tail), then
 * replay that question via ``sendChatQuery``. The history refresh on
 * stream completion restores the correct DOM state.
 */
async function regenerateLastAnswer() {
    if (State.isStreaming) return;
    const page = State.currentPage;
    const sessionId = page === 'doc-chat'
        ? State.docChat.activeSessionId
        : State.kbChat.activeSessionId;
    if (!sessionId) return;

    try {
        const r = await fetch(`/api/sessions/${sessionId}`);
        const d = await r.json();
        const msgs = (d.session && d.session.messages) || [];
        // Find the last user message — we want to keep it and drop
        // everything after (including any superseded drafts that followed).
        let lastUserIdx = -1;
        for (let i = msgs.length - 1; i >= 0; i--) {
            if (msgs[i].role === 'user') { lastUserIdx = i; break; }
        }
        if (lastUserIdx < 0) return;
        const userText = msgs[lastUserIdx].content || '';
        // Truncate right AFTER the last user message — keep it, drop replies.
        await fetch(`/api/sessions/${sessionId}/truncate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ index: lastUserIdx + 1 }),
        });
        // Redraw the chat locally from the truncated slice BEFORE firing the
        // new query. Doing it synchronously (from the fetched data) avoids
        // the flicker we'd get by waiting on an async get_history round-trip
        // and prevents the typing indicator from being wiped mid-stream.
        const ui = page === 'doc-chat'
            ? { messages: document.getElementById('docChatMessages') }
            : { messages: document.getElementById('kbChatMessages') };
        if (ui.messages) {
            const kept = msgs.slice(0, lastUserIdx + 1);
            ui.messages.innerHTML = '';
            // No assistant in the kept slice, so no message gets the
            // regenerate button yet; the history refresh on stream
            // completion will attach it to the new answer.
            kept.forEach((m, idx) => appendHistoryMessage(ui.messages, m, {
                index: idx, isLastAssistant: false,
            }));
        }
        sendChatQuery(page, sessionId, userText, { appendUserBubble: false });
    } catch (e) {
        showNotification('Échec de la régénération : ' + e.message, 'error');
    }
}

/**
 * In-place edit of the user message at ``index``:
 *   1. Swap the bubble's content for a textarea + Save/Cancel controls.
 *   2. On Save: truncate session at ``index``, synchronously redraw the
 *      preserved prefix, then fire a fresh ``agent_chat`` with the edited
 *      text. (The history refresh on stream completion puts buttons back.)
 *   3. On Cancel: restore the original rendered bubble, no server changes.
 *
 * We intentionally do NOT route editing through the bottom input box —
 * users expect the familiar ChatGPT / Claude behaviour where edits happen
 * on the message itself.
 */
async function startEditUserMessage(index) {
    if (State.isStreaming) return;
    const page = State.currentPage;
    const sessionId = page === 'doc-chat'
        ? State.docChat.activeSessionId
        : State.kbChat.activeSessionId;
    if (!sessionId) return;
    const msgsEl = page === 'doc-chat'
        ? document.getElementById('docChatMessages')
        : document.getElementById('kbChatMessages');
    if (!msgsEl) return;
    const bubble = msgsEl.querySelector(`.message-user[data-index="${index}"]`);
    if (!bubble || bubble.classList.contains('editing')) return;

    // Snapshot original HTML so Cancel can restore it verbatim (preserves
    // the action button, escaping, etc. — cheaper than re-rendering).
    const originalHtml = bubble.innerHTML;
    const contentEl = bubble.querySelector('.message-content');
    const originalText = contentEl ? (contentEl.textContent || '') : '';

    bubble.classList.add('editing');
    bubble.innerHTML = `
        <div class="message-edit-box">
            <textarea class="message-edit-textarea" rows="3">${esc(originalText)}</textarea>
            <div class="message-edit-actions">
                <button class="btn-edit-cancel" type="button">Annuler</button>
                <button class="btn-edit-send" type="button">
                    <i class="bi bi-send"></i> Envoyer
                </button>
            </div>
        </div>
    `;
    const ta = bubble.querySelector('.message-edit-textarea');
    const cancelBtn = bubble.querySelector('.btn-edit-cancel');
    const sendBtn = bubble.querySelector('.btn-edit-send');
    // Auto-grow up to a sensible max so long edits stay usable.
    const autoGrow = () => {
        ta.style.height = 'auto';
        ta.style.height = Math.min(ta.scrollHeight, 320) + 'px';
    };
    ta.addEventListener('input', autoGrow);
    ta.focus();
    try { ta.setSelectionRange(ta.value.length, ta.value.length); } catch (_) {}
    autoGrow();

    const restore = () => {
        bubble.classList.remove('editing');
        bubble.innerHTML = originalHtml;
    };
    cancelBtn.addEventListener('click', restore);
    ta.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') { e.preventDefault(); restore(); }
        // Ctrl/Cmd+Enter to submit (plain Enter inserts newline — users
        // frequently edit multi-line prompts).
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            sendBtn.click();
        }
    });

    sendBtn.addEventListener('click', async () => {
        const newText = (ta.value || '').trim();
        if (!newText) return;
        if (State.isStreaming) return;
        sendBtn.disabled = true;
        cancelBtn.disabled = true;

        try {
            // Truncate server-side from ``index`` (inclusive): the old user
            // message and every reply after it are dropped. The freshly
            // submitted query will be appended as a brand-new turn.
            await fetch(`/api/sessions/${sessionId}/truncate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ index }),
            });
            // Redraw the preserved prefix in place so the screen keeps
            // showing earlier history (instead of going blank). We pull
            // fresh messages to be sure about what survived.
            const r = await fetch(`/api/sessions/${sessionId}`);
            const d = await r.json();
            const kept = ((d.session && d.session.messages) || []);
            msgsEl.innerHTML = '';
            kept.forEach((m, i) => appendHistoryMessage(msgsEl, m, {
                index: i, isLastAssistant: false,
            }));
            // Now fire the edited query; sendChatQuery adds the new user
            // bubble + typing indicator and streams the answer.
            sendChatQuery(page, sessionId, newText, { appendUserBubble: true });
        } catch (e) {
            showNotification('Échec du renvoi : ' + e.message, 'error');
            restore();
        }
    });
}

function truncateTitle(text) {
    return text.length > 30 ? text.slice(0, 28) + '…' : text;
}

function stopGenerating() {
    if (State.isStreaming) State.socket.emit('stop_generating');
}

function updateSendButton() {
    const page = State.currentPage;
    const btnId = page === 'doc-chat' ? 'docSendBtn' : 'kbSendBtn';
    const btn = document.getElementById(btnId);
    if (!btn) return;
    if (State.isStreaming) {
        btn.innerHTML = '<i class="bi bi-stop-fill"></i>';
        btn.classList.add('stop-mode');
        btn.onclick = stopGenerating;
    } else {
        btn.innerHTML = '<i class="bi bi-send"></i>';
        btn.classList.remove('stop-mode');
        btn.onclick = () => sendChatMessage(page);
    }
    // Flag the message container so CSS can hide hover actions (edit /
    // regenerate) during generation — prevents accidental re-entry.
    ['docChatMessages', 'kbChatMessages'].forEach(id => {
        const box = document.getElementById(id);
        if (!box) return;
        box.classList.toggle('streaming', State.isStreaming);
    });
}

// ========================================================================
//  Streaming event handlers
// ========================================================================
function onStreamStatus(status) {
    const msgs = activeChatUI()?.messages;
    if (!msgs) return;
    if (status === 'retry_answering') {
        // Phase 4 retry: finalize the low-score draft as its own bubble
        // (strip streaming ids so subsequent chunks create a NEW responseBox)
        // and reset the streaming text buffer. The reflect-box + extra-search steps
        // that follow will naturally sit between the two assistant bubbles.
        State.streamingRawText = '';
        ['responseBox', 'responseContent', 'thinkingBox', 'agentTimeline', 'agentSteps'].forEach(id => {
            msgs.querySelector('#' + id)?.removeAttribute('id');
        });
    }
    const ti = msgs.querySelector('.typing-indicator');
    const st = ti?.querySelector('.status-text');
    if (st) st.textContent = {
        preparing: 'Préparation des données du document...',
        prepared: 'Préparation terminée',
        searching: 'Recherche du contenu pertinent...',
        answering: 'Génération de la réponse...',
        retrying: 'L\'Agent complète sa recherche...',
        retry_answering: 'Régénération de la réponse...',
    }[status] || '';
}

function onStreamThinking(content) {
    const msgs = activeChatUI()?.messages; if (!msgs) return;
    let b = msgs.querySelector('#thinkingBox');
    if (!b) {
        const ti = msgs.querySelector('.typing-indicator');
        b = document.createElement('div');
        b.className = 'thinking-box';
        b.id = 'thinkingBox';
        b.innerHTML = '<strong>Raisonnement</strong><span class="thinking-content"></span>';
        if (ti) ti.before(b); else msgs.appendChild(b);
    }
    const tc = b.querySelector('.thinking-content');
    if (tc) { tc.textContent += content; scrollChatToBottom(); }
}

function onStreamNodes(nodes) {
    State.streamingNodes = nodes || [];   // remembered so we can link inline citations on done
    const msgs = activeChatUI()?.messages; if (!msgs) return;
    const anchor = msgs.querySelector('#thinkingBox') || msgs.querySelector('#agentTimeline');
    if (!anchor) return;
    const fallbackDoc = State.docChat.docId;   // single-doc fallback
    anchor.insertAdjacentHTML('afterend', renderNodesGrouped(nodes, fallbackDoc));
}

// Split "doc_id::node_id" or plain "node_id" into parts.
// Returns { docId, nodeId, label } where label is what the user sees on the tag.
function parseNodeRef(ref, fallbackDocId) {
    if (typeof ref !== 'string') return { docId: fallbackDocId || '', nodeId: String(ref || ''), label: String(ref || '') };
    const idx = ref.indexOf('::');
    if (idx > 0) {
        return {
            docId: ref.slice(0, idx),
            nodeId: ref.slice(idx + 2),
            // In multi-doc (kb) mode show docId:nodeId; in single mode just nodeId.
            label: fallbackDocId && ref.startsWith(fallbackDocId + '::') ? ref.slice(idx + 2) : ref.slice(idx + 2),
        };
    }
    return { docId: fallbackDocId || '', nodeId: ref, label: ref };
}

// Build a { nodeId -> docId } lookup from a list of (possibly qualified)
// node refs. Used to resolve which document an inline citation belongs to
// when linkifying the answer text (essential in multi-doc / kb mode).
function buildNodeDocMap(nodes, fallbackDocId) {
    const map = {};
    for (const ref of (nodes || [])) {
        const { docId, nodeId } = parseNodeRef(ref, fallbackDocId);
        if (nodeId && !(nodeId in map)) map[nodeId] = docId || fallbackDocId || '';
    }
    return map;
}

// Turn inline citations the model wrote as plain text into clickable elements:
//   (node_0007, page 3)                    → badge numéroté [1]
//   (doc: rapport.pdf, node_0007, page 3)  → badge numéroté (mode multi-docs ;
//       tolère un id nu : "(doc: rapport.pdf, 1, page 5)")
//   node_0007 seul                         → badge numéroté
//   (page 12) / (pages 5-6) seul           → lien de page ouvrant la visionneuse
// The same node always gets the same number within one message. Walks text nodes
// so Markdown/HTML/KaTeX structure is preserved; skips code, links, math and tags
// we've already produced.
const CITE_RE = /node_[A-Za-z0-9_.\-]+|\(\s*doc\s*:|\(\s*(?:pages?|p\.)\s*\d/i;
function linkifyCitations(container, nodeDocMap, fallbackDocId) {
    if (!container) return;
    const SKIP = new Set(['CODE', 'PRE', 'A', 'BUTTON']);
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, {
        acceptNode(node) {
            if (!node.nodeValue || !CITE_RE.test(node.nodeValue)) return NodeFilter.FILTER_REJECT;
            for (let p = node.parentElement; p && p !== container; p = p.parentElement) {
                if (SKIP.has(p.tagName) || p.classList.contains('katex')
                    || p.classList.contains('cite-link')) {
                    return NodeFilter.FILTER_REJECT;
                }
            }
            return NodeFilter.FILTER_ACCEPT;
        },
    });
    const targets = [];
    let t;
    while ((t = walker.nextNode())) targets.push(t);

    const numbering = new Map();   // "docId::nodeId" -> citation number (per message)

    // Resolve a doc id from the filename written in a "(doc: …)" citation.
    const docIdByName = (name) => {
        const n = (name || '').trim().toLowerCase();
        const hit = (State.documents || []).find(d => (d.filename || '').toLowerCase() === n);
        return hit ? hit.doc_id : '';
    };
    // Page-only references ("(pages 5-6)") can only link when the target
    // document is unambiguous: explicit fallback, a single doc in [NODES],
    // or — last resort — a single doc named by "(doc: …)" citations in the
    // same message (covers answers whose node list wasn't persisted).
    let pageDocId = fallbackDocId || '';
    if (!pageDocId) {
        const ids = [...new Set(Object.values(nodeDocMap || {}).filter(Boolean))];
        if (ids.length === 1) pageDocId = ids[0];
    }
    if (!pageDocId) {
        const named = new Set();
        for (const dm of (container.textContent || '').matchAll(/\(\s*doc\s*:\s*([^,()]+)/gi)) {
            const did = docIdByName(dm[1]);
            if (did) named.add(did);
        }
        if (named.size === 1) pageDocId = [...named][0];
    }

    for (const textNode of targets) {
        const s = textNode.nodeValue;
        // 1-3: (doc: <fichier>, [node_]<id>[, page N]) — kb mode, id nu toléré
        // 4-5: (node_<id>[, page N])
        // 6:   node_<id> nu
        // 7:   (page N) / (pages N-M) seul
        // Ids must end on an alphanumeric so a sentence-final "node_0001." keeps
        // its period as prose text.
        const ID = 'node_[A-Za-z0-9_.\\-]*[A-Za-z0-9]';
        const re = new RegExp(
            '\\(\\s*doc\\s*:\\s*([^,()]+?)\\s*,\\s*(' + ID + '|(?:node[_\\s]*)?\\d{1,4})\\s*(?:,\\s*((?:pages?|p\\.)[^)]*?))?\\s*\\)'
            + '|\\(\\s*(' + ID + ')\\s*(?:,\\s*((?:pages?|p\\.)[^)]*?))?\\s*\\)'
            + '|(' + ID + ')'
            + '|\\(\\s*((?:pages?|p\\.)\\s*\\d+(?:\\s*[-–‑—]\\s*\\d+)?)\\s*\\)',
            'gi');
        const frag = document.createDocumentFragment();
        let last = 0, m;
        while ((m = re.exec(s))) {
            if (m.index > last) frag.appendChild(document.createTextNode(s.slice(last, m.index)));
            last = m.index + m[0].length;

            if (m[7]) {
                // Page-only reference → link straight to that page in the viewer.
                if (pageDocId) {
                    const page = parseInt(m[7].match(/\d+/)[0], 10);
                    const span = document.createElement('span');
                    span.className = 'cite-link cite-page';
                    span.textContent = m[7];
                    span.title = 'Voir cette page dans le document';
                    span.addEventListener('click', (e) => { e.stopPropagation(); showPageRef(pageDocId, page); });
                    frag.appendChild(document.createTextNode('('));
                    frag.appendChild(span);
                    frag.appendChild(document.createTextNode(')'));
                } else {
                    frag.appendChild(document.createTextNode(m[0]));
                }
                continue;
            }

            const rawId = m[2] || m[4] || m[6];
            const pageInfo = (m[3] || m[5] || '').trim();
            // Normalise "node_0004" / "node 4" / "4" → key used by [NODES] ("0004").
            const bareId = rawId.replace(/^node[_\s]*/i, '');
            const paddedId = /^\d+$/.test(bareId) ? bareId.padStart(4, '0') : bareId;
            const docId = (m[1] ? docIdByName(m[1]) : '')
                || (nodeDocMap && (nodeDocMap[rawId] || nodeDocMap[bareId] || nodeDocMap[paddedId]))
                || fallbackDocId || '';
            const key = docId + '::' + paddedId;
            if (!numbering.has(key)) numbering.set(key, numbering.size + 1);
            const span = document.createElement('span');
            span.className = 'cite-link cite-num';
            span.textContent = numbering.get(key);
            span.title = (m[1] ? m[1].trim() + ' · ' : '') + 'node_' + paddedId
                + (pageInfo ? ' · ' + pageInfo : '') + ' — voir la source';
            // Jump to the precise page cited, not just the node's first page.
            const pageMatch = pageInfo.match(/\d+/);
            const citedPage = pageMatch ? parseInt(pageMatch[0], 10) : null;
            span.addEventListener('click', (e) => { e.stopPropagation(); showNodePreview(paddedId, docId, citedPage); });
            frag.appendChild(span);
        }
        if (last < s.length) frag.appendChild(document.createTextNode(s.slice(last)));
        textNode.parentNode.replaceChild(frag, textNode);
    }
}

// Group retrieved node refs by their source document and render one line per
// document, so the user can see at a glance which file each node comes from
// (especially useful in kb / multi-doc mode).
function renderNodesGrouped(nodes, fallbackDocId) {
    if (!nodes || !nodes.length) return '';
    const groups = new Map();   // docId -> [{nodeId, label}]
    const orderedKeys = [];
    for (const n of nodes) {
        const { docId, nodeId, label } = parseNodeRef(n, fallbackDocId);
        const key = docId || '';
        if (!groups.has(key)) { groups.set(key, []); orderedKeys.push(key); }
        groups.get(key).push({ nodeId, label, docId });
    }
    const rows = orderedKeys.map(key => {
        const items = groups.get(key);
        const docInfo = key ? (State.documents || []).find(x => x.doc_id === key) : null;
        const name = docInfo ? docInfo.filename : (key || 'Document inconnu');
        const tags = items.map(it => (
            `<span class="node-tag" onclick="showNodePreview('${esc(it.nodeId)}', '${esc(it.docId || '')}')">${esc(it.label)}</span>`
        )).join(' ');
        return `<div class="nodes-row"><span class="nodes-doc-name" title="${esc(name)}">${esc(name)}</span><span class="nodes-row-tags">${tags}</span></div>`;
    }).join('');
    return `<div class="nodes-box"><strong>Nœuds récupérés</strong>${rows}</div>`;
}

function onStreamChunk(content) {
    const msgs = activeChatUI()?.messages; if (!msgs) return;
    let rc = msgs.querySelector('#responseContent');
    if (!rc) {
        State.streamingRawText = '';
        msgs.querySelector('.typing-indicator')?.remove();
        const box = document.createElement('div');
        box.className = 'message message-assistant';
        box.id = 'responseBox';
        box.innerHTML = '<div class="message-content" id="responseContent"></div>';
        msgs.appendChild(box);
        rc = msgs.querySelector('#responseContent');
    }
    State.streamingRawText += content;
    rc.innerHTML = renderMarkdown(State.streamingRawText);
    renderMathInContainer(rc);
    scrollChatToBottom();
}

function onStreamFullResponse(content) {
    const msgs = activeChatUI()?.messages; if (!msgs) return;
    msgs.querySelector('.typing-indicator')?.remove();
    const box = document.createElement('div');
    box.className = 'message message-assistant';
    box.innerHTML = `<div class="message-content">${renderMarkdown(content)}</div>`;
    msgs.appendChild(box);
    const contentEl = box.querySelector('.message-content');
    renderMathInContainer(contentEl);
    linkifyCitations(contentEl, buildNodeDocMap(State.streamingNodes, State.docChat.docId), State.docChat.docId);
    scrollChatToBottom();
}

function onStreamDone(wasStopped) {
    State.isStreaming = false;
    updateSendButton();
    const msgs = activeChatUI()?.messages;
    if (msgs) {
        msgs.querySelector('.typing-indicator')?.remove();
        const rc = msgs.querySelector('#responseContent');
        if (rc && State.streamingRawText) {
            const finalText = wasStopped ? State.streamingRawText + '\n\n---\n*(génération interrompue)*' : State.streamingRawText;
            rc.innerHTML = renderMarkdown(finalText);
            renderMathInContainer(rc);
            linkifyCitations(rc, buildNodeDocMap(State.streamingNodes, State.docChat.docId), State.docChat.docId);
        }
        ['responseBox', 'responseContent', 'thinkingBox', 'agentTimeline', 'agentSteps'].forEach(id => {
            msgs.querySelector('#' + id)?.removeAttribute('id');
        });
    }
    State.streamingRawText = '';
    // Refresh session list (message_count / updated_at)
    if (State.currentPage === 'doc-chat') loadDocSessions();
    if (State.currentPage === 'kb-chat') loadKbSessions();
    // Re-fetch full history so we can (a) render the correct "regenerate"
    // button on the freshly completed assistant reply only, and (b) drop
    // any stale buttons from earlier turns. The redraw happens in-place
    // and is visually near-instant for static content.
    const refreshedSessionId = State.currentPage === 'doc-chat'
        ? State.docChat.activeSessionId
        : State.kbChat.activeSessionId;
    if (refreshedSessionId && State.socket) {
        State.socket.emit('get_history', { session_id: refreshedSessionId });
    }
}

function onStreamError(msg) {
    State.isStreaming = false; updateSendButton();
    const msgs = activeChatUI()?.messages;
    if (msgs) {
        msgs.querySelector('.typing-indicator')?.remove();
        addSystemMessage(msgs, 'Erreur : ' + msg);
    }
}

// ========================================================================
//  Agent UI
// ========================================================================
function getOrCreateTimeline(msgs) {
    let tl = msgs.querySelector('#agentTimeline');
    if (!tl) {
        const ti = msgs.querySelector('.typing-indicator');
        tl = document.createElement('div');
        tl.className = 'agent-timeline'; tl.id = 'agentTimeline';
        tl.innerHTML = '<div class="agent-timeline-header"><i class="bi bi-robot"></i> Raisonnement de l\'Agent</div><div id="agentSteps"></div>';
        if (ti) ti.before(tl); else msgs.appendChild(tl);
    }
    return tl;
}

function onAgentStep(d) {
    const msgs = activeChatUI()?.messages; if (!msgs) return;
    getOrCreateTimeline(msgs);
    const sc = msgs.querySelector('#agentSteps'); if (!sc) return;
    const tool = d.tool === 'final_answer' ? 'Préparation de la réponse' : (d.tool || '');
    const docChip = d.doc_id ? `<span class="step-doc-chip"><i class="bi bi-file-earmark"></i> ${esc(docFilenameShort(d.doc_id))}</span>` : '';
    const div = document.createElement('div');
    div.className = 'agent-step';
    div.innerHTML = `
        <div class="step-header">
            <span class="step-number">Step ${d.step || ''}</span>
            <span class="step-tool">${esc(tool)}</span>
            ${docChip}
        </div>
        ${d.thought ? `<div class="step-thought">${esc(d.thought)}</div>` : ''}
        ${d.observation ? `<div class="step-observation">${esc(d.observation)}</div>` : ''}`;
    sc.appendChild(div);
    scrollChatToBottom();
}

function docFilenameShort(docId) {
    const d = State.documents.find(x => x.doc_id === docId);
    if (!d) return docId;
    const fn = d.filename;
    return fn.length > 20 ? fn.slice(0, 18) + '…' : fn;
}

function onAgentDecompose(d) {
    if (!d.needs_decomposition) return;
    const msgs = activeChatUI()?.messages; if (!msgs) return;
    const ti = msgs.querySelector('.typing-indicator');
    const box = document.createElement('div');
    box.className = 'decompose-box';
    const qs = (d.sub_questions || []).map((q, i) => `<div class="sub-question">${i + 1}. ${esc(q)}</div>`).join('');
    box.innerHTML = `<strong><i class="bi bi-diagram-3"></i> Décomposition de la question (${esc(d.synthesis_strategy || 'direct')})</strong>${qs}`;
    if (ti) ti.before(box); else msgs.appendChild(box);
    scrollChatToBottom();
}

function onAgentReflect(d) {
    const msgs = activeChatUI()?.messages; if (!msgs) return;
    const box = document.createElement('div');
    box.className = 'reflect-box';
    const s = d.score || 0;
    const cls = s < 6 ? 'poor' : s < 8 ? 'medium' : 'good';
    const action = d.action === 'accept' ? 'Qualité de la réponse satisfaisante' : 'Recherche complémentaire en cours...';
    const icon = d.action === 'accept' ? 'bi-check-circle-fill' : 'bi-arrow-repeat';
    const issues = (d.issues || []).map(i => `<li>${esc(i)}</li>`).join('');
    box.innerHTML = `<strong><i class="bi bi-shield-check"></i> Auto-vérification</strong>
        <span class="reflect-score ${cls}">${s}/10</span>
        <span><i class="bi ${icon}"></i> ${action}</span>
        ${issues ? `<ul style="margin-top:6px;padding-left:18px;font-size:12px;color:#64748b">${issues}</ul>` : ''}`;
    msgs.appendChild(box);
    scrollChatToBottom();
}

// ========================================================================
//  History / Messages
// ========================================================================
function addUserMessage(msgs, content) {
    const d = document.createElement('div');
    d.className = 'message message-user';
    d.innerHTML = `<div class="message-content">${esc(content)}</div>`;
    msgs.appendChild(d);
    scrollChatToBottom();
}

function addSystemMessage(msgs, content) {
    const d = document.createElement('div');
    d.className = 'message message-assistant';
    d.innerHTML = `<div class="message-content" style="background:#fef3c7;color:#92400e"><i class="bi bi-info-circle"></i> ${esc(content)}</div>`;
    msgs.appendChild(d); scrollChatToBottom();
}

function showTypingIndicator(msgs) {
    const ti = document.createElement('div');
    ti.className = 'typing-indicator';
    ti.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span><span class="status-text" style="margin-left:10px;font-size:14px;color:#64748b"></span>';
    msgs.appendChild(ti); scrollChatToBottom();
}

function onHistoryReceived(data) {
    const msgs = activeChatUI()?.messages;
    if (!msgs) return;
    msgs.innerHTML = '';
    const history = data.history || [];
    if (!history.length) {
        addSystemMessage(msgs, 'Nouvelle conversation, posez votre question !');
        return;
    }
    // Precompute the index of the most recent non-superseded assistant
    // message so only that one gets a "Regenerate" button (per product
    // decision: regenerate only applies to the latest answer).
    let lastAssistantIdx = -1;
    for (let i = history.length - 1; i >= 0; i--) {
        if (history[i].role === 'assistant' && !history[i].superseded) {
            lastAssistantIdx = i;
            break;
        }
    }
    history.forEach((m, idx) => appendHistoryMessage(msgs, m, {
        index: idx,
        isLastAssistant: idx === lastAssistantIdx,
    }));
    scrollChatToBottom();
}

function appendHistoryMessage(msgs, m, ctx) {
    ctx = ctx || {};
    if (m.thinking) {
        const steps = parseAgentSteps(m.thinking);
        if (steps.length > 0) {
            const tl = document.createElement('div');
            tl.className = 'agent-timeline';
            tl.innerHTML = '<div class="agent-timeline-header"><i class="bi bi-robot"></i> Raisonnement de l\'Agent</div>';
            const sc = document.createElement('div');
            steps.forEach(s => {
                const tool = s.tool === 'final_answer' ? 'Préparation de la réponse' : s.tool;
                const div = document.createElement('div');
                div.className = 'agent-step';
                const docChip = s.doc_id ? `<span class="step-doc-chip"><i class="bi bi-file-earmark"></i> ${esc(docFilenameShort(s.doc_id))}</span>` : '';
                div.innerHTML = `
                    <div class="step-header">
                        <span class="step-number">Step ${s.step}</span>
                        <span class="step-tool">${esc(tool)}</span>
                        ${docChip}
                    </div>
                    <div class="step-thought">${esc(s.thought)}</div>`;
                sc.appendChild(div);
            });
            tl.appendChild(sc);
            msgs.appendChild(tl);
        } else {
            const tb = document.createElement('div');
            tb.className = 'thinking-box';
            tb.innerHTML = `<strong>Raisonnement</strong><span class="thinking-content">${esc(m.thinking)}</span>`;
            msgs.appendChild(tb);
        }
    }
    if (m.nodes?.length > 0) {
        const primaryDoc = State.docChat.docId;
        const wrap = document.createElement('div');
        wrap.innerHTML = renderNodesGrouped(m.nodes, primaryDoc);
        const nb = wrap.firstElementChild;
        if (nb) msgs.appendChild(nb);
    }
    const div = document.createElement('div');
    div.className = `message message-${m.role}${m.superseded ? ' message-superseded' : ''}`;
    if (typeof ctx.index === 'number') div.dataset.index = String(ctx.index);
    const rendered = m.role === 'assistant' ? renderMarkdown(m.content) : esc(m.content);
    const supersededBadge = m.superseded
        ? '<div class="superseded-badge"><i class="bi bi-arrow-repeat"></i> Révisée après réflexion (réponse finale ci-dessous)</div>'
        : '';
    // Hover actions: edit any user message, regenerate only the newest
    // assistant reply. Superseded drafts never get actions (they're frozen
    // history). Buttons are disabled via CSS during streaming.
    let actionsHtml = '';
    if (m.role === 'user') {
        actionsHtml = `<div class="message-actions">
            <button class="msg-action-btn" title="Modifier et renvoyer"
                onclick="startEditUserMessage(${ctx.index})">
                <i class="bi bi-pencil"></i>
            </button>
        </div>`;
    } else if (m.role === 'assistant' && !m.superseded && ctx.isLastAssistant) {
        actionsHtml = `<div class="message-actions">
            <button class="msg-action-btn" title="Régénérer"
                onclick="regenerateLastAnswer()">
                <i class="bi bi-arrow-clockwise"></i>
            </button>
        </div>`;
    }
    div.innerHTML = `${supersededBadge}<div class="message-content">${rendered}</div>${actionsHtml}`;
    msgs.appendChild(div);
    if (m.role === 'assistant') {
        const contentEl = div.querySelector('.message-content');
        renderMathInContainer(contentEl);
        linkifyCitations(contentEl, buildNodeDocMap(m.nodes, State.docChat.docId), State.docChat.docId);
    }
}

function parseAgentSteps(thinking) {
    const regex = /^Step\s+(\d+)\s+\[([^\]]+)\](?:\s*\(doc:\s*([^)]+)\))?:\s*(.+)$/gm;
    const steps = [];
    let m;
    while ((m = regex.exec(thinking)) !== null) {
        steps.push({ step: parseInt(m[1]), tool: m[2], doc_id: m[3] || null, thought: m[4] });
    }
    return steps;
}

function onHistoryCleared(data) {
    showNotification('Conversation effacée');
}

// ========================================================================
//  Settings
// ========================================================================
function setupSettings() {
    document.getElementById('settingsBtn')?.addEventListener('click', () => {
        const el = document.getElementById('settingsModal');
        if (el) new bootstrap.Modal(el).show();
    });
    document.getElementById('saveSettingsBtn')?.addEventListener('click', saveSettings);
}

async function loadConfig() {
    try {
        const r = await fetch('/api/config/models');
        const d = await r.json();
        const tm = d.models?.text || {}, vm = d.models?.vision || {};
        document.getElementById('textModelName').value = tm.name || '';
        document.getElementById('textApiKey').value = tm.api_key || '';
        document.getElementById('textBaseUrl').value = tm.base_url || '';
        document.getElementById('visionModelName').value = vm.name || '';
        document.getElementById('visionApiKey').value = vm.api_key || '';
        document.getElementById('visionBaseUrl').value = vm.base_url || '';
        State.modelType = d.default_type || 'text';
        switchModel(State.modelType);
    } catch (e) { console.error('load config', e); }
}

async function saveSettings() {
    const tc = {
        name: document.getElementById('textModelName').value,
        api_key: document.getElementById('textApiKey').value,
        base_url: document.getElementById('textBaseUrl').value,
        type: 'text',
    };
    const vc = {
        name: document.getElementById('visionModelName').value,
        api_key: document.getElementById('visionApiKey').value,
        base_url: document.getElementById('visionBaseUrl').value,
        type: 'vision',
    };
    try {
        await fetch('/api/config/models/text', {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(tc)
        });
        await fetch('/api/config/models/vision', {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(vc)
        });
        bootstrap.Modal.getInstance(document.getElementById('settingsModal'))?.hide();
        showNotification('Configuration enregistrée');
    } catch { showNotification('Échec de l\'enregistrement', 'error'); }
}

// ========================================================================
//  Skills
// ========================================================================
let _skillsCache = [];

function setupSkills() {
    document.getElementById('skillsBtn')?.addEventListener('click', () => {
        loadSkills();
        new bootstrap.Modal(document.getElementById('skillsModal')).show();
    });
    document.getElementById('skillFileInput')?.addEventListener('change', e => {
        const f = e.target.files?.[0];
        if (f) uploadSkillFile(f);
        e.target.value = '';
    });
}

async function loadSkills() {
    try {
        const r = await fetch('/api/skills');
        const d = await r.json();
        _skillsCache = d.skills || [];
        renderSkillsGrid();
    } catch (e) { console.warn('load skills', e); }
}

function renderSkillsGrid() {
    const grid = document.getElementById('skillsGrid');
    if (!grid) return;
    if (!_skillsCache.length) {
        grid.innerHTML = '<div style="grid-column:1/-1;padding:30px;text-align:center;color:var(--text-secondary)">Aucun Skill ; cliquez sur « Nouveau » ou « Importer » en haut à droite</div>';
        return;
    }
    grid.innerHTML = _skillsCache.map(s => `
        <div class="skill-card">
            <div class="skill-toggle ${s.enabled ? 'active' : ''}" data-id="${esc(s.skill_id)}" data-enabled="${s.enabled ? 'true' : 'false'}"></div>
            <div class="skill-card-body" data-id="${esc(s.skill_id)}">
                <div class="skill-card-name">${esc(s.name)}</div>
                <div class="skill-card-desc">${esc(s.description || 'Aucune description')}</div>
            </div>
            <button class="skill-card-edit" data-id="${esc(s.skill_id)}" title="Modifier"><i class="bi bi-pencil"></i></button>
        </div>`).join('');
    grid.querySelectorAll('.skill-toggle').forEach(el => {
        el.addEventListener('click', async e => {
            e.stopPropagation();
            await toggleSkillEnabled(el.dataset.id, el.dataset.enabled !== 'true');
        });
    });
    grid.querySelectorAll('.skill-card-body').forEach(el =>
        el.addEventListener('click', () => openSkillEditor(el.dataset.id)));
    grid.querySelectorAll('.skill-card-edit').forEach(el =>
        el.addEventListener('click', e => { e.stopPropagation(); openSkillEditor(el.dataset.id); }));
}

async function toggleSkillEnabled(skillId, enabled) {
    try {
        await fetch(`/api/skills/${skillId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
        const s = _skillsCache.find(x => x.skill_id === skillId);
        if (s) s.enabled = enabled;
        renderSkillsGrid();
    } catch (e) { console.error('toggle skill', e); }
}

function openSkillEditor(skillId) {
    const modal = new bootstrap.Modal(document.getElementById('skillEditorModal'));
    const titleEl = document.getElementById('skillEditorTitle');
    const nameEl = document.getElementById('skillEditorName');
    const descEl = document.getElementById('skillEditorDesc');
    const contentEl = document.getElementById('skillEditorContent');
    const idEl = document.getElementById('skillEditorId');
    const deleteBtn = document.getElementById('skillDeleteBtn');
    const previewPane = document.getElementById('skillPreviewPane');
    if (previewPane) previewPane.style.display = 'none';

    if (skillId) {
        const s = _skillsCache.find(x => x.skill_id === skillId);
        if (!s) return;
        titleEl.textContent = 'Modifier le Skill';
        nameEl.value = s.name;
        descEl.value = s.description || '';
        contentEl.value = s.content || '';
        idEl.value = s.skill_id;
        deleteBtn.style.display = 'inline-flex';
    } else {
        titleEl.textContent = 'Nouveau Skill';
        nameEl.value = ''; descEl.value = ''; contentEl.value = '';
        idEl.value = '';
        deleteBtn.style.display = 'none';
    }
    modal.show();
}

async function saveSkill() {
    const id = document.getElementById('skillEditorId')?.value;
    const name = document.getElementById('skillEditorName')?.value?.trim();
    const description = document.getElementById('skillEditorDesc')?.value?.trim();
    const content = document.getElementById('skillEditorContent')?.value?.trim();
    if (!name) { showNotification('Veuillez saisir le nom du Skill', 'error'); return; }
    try {
        if (id) {
            await fetch(`/api/skills/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, description, content }) });
        } else {
            await fetch('/api/skills', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, description, content }) });
        }
        bootstrap.Modal.getInstance(document.getElementById('skillEditorModal'))?.hide();
        await loadSkills();
        showNotification(id ? 'Skill mis à jour' : 'Skill créé');
    } catch (e) { showNotification('Échec de l\'enregistrement : ' + e.message, 'error'); }
}

async function deleteCurrentSkill() {
    const id = document.getElementById('skillEditorId')?.value;
    if (!id) return;
    if (!confirm('Supprimer ce Skill ?')) return;
    try {
        await fetch(`/api/skills/${id}`, { method: 'DELETE' });
        bootstrap.Modal.getInstance(document.getElementById('skillEditorModal'))?.hide();
        await loadSkills();
        showNotification('Skill supprimé');
    } catch (e) { showNotification('Échec de la suppression', 'error'); }
}

async function uploadSkillFile(file) {
    if (!file || !file.name.endsWith('.md')) { showNotification('Seuls les fichiers .md sont pris en charge', 'error'); return; }
    const fd = new FormData(); fd.append('file', file);
    try {
        const r = await fetch('/api/skills/upload', { method: 'POST', body: fd });
        const d = await r.json();
        if (d.success) { await loadSkills(); showNotification('Skill importé'); }
        else showNotification('Échec de l\'import : ' + (d.error || 'Erreur inconnue'), 'error');
    } catch (e) { showNotification('Échec de l\'import', 'error'); }
}

function toggleSkillPreview() {
    const pane = document.getElementById('skillPreviewPane');
    const editor = document.getElementById('skillEditorContent');
    if (!pane || !editor) return;
    if (pane.style.display === 'none') {
        pane.style.display = 'block';
        pane.innerHTML = typeof marked !== 'undefined' ? marked.parse(editor.value || '') : esc(editor.value || '');
        document.getElementById('skillPreviewToggle').classList.add('active');
    } else {
        pane.style.display = 'none';
        document.getElementById('skillPreviewToggle').classList.remove('active');
    }
}

// Expose for inline handlers
window.saveSkill = saveSkill;
window.deleteCurrentSkill = deleteCurrentSkill;
window.toggleSkillPreview = toggleSkillPreview;
window.openSkillEditor = openSkillEditor;
window.startNewDocSession = startNewDocSession;

// ========================================================================
//  Page preview modal (per-document, unchanged core logic)
// ========================================================================
async function ensurePreviewData(docId) {
    if (State.nodeMapCache[docId] && State.allPagesCache[docId]) return true;
    try {
        const r = await fetch(`/api/documents/${docId}/node-info`);
        const d = await r.json();
        if (!d.node_map) return false;
        State.nodeMapCache[docId] = d.node_map;
        State.allPagesCache[docId] = d.all_pages || [];
        return true;
    } catch { return false; }
}

async function showNodePreview(nodeId, docId, focusPage = null) {
    if (!docId) docId = State.docChat.docId;
    if (!docId) return;
    if (!(await ensurePreviewData(docId))) return;
    // The model cites "node_0004" (or even a bare "4") but node_map / highlight
    // keys are "0004": resolve to whichever form the map actually uses.
    const map = State.nodeMapCache[docId] || {};
    if (!(nodeId in map)) {
        const bare = nodeId.replace(/^node[_\s]*/i, '');
        if (bare in map) nodeId = bare;
        else if (/^\d+$/.test(bare) && bare.padStart(4, '0') in map) nodeId = bare.padStart(4, '0');
    }
    const info = map[nodeId];
    if (!info) { showNotification('Informations du nœud introuvables', 'error'); return; }
    showPagePreviewModal(docId, nodeId, info, State.allPagesCache[docId], true, focusPage);
}

// Browse the whole document — same side panel, no active node. Optionally
// lands on a given page (library "Aperçu" button).
async function showDocPreview(docId, focusPage = null) {
    if (!(await ensurePreviewData(docId))) {
        showNotification('Aperçu indisponible pour ce document', 'error');
        return;
    }
    showPagePreviewModal(docId, null, { start_index: 1 }, State.allPagesCache[docId], false, focusPage);
}

// Page-only citation ("(pages 5-6)" without a node id): infer the owning node
// from the node_map page ranges so the viewer highlights it like a full
// citation. On boundary pages shared by two sections, prefer the one that
// STARTS on the cited page (its content dominates it); if still ambiguous,
// fall back to plain browsing without highlight.
async function showPageRef(docId, page) {
    if (!(await ensurePreviewData(docId))) {
        showNotification('Aperçu indisponible pour ce document', 'error');
        return;
    }
    const map = State.nodeMapCache[docId] || {};
    let owners = Object.keys(map).filter(nid => {
        const s = map[nid].start_index || 0;
        const e = map[nid].end_index || s;
        return page >= s && page <= e;
    });
    if (owners.length > 1) {
        const starting = owners.filter(nid => map[nid].start_index === page);
        if (starting.length === 1) owners = starting;
    }
    if (owners.length === 1) {
        showPagePreviewModal(docId, owners[0], map[owners[0]], State.allPagesCache[docId], true, page);
    } else {
        showPagePreviewModal(docId, null, { start_index: 1 }, State.allPagesCache[docId], false, page);
    }
}

// PageIndex tree (table of contents) viewer, fed by /api/documents/<id>/tree.
async function showDocTree(docId) {
    let tree;
    try {
        const r = await fetch(`/api/documents/${docId}/tree`);
        const d = await r.json();
        if (!r.ok || !d.tree) { showNotification(d.error || 'Structure introuvable', 'error'); return; }
        tree = d.tree;
    } catch {
        showNotification('Impossible de charger la structure', 'error');
        return;
    }
    let modal = document.getElementById('docTreeModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'docTreeModal';
        modal.className = 'doc-tree-modal';
        modal.innerHTML = `<div class="doc-tree-content">
            <div class="doc-tree-header">
                <h5 class="doc-tree-title"><i class="bi bi-diagram-3"></i> <span></span></h5>
                <button class="doc-tree-close"><i class="bi bi-x-lg"></i></button>
            </div>
            <div class="doc-tree-body"></div>
        </div>`;
        document.body.appendChild(modal);
        modal.querySelector('.doc-tree-close').addEventListener('click', () => modal.classList.remove('active'));
        modal.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('active'); });
    }
    const docInfo = (State.documents || []).find(x => x.doc_id === docId);
    modal.querySelector('.doc-tree-title span').textContent = docInfo?.filename || 'Structure du document';
    modal.querySelector('.doc-tree-body').innerHTML = renderTreeNodes(tree);
    modal.querySelectorAll('.tree-node-row[data-node-id]').forEach(row => {
        row.addEventListener('click', () => {
            modal.classList.remove('active');
            showNodePreview(row.dataset.nodeId, docId);
        });
    });
    modal.classList.add('active');
}

function renderTreeNodes(node, depth = 0) {
    if (Array.isArray(node)) return node.map(n => renderTreeNodes(n, depth)).join('');
    if (!node || typeof node !== 'object') return '';
    const children = node.children || node.nodes || [];
    if (!node.title) return renderTreeNodes(children, depth);
    const pages = node.start_index
        ? `<span class="tree-node-pages">p. ${node.start_index}${node.end_index && node.end_index !== node.start_index ? '–' + node.end_index : ''}</span>`
        : '';
    return `
        <div class="tree-node" style="--tree-depth:${depth}">
            <div class="tree-node-row" ${node.node_id ? `data-node-id="${esc(node.node_id)}"` : ''} title="Voir dans le document">
                <span class="tree-node-title">${esc(node.title)}</span>${pages}
            </div>
            ${node.summary ? `<div class="tree-node-summary">${esc(node.summary)}</div>` : ''}
        </div>` + renderTreeNodes(children, depth + 1);
}
window.showNodePreview = showNodePreview;

function buildPageNodeMap(nodeMap) {
    const pageNodes = {};
    if (!nodeMap) return pageNodes;
    Object.entries(nodeMap).forEach(([nid, info], idx) => {
        const s = info.start_index || 1;
        const e = info.end_index || s;
        const color = NODE_COLORS[idx % NODE_COLORS.length];
        for (let p = s; p <= e; p++) {
            if (!pageNodes[p]) pageNodes[p] = [];
            pageNodes[p].push({ id: nid, title: info.title || nid, color });
        }
    });
    return pageNodes;
}

function getNodeColor(nodeId, nodeMap) {
    const keys = Object.keys(nodeMap || {});
    const idx = keys.indexOf(nodeId);
    return NODE_COLORS[(idx >= 0 ? idx : 0) % NODE_COLORS.length];
}

async function showPagePreviewModal(docId, nodeId, nodeInfo, allPages, autoHighlight = true, focusPage = null) {
    let modal = document.getElementById('pagePreviewModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'pagePreviewModal';
        modal.className = 'page-preview-modal';
        modal.innerHTML = `<div class="page-preview-content">
            <div class="page-preview-header">
                <h5 class="page-preview-title"></h5>
                <div class="page-preview-header-actions">
                    <button class="highlight-toggle-btn" id="highlightToggleBtn" title="Cliquez sur une étiquette de nœud pour la surligner"><i class="bi bi-highlighter"></i></button>
                    <button class="page-preview-close"><i class="bi bi-x-lg"></i></button>
                </div>
            </div>
            <div class="node-info-card" id="nodeInfoCard"></div>
            <div class="page-preview-body"><div class="page-preview-images"></div></div>
            <div class="page-preview-footer"><div class="page-preview-nav">
                <button class="page-nav-btn" id="prevPageBtn"><i class="bi bi-chevron-left"></i> Page précédente</button>
                <span class="page-indicator" id="pageIndicator"></span>
                <button class="page-nav-btn" id="nextPageBtn">Page suivante <i class="bi bi-chevron-right"></i></button>
            </div></div></div>`;
        document.body.appendChild(modal);
        modal.querySelector('.page-preview-close').addEventListener('click', closePagePreviewModal);
        modal.querySelector('#prevPageBtn').addEventListener('click', () => navPage(-1));
        modal.querySelector('#nextPageBtn').addEventListener('click', () => navPage(1));
        modal.querySelector('#highlightToggleBtn').addEventListener('click', () => toggleHighlights());
    }

    State.activeHighlightNodeId = null;
    modal.dataset.docId = docId;
    updateHighlightToggleBtn();

    const nMap = State.nodeMapCache[docId] || {};
    const pageNodeMap = buildPageNodeMap(nMap);
    const currentStart = nodeInfo.start_index || 1;
    const currentEnd = nodeInfo.end_index || currentStart;
    const nodeColor = getNodeColor(nodeId, nMap);

    const docInfo = State.documents.find(x => x.doc_id === docId);
    modal.querySelector('.page-preview-title').textContent = docInfo?.filename || 'Aperçu du PDF';

    const infoCard = modal.querySelector('#nodeInfoCard');
    if (nodeId) {
        infoCard.style.display = '';
        infoCard.innerHTML = `
        <div class="node-info-badge" style="background:${nodeColor.bg};color:${nodeColor.text}">${esc(nodeId)}</div>
        <div class="node-info-detail">
            <div class="node-info-title">${esc(nodeInfo.title || 'Nœud sans titre')}</div>
            <div class="node-info-meta">
                <span><i class="bi bi-file-earmark"></i> Pages ${currentStart}–${currentEnd}</span>
            </div>
            ${nodeInfo.summary ? `<div class="node-info-summary">${esc(nodeInfo.summary)}</div>` : ''}
        </div>`;
    } else {
        // Whole-document browsing (library "Aperçu"): no active node to describe.
        infoCard.style.display = 'none';
        infoCard.innerHTML = '';
    }

    const imgs = modal.querySelector('.page-preview-images');
    if (!allPages?.length) {
        imgs.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-secondary)">Aucune image de page</div>';
    } else {
        imgs.innerHTML = allPages.map((p, i) => {
            const pageNum = p.page;
            const isCurrent = !!nodeId && pageNum >= currentStart && pageNum <= currentEnd;
            const nodes = pageNodeMap[pageNum] || [];
            const tags = nodes.map(n => {
                const isActive = n.id === nodeId;
                const label = n.title.length > 20 ? n.title.slice(0, 18) + '…' : n.title;
                return `<span class="page-node-tag${isActive ? ' active-node' : ''}" data-node-id="${n.id}" `
                    + `style="background:${n.color.bg};color:${n.color.text}" `
                    + `title="Cliquer pour surligner ${esc(n.id + ': ' + n.title)}">`
                    + `<span class="page-node-tag-id">${n.id}</span> ${esc(label)}</span>`;
            }).join('');
            return `<div class="page-image-container${isCurrent ? ' current-node-page' : ''}" data-index="${i}">`
                + `<img src="${p.url}" alt="Page ${pageNum}" class="page-preview-image">`
                + (tags ? `<div class="page-node-tags">${tags}</div>` : '')
                + `<div class="page-number">Page ${pageNum}</div></div>`;
        }).join('');
        imgs.querySelectorAll('.page-preview-image').forEach(img => {
            img.addEventListener('click', () => openFullscreen(img.src));
            // Highlights are drawn in image-pixel space, so a page can only be
            // highlighted once its image has real dimensions. Redraw on load so
            // an auto-activated highlight appears even before the user scrolls.
            img.addEventListener('load', () => {
                if (!State.activeHighlightNodeId) return;
                const container = img.closest('.page-image-container');
                if (!container) return;
                const idx = parseInt(container.dataset.index);
                drawHighlightsOnPage(container, idx + 1, State.highlightsCache[docId], nMap, State.activeHighlightNodeId);
            });
        });
        imgs.querySelectorAll('.page-node-tag').forEach(tag => {
            tag.addEventListener('click', e => {
                e.stopPropagation();
                activateNodeHighlight(tag.dataset.nodeId);
            });
        });
    }

    modal.dataset.pages = JSON.stringify(allPages);
    const si = Math.max(0, Math.min((focusPage || currentStart) - 1, allPages.length - 1));
    modal.dataset.currentIndex = si;
    updatePageNav();
    modal.classList.add('active');
    document.querySelector('.main-content.preview-open')?.classList.remove('preview-open');
    const main = document.querySelector('.page.active .main-content');
    main?.classList.add('preview-open');

    await initHighlightsForModal(modal, nMap, docId);
    // Land directly on the highlighted source (matching the "scroll to and
    // highlight" UX) rather than requiring the user to click the node tag.
    if (autoHighlight && nodeId) activateNodeHighlight(nodeId);
    setTimeout(() => {
        const target = modal.querySelectorAll('.page-image-container')[si];
        const scrollParent = modal.querySelector('.page-preview-body');
        if (target && scrollParent) scrollParent.scrollTop = target.offsetTop - scrollParent.offsetTop;
    }, 100);
}

async function initHighlightsForModal(modal, nMap, docId) {
    const hlData = await fetchTextHighlights(docId);
    if (!hlData) return;
    if (State._highlightObserver) { State._highlightObserver.disconnect(); State._highlightObserver = null; }
    State._highlightObserver = new ResizeObserver(() => {
        if (State.activeHighlightNodeId) {
            redrawAllHighlights(modal, hlData, nMap, State.activeHighlightNodeId);
        }
    });
    const body = modal.querySelector('.page-preview-body');
    if (body) State._highlightObserver.observe(body);
}

async function fetchTextHighlights(docId) {
    if (State.highlightsCache[docId]) return State.highlightsCache[docId];
    try {
        const r = await fetch(`/api/documents/${docId}/text-highlights`);
        if (r.ok) {
            const d = await r.json();
            State.highlightsCache[docId] = d;
            return d;
        }
    } catch (e) { console.error('Highlights fetch:', e); }
    return null;
}

function drawHighlightsOnPage(container, pageNum, hlData, nodeMap, targetNodeId) {
    container.querySelectorAll('.highlight-canvas').forEach(c => c.remove());
    if (!targetNodeId || !hlData) return;
    const pageInfo = hlData.pages?.[String(pageNum)];
    if (!pageInfo || !pageInfo.blocks?.length) return;
    const hasTarget = pageInfo.blocks.some(b => b.node_id === targetNodeId);
    if (!hasTarget) return;
    const img = container.querySelector('.page-preview-image');
    if (!img || !img.naturalWidth) return;

    const canvas = document.createElement('canvas');
    canvas.className = 'highlight-canvas';
    const displayW = img.clientWidth, displayH = img.clientHeight;
    canvas.width = displayW; canvas.height = displayH;
    canvas.style.width = displayW + 'px'; canvas.style.height = displayH + 'px';
    container.insertBefore(canvas, img.nextSibling);

    const ctx = canvas.getContext('2d');
    const scale = hlData.scale || 2.0;
    const sx = displayW / (pageInfo.width * scale);
    const sy = displayH / (pageInfo.height * scale);
    const nodeKeys = Object.keys(nodeMap || {});
    const colorIdx = nodeKeys.indexOf(targetNodeId);
    const color = NODE_COLORS[(colorIdx >= 0 ? colorIdx : 0) % NODE_COLORS.length];
    const rgb = hexToRgb(color.text) || { r: 79, g: 70, b: 229 };

    for (const block of pageInfo.blocks) {
        if (block.node_id !== targetNodeId) continue;
        const [x0, y0, x1, y1] = block.bbox;
        ctx.fillStyle = `rgba(${rgb.r},${rgb.g},${rgb.b},0.18)`;
        ctx.fillRect(x0 * scale * sx, y0 * scale * sy, (x1 - x0) * scale * sx, (y1 - y0) * scale * sy);
    }
}

function hexToRgb(hex) {
    if (!hex || hex[0] !== '#') return null;
    const v = parseInt(hex.slice(1), 16);
    return { r: (v >> 16) & 255, g: (v >> 8) & 255, b: v & 255 };
}

function redrawAllHighlights(modal, hlData, nodeMap, targetNodeId) {
    modal.querySelectorAll('.page-image-container').forEach(c => {
        const idx = parseInt(c.dataset.index);
        drawHighlightsOnPage(c, idx + 1, hlData, nodeMap, targetNodeId);
    });
}

function clearAllHighlights() {
    const modal = document.getElementById('pagePreviewModal');
    if (modal) modal.querySelectorAll('.highlight-canvas').forEach(c => c.remove());
    State.activeHighlightNodeId = null;
    updateHighlightToggleBtn();
    updateActiveNodeTags();
}

function activateNodeHighlight(nodeId) {
    if (State.activeHighlightNodeId === nodeId) { clearAllHighlights(); return; }
    State.activeHighlightNodeId = nodeId;
    const modal = document.getElementById('pagePreviewModal');
    if (!modal) return;
    const docId = modal.dataset.docId;
    const nMap = State.nodeMapCache[docId] || {};
    const hlData = State.highlightsCache[docId];
    redrawAllHighlights(modal, hlData, nMap, nodeId);
    updateHighlightToggleBtn();
    updateActiveNodeTags();
}

function toggleHighlights() {
    if (State.activeHighlightNodeId) clearAllHighlights();
}

function updateHighlightToggleBtn() {
    const btn = document.getElementById('highlightToggleBtn');
    if (btn) {
        btn.classList.toggle('active', !!State.activeHighlightNodeId);
        btn.title = State.activeHighlightNodeId ? 'Effacer le surlignage (' + State.activeHighlightNodeId + ')' : 'Cliquez sur une étiquette de nœud pour la surligner';
    }
}

function updateActiveNodeTags() {
    document.querySelectorAll('.page-node-tag').forEach(tag => {
        tag.classList.toggle('highlight-active', tag.dataset.nodeId === State.activeHighlightNodeId);
    });
}

function closePagePreviewModal() {
    State.activeHighlightNodeId = null;
    if (State._highlightObserver) { State._highlightObserver.disconnect(); State._highlightObserver = null; }
    const m = document.getElementById('pagePreviewModal');
    if (m) {
        m.classList.remove('active');
        document.querySelectorAll('.main-content').forEach(el => el.classList.remove('preview-open'));
    }
}
window.closePagePreviewModal = closePagePreviewModal;

function navPage(dir) {
    const m = document.getElementById('pagePreviewModal'); if (!m) return;
    const pages = JSON.parse(m.dataset.pages || '[]');
    let i = Math.max(0, Math.min(pages.length - 1, (parseInt(m.dataset.currentIndex) || 0) + dir));
    m.dataset.currentIndex = i;
    const target = m.querySelectorAll('.page-image-container')[i];
    const scrollParent = m.querySelector('.page-preview-body');
    if (target && scrollParent) scrollParent.scrollTop = target.offsetTop - scrollParent.offsetTop;
    updatePageNav();
}

function updatePageNav() {
    const m = document.getElementById('pagePreviewModal'); if (!m) return;
    const pages = JSON.parse(m.dataset.pages || '[]');
    const i = parseInt(m.dataset.currentIndex) || 0;
    const ind = document.getElementById('pageIndicator');
    if (ind) ind.textContent = pages.length ? `${i + 1} / ${pages.length}` : '0 / 0';
    const pb = document.getElementById('prevPageBtn'); if (pb) pb.disabled = i === 0;
    const nb = document.getElementById('nextPageBtn'); if (nb) nb.disabled = i >= pages.length - 1;
}

function openFullscreen(url) {
    const o = document.createElement('div');
    o.className = 'fullscreen-image-overlay'; o.onclick = () => o.remove();
    o.innerHTML = `<img src="${url}" class="fullscreen-image"><button class="fullscreen-close"><i class="bi bi-x-lg"></i></button>`;
    o.querySelector('.fullscreen-close').addEventListener('click', e => { e.stopPropagation(); o.remove(); });
    document.body.appendChild(o);
}

// slideIn / slideOut keyframes
const _s = document.createElement('style');
_s.textContent = '@keyframes slideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}@keyframes slideOut{from{transform:translateX(0);opacity:1}to{transform:translateX(100%);opacity:0}}';
document.head.appendChild(_s);
