// Gerenciamento de tema claro/escuro

class ThemeManager {
    constructor() {
        this.themeToggle = document.getElementById('themeToggle');
        this.htmlElement = document.documentElement;
        this.init();
    }

    init() {
        this.loadTheme();
        this.bindEvents();
        this.applySystemPreference();
    }

    loadTheme() {
        const savedTheme = localStorage.getItem('theme') || 'light';
        this.setTheme(savedTheme);
        this.updateTogglePosition(savedTheme);
    }

    bindEvents() {
        if (this.themeToggle) {
            this.themeToggle.addEventListener('click', () => this.toggleTheme());
        }

        // Detecta mudança no tema do sistema
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
            if (!localStorage.getItem('theme')) {
                this.setTheme(e.matches ? 'dark' : 'light');
            }
        });
    }

    toggleTheme() {
        const currentTheme = this.htmlElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        
        this.setTheme(newTheme);
        this.saveTheme(newTheme);
        this.animateThemeChange();
    }

    setTheme(theme) {
        this.htmlElement.setAttribute('data-theme', theme);
        this.updateTogglePosition(theme);
        this.dispatchThemeChangeEvent(theme);
    }

    updateTogglePosition(theme) {
        const slider = document.querySelector('.toggle-slider');
        if (slider) {
            slider.style.transform = theme === 'dark' ? 'translateX(30px)' : 'translateX(0)';
        }
    }

    saveTheme(theme) {
        localStorage.setItem('theme', theme);
    }

    applySystemPreference() {
        if (!localStorage.getItem('theme')) {
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            this.setTheme(prefersDark ? 'dark' : 'light');
        }
    }

    animateThemeChange() {
        // Adiciona efeito de transição suave
        document.body.style.transition = 'background-color 0.5s ease, color 0.5s ease';
        
        setTimeout(() => {
            document.body.style.transition = '';
        }, 500);

        // Efeito de partículas durante a transição
        this.createThemeTransitionParticles();
    }

    createThemeTransitionParticles() {
        const particleCount = 20;
        const colors = this.htmlElement.getAttribute('data-theme') === 'dark' 
            ? ['#A78BFA', '#F472B6', '#22D3EE'] 
            : ['#7C3AED', '#EC4899', '#06B6D4'];

        for (let i = 0; i < particleCount; i++) {
            const particle = document.createElement('div');
            particle.className = 'theme-particle';
            
            // Posição aleatória
            const x = Math.random() * window.innerWidth;
            const y = Math.random() * window.innerHeight;
            
            // Cor aleatória
            const color = colors[Math.floor(Math.random() * colors.length)];
            
            // Tamanho aleatório
            const size = Math.random() * 10 + 5;
            
            // Configurações de estilo
            particle.style.cssText = `
                position: fixed;
                left: ${x}px;
                top: ${y}px;
                width: ${size}px;
                height: ${size}px;
                background: ${color};
                border-radius: 50%;
                pointer-events: none;
                z-index: 9999;
                opacity: 0;
                transform: scale(0);
            `;
            
            document.body.appendChild(particle);
            
            // Animação
            const animation = particle.animate([
                { 
                    opacity: 0.8, 
                    transform: 'scale(1)',
                    offset: 0.1
                },
                { 
                    opacity: 0, 
                    transform: 'scale(0) translate(var(--tx), var(--ty))',
                    offset: 1
                }
            ], {
                duration: 1000,
                easing: 'cubic-bezier(0.215, 0.610, 0.355, 1)',
                fill: 'forwards'
            });
            
            // Direção aleatória
            const tx = (Math.random() - 0.5) * 200;
            const ty = (Math.random() - 0.5) * 200;
            particle.style.setProperty('--tx', `${tx}px`);
            particle.style.setProperty('--ty', `${ty}px`);
            
            // Remover após animação
            animation.onfinish = () => particle.remove();
        }
    }

    dispatchThemeChangeEvent(theme) {
        const event = new CustomEvent('themeChanged', { detail: { theme } });
        window.dispatchEvent(event);
    }

    // Métodos públicos
    getCurrentTheme() {
        return this.htmlElement.getAttribute('data-theme');
    }

    setLightTheme() {
        this.setTheme('light');
        this.saveTheme('light');
    }

    setDarkTheme() {
        this.setTheme('dark');
        this.saveTheme('dark');
    }
}

// Inicialização quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    window.themeManager = new ThemeManager();
});