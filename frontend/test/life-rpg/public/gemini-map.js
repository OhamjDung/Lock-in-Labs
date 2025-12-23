// Gemini Map JavaScript - Full Implementation
console.log("Gemini Map script loading...");

// --- Global State ---
const viewport = document.getElementById('viewport');
const canvas = document.getElementById('canvas');
const popup = document.getElementById('highlight-popup');
const popupHighlightedTextEl = document.getElementById('popup-highlighted-text');
const popupPromptInputEl = document.getElementById('popup-prompt-input');
const popupCreateBranchBtn = document.getElementById('popup-create-branch-btn');
const svgCanvas = document.getElementById('connector-svg');
const historyBar = document.getElementById('history-bar');
const historyLinksContainer = document.getElementById('history-links-container');
const modelSelect = document.getElementById('gemini-model-select');
const startScreen = document.getElementById('start-screen');
const startPromptInput = document.getElementById('start-prompt-input');
const startBtn = document.getElementById('start-btn');
const startFileInput = document.getElementById('start-file-input');
const startFileName = document.getElementById('start-file-name');
const popupFileInput = document.getElementById('popup-file-input');
const popupFileName = document.getElementById('popup-file-name');
const NS = 'http://www.w3.org/2000/svg';

// Load Model preference
if(localStorage.getItem('gemini_model')) {
    modelSelect.value = localStorage.getItem('gemini_model');
}

modelSelect.addEventListener('change', (e) => {
    localStorage.setItem('gemini_model', e.target.value);
});

let isPanning = false;
let lastMouseX = 0;
let lastMouseY = 0;
let didDrag = false; 
let justPanned = false;

let canvasX = 0;
let canvasY = 0;
let scale = 1;
const minScale = 0.2;
const maxScale = 3;

let currentParentNode = null;
let currentSelectedText = "";

// --- NEW: History State ---
let viewHistory = [];

// --- Panning & Zooming Logic ---
function applyTransform() {
    canvas.style.transform = `translate(${canvasX}px, ${canvasY}px) scale(${scale})`;
    requestAnimationFrame(updateAllLines);
}

function resetPanAndZoom() {
    const currentRootId = viewHistory[viewHistory.length - 1];
    const rootNode = document.getElementById(currentRootId);
    
    if (!rootNode) {
        canvasX = 0;
        canvasY = 0;
        scale = 1;
    } else {
        scale = 1;
        const targetScreenX = (currentRootId === 'A') ? 100 : 50;
        const targetScreenY = (currentRootId === 'A') ? 150 : 50;
        const nodeCanvasX = getNodeLeft(rootNode); 
        const nodeCanvasY = getNodeTop(rootNode);
        canvasX = targetScreenX - (nodeCanvasX * scale);
        canvasY = targetScreenY - (nodeCanvasY * scale);
    }
    
    applyTransform();
}

function panToNode(node) {
    if (!node) return;
    const viewportWidth = viewport.clientWidth;
    const viewportHeight = viewport.clientHeight;
    const targetScreenX = 100; 
    const targetScreenY = viewportHeight / 2 - (node.offsetHeight * scale) / 2;
    const nodeCanvasX = getNodeLeft(node);
    const nodeCanvasY = getNodeTop(node);
    const targetCanvasX = targetScreenX - (nodeCanvasX * scale);
    const targetCanvasY = targetScreenY - (nodeCanvasY * scale);
    const startCanvasX = canvasX;
    const startCanvasY = canvasY;
    const startTime = performance.now();
    const duration = 500;

    function step(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const ease = 1 - Math.pow(1 - progress, 3);
        canvasX = startCanvasX + (targetCanvasX - startCanvasX) * ease;
        canvasY = startCanvasY + (targetCanvasY - startCanvasY) * ease;
        applyTransform();
        if (progress < 1) {
            requestAnimationFrame(step);
        }
    }
    requestAnimationFrame(step);
}

viewport.addEventListener('mousedown', (e) => {
    const isTextClick = e.target.closest('.node-response-content');
    const isPopupClick = e.target.closest('#highlight-popup');
    const isBtnClick = e.target.closest('.node-btn'); 
    const isInputClick = e.target.closest('input, textarea, button, .node-reprompt-form');
    if (isTextClick || isPopupClick || isBtnClick || isInputClick) return;
    e.preventDefault();
    isPanning = true;
    didDrag = false; 
    justPanned = false;
    viewport.classList.add('is-panning');
    lastMouseX = e.clientX;
    lastMouseY = e.clientY;
});

viewport.addEventListener('mousemove', (e) => {
    if (!isPanning) return;
    didDrag = true;
    justPanned = true; 
    const dx = e.clientX - lastMouseX;
    const dy = e.clientY - lastMouseY;
    canvasX += dx;
    canvasY += dy;
    applyTransform(); 
    lastMouseX = e.clientX;
    lastMouseY = e.clientY;
});

viewport.addEventListener('mouseup', () => {
    if (isPanning && !didDrag) {
        popup.style.display = 'none';
        currentParentNode = null;
        currentSelectedText = "";
    } 
    isPanning = false;
    viewport.classList.remove('is-panning');
});

viewport.addEventListener('mouseleave', () => {
    isPanning = false;
    viewport.classList.remove('is-panning');
});

viewport.addEventListener('wheel', (e) => {
    e.preventDefault();
    if (e.ctrlKey) {
        const scaleAmount = 1 - e.deltaY * 0.005;
        const newScale = Math.max(minScale, Math.min(maxScale, scale * scaleAmount));
        const rect = viewport.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        const mouseXOnCanvas = (mouseX - canvasX) / scale;
        const mouseYOnCanvas = (mouseY - canvasY) / scale;
        canvasX = mouseX - (mouseXOnCanvas * newScale);
        canvasY = mouseY - (mouseYOnCanvas * newScale);
        scale = newScale;
    } else {
        canvasX -= e.deltaX;
        canvasY -= e.deltaY;
    }
    applyTransform();
});

// --- Highlight-to-Branch Logic ---
document.addEventListener('mouseup', (e) => {
    if (justPanned) {
        justPanned = false; 
        return;
    }
    if (isPanning) return;
    
    const responseContent = e.target.closest('.node-response-content');
    const selection = window.getSelection();
    const selectedText = selection.toString().trim();

    if (selectedText.length > 0 && responseContent) {
        currentParentNode = responseContent.closest('.chat-node');
        currentSelectedText = selectedText;
        popupHighlightedTextEl.textContent = currentSelectedText;
        const range = selection.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        const viewportRect = viewport.getBoundingClientRect();
        const popupScreenX = rect.left - viewportRect.left + (rect.width / 2) - (popup.offsetWidth / 2);
        const popupScreenY = rect.bottom - viewportRect.top + 10;
        const canvasPopupX = (popupScreenX - canvasX) / scale;
        const canvasPopupY = (popupScreenY - canvasY) / scale;
        popup.style.left = `${canvasPopupX}px`;
        popup.style.top = `${canvasPopupY}px`;
        popup.style.display = 'flex';
        popupPromptInputEl.value = ""; 
        popupPromptInputEl.focus();
    } else {
        if (!e.target.closest('#highlight-popup')) {
            popup.style.display = 'none';
            currentParentNode = null;
            currentSelectedText = "";
        }
    }
});

popupCreateBranchBtn.addEventListener('click', async () => {
    const newPromptText = popupPromptInputEl.value.trim();
    if (currentParentNode && currentSelectedText) {
        let attachment = null;
        if (popupFileInput.files.length > 0) {
            try {
                attachment = await fileToBase64(popupFileInput.files[0]);
            } catch (e) {
                console.error("File read error:", e);
            }
        }
        createBranchNode(currentParentNode, currentSelectedText, newPromptText, attachment);
        window.getSelection().removeAllRanges();
        popup.style.display = 'none';
        currentParentNode = null;
        currentSelectedText = "";
        popupPromptInputEl.value = "";
        popupFileInput.value = "";
        popupFileName.textContent = "";
    }
});

// --- View, History, and Rooting Logic ---
canvas.addEventListener('click', (e) => {
    const btn = e.target.closest('.node-btn');
    if (!btn) return;
    const nodeEl = btn.closest('.chat-node');
    if (!nodeEl) return;

    if (btn.classList.contains('node-collapse-btn')) {
        toggleCollapse(nodeEl);
    }
    
    if (btn.classList.contains('node-root-btn')) {
        viewHistory.push(nodeEl.id);
        renderView();
    }

    if (btn.classList.contains('node-remove-btn')) {
        if (confirm('Are you sure you want to remove this node and its descendants?')) {
            removeNode(nodeEl);
        }
    }
});

historyBar.addEventListener('click', (e) => {
    const link = e.target.closest('.history-link');
    if (link && !link.disabled) {
        const nodeId = link.dataset.nodeId;
        const index = viewHistory.indexOf(nodeId);
        if (index > -1) {
            viewHistory = viewHistory.slice(0, index + 1);
            renderView();
            const targetNode = document.getElementById(nodeId);
            if (nodeId === 'A') {
                runFullTreeReflow();
            } else {
                reflowRecursive(targetNode);
                requestAnimationFrame(updateAllLines);
            }
        }
    }
});

function renderView() {
    if (viewHistory.length === 0) return;
    const currentRootId = viewHistory[viewHistory.length - 1];
    const currentRootNode = document.getElementById(currentRootId);
    
    historyLinksContainer.innerHTML = '';
    viewHistory.forEach((nodeId, index) => {
        const node = document.getElementById(nodeId);
        const isLast = index === viewHistory.length - 1;
        if (index > 0) {
            const separator = document.createElement('span');
            separator.className = 'history-separator';
            separator.textContent = '>';
            historyLinksContainer.appendChild(separator);
        }
        const link = document.createElement('button');
        link.className = 'history-link';
        link.textContent = (nodeId === 'A') ? 'Root' : `Node ${nodeId}`;
        link.dataset.nodeId = nodeId;
        if (isLast) {
            link.disabled = true;
        }
        historyLinksContainer.appendChild(link);
    });
    
    const allNodes = document.querySelectorAll('.chat-node');
    
    if (currentRootId === 'A') {
        allNodes.forEach(node => {
            node.style.display = 'block';
        });
        document.querySelectorAll('.chat-node.collapsed').forEach(collapsedNode => {
            const descendants = getSubtreeNodes(collapsedNode);
            for (let i = 1; i < descendants.length; i++) {
                descendants[i].style.display = 'none';
            }
        });
    } else {
        allNodes.forEach(node => {
            node.style.display = 'none';
        });
        const visibleNodes = getSubtreeNodes(currentRootNode);
        visibleNodes.forEach(node => {
            node.style.display = 'block';
            if (node.classList.contains('collapsed')) {
                const descendants = getSubtreeNodes(node);
                for (let i = 1; i < descendants.length; i++) {
                    descendants[i].style.display = 'none';
                }
            }
        });
    }

    resetPanAndZoom();
    requestAnimationFrame(updateAllLines);
}

function toggleCollapse(nodeEl) {
    const btn = nodeEl.querySelector('.node-collapse-btn');
    const isCollapsing = !nodeEl.classList.contains('collapsed');

    if (isCollapsing) {
        nodeEl.classList.add('collapsed');
        if (btn) btn.textContent = '+';
        const descendants = getSubtreeNodes(nodeEl);
        for (let i = 1; i < descendants.length; i++) {
            descendants[i].style.display = 'none';
        }
    } else {
        nodeEl.classList.remove('collapsed');
        if (btn) btn.textContent = '-';
        showVisibleDescendants(nodeEl);
    }

    const currentRootId = viewHistory[viewHistory.length - 1];
    if (currentRootId === 'A') {
        runReflow(nodeEl);
    } else {
        reflowFocusedView(document.getElementById(currentRootId));
    }
}

function showVisibleDescendants(parentNode) {
    let visibleNodes = [];
    const children = document.querySelectorAll(`.chat-node[data-parent-id="${parentNode.id}"]`);
    children.forEach(child => {
        child.style.display = 'block';
        visibleNodes.push(child);
        if (!child.classList.contains('collapsed')) {
            visibleNodes = visibleNodes.concat(showVisibleDescendants(child));
        }
    });
    return visibleNodes;
}

// --- SVG Line Drawing Logic ---
function updateAllLines() {
    if (!svgCanvas) return;
    svgCanvas.innerHTML = '';
    const svgOffsetX = 10000;
    const svgOffsetY = 10000;

    const allNodes = document.querySelectorAll('.chat-node:not(#A)');
    
    allNodes.forEach(node => {
        if (node.style.display === 'none') return;
        const parentId = node.dataset.parentId;
        if (!parentId) return; 
        const parentNode = document.getElementById(parentId);
        if (!parentNode || parentNode.style.display === 'none') return;
        const startX = getNodeLeft(parentNode) + parentNode.offsetWidth + svgOffsetX;
        const startY = getNodeTop(parentNode) + (parentNode.offsetHeight / 2) + svgOffsetY;
        const endX = getNodeLeft(node) + svgOffsetX;
        const endY = getNodeTop(node) + (node.offsetHeight / 2) + svgOffsetY;
        const midX = startX + (endX - startX) / 2;
        const pathData = `M ${startX} ${startY} L ${midX} ${startY} L ${midX} ${endY} L ${endX} ${endY}`;
        const path = document.createElementNS(NS, 'path');
        path.setAttribute('d', pathData);
        path.setAttribute('stroke', '#39ff14'); // Green color
        path.setAttribute('stroke-width', '2');
        path.setAttribute('fill', 'none');
        path.setAttribute('vector-effect', 'non-scaling-stroke');
        svgCanvas.appendChild(path);
    });
}

function getNodeTop(node) {
    if (!node) return 0;
    const styleTop = parseFloat(node.style.top);
    if (isNaN(styleTop)) {
        return node.offsetTop || 0;
    }
    return styleTop;
}

function getNodeLeft(node) {
    if (!node) return 0;
    const styleLeft = parseFloat(node.style.left);
    if (isNaN(styleLeft)) {
        return node.offsetLeft || 0;
    }
    return styleLeft;
}

function getSubtreeMaxBottom(startNode) {
    let maxBottom = getNodeTop(startNode) + startNode.offsetHeight;
    if (startNode.classList.contains('collapsed')) {
        return maxBottom;
    }
    const children = document.querySelectorAll(`.chat-node[data-parent-id="${startNode.id}"]`);
    children.forEach(child => {
        maxBottom = Math.max(maxBottom, getSubtreeMaxBottom(child));
    });
    return maxBottom;
}

function getSubtreeNodes(startNode) {
    let nodes = [startNode];
    const children = document.querySelectorAll(`.chat-node[data-parent-id="${startNode.id}"]`);
    children.forEach(child => {
        nodes = nodes.concat(getSubtreeNodes(child));
    });
    return nodes;
}

function runFullTreeReflow() {
    const root = document.getElementById('A');
    reflowRecursive(root);
    reflowVerticalLayout();
}

function reflowRecursive(parentNode) {
    const children = document.querySelectorAll(`.chat-node[data-parent-id="${parentNode.id}"]`);
    children.forEach(child => reflowRecursive(child));
    if (children.length > 0 && parentNode.id !== 'A') {
        reflowSubBranchLayout(parentNode);
    }
}

function reflowSubBranchLayout(parentNode) {
    const children = [];
    document.querySelectorAll(`.chat-node[data-parent-id="${parentNode.id}"]`).forEach(node => {
        children.push(node);
    });
    children.sort((a, b) => {
        const aId = a.id.split('-').pop();
        const bId = b.id.split('-').pop();
        return parseInt(aId) - parseInt(bId);
    });
    
    let currentMaxBottom = 0; 
    const parentTop = getNodeTop(parentNode);

    children.forEach((childNode, index) => {
        const oldTop = getNodeTop(childNode);
        let newTop;
        if (index === 0) {
            newTop = parentTop;
        } else {
            newTop = currentMaxBottom + 20; 
        }
        const deltaY = newTop - oldTop;
        if (deltaY !== 0) {
            const subtreeNodes = getSubtreeNodes(childNode);
            subtreeNodes.forEach(node => {
                node.style.top = (getNodeTop(node) + deltaY) + 'px';
            });
        }
        canvas.offsetHeight;
        currentMaxBottom = getSubtreeMaxBottom(childNode);
    });
}

function reflowVerticalLayout() {
    const rootNode = document.getElementById('A');
    const rootBranches = [];
    document.querySelectorAll('.chat-node[data-parent-id="A"]').forEach(node => {
        rootBranches.push(node);
    });
    rootBranches.sort((a, b) => {
        const aNum = parseInt(a.id.replace('A', ''));
        const bNum = parseInt(b.id.replace('A', ''));
        return aNum - bNum;
    });
    
    let currentMaxBottom = 0;
    const rootTop = getNodeTop(rootNode);

    rootBranches.forEach((rootBranchNode, index) => {
        const branchId = rootBranchNode.dataset.branchId;
        const allBranchNodes = document.querySelectorAll(`.chat-node[data-branch-id="${branchId}"]`);
        if (allBranchNodes.length === 0) return;
        const oldTop = getNodeTop(rootBranchNode);
        let newTop;
        if (index === 0) {
            newTop = rootTop;
        } else {
            newTop = currentMaxBottom + 20;
        }
        const deltaY = newTop - oldTop;
        if (deltaY !== 0) {
            allBranchNodes.forEach(node => {
                node.style.top = (getNodeTop(node) + deltaY) + 'px';
            });
        }
        canvas.offsetHeight;
        currentMaxBottom = getSubtreeMaxBottom(rootBranchNode);
    });

    requestAnimationFrame(updateAllLines);
}

function runReflow(changedNode) {
    let currentNode = changedNode;
    while (currentNode && currentNode.dataset.parentId) {
        const parent = document.getElementById(currentNode.dataset.parentId);
        if (!parent) break;
        if (parent.id === 'A') break; 
        reflowSubBranchLayout(parent);
        currentNode = parent;
    }
    reflowVerticalLayout();
}

function reflowFocusedView(focusedRootNode) {
    const children = [];
    document.querySelectorAll(`.chat-node[data-parent-id="${focusedRootNode.id}"]`).forEach(node => {
        if (node.style.display !== 'none') {
            children.push(node);
        }
    });
    children.sort((a, b) => {
        const aId = parseInt(a.id.split('-').pop());
        const bId = parseInt(b.id.split('-').pop());
        return aId - bId;
    });
    
    let currentMaxBottom = 0;
    const parentTop = getNodeTop(focusedRootNode); 

    children.forEach((childNode, index) => {
        const oldTop = getNodeTop(childNode);
        let newTop;
        if (index === 0) {
            newTop = parentTop;
        } else {
            newTop = currentMaxBottom + 20; 
        }
        const deltaY = newTop - oldTop;
        if (deltaY !== 0) {
            const subtreeNodes = getSubtreeNodes(childNode);
            subtreeNodes.forEach(node => {
                node.style.top = (getNodeTop(node) + deltaY) + 'px';
            });
        }
        currentMaxBottom = getSubtreeMaxBottom(childNode);
    });
    
    requestAnimationFrame(updateAllLines);
}

// --- API Call Function (Uses Backend) ---
async function callGeminiAPI(prompt, context, attachment = null) {
    const model = localStorage.getItem('gemini_model') || 'gemini-2.0-flash-exp';
    
    let fullPrompt = `Context: "${context}"\n\nUser Prompt: ${prompt}\n\nPlease provide a concise and helpful response. With thinking steps that you do behind the scene`;
    
    const parts = [{ text: fullPrompt }];
    
    if (attachment) {
        parts.push({
            inline_data: {
                mime_type: attachment.mimeType,
                data: attachment.data
            }
        });
    }

    try {
        const backend = (window && window.location && window.location.hostname === 'localhost') ? 'http://127.0.0.1:8000' : '';
        const response = await fetch(`${backend}/api/gemini-map/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                model: model,
                contents: [{ role: 'user', parts: parts }]
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            return `Error: ${errorData.detail || response.statusText}`;
        }

        const data = await response.json();
        const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
        return text || "Error: No response text found.";

    } catch (e) {
        return `Error: ${e.message}`;
    }
}

async function createBranchNode(parentNode, highlightedText, newPromptText, attachment = null) {
    const parentTop = getNodeTop(parentNode);
    const parentLeft = getNodeLeft(parentNode);
    const parentWidth = parentNode.offsetWidth;
    const parentId = parentNode.id;
    
    const newNodeX = parentLeft + parentWidth + 100;
    let newNodeY;

    const currentRootId = viewHistory[viewHistory.length - 1];
    
    if (parentId === currentRootId) {
        const siblingNodes = document.querySelectorAll(`.chat-node[data-parent-id="${parentId}"][style*="display: block"]`);
        let maxBottom = 0;
        
        if (siblingNodes.length === 0) {
            newNodeY = parentTop;
        } else {
            siblingNodes.forEach(node => {
                maxBottom = Math.max(maxBottom, getSubtreeMaxBottom(node));
            });
            newNodeY = maxBottom + 20;
        }
    } else {
        const siblingNodes = document.querySelectorAll(`.chat-node[data-parent-id="${parentId}"]`);
        let maxBottom = 0; 
        if (siblingNodes.length > 0) {
             siblingNodes.forEach(node => {
                maxBottom = Math.max(maxBottom, getSubtreeMaxBottom(node));
            });
        }
        if (maxBottom === 0) {
            newNodeY = parentTop;
        } else {
            newNodeY = maxBottom + 20;
        }
    }
    
    let childCounter = parseInt(parentNode.dataset.childCounter || 0) + 1;
    parentNode.dataset.childCounter = childCounter;
    let newNodeId = (parentId === 'A') ? 'A' + childCounter : parentId + '-' + childCounter;
    const parentBranchId = parentNode.dataset.branchId;
    let newBranchId = (parentId === 'A') ? newNodeId : parentBranchId; 
    
    let promptTitle, promptContent;
    
    let attachmentHTML = "";
    if (attachment) {
         if (attachment.mimeType.startsWith('image/')) {
             attachmentHTML = `<img src="data:${attachment.mimeType};base64,${attachment.data}" style="max-width: 100%; max-height: 150px; border-radius: 8px; margin-top: 8px; display: block;">`;
         } else {
             attachmentHTML = `<div style="background:#001100; padding:8px; border-radius:6px; margin-top:8px; font-size:0.8rem; color:#39ff14;">📎 ${attachment.name}</div>`;
         }
    }

    if (newPromptText && newPromptText.length > 0) {
        promptTitle = "You (follow-up)";
        promptContent = `
            <p class="prompt-context" style="font-size:0.8rem; color:#39ff14; opacity:0.7; margin-bottom:4px;">
                Context: "<em>${highlightedText.substring(0, 50)}${highlightedText.length > 50 ? '...' : ''}</em>"
            </p>
            <p class="prompt-text">${newPromptText}</p>
            ${attachmentHTML}
        `;
    } else {
        promptTitle = "You (highlighted)";
        promptContent = `<p class="prompt-text">${highlightedText}</p>${attachmentHTML}`;
    }

    const newNode = document.createElement('div');
    newNode.id = newNodeId;
    newNode.className = 'chat-node';
    newNode.style.top = `${newNodeY}px`;
    newNode.style.left = `${newNodeX}px`;
    newNode.dataset.branchId = newBranchId;
    newNode.dataset.childCounter = "0";
    newNode.dataset.parentId = parentId;
    newNode.dataset.context = encodeURIComponent(highlightedText);

    newNode.innerHTML = `
        <button class="node-btn node-collapse-btn" title="Collapse/Expand Branch">-</button>
        <button class="node-btn node-root-btn" title="Focus on this node" data-node-id="${newNodeId}">◉</button>
        <button class="node-btn node-remove-btn" title="Remove Node">×</button>

        <div class="node-content-wrapper">
            <div class="node-prompt">
                <p>${promptTitle}</p>
                ${promptContent}
            </div>
            <div class="node-response" id="response-${newNodeId}">
                <p>Gemini:</p>
                <div class="node-response-content">Generating...</div>
            </div>
        </div>

        <div class="node-reprompt-form" style="display:none">
            <textarea class="reprompt-input" placeholder="Enter new prompt..."></textarea>
            <div class="reprompt-actions">
                <button class="confirm-reprompt">Generate</button>
                <button class="cancel-reprompt">Cancel</button>
            </div>
        </div>

        <div class="node-quick-branch">
            <input type="text" class="quick-branch-input" placeholder="Ask follow-up (uses full node context)...">
            <button class="quick-branch-btn">Send</button>
        </div>

        <div class="node-footer">
            <button class="node-action-btn reprompt-btn">Re-prompt</button>
            <button class="node-action-btn undo-btn" style="display:none">Undo</button>
        </div>
    `;
    
    canvas.appendChild(newNode);
    
    if (currentRootId === 'A') {
        runReflow(newNode);
    } else {
        reflowFocusedView(document.getElementById(currentRootId));
    }

    panToNode(newNode);

    const apiPrompt = newPromptText || "Elaborate on this.";
    const fullParentText = parentNode.querySelector('.node-response-content') ? parentNode.querySelector('.node-response-content').innerText : "";
    const combinedContext = `Full Context of Parent Node:\n"${fullParentText}"\n\nSpecific Highlighted Text:\n"${highlightedText}"`;

    const responseText = await callGeminiAPI(apiPrompt, combinedContext, attachment);
    
    const formattedText = responseText
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');

    const responseContainer = document.getElementById(`response-${newNodeId}`);
    if(responseContainer) {
        const contentEl = responseContainer.querySelector('.node-response-content');
        contentEl.innerHTML = formattedText;
        
        if (window.renderMathInElement) {
            renderMathInElement(contentEl, {
                delimiters: [
                    {left: '$$', right: '$$', display: true},
                    {left: '$', right: '$', display: false},
                    {left: '\\(', right: '\\)', display: false},
                    {left: '\\[', right: '\\]', display: true}
                ],
                throwOnError : false
            });
        }
    }
    
    if (currentRootId === 'A') {
        runReflow(newNode);
    } else {
        reflowFocusedView(document.getElementById(currentRootId));
    }
} 

function removeNode(nodeEl) {
    const parentId = nodeEl.dataset.parentId;
    const parentNode = document.getElementById(parentId);
    const descendants = getSubtreeNodes(nodeEl);
    descendants.forEach(node => node.remove());
    if (parentNode) {
        const currentRootId = viewHistory[viewHistory.length - 1];
        if (currentRootId === 'A') {
            runReflow(parentNode);
        } else {
            reflowFocusedView(document.getElementById(currentRootId));
        }
    }
    requestAnimationFrame(updateAllLines);
}

// --- Start Screen Logic ---
startBtn.addEventListener('click', async () => {
    const prompt = startPromptInput.value.trim();
    if (!prompt) return;
    
    startBtn.disabled = true;
    startBtn.textContent = "Generating...";
    
    let attachment = null;
    if (startFileInput.files.length > 0) {
        try {
            attachment = await fileToBase64(startFileInput.files[0]);
        } catch (e) {
            console.error("File read error:", e);
        }
    }

    try {
        await createRootNode(prompt, attachment);
        startScreen.style.display = 'none';
    } catch (error) {
        console.error("Error creating root node:", error);
        startBtn.disabled = false;
        startBtn.textContent = "Start Mapping";
        alert("Error creating map: " + error.message);
    }
});

async function createRootNode(promptText, attachment = null) {
     const newNodeId = 'A';
     const newNode = document.createElement('div');
     newNode.id = newNodeId;
     newNode.className = 'chat-node';
     newNode.style.top = '150px';
     newNode.style.left = '100px';
     newNode.dataset.branchId = 'A';
     newNode.dataset.childCounter = "0";
     newNode.dataset.parentId = "";
     newNode.dataset.context = encodeURIComponent("Start of conversation");

     let attachmentHTML = "";
     if (attachment) {
         if (attachment.mimeType.startsWith('image/')) {
             attachmentHTML = `<img src="data:${attachment.mimeType};base64,${attachment.data}" style="max-width: 100%; max-height: 150px; border-radius: 8px; margin-top: 8px; display: block;">`;
         } else {
             attachmentHTML = `<div style="background:#001100; padding:8px; border-radius:6px; margin-top:8px; font-size:0.8rem; color:#39ff14;">📎 ${attachment.name}</div>`;
         }
     }

     newNode.innerHTML = `
        <button class="node-btn node-collapse-btn" title="Collapse/Expand Branch">-</button>
        <button class="node-btn node-root-btn" title="Focus on this node" data-node-id="${newNodeId}">◉</button>
        <button class="node-btn node-remove-btn" title="Remove Node">×</button>

        <div class="node-content-wrapper">
            <div class="node-prompt">
                <p>You (Start)</p>
                <p class="prompt-text">${promptText}</p>
                ${attachmentHTML}
            </div>
            <div class="node-response" id="response-${newNodeId}">
                <p>Gemini:</p>
                <div class="node-response-content">Generating...</div>
            </div>
        </div>

        <div class="node-reprompt-form" style="display:none">
            <textarea class="reprompt-input" placeholder="Enter new prompt..."></textarea>
            <div class="reprompt-actions">
                <button class="confirm-reprompt">Generate</button>
                <button class="cancel-reprompt">Cancel</button>
            </div>
        </div>

        <div class="node-quick-branch">
            <input type="text" class="quick-branch-input" placeholder="Ask follow-up (uses full node context)...">
            <button class="quick-branch-btn">Send</button>
        </div>

        <div class="node-footer">
            <button class="node-action-btn reprompt-btn">Re-prompt</button>
            <button class="node-action-btn undo-btn" style="display:none">Undo</button>
        </div>
    `;
    
    canvas.appendChild(newNode);
    viewHistory = ['A'];
    renderView();

    const responseText = await callGeminiAPI(promptText, "Start of conversation", attachment);
    
    const formattedText = responseText
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');

    const responseContainer = document.getElementById(`response-${newNodeId}`);
    if(responseContainer) {
        const contentEl = responseContainer.querySelector('.node-response-content');
        contentEl.innerHTML = formattedText;

        if (window.renderMathInElement) {
            renderMathInElement(contentEl, {
                delimiters: [
                    {left: '$$', right: '$$', display: true},
                    {left: '$', right: '$', display: false},
                    {left: '\\(', right: '\\)', display: false},
                    {left: '\\[', right: '\\]', display: true}
                ],
                throwOnError : false
            });
        }
    }
    
    runReflow(newNode);
}

// --- File Input Listeners ---
startFileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        startFileName.textContent = e.target.files[0].name;
    } else {
        startFileName.textContent = "";
    }
});

popupFileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        popupFileName.textContent = e.target.files[0].name;
    } else {
        popupFileName.textContent = "";
    }
});

// --- Helper: File to Base64 ---
function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => {
            const base64String = reader.result.split(',')[1];
            resolve({
                mimeType: file.type,
                data: base64String,
                name: file.name
            });
        };
        reader.onerror = error => reject(error);
    });
}

// --- Reprompt Event Listeners ---
canvas.addEventListener('click', async (e) => {
    if (e.target.classList.contains('quick-branch-btn')) {
        const node = e.target.closest('.chat-node');
        const input = node.querySelector('.quick-branch-input');
        const prompt = input.value.trim();
        if (!prompt) return;
        const responseContent = node.querySelector('.node-response-content');
        const fullText = responseContent ? responseContent.innerText : "";
        await createBranchNode(node, fullText, prompt);
        input.value = "";
    }

    if (e.target.classList.contains('reprompt-btn')) {
        const node = e.target.closest('.chat-node');
        const promptTextEl = node.querySelector('.prompt-text');
        const currentPrompt = promptTextEl ? promptTextEl.textContent : "";
        node.querySelector('.node-content-wrapper').style.display = 'none';
        node.querySelector('.node-reprompt-form').style.display = 'block';
        node.querySelector('.reprompt-input').value = currentPrompt;
        node.querySelector('.node-footer').style.display = 'none'; 
    }

    if (e.target.classList.contains('cancel-reprompt')) {
        const node = e.target.closest('.chat-node');
        node.querySelector('.node-reprompt-form').style.display = 'none';
        node.querySelector('.node-content-wrapper').style.display = 'block';
        node.querySelector('.node-footer').style.display = 'flex';
    }

    if (e.target.classList.contains('confirm-reprompt')) {
        const node = e.target.closest('.chat-node');
        const input = node.querySelector('.reprompt-input');
        const newPrompt = input.value.trim();
        if (!newPrompt) return;

        const contentWrapper = node.querySelector('.node-content-wrapper');
        const previousState = {
            html: contentWrapper.innerHTML
        };
        node.dataset.previousState = JSON.stringify(previousState);

        node.querySelector('.node-reprompt-form').style.display = 'none';
        contentWrapper.style.display = 'block';
        node.querySelector('.node-footer').style.display = 'flex';
        
        const promptTextEl = node.querySelector('.prompt-text');
        if (promptTextEl) promptTextEl.textContent = newPrompt;
        
        const responseContentEl = node.querySelector('.node-response-content');
        responseContentEl.textContent = "Regenerating...";

        const context = decodeURIComponent(node.dataset.context || "");
        let apiContext = context;
        if (node.dataset.parentId) {
             const parentNode = document.getElementById(node.dataset.parentId);
             if (parentNode) {
                const fullParentText = parentNode.querySelector('.node-response-content') ? parentNode.querySelector('.node-response-content').innerText : "";
                apiContext = `Full Context of Parent Node:\n"${fullParentText}"\n\nSpecific Highlighted Text:\n"${context}"`;
             }
        }

        const responseText = await callGeminiAPI(newPrompt, apiContext, null); 
        
        const formattedText = responseText
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');
        
        responseContentEl.innerHTML = formattedText;

        if (window.renderMathInElement) {
            renderMathInElement(responseContentEl, {
                delimiters: [
                    {left: '$$', right: '$$', display: true},
                    {left: '$', right: '$', display: false},
                    {left: '\\(', right: '\\)', display: false},
                    {left: '\\[', right: '\\]', display: true}
                ],
                throwOnError : false
            });
        }

        node.querySelector('.undo-btn').style.display = 'inline-block';
        
        const currentRootId = viewHistory[viewHistory.length - 1];
        if (currentRootId === 'A') {
            runReflow(node);
        } else {
            reflowFocusedView(document.getElementById(currentRootId));
        }
    }

    if (e.target.classList.contains('undo-btn')) {
        const node = e.target.closest('.chat-node');
        if (node.dataset.previousState) {
            const state = JSON.parse(node.dataset.previousState);
            node.querySelector('.node-content-wrapper').innerHTML = state.html;
            node.querySelector('.undo-btn').style.display = 'none';
            delete node.dataset.previousState;
            
            const currentRootId = viewHistory[viewHistory.length - 1];
            if (currentRootId === 'A') {
                runReflow(node);
            } else {
                reflowFocusedView(document.getElementById(currentRootId));
            }
        }
    }
});

canvas.addEventListener('keydown', async (e) => {
    if (e.target.classList.contains('quick-branch-input') && e.key === 'Enter') {
        const node = e.target.closest('.chat-node');
        const input = e.target;
        const prompt = input.value.trim();
        if (!prompt) return;
        const responseContent = node.querySelector('.node-response-content');
        const fullText = responseContent ? responseContent.innerText : "";
        await createBranchNode(node, fullText, prompt);
        input.value = "";
    }
});

// --- Initial Load ---
document.addEventListener('DOMContentLoaded', () => {
    renderView();
});

console.log("Gemini Map script loaded");

