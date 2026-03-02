/**
 * Token Admin JavaScript
 * 
 * Provides API documentation modal for authentication tokens.
 */

// Global function to show API example modal
function showApiExample(token, apiUrl) {
    // Create modal if it doesn't exist
    let modal = document.getElementById('token-api-modal');
    if (!modal) {
        createApiModal();
        modal = document.getElementById('token-api-modal');
    }
    
    // Update content with token
    updateModalContent(token, apiUrl);
    
    // Show modal
    modal.style.display = 'block';
    document.body.style.overflow = 'hidden';
}

function createApiModal() {
    const modal = document.createElement('div');
    modal.id = 'token-api-modal';
    modal.className = 'token-api-modal';
    
    modal.innerHTML = `
        <div class="token-api-modal-content">
            <div class="token-api-modal-header">
                <h2><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg> API Authentication Token</h2>
                <button class="token-api-modal-close" onclick="closeApiModal()">&times;</button>
            </div>
            
            <div class="token-api-description">
                <p>Use this token to authenticate API requests. Include it in the <code>Authorization</code> header.</p>
            </div>
            
            <div class="token-api-example">
                <strong>Your Token:</strong><br>
                <code id="token-display"></code>
                <button class="token-copy-btn" onclick="copyToken()">Copy</button>
            </div>
            
            <div class="token-api-endpoints">
                <h3><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><path d="M4 11a9 9 0 0 1 9 9"></path><path d="M4 4a16 16 0 0 1 16 16"></path><circle cx="5" cy="19" r="1"></circle></svg> API Endpoints</h3>
                
                <div class="token-api-endpoint">
                    <strong>GET License Metadata:</strong><br>
                    <code id="api-url-example"></code>
                </div>
                
                <div class="token-api-example">
                    <strong>cURL Example:</strong><br>
                    <code id="curl-example"></code>
                    <button class="token-copy-btn" onclick="copyCurl()">Copy</button>
                </div>
                
                <div class="token-api-example">
                    <strong>JavaScript Example:</strong><br>
                    <code id="js-example"></code>
                    <button class="token-copy-btn" onclick="copyJs()">Copy</button>
                </div>
            </div>
            
            <div class="token-api-description">
                <p><strong>Security Note:</strong> Keep your token secure and never share it publicly. Use HTTPS in production.</p>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Close modal when clicking outside
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeApiModal();
        }
    });
    
    // Close modal with Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeApiModal();
        }
    });
}

function updateModalContent(token, apiUrl) {
    // Get current domain
    const domain = window.location.origin;
    const fullApiUrl = domain + apiUrl;
    
    // Update token display
    document.getElementById('token-display').textContent = token;
    
    // Update API URL example
    document.getElementById('api-url-example').textContent = fullApiUrl;
    
    // Update cURL example
    const curlExample = `curl -H "Authorization: Token ${token}" \\\n  "${fullApiUrl}"`;
    document.getElementById('curl-example').textContent = curlExample;
    
    // Update JavaScript example
    const jsExample = `fetch('${fullApiUrl}', {\n  headers: {\n    'Authorization': 'Token ${token}'\n  }\n})\n.then(response => response.json())\n.then(data => console.log(data));`;
    document.getElementById('js-example').textContent = jsExample;
}

function closeApiModal() {
    const modal = document.getElementById('token-api-modal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
}

function copyToken() {
    const token = document.getElementById('token-display').textContent;
    copyToClipboard(token, 'Token copied to clipboard!');
}

function copyCurl() {
    const curlExample = document.getElementById('curl-example').textContent;
    copyToClipboard(curlExample, 'cURL command copied to clipboard!');
}

function copyJs() {
    const jsExample = document.getElementById('js-example').textContent;
    copyToClipboard(jsExample, 'JavaScript code copied to clipboard!');
}

function copyToClipboard(text, message) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
            showNotification(message);
        }).catch(err => {
            console.error('Failed to copy: ', err);
            fallbackCopyTextToClipboard(text, message);
        });
    } else {
        fallbackCopyTextToClipboard(text, message);
    }
}

function fallbackCopyTextToClipboard(text, message) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        document.execCommand('copy');
        showNotification(message);
    } catch (err) {
        console.error('Fallback: Could not copy text: ', err);
        showNotification('Failed to copy to clipboard');
    }
    
    document.body.removeChild(textArea);
}

function showNotification(message) {
    // Create notification element
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #28a745;
        color: white;
        padding: 12px 20px;
        border-radius: 4px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        z-index: 10000;
        font-size: 14px;
        opacity: 0;
        transition: opacity 0.3s ease;
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    // Fade in
    setTimeout(() => {
        notification.style.opacity = '1';
    }, 10);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 3000);
}
