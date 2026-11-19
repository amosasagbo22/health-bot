document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const themeToggleBtn = document.getElementById('theme-toggle');
    const themeIcon = document.getElementById('theme-icon');
    const chatMessagesContainer = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const suggestionCards = document.querySelectorAll('.suggestion-card:not(#vision-suggestion-card)');
    const visionSuggestionCard = document.getElementById('vision-suggestion-card');
    const inlineWarning = document.getElementById('inline-warning');
    const inlineWarningClose = document.getElementById('inline-warning-close');
    const emergencyBtn = document.getElementById('emergency-btn');

    // Image / Vision Elements
    const cameraBtn = document.getElementById('camera-btn');
    const imageFileInput = document.getElementById('image-file-input');
    const imagePreviewStrip = document.getElementById('image-preview-strip');
    const imagePreviewThumb = document.getElementById('image-preview-thumb');
    const previewRemoveBtn = document.getElementById('preview-remove-btn');

    // State
    let chatHistory = [];
    let isGenerating = false;
    let pendingImage = null; // { base64: string, mimeType: string, dataUrl: string }

    // Load theme from localStorage
    const savedTheme = localStorage.getItem('healthbot-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);

    // Initialize Lucide Icons
    if (window.lucide) window.lucide.createIcons();

    // Configure Marked.js
    if (window.marked) {
        window.marked.setOptions({ gfm: true, breaks: true, headerIds: false, mangle: false });
    }

    // ────────────────────────────────────────────────────
    // Theme Toggle
    // ────────────────────────────────────────────────────
    themeToggleBtn.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('healthbot-theme', next);
        updateThemeIcon(next);
    });

    function updateThemeIcon(theme) {
        if (!themeIcon) return;
        themeIcon.setAttribute('data-lucide', theme === 'light' ? 'moon' : 'sun');
        if (window.lucide) window.lucide.createIcons();
    }

    // ────────────────────────────────────────────────────
    // Suggestion Cards
    // ────────────────────────────────────────────────────
    suggestionCards.forEach(card => {
        card.addEventListener('click', () => {
            const query = card.getAttribute('data-query');
            if (query && !isGenerating) {
                chatInput.value = query;
                sendMessage();
            }
        });
    });

    // Vision scan suggestion card → open file picker
    if (visionSuggestionCard) {
        visionSuggestionCard.addEventListener('click', () => {
            if (!isGenerating) imageFileInput.click();
        });
    }

    // ────────────────────────────────────────────────────
    // Emergency Banner
    // ────────────────────────────────────────────────────
    if (inlineWarningClose) {
        inlineWarningClose.addEventListener('click', () => {
            inlineWarning.style.display = 'none';
        });
    }

    if (emergencyBtn) {
        emergencyBtn.addEventListener('click', () => {
            showEmergencyBanner('🚨 Emergency: Call 911 (US/Canada), 999 (UK), 112 (Europe), or your local emergency number immediately.');
        });
    }

    // ────────────────────────────────────────────────────
    // Image Upload & Preview
    // ────────────────────────────────────────────────────
    cameraBtn.addEventListener('click', () => {
        if (!isGenerating) imageFileInput.click();
    });

    imageFileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;
        if (!file.type.startsWith('image/')) {
            showEmergencyBanner('⚠️ Please select an image file (JPEG, PNG, etc.).');
            return;
        }
        const reader = new FileReader();
        reader.onload = (ev) => {
            const dataUrl = ev.target.result;
            // dataUrl format: "data:image/jpeg;base64,XXXX"
            const commaIdx = dataUrl.indexOf(',');
            const mimeType = dataUrl.substring(5, dataUrl.indexOf(';'));
            const base64 = dataUrl.substring(commaIdx + 1);

            pendingImage = { base64, mimeType, dataUrl };

            // Show preview strip
            imagePreviewThumb.src = dataUrl;
            imagePreviewStrip.style.display = 'flex';
            cameraBtn.classList.add('has-image');
            chatInput.placeholder = 'Add an optional note about this image (or just press send)…';
            if (window.lucide) window.lucide.createIcons();
        };
        reader.readAsDataURL(file);
        // Reset so same file can be selected again
        imageFileInput.value = '';
    });

    previewRemoveBtn.addEventListener('click', clearPendingImage);

    function clearPendingImage() {
        pendingImage = null;
        imagePreviewStrip.style.display = 'none';
        imagePreviewThumb.src = '';
        cameraBtn.classList.remove('has-image');
        chatInput.placeholder = 'Type a health query or add a note about your image...';
    }

    // ────────────────────────────────────────────────────
    // Textarea Auto-resize
    // ────────────────────────────────────────────────────
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = chatInput.scrollHeight + 'px';
    });

    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    sendBtn.addEventListener('click', sendMessage);

    // ────────────────────────────────────────────────────
    // Send Message (text or vision)
    // ────────────────────────────────────────────────────
    async function sendMessage() {
        const text = chatInput.value.trim();
        if ((!text && !pendingImage) || isGenerating) return;

        // Reset input
        chatInput.value = '';
        chatInput.style.height = 'auto';

        // Hide welcome overlay
        const welcomeOverlay = document.getElementById('welcome-overlay');
        if (welcomeOverlay) welcomeOverlay.style.display = 'none';

        if (pendingImage) {
            // ── Vision flow ──
            const imageSnapshot = { ...pendingImage };
            const userNote = text || null;
            clearPendingImage();
            await sendVisionMessage(imageSnapshot, userNote);
        } else {
            // ── Chat flow ──
            checkEmergencyKeywords(text);
            appendMessage('user', text);
            chatHistory.push({ role: 'user', content: text });
            await sendChatMessage();
        }
    }

    // ────────────────────────────────────────────────────
    // Chat (text-only) Flow
    // ────────────────────────────────────────────────────
    async function sendChatMessage() {
        const botMsgId = appendMessage('bot', '');
        const bubble = getBubble(botMsgId);
        bubble.innerHTML = typingHTML();

        isGenerating = true;
        updateSendButtonState();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: chatHistory })
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            bubble.innerHTML = '';
            const botText = await streamSSE(response, bubble);
            chatHistory.push({ role: 'assistant', content: botText });

        } catch (err) {
            bubble.innerHTML = `<span style="color:var(--danger)">Connection error: ${err.message}</span>`;
        } finally {
            isGenerating = false;
            updateSendButtonState();
            scrollToBottom();
        }
    }

    // ────────────────────────────────────────────────────
    // Vision (image) Flow
    // ────────────────────────────────────────────────────
    async function sendVisionMessage(image, userNote) {
        // User bubble — show thumbnail + optional note
        const userBubbleId = appendVisionUserBubble(image.dataUrl, userNote);

        // Bot bubble — typing indicator
        const botMsgId = appendMessage('bot', '');
        const bubble = getBubble(botMsgId);
        bubble.innerHTML = `
            <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.5rem; color:var(--accent-color); font-size:0.85rem; font-weight:600;">
                <i data-lucide="scan" style="width:16px;height:16px;"></i>
                Analyzing image…
            </div>
            ${typingHTML()}
        `;
        if (window.lucide) window.lucide.createIcons();

        isGenerating = true;
        updateSendButtonState();

        try {
            const payload = {
                image_data: image.base64,
                mime_type: image.mimeType,
                user_note: userNote
            };
            const response = await fetch('/api/vision', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            bubble.innerHTML = '';
            await streamSSE(response, bubble);

        } catch (err) {
            bubble.innerHTML = `<span style="color:var(--danger)">Vision analysis error: ${err.message}</span>`;
        } finally {
            isGenerating = false;
            updateSendButtonState();
            scrollToBottom();
        }
    }

    // ────────────────────────────────────────────────────
    // SSE Stream Reader — returns full accumulated text
    // ────────────────────────────────────────────────────
    async function streamSSE(response, bubble) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let fullText = '';
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                const clean = line.trim();
                if (!clean.startsWith('data: ')) continue;
                const raw = clean.substring(6).trim();
                if (raw === '[DONE]') break;
                try {
                    const parsed = JSON.parse(raw);
                    if (parsed.content) {
                        fullText += parsed.content;
                        bubble.innerHTML = window.marked ? window.marked.parse(fullText) : fullText;
                        scrollToBottom();
                    }
                } catch (_) {}
            }
        }
        return fullText;
    }

    // ────────────────────────────────────────────────────
    // DOM Helper Functions
    // ────────────────────────────────────────────────────
    function appendMessage(sender, text) {
        const id = Date.now().toString();
        const row = document.createElement('div');
        row.className = `message-row ${sender}-row`;
        row.id = `msg-${id}`;

        const avatar = document.createElement('div');
        avatar.className = 'user-avatar';
        avatar.style.flexShrink = '0';
        if (sender === 'user') {
            avatar.innerHTML = `<i data-lucide="user" style="width:16px;height:16px;"></i>`;
        } else {
            avatar.style.background = 'var(--accent-gradient)';
            avatar.style.color = '#fff';
            avatar.innerHTML = `<i data-lucide="activity" style="width:16px;height:16px;"></i>`;
        }

        const bubble = document.createElement('div');
        bubble.className = 'msg-bubble';
        bubble.innerHTML = window.marked && text ? window.marked.parse(text) : text;

        row.appendChild(avatar);
        row.appendChild(bubble);
        chatMessagesContainer.appendChild(row);
        if (window.lucide) window.lucide.createIcons();
        scrollToBottom();
        return id;
    }

    function appendVisionUserBubble(dataUrl, note) {
        const id = Date.now().toString();
        const row = document.createElement('div');
        row.className = 'message-row user-row';
        row.id = `msg-${id}`;

        const avatar = document.createElement('div');
        avatar.className = 'user-avatar';
        avatar.style.flexShrink = '0';
        avatar.innerHTML = `<i data-lucide="user" style="width:16px;height:16px;"></i>`;

        const bubble = document.createElement('div');
        bubble.className = 'msg-bubble';
        bubble.innerHTML = `<img src="${dataUrl}" alt="Uploaded for analysis" class="msg-uploaded-image" />` +
            (note ? `<div>${window.marked ? window.marked.parse(note) : note}</div>` : '');

        row.appendChild(avatar);
        row.appendChild(bubble);
        chatMessagesContainer.appendChild(row);
        if (window.lucide) window.lucide.createIcons();
        scrollToBottom();
        return id;
    }

    function getBubble(msgId) {
        const row = document.getElementById(`msg-${msgId}`);
        return row ? row.querySelector('.msg-bubble') : null;
    }

    function typingHTML() {
        return `<div class="typing-indicator"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div>`;
    }

    function scrollToBottom() {
        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    }

    function updateSendButtonState() {
        sendBtn.disabled = isGenerating;
        sendBtn.innerHTML = isGenerating
            ? `<div class="typing-indicator" style="justify-content:center;"><span class="typing-dot" style="background:#fff;"></span><span class="typing-dot" style="background:#fff;"></span><span class="typing-dot" style="background:#fff;"></span></div>`
            : `<i data-lucide="send" style="width:18px;height:18px;"></i>`;
        if (window.lucide) window.lucide.createIcons();
    }

    function showEmergencyBanner(text) {
        const bannerText = document.getElementById('warning-banner-text');
        if (inlineWarning && bannerText) {
            bannerText.innerText = text;
            inlineWarning.style.display = 'flex';
        }
    }

    function checkEmergencyKeywords(text) {
        const lower = text.toLowerCase();
        const keywords = ['chest pain', 'breathing', 'seizure', 'stroke', 'heavy bleeding', 'unconscious', 'emergency', 'poisoning', 'suicide', 'choking'];
        const matched = keywords.find(kw => lower.includes(kw));
        if (matched) {
            showEmergencyBanner(`🚨 Critical symptom detected: "${matched}". Please call 911 or go to the nearest emergency room immediately!`);
        }
    }
});
