// Script principal simplificado - REMOVE o AJAX que estava bloqueando

class FluxDownloader {
    constructor() {
        this.init();
    }

    init() {
        this.bindEvents();
        this.initPasteButton();
        this.initFormatToggle();
        this.initLoadingState();
        this.initFormValidation();
        this.initScrollAnimations();
        this.initRippleEffect();
    }

    bindEvents() {
        // Prevenir múltiplos envios
        this.preventMultipleSubmissions();
    }

    initPasteButton() {
        const pasteBtn = document.getElementById('pasteBtn');
        const urlInput = document.getElementById('url');
        
        if (pasteBtn && urlInput) {
            pasteBtn.addEventListener('click', async () => {
                try {
                    const text = await navigator.clipboard.readText();
                    
                    if (text.includes('youtube.com') || text.includes('youtu.be')) {
                        urlInput.value = text;
                        this.showMessage('Link colado com sucesso!', 'success');
                        urlInput.focus();
                    } else {
                        this.showMessage('Isso não parece um link do YouTube', 'error');
                    }
                } catch (err) {
                    this.showMessage('Não foi possível acessar a área de transferência', 'error');
                }
            });
        }
    }

    initFormatToggle() {
        const formatOptions = document.querySelectorAll('input[name="format"]');
        const qualitySection = document.getElementById('qualitySection');
        
        if (formatOptions.length && qualitySection) {
            formatOptions.forEach(option => {
                option.addEventListener('change', (e) => {
                    const isVideo = e.target.value === 'mp4';
                    
                    if (isVideo) {
                        qualitySection.style.display = 'block';
                        setTimeout(() => {
                            qualitySection.style.opacity = '1';
                            qualitySection.style.transform = 'translateY(0)';
                        }, 10);
                    } else {
                        qualitySection.style.opacity = '0';
                        qualitySection.style.transform = 'translateY(-10px)';
                        setTimeout(() => {
                            qualitySection.style.display = 'none';
                        }, 300);
                    }
                });
            });
        }
    }

    initLoadingState() {
        const forms = document.querySelectorAll('form');
        
        forms.forEach(form => {
            form.addEventListener('submit', (e) => {
                // Validar formulário antes de mostrar loading
                if (!this.validateForm(form)) {
                    e.preventDefault();
                    return;
                }
                
                // Mostrar loading apenas para formulário de download
                if (form.id === 'downloadForm') {
                    const loadingOverlay = document.getElementById('loadingOverlay');
                    if (loadingOverlay) {
                        loadingOverlay.classList.add('active');
                        document.body.style.overflow = 'hidden';
                    }
                    
                    // Desabilitar botão
                    const submitBtn = form.querySelector('button[type="submit"]');
                    if (submitBtn) {
                        submitBtn.disabled = true;
                        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processando...';
                    }
                }
            });
        });
    }

    initFormValidation() {
        const urlInput = document.getElementById('url');
        
        if (urlInput) {
            urlInput.addEventListener('input', (e) => {
                this.validateURL(e.target.value);
            });
        }
    }

    validateURL(url) {
        if (!url) return true;
        const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.?be)\/.+$/;
        return youtubeRegex.test(url);
    }

    validateForm(form) {
        const urlInput = form.querySelector('input[type="url"]');
        
        if (urlInput && !this.validateURL(urlInput.value)) {
            this.showMessage('Por favor, insira um link válido do YouTube.', 'error');
            urlInput.focus();
            return false;
        }
        
        return true;
    }

    showMessage(text, type = 'info') {
        // Criar elemento de mensagem
        const message = document.createElement('div');
        message.className = `message message-${type} animate-in`;
        message.innerHTML = `
            <div class="message-icon">
                <i class="fas fa-${this.getMessageIcon(type)}"></i>
            </div>
            <div class="message-content">
                ${text}
            </div>
            <button class="message-close" aria-label="Fechar">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        // Adicionar ao container de mensagens
        const messagesContainer = document.querySelector('.messages-container');
        if (messagesContainer) {
            messagesContainer.appendChild(message);
        } else {
            // Se não houver container, criar um
            const container = document.createElement('div');
            container.className = 'messages-container';
            container.appendChild(message);
            document.querySelector('.main-content').prepend(container);
        }
        
        // Botão de fechar
        const closeBtn = message.querySelector('.message-close');
        closeBtn.addEventListener('click', () => {
            message.remove();
        });
        
        // Auto-remover após 5 segundos
        setTimeout(() => {
            if (message.parentNode) {
                message.remove();
            }
        }, 5000);
    }

    getMessageIcon(type) {
        const icons = {
            success: 'check-circle',
            error: 'exclamation-circle',
            info: 'info-circle'
        };
        return icons[type] || 'info-circle';
    }

    initScrollAnimations() {
        // Implementação simples se necessário
    }

    initRippleEffect() {
        // Implementação simples se necessário
    }

    preventMultipleSubmissions() {
        const forms = document.querySelectorAll('form');
        
        forms.forEach(form => {
            let isSubmitting = false;
            
            form.addEventListener('submit', (e) => {
                if (isSubmitting) {
                    e.preventDefault();
                    return;
                }
                
                isSubmitting = true;
                
                // Permitir reenvio após 30 segundos (fallback)
                setTimeout(() => {
                    isSubmitting = false;
                    const submitButton = form.querySelector('button[type="submit"]');
                    if (submitButton) {
                        submitButton.disabled = false;
                    }
                }, 30000);
            });
        });
    }
}

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    window.fluxDownloader = new FluxDownloader();
    
    // Inicializar efeito de digitação no input
    const urlInput = document.getElementById('url');
    if (urlInput && !urlInput.value) {
        const examples = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/9bZkp7q19f0",
            "https://www.youtube.com/watch?v=JGwWNGJdvx8"
        ];
        
        let exampleIndex = 0;
        let charIndex = 0;
        let isTyping = true;
        let timeout;
        
        function type() {
            if (isTyping) {
                if (charIndex < examples[exampleIndex].length) {
                    urlInput.placeholder = examples[exampleIndex].substring(0, charIndex + 1);
                    charIndex++;
                    timeout = setTimeout(type, 50);
                } else {
                    isTyping = false;
                    timeout = setTimeout(erase, 2000);
                }
            }
        }
        
        function erase() {
            if (!isTyping) {
                if (charIndex > 0) {
                    urlInput.placeholder = examples[exampleIndex].substring(0, charIndex - 1);
                    charIndex--;
                    timeout = setTimeout(erase, 30);
                } else {
                    isTyping = true;
                    exampleIndex = (exampleIndex + 1) % examples.length;
                    timeout = setTimeout(type, 500);
                }
            }
        }
        
        urlInput.addEventListener('focus', () => {
            if (!urlInput.value) {
                type();
            }
        });
        
        urlInput.addEventListener('blur', () => {
            clearTimeout(timeout);
            urlInput.placeholder = "https://www.youtube.com/watch?v=...";
        });
        
        urlInput.addEventListener('input', () => {
            if (urlInput.value) {
                clearTimeout(timeout);
                urlInput.placeholder = "https://www.youtube.com/watch?v=...";
            }
        });
    }
});