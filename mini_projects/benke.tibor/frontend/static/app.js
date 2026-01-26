const chatMessages = document.getElementById('chatMessages');
const queryForm = document.getElementById('queryForm');
const queryInput = document.getElementById('queryInput');
const userIdInput = document.getElementById('userIdInput');
const sessionIdInput = document.getElementById('sessionIdInput');
const sendBtn = document.getElementById('sendBtn');
const resetBtn = document.getElementById('resetBtn');
const debugSession = document.getElementById('debugSession');
const debugDomain = document.getElementById('debugDomain');
const debugCitations = document.getElementById('debugCitations');
const debugChunkCount = document.getElementById('debugChunkCount');
const debugMaxScore = document.getElementById('debugMaxScore');
const debugLatency = document.getElementById('debugLatency');
const debugRequestCost = document.getElementById('debugRequestCost');
const debugWorkflow = document.getElementById('debugWorkflow');
const debugNextStep = document.getElementById('debugNextStep');
const debugRequestJson = document.getElementById('debugRequestJson');
const debugResponseJson = document.getElementById('debugResponseJson');
const debugRagContext = document.getElementById('debugRagContext');
const debugLlmPrompt = document.getElementById('debugLlmPrompt');
const debugLlmResponse = document.getElementById('debugLlmResponse');
let typingEl = null;

function clearEmptyState() {
    const emptyState = chatMessages.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }
}

function showTyping() {
    clearEmptyState();
    if (typingEl) return;
    const wrapper = document.createElement('div');
    wrapper.className = 'message bot';
    wrapper.id = 'typing-indicator';
    wrapper.innerHTML = `
        <div class="message-content">
            <div class="typing">
                <span class="dot"></span><span class="dot"></span><span class="dot"></span>
            </div>
        </div>
    `;
    chatMessages.appendChild(wrapper);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    typingEl = wrapper;
}

function hideTyping() {
    if (typingEl && typingEl.parentNode) {
        typingEl.parentNode.removeChild(typingEl);
    }
    typingEl = null;
}

function addMessage(content, type = 'info', citations = null, originalQuery = null, citationObjects = null, domain = null, sessionId = null) {
    clearEmptyState();

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;

    let html = `<div class="message-content">`;
    
    // Add dual refresh buttons for bot messages (top-right corner)
    if (type === 'bot' && originalQuery) {
        const escapedQuery = escapeHtml(originalQuery).replace(/'/g, "\\'");
        html += `
            <div class="refresh-buttons">
                <button class="refresh-btn refresh-fast" title="⚡ Gyors újragenerálás (cache)" onclick="refreshQuery('${escapedQuery}', true)">⚡</button>
                <button class="refresh-btn refresh-full" title="🔄 Teljes újrakeresés (RAG)" onclick="refreshQuery('${escapedQuery}', false)">🔄</button>
            </div>
        `;
    }
    
    html += formatMessage(content);

    // Always show feedback for bot responses
    if (type === 'bot' && domain && sessionId) {
        const responseId = `response-${sessionId}-${Date.now()}`;
        
        // Display citations if available
        if (citationObjects && citationObjects.length > 0) {
            html += `<div class="citations-container">`;
            html += `<div class="citations-header">`;
            html += `<h4 class="citations-title">📚 Felhasznált források (${citationObjects.length})</h4>`;
            html += `</div>`;
            
            // Display citations as enhanced cards with score and metadata
            citationObjects.forEach((citation, index) => {
                const title = citation.title || 'Ismeretlen dokumentum';
                const url = citation.url || null;
                const score = citation.score || 0;
                const scorePercent = Math.round(score * 100);
                const sectionId = citation.section_id || null;
                const docId = citation.doc_id || null;
                
                html += `<div class="citation-card">`;
                html += `  <div class="citation-header">`;
                html += `    <div class="citation-title">`;
                
                if (url) {
                    html += `<a href="${url}" target="_blank">🔗 ${escapeHtml(title)}</a>`;
                } else {
                    html += `📄 ${escapeHtml(title)}`;
                }
                
                html += `    </div>`;
                html += `    <div class="citation-score">${scorePercent}%</div>`;
                html += `  </div>`;
                
                // Display metadata (section_id, doc_id)
                if (sectionId || docId) {
                    html += `  <div class="citation-metadata">`;
                    if (sectionId) {
                        html += `    <span class="citation-meta-item">`;
                        html += `      <span class="citation-meta-icon">🔖</span>`;
                        html += `      <span>${escapeHtml(sectionId)}</span>`;
                        html += `    </span>`;
                    }
                    if (docId) {
                        html += `    <span class="citation-meta-item">`;
                        html += `      <span class="citation-meta-icon">🆔</span>`;
                        html += `      <span>${escapeHtml(docId)}</span>`;
                        html += `    </span>`;
                    }
                    html += `  </div>`;
                }
                
                html += `</div>`;
            });
        } else {
            // No citations - show info message
            html += `<div class="no-citations-container">`;
            html += `<p class="no-citations-text">💡 Ez a válasz általános tudáson alapul, nincs konkrét dokumentum forrás.</p>`;
        }
        
        // Single feedback for entire response (always shown)
        html += `<div class="response-feedback">`;
        html += `<span class="feedback-label">Hasznos volt a válasz?</span>`;
        html += `<div class="feedback-buttons">`;
        
        const escapedQuery = escapeHtml(originalQuery).replace(/'/g, "\\'");
        
        html += `
            <button class="feedback-btn like-btn" onclick="submitResponseFeedback(this, '${responseId}', '${domain}', '${sessionId}', '${escapedQuery}', 'like')" title="Igen, segített">
                👍 Igen
            </button>
            <button class="feedback-btn dislike-btn" onclick="submitResponseFeedback(this, '${responseId}', '${domain}', '${sessionId}', '${escapedQuery}', 'dislike')" title="Nem volt releváns">
                👎 Nem
            </button>
        `;
        html += `</div>`;
        html += `</div>`;
        
        if (citationObjects && citationObjects.length > 0) {
            html += `</div>`; // Close citations-container
        } else {
            html += `</div>`; // Close no-citations-container
        }
    } else if (citations && citations.length > 0) {
        // Fallback for simple citation list (old style)
        html += `<div class="citations">📎 Források: ${citations.join(', ')}</div>`;
    }

    html += `</div>`;
    
    messageDiv.innerHTML = html;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

function formatMessage(text) {
    // Escape HTML first
    let formatted = escapeHtml(text);
    
    // Convert Markdown-style headers to HTML
    formatted = formatted.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    formatted = formatted.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    formatted = formatted.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    
    // Convert **bold** to <strong>
    formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    
    // Convert bullet points (- item) to <ul><li>
    formatted = formatted.replace(/^- (.+)$/gm, '<li>$1</li>');
    formatted = formatted.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
    
    // Convert numbered lists (1. item) to <ol><li>
    formatted = formatted.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
    
    // Convert line breaks to <br>
    formatted = formatted.replace(/\n/g, '<br>');
    
    return formatted;
}

function askQuestion(question) {
    clearEmptyState();
    queryInput.value = question;
    queryInput.focus();
    // Trigger submit
    queryForm.dispatchEvent(new Event('submit'));
}

async function refreshQuery(question, useCache = true) {
    const userId = userIdInput.value.trim() || 'demo_user';
    const sessionId = sessionIdInput.value.trim() || 'demo_session';
    
    showTyping();
    sendBtn.disabled = true;
    
    try {
        let endpoint, body;
        
        if (useCache) {
            // Cached regeneration (FAST ⚡ - skips intent + RAG)
            endpoint = 'http://localhost:8001/api/regenerate/';
            body = {
                session_id: sessionId,
                query: question,
                user_id: userId
            };
        } else {
            // Full re-execution (SLOW 🔄 - full 4-node pipeline)
            endpoint = 'http://localhost:8001/api/query/';
            body = {
                user_id: userId,
                session_id: sessionId,
                query: question,
                organisation: 'Demo Org'
            };
        }
        
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        
        if (!response.ok) {
            const error = await response.json();
            hideTyping();
            addMessage(`❌ Újragenerálás hiba: ${error.error || 'Ismeretlen hiba'}`, 'error');
            return;
        }
        
        const raw = await response.json();
        const payload = raw.data ?? raw;
        
        // Deduplicate citation objects by citation_id (or title if no ID)
        const uniqueCitationObjects = payload.citations ? 
            Array.from(
                new Map(
                    payload.citations.map(c => [c.citation_id || c.title || c.source, c])
                ).values()
            ) : [];
        
        // Extract unique titles for legacy citations array
        const citations = uniqueCitationObjects
            .map(c => c.title || c.source || null)
            .filter(s => s && s !== 'Unknown' && s !== 'Unknown Document');
        
        // Update debug panel
        debugSession.textContent = sessionId;
        debugDomain.textContent = payload.domain || 'general';
        
        // Chunk count and max score
        const chunkCount = uniqueCitationObjects.length;
        debugChunkCount.textContent = chunkCount;
        
        if (payload.telemetry) {
            debugMaxScore.textContent = payload.telemetry.max_similarity_score || '-';
            debugLatency.textContent = payload.telemetry.total_latency_ms ? `${payload.telemetry.total_latency_ms}ms` : '-';
            
            // Update Request Cost from LLM telemetry
            if (payload.telemetry.llm && payload.telemetry.llm.total_cost_usd !== undefined) {
                const cost = payload.telemetry.llm.total_cost_usd;
                debugRequestCost.textContent = `$${cost.toFixed(6)}`;
            } else {
                debugRequestCost.textContent = '-';
            }
        } else if (uniqueCitationObjects.length > 0) {
            const maxScore = Math.max(...uniqueCitationObjects.map(c => c.score || 0));
            debugMaxScore.textContent = maxScore.toFixed(3);
            debugRequestCost.textContent = '-';
        } else {
            debugMaxScore.textContent = '-';
            debugLatency.textContent = '-';
            debugRequestCost.textContent = '-';
        }
        
        if (payload.workflow) {
            const action = payload.workflow.action || 'none';
            const status = payload.workflow.status || '';
            debugWorkflow.textContent = status ? `${action} (${status})` : action;
            debugNextStep.textContent = payload.workflow.next_step || payload.workflow.type || '-';
        } else {
            debugWorkflow.textContent = 'none';
            debugNextStep.textContent = '-';
        }
        
        // Update JSON debug info
        if (payload.telemetry && payload.telemetry.request) {
            debugRequestJson.textContent = JSON.stringify(payload.telemetry.request, null, 2);
        } else {
            debugRequestJson.textContent = '-';
        }
        if (payload.telemetry && payload.telemetry.response) {
            debugResponseJson.textContent = JSON.stringify(payload.telemetry.response, null, 2);
        } else {
            debugResponseJson.textContent = '-';
        }
        if (payload.telemetry && payload.telemetry.rag && payload.telemetry.rag.context) {
            debugRagContext.textContent = payload.telemetry.rag.context;
        } else {
            debugRagContext.textContent = 'No RAG context (general domain or no retrieval)';
        }
        if (payload.telemetry && payload.telemetry.llm && payload.telemetry.llm.prompt) {
            debugLlmPrompt.textContent = payload.telemetry.llm.prompt;
        } else {
            debugLlmPrompt.textContent = '-';
        }
        if (payload.telemetry && payload.telemetry.llm && payload.telemetry.llm.response) {
            debugLlmResponse.textContent = payload.telemetry.llm.response;
        } else {
            debugLlmResponse.textContent = '-';
        }
        
        hideTyping();
        
        // Add regeneration badge
        let answerText = payload.answer || 'Sajnos nem tudtam válaszolni.';
        if (payload.regenerated) {
            answerText = `⚡ **Gyors újragenerálás** (cached context)\n\n${answerText}`;
        }
        
        addMessage(
            answerText,
            'bot',
            citations,
            question,
            uniqueCitationObjects,
            payload.domain,
            sessionId
        );
        
    } catch (error) {
        console.error('Refresh error:', error);
        hideTyping();
        addMessage('❌ Hálózati hiba az újragenerálás során.', 'error');
    } finally {
        sendBtn.disabled = false;
    }
}

// Track last IT response for Jira ticket context
let lastITContext = null;

queryForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const query = queryInput.value.trim();
    const userId = userIdInput.value.trim() || 'demo_user';
    const sessionId = sessionIdInput.value.trim() || 'demo_session';

    if (!query) return;

    // Check if user is responding to Jira ticket offer (yes/no)
    const normalizedQuery = query.toLowerCase().trim();
    const isJiraDecline = lastITContext && (
        normalizedQuery === 'nem' ||
        normalizedQuery === 'no' ||
        normalizedQuery.includes('mégsem') ||
        normalizedQuery.includes('nem kell') ||
        normalizedQuery.includes('nem kérem') ||
        (normalizedQuery.includes('nem') && query.split(' ').length <= 3)
    );
    const isJiraConfirmation = lastITContext && 
        (normalizedQuery === 'igen' || 
         normalizedQuery === 'yes' ||
         normalizedQuery === 'ok' ||
         normalizedQuery === 'i' ||
         (normalizedQuery.includes('igen') && query.split(' ').length <= 3));
    
    if (isJiraDecline) {
        addMessage(query, 'user');
        if (lastITContext) {
            addMessage('Köszönöm a visszajelzést, nem hozok létre Jira ticketet. Szólj, ha mégis szeretnéd, vagy írd le, miben segíthetek még.', 'bot');
        } else {
            addMessage('Rendben, nem hozok létre ticketet. Miben segíthetek helyette?', 'bot');
        }
        queryInput.value = '';
        lastITContext = null;
        return;
    }
    
    if (isJiraConfirmation) {
        console.log('🎫 Jira confirmation detected, creating ticket...');
        addMessage(query, 'user');
        queryInput.value = '';
        
        // Create Jira ticket with stored context
        await createJiraTicket(lastITContext.query, lastITContext.answer);
        
        // Clear context after use
        lastITContext = null;
        return;
    }

    addMessage(query, 'user');
    queryInput.value = '';
    sendBtn.disabled = true;
    showTyping();

    try {
        // Set 120 second timeout for complex workflow queries
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 120000);

        const response = await fetch('http://localhost:8001/api/query/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                session_id: sessionId,
                query: query,
                organisation: 'Demo Org'
            }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            const error = await response.json();
            addMessage(`❌ Hiba: ${error.error || 'Ismeretlen hiba'}`, 'error');
            return;
        }

        const raw = await response.json();
        const payload = raw.data ?? raw; // backend wraps in { success, data }

        // Deduplicate citation objects by title (so IT Policy appears only once)
        const uniqueCitationObjects = payload.citations ? 
            Array.from(
                new Map(
                    payload.citations.map(c => [c.title || c.citation_id || c.source, c])
                ).values()
            ) : [];
        
        // Extract unique titles for legacy citations array
        const citations = uniqueCitationObjects
            .map(c => c.title || c.source || null)
            .filter(s => s && s !== 'Unknown' && s !== 'Unknown Document');

        // Update debug panel
        debugSession.textContent = sessionId;
        debugDomain.textContent = payload.domain || 'general';
        
        // Chunk count and max score
        const chunkCount = uniqueCitationObjects.length;
        debugChunkCount.textContent = chunkCount;
        
        if (payload.telemetry) {
            debugMaxScore.textContent = payload.telemetry.max_similarity_score || '-';
            debugLatency.textContent = payload.telemetry.total_latency_ms ? `${payload.telemetry.total_latency_ms}ms` : '-';
            
            // Update Request Cost from LLM telemetry
            if (payload.telemetry.llm && payload.telemetry.llm.total_cost_usd !== undefined) {
                const cost = payload.telemetry.llm.total_cost_usd;
                debugRequestCost.textContent = `$${cost.toFixed(6)}`;
            } else {
                debugRequestCost.textContent = '-';
            }
        } else if (uniqueCitationObjects.length > 0) {
            const maxScore = Math.max(...uniqueCitationObjects.map(c => c.score || 0));
            debugMaxScore.textContent = maxScore.toFixed(3);
            debugRequestCost.textContent = '-';
        } else {
            debugMaxScore.textContent = '-';
            debugLatency.textContent = '-';
            debugRequestCost.textContent = '-';
        }
        
        if (payload.workflow) {
            const action = payload.workflow.action || 'none';
            const status = payload.workflow.status || '';
            debugWorkflow.textContent = status ? `${action} (${status})` : action;
            debugNextStep.textContent = payload.workflow.next_step || payload.workflow.type || '-';
        } else {
            debugWorkflow.textContent = 'none';
            debugNextStep.textContent = '-';
        }
        
        // Update JSON debug info
        if (payload.telemetry && payload.telemetry.request) {
            debugRequestJson.textContent = JSON.stringify(payload.telemetry.request, null, 2);
        } else {
            debugRequestJson.textContent = '-';
        }
        if (payload.telemetry && payload.telemetry.response) {
            debugResponseJson.textContent = JSON.stringify(payload.telemetry.response, null, 2);
        } else {
            debugResponseJson.textContent = '-';
        }
        if (payload.telemetry && payload.telemetry.rag && payload.telemetry.rag.context) {
            debugRagContext.textContent = payload.telemetry.rag.context;
        } else {
            debugRagContext.textContent = 'No RAG context (general domain or no retrieval)';
        }
        if (payload.telemetry && payload.telemetry.llm && payload.telemetry.llm.prompt) {
            debugLlmPrompt.textContent = payload.telemetry.llm.prompt;
        } else {
            debugLlmPrompt.textContent = '-';
        }
        if (payload.telemetry && payload.telemetry.llm && payload.telemetry.llm.response) {
            debugLlmResponse.textContent = payload.telemetry.llm.response;
        } else {
            debugLlmResponse.textContent = '-';
        }

        hideTyping();
        addMessage(
            payload.answer || 'Sajnos nem tudtam válaszolni.',
            'bot',
            citations,
            query,  // Pass original query for refresh button
            uniqueCitationObjects,  // Pass deduplicated citation objects
            payload.domain,  // Pass domain
            sessionId  // Pass session ID
        );
        
        // Store context for potential Jira ticket creation (independent of domain)
        if (payload.answer) {
            const lowerAns = payload.answer.toLowerCase();
            const hasJiraOffer = lowerAns.includes('jira') ||
                                 lowerAns.includes('ticket') ||
                                 payload.answer.includes('📋') ||
                                 lowerAns.includes('szeretnéd') ||
                                 lowerAns.includes('támogatási jegy') ||
                                 lowerAns.includes('support ticket') ||
                                 lowerAns.includes('hozzak létre') ||
                                 lowerAns.includes('létrehozzak');

            if (hasJiraOffer) {
                lastITContext = { query, answer: payload.answer };
                console.log('✅ Jira context stored for ticket flow:', lastITContext);
            } else {
                lastITContext = null;
            }
        } else {
            lastITContext = null;
        }

    } catch (error) {
        console.error('Fetch error:', error);
        hideTyping();
        
        if (error.name === 'AbortError') {
            addMessage('⏱️ A kérés túllépte a 120 másodperces időkorlátot. Próbáld meg újra vagy kapcsold be a gyors módot (USE_SIMPLE_PIPELINE=True).', 'error');
        } else {
            addMessage(`❌ Hálózati hiba: ${error.message}`, 'error');
        }
    } finally {
        sendBtn.disabled = false;
        queryInput.focus();
        hideTyping();
    }
});

// Submit response-level feedback (single feedback for entire answer)
async function submitResponseFeedback(buttonElement, responseId, domain, sessionId, queryText, feedbackType) {
    const userId = userIdInput.value.trim() || 'demo_user';
    
    try {
        const response = await fetch('http://localhost:8001/api/feedback/citation/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                citation_id: responseId,
                domain: domain,
                user_id: userId,
                session_id: sessionId,
                query_text: queryText,
                feedback_type: feedbackType,
                citation_rank: 0  // 0 = response-level feedback
            })
        });
        
        if (!response.ok) {
            console.error('Feedback submission failed:', await response.text());
            return;
        }
        
        const result = await response.json();
        console.log('✅ Feedback saved:', result);
        
        // Visual feedback - disable both buttons and show confirmation
        const feedbackContainer = buttonElement.closest('.response-feedback');
        if (feedbackContainer) {
            const buttons = feedbackContainer.querySelectorAll('.feedback-btn');
            buttons.forEach(btn => {
                btn.disabled = true;
                btn.classList.remove('active');
            });
            
            buttonElement.classList.add('active');
            
            // Show thank you message
            const label = feedbackContainer.querySelector('.feedback-label');
            if (label) {
                label.textContent = feedbackType === 'like' ? '✅ Köszönjük a visszajelzést!' : '📝 Köszönjük, dolgozunk a javításon!';
            }
        }

    } catch (error) {
        console.error('Feedback error:', error);
    }
}

// Submit citation feedback (kept for backward compatibility, but not used in new design)
async function submitFeedback(citationId, domain, sessionId, queryText, feedbackType, rank) {
    const userId = userIdInput.value.trim() || 'demo_user';
    
    try {
        const response = await fetch('http://localhost:8001/api/feedback/citation/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                citation_id: citationId,
                domain: domain,
                user_id: userId,
                session_id: sessionId,
                query_text: queryText,
                feedback_type: feedbackType,
                citation_rank: rank
            })
        });
        
        if (!response.ok) {
            console.error('Feedback submission failed:', await response.text());
            return;
        }
        
        const result = await response.json();
        console.log('✅ Feedback saved:', result);
        
        // Visual feedback - highlight the clicked button
        const citationCard = document.querySelector(`[data-citation-id="${citationId}"]`);
        if (citationCard) {
            const buttons = citationCard.querySelectorAll('.feedback-btn');
            buttons.forEach(btn => btn.classList.remove('active'));
            
            const clickedBtn = citationCard.querySelector(`.${feedbackType}-btn`);
            if (clickedBtn) {
                clickedBtn.classList.add('active');
                
                // Show temporary checkmark
                const originalText = clickedBtn.textContent;
                clickedBtn.textContent = feedbackType === 'like' ? '✅' : '❌';
                setTimeout(() => {
                    clickedBtn.textContent = originalText;
                }, 1000);
            }
        }
        
    } catch (error) {
        console.error('Feedback error:', error);
    }
}

// Reset chat to empty state
if (resetBtn) {
    resetBtn.addEventListener('click', () => {
        chatMessages.innerHTML = `
            <div class="empty-state">
                <h2>🤖 Üdvözöljük a KnowledgeRouter-ben!</h2>
                <p>Kérdezz meg bármit az alábbi doménekről. Az AI agent intelligensen felismeri és irányítja a kérdéseket.</p>
                
                <div class="example-questions">
                    <button class="example-btn" onclick="askQuestion('Szeretnék szabadságot igényelni október 3-4-re.')">HR: Szabadság igénylés</button>
                    <button class="example-btn" onclick="askQuestion('Nem működik a VPN-em, hogyan lehet megoldani?')">IT: VPN probléma</button>
                    <button class="example-btn" onclick="askQuestion('Mi a cégünk brand guideline-ja?')">Marketing: Brand guide</button>
                    <button class="example-btn" onclick="askQuestion('Mennyi pénz maradt a költségvetésből?')">Finance: Költségvetés</button>
                    <button class="example-btn" onclick="askQuestion('Mit kell tudni az alkalmazotti szerződésről?')">Legal: Szerződés</button>
                    <button class="example-btn" onclick="askQuestion('Milyen általános információk érdekelnek?')">General: Egyéb kérdés</button>
                </div>
            </div>
        `;
        queryInput.value = '';
        if (debugSession) debugSession.textContent = sessionIdInput.value;
        if (debugDomain) debugDomain.textContent = '-';
        if (debugChunkCount) debugChunkCount.textContent = '0';
        if (debugMaxScore) debugMaxScore.textContent = '-';
        if (debugLatency) debugLatency.textContent = '-';
        if (debugRequestCost) debugRequestCost.textContent = '-';
        if (debugWorkflow) debugWorkflow.textContent = 'none';
        if (debugNextStep) debugNextStep.textContent = '-';
        if (debugRequestJson) debugRequestJson.textContent = '-';
        if (debugResponseJson) debugResponseJson.textContent = '-';
        if (debugRagContext) debugRagContext.textContent = '-';
        if (debugLlmPrompt) debugLlmPrompt.textContent = '-';
        if (debugLlmResponse) debugLlmResponse.textContent = '-';
    });
}

// Initialize debug panel
if (debugSession && sessionIdInput) {
    debugSession.textContent = sessionIdInput.value;
}
if (queryInput) {
    queryInput.focus();
}
if (debugWorkflow) debugWorkflow.textContent = 'none';
if (debugNextStep) debugNextStep.textContent = '-';

// Debug panel toggle functionality
const debugToggle = document.getElementById('debugToggle');
const debugContent = document.getElementById('debugContent');
const debugPanel = document.getElementById('debugPanel');

if (debugToggle && debugContent && debugPanel) {
    // Load saved state from localStorage
    const isMinimized = localStorage.getItem('debugPanelMinimized') === 'true';
    if (isMinimized) {
        debugContent.classList.add('hidden');
        debugPanel.classList.add('minimized');
        debugToggle.textContent = '+';
    }
    
    debugToggle.addEventListener('click', () => {
        const isCurrentlyMinimized = debugContent.classList.contains('hidden');
        
        if (isCurrentlyMinimized) {
            // Expand
            debugContent.classList.remove('hidden');
            debugPanel.classList.remove('minimized');
            debugToggle.textContent = '−';
            localStorage.setItem('debugPanelMinimized', 'false');
        } else {
            // Minimize
            debugContent.classList.add('hidden');
            debugPanel.classList.add('minimized');
            debugToggle.textContent = '+';
            localStorage.setItem('debugPanelMinimized', 'true');
        }
    });
}

/**
 * Create Jira ticket for IT support.
 * Called when user confirms with "igen" response.
 */
async function createJiraTicket(query, answer) {
    try {
        addMessage('🎫 Jira ticket létrehozása folyamatban...', 'info');
        
        const response = await fetch('http://localhost:8001/api/jira/ticket/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                summary: `IT Support: ${query.substring(0, 80)}`,
                description: `Kérdés: ${query}\n\nBOT válasz:\n${answer}`,
                issue_type: 'Task',
                priority: 'Medium'
            }),
        });

        const data = await response.json();
        
        if (data.success) {
            const ticketUrl = data.ticket.url;
            const ticketKey = data.ticket.key;
            
            // Create a custom success message with clickable link
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message success';
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            contentDiv.innerHTML = `✅ Jira ticket sikeresen létrehozva: <a href="${ticketUrl}" target="_blank" style="color: #10a37f; font-weight: bold;">${ticketKey}</a>`;
            
            messageDiv.appendChild(contentDiv);
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        } else {
            addMessage(`❌ Hiba a Jira ticket létrehozásakor: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('Jira ticket creation error:', error);
        addMessage('❌ Hiba történt a ticket létrehozásakor.', 'error');
    }
}

/**
 * Fetch and display monitoring statistics from Prometheus metrics.
 * Parses Prometheus text format and extracts key metrics.
 */
async function fetchMonitoringStats() {
    try {
        const response = await fetch('http://localhost:8001/api/metrics/');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const metricsText = await response.text();
        
        // Parse Prometheus metrics (simple text parsing)
        const lines = metricsText.split('\n');
        const metrics = {};
        
        lines.forEach(line => {
            if (line.startsWith('#') || !line.trim()) return;
            
            // Extract metric name and value - improved regex for labels
            const match = line.match(/^([a-z_]+)(?:\{[^}]+\})?\s+([0-9.eE+-]+)/);
            if (match) {
                const metricName = match[1];
                const value = parseFloat(match[2]);
                
                if (!metrics[metricName]) {
                    metrics[metricName] = [];
                }
                metrics[metricName].push(value);
            }
        });
        
        // Calculate stats
        const totalRequests = metrics['knowledgerouter_requests_total'] 
            ? metrics['knowledgerouter_requests_total'].reduce((a, b) => a + b, 0) 
            : 0;
        
        const cacheHits = metrics['knowledgerouter_cache_hits_total']
            ? metrics['knowledgerouter_cache_hits_total'].reduce((a, b) => a + b, 0)
            : 0;
        
        const cacheMisses = metrics['knowledgerouter_cache_misses_total']
            ? metrics['knowledgerouter_cache_misses_total'].reduce((a, b) => a + b, 0)
            : 0;
        
        const cacheHitRate = (cacheHits + cacheMisses) > 0
            ? ((cacheHits / (cacheHits + cacheMisses)) * 100).toFixed(1)
            : '0.0';
        
        const llmCalls = metrics['knowledgerouter_llm_calls_total']
            ? metrics['knowledgerouter_llm_calls_total'].reduce((a, b) => a + b, 0)
            : 0;
        
        const activeRequests = metrics['knowledgerouter_active_requests']
            ? Math.max(...metrics['knowledgerouter_active_requests'])
            : 0;
        
        const errors = metrics['knowledgerouter_errors_total']
            ? metrics['knowledgerouter_errors_total'].reduce((a, b) => a + b, 0)
            : 0;
        
        // Latency calculation from histogram _count and _sum metrics
        const latencyCount = metrics['knowledgerouter_latency_seconds_count']
            ? metrics['knowledgerouter_latency_seconds_count'].reduce((a, b) => a + b, 0)
            : 0;
        
        const latencySum = metrics['knowledgerouter_latency_seconds_sum']
            ? metrics['knowledgerouter_latency_seconds_sum'].reduce((a, b) => a + b, 0)
            : 0;
        
        const avgLatency = latencyCount > 0
            ? ((latencySum / latencyCount) * 1000).toFixed(0) + 'ms'
            : '-';
        
        // Cost calculation
        const totalCost = metrics['knowledgerouter_llm_cost_total']
            ? metrics['knowledgerouter_llm_cost_total'].reduce((a, b) => a + b, 0)
            : 0;
        
        const avgCost = totalRequests > 0
            ? (totalCost / totalRequests).toFixed(4)
            : '0.0000';
        
        // Update UI
        document.getElementById('monitorTotalRequests').textContent = totalRequests;
        document.getElementById('monitorCacheHitRate').textContent = cacheHitRate + '%';
        document.getElementById('monitorAvgLatency').textContent = avgLatency;
        document.getElementById('monitorLlmCalls').textContent = llmCalls;
        document.getElementById('monitorActiveRequests').textContent = activeRequests;
        document.getElementById('monitorErrors').textContent = errors;
        document.getElementById('monitorTotalCost').textContent = '$' + totalCost.toFixed(4);
        document.getElementById('monitorAvgCost').textContent = '$' + avgCost;
        
    } catch (error) {
        console.error('Failed to fetch monitoring stats:', error);
        document.getElementById('monitorTotalRequests').textContent = 'Error';
        document.getElementById('monitorCacheHitRate').textContent = 'Error';
        document.getElementById('monitorAvgLatency').textContent = 'Error';
        document.getElementById('monitorLlmCalls').textContent = 'Error';
        document.getElementById('monitorActiveRequests').textContent = 'Error';
        document.getElementById('monitorErrors').textContent = 'Error';
        document.getElementById('monitorTotalCost').textContent = 'Error';
        document.getElementById('monitorAvgCost').textContent = 'Error';
    }
}

// Auto-fetch monitoring stats every 10 seconds
setInterval(fetchMonitoringStats, 10000);
// Initial fetch on page load
setTimeout(fetchMonitoringStats, 1000);

