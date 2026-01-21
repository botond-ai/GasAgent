// API Configuration
const API_URL = 'http://localhost:5000';

// DOM Elements
const messagesContainer = document.getElementById('messages');
const questionForm = document.getElementById('questionForm');
const questionInput = document.getElementById('questionInput');
const sendButton = document.getElementById('sendButton');
const buttonText = document.getElementById('buttonText');
const buttonLoader = document.getElementById('buttonLoader');

// Add message to chat
function addMessage(content, isUser = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    
    if (typeof content === 'string') {
        messageContent.innerHTML = `<p>${escapeHtml(content)}</p>`;
    } else {
        messageContent.appendChild(content);
    }
    
    messageDiv.appendChild(messageContent);
    messagesContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Add error message
function addErrorMessage(error) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error';
    errorDiv.innerHTML = `<strong>⚠️ Hiba:</strong> ${escapeHtml(error)}`;
    addMessage(errorDiv);
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Set loading state
function setLoading(isLoading) {
    if (isLoading) {
        sendButton.disabled = true;
        questionInput.disabled = true;
        buttonText.style.display = 'none';
        buttonLoader.style.display = 'inline-block';
    } else {
        sendButton.disabled = false;
        questionInput.disabled = false;
        buttonText.style.display = 'inline';
        buttonLoader.style.display = 'none';
    }
}

// Send question to API
async function sendQuestion(question) {
    console.log('[DEBUG] Sending question:', question);
    try {
        const response = await fetch(`${API_URL}/api/ask`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ question }),
        });
        
        console.log('[DEBUG] Response status:', response.status);
        const data = await response.json();
        console.log('[DEBUG] Response data:', data);
        
        if (!response.ok) {
            throw new Error(data.error || 'Ismeretlen hiba történt');
        }
        
        if (data.success) {
            console.log('[DEBUG] Returning answer:', data.answer);
            return data.answer;
        } else {
            throw new Error(data.error || 'Nem sikerült választ kapni');
        }
    } catch (error) {
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            throw new Error('Nem sikerült kapcsolódni a szerverhez. Biztos, hogy fut az API? (python src/api.py)');
        }
        throw error;
    }
}

// Handle form submission
questionForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const question = questionInput.value.trim();
    if (!question) return;
    
    console.log('[DEBUG] Form submitted with question:', question);
    
    // Add user message
    addMessage(question, true);
    
    // Clear input
    questionInput.value = '';
    
    // Set loading state
    setLoading(true);
    
    try {
        // Send question to API
        const answer = await sendQuestion(question);
        console.log('[DEBUG] Got answer, adding to chat:', answer);
        
        // Add bot response
        addMessage(answer);
    } catch (error) {
        console.error('[DEBUG] Error:', error);
        // Add error message
        addErrorMessage(error.message);
    } finally {
        // Remove loading state
        setLoading(false);
        
        // Focus input
        questionInput.focus();
    }
});

// Check API health on load
async function checkApiHealth() {
    try {
        const response = await fetch(`${API_URL}/api/health`);
        const data = await response.json();
        
        if (data.status === 'ok') {
            console.log('✅ API connection successful');
        }
    } catch (error) {
        console.warn('⚠️ API not reachable. Make sure to run: python src/api.py');
        addErrorMessage('Az API szerver nem érhető el. Indítsd el a következő paranccsal: python src/api.py');
    }
}

// Initialize
checkApiHealth();
questionInput.focus();
