// Sistema de partículas orgânico para fundo

class ParticleSystem {
    constructor(containerId = 'particles') {
        this.container = document.getElementById(containerId);
        this.particles = [];
        this.particleCount = 30;
        this.colors = {
            light: ['#7C3AED', '#EC4899', '#06B6D4', '#10B981', '#F59E0B'],
            dark: ['#A78BFA', '#F472B6', '#22D3EE', '#34D399', '#FBBF24']
        };
        
        if (this.container) {
            this.init();
            this.startAnimation();
            this.bindResize();
            this.bindThemeChange();
        }
    }

    init() {
        this.createParticles();
        this.updateColors();
    }

    getCurrentColors() {
        const theme = document.documentElement.getAttribute('data-theme') || 'light';
        return this.colors[theme];
    }

    createParticles() {
        // Limpar partículas existentes
        this.container.innerHTML = '';
        this.particles = [];

        for (let i = 0; i < this.particleCount; i++) {
            this.createParticle(i);
        }
    }

    createParticle(index) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        
        // Tamanho aleatório
        const size = Math.random() * 40 + 10;
        
        // Posição aleatória
        const x = Math.random() * 100;
        const y = Math.random() * 100;
        
        // Cor aleatória baseada no tema
        const colors = this.getCurrentColors();
        const color = colors[Math.floor(Math.random() * colors.length)];
        
        // Opacidade aleatória
        const opacity = Math.random() * 0.1 + 0.05;
        
        // Configuração inicial
        particle.style.cssText = `
            width: ${size}px;
            height: ${size}px;
            background: ${color};
            opacity: ${opacity};
            left: ${x}%;
            top: ${y}%;
            border-radius: ${this.getRandomShape()};
            filter: blur(${Math.random() * 10 + 5}px);
        `;
        
        // Adicionar ao container
        this.container.appendChild(particle);
        
        // Armazenar propriedades da partícula
        this.particles.push({
            element: particle,
            x,
            y,
            size,
            color,
            opacity,
            speedX: (Math.random() - 0.5) * 0.2,
            speedY: (Math.random() - 0.5) * 0.2,
            rotation: Math.random() * 360,
            rotationSpeed: (Math.random() - 0.5) * 0.5,
            pulseSpeed: Math.random() * 0.02 + 0.01,
            pulseDirection: 1,
            pulsePhase: Math.random() * Math.PI * 2
        });
    }

    getRandomShape() {
        const shapes = ['50%', '30%', '10% 50%', '50% 10%'];
        return shapes[Math.floor(Math.random() * shapes.length)];
    }

    startAnimation() {
        const animate = () => {
            this.updateParticles();
            this.animationFrame = requestAnimationFrame(animate);
        };
        animate();
    }

    updateParticles() {
        const time = Date.now() * 0.001;
        
        this.particles.forEach(particle => {
            // Movimento suave
            particle.x += particle.speedX;
            particle.y += particle.speedY;
            
            // Rotação
            particle.rotation += particle.rotationSpeed;
            
            // Pulsação
            particle.pulsePhase += particle.pulseSpeed;
            const pulse = Math.sin(particle.pulsePhase) * 0.1 + 1;
            
            // Atualizar posição
            particle.element.style.transform = `
                translate(-50%, -50%) 
                rotate(${particle.rotation}deg)
                scale(${pulse})
            `;
            
            // Movimento baseado em onda
            const waveX = Math.sin(time + particle.x * 0.01) * 0.5;
            const waveY = Math.cos(time + particle.y * 0.01) * 0.5;
            
            particle.element.style.left = `calc(${particle.x}% + ${waveX}%)`;
            particle.element.style.top = `calc(${particle.y}% + ${waveY}%)`;
            
            // Wrap-around
            if (particle.x < -10) particle.x = 110;
            if (particle.x > 110) particle.x = -10;
            if (particle.y < -10) particle.y = 110;
            if (particle.y > 110) particle.y = -10;
        });
    }

    bindResize() {
        let resizeTimeout;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                this.handleResize();
            }, 100);
        });
    }

    handleResize() {
        // Ajustar número de partículas baseado no tamanho da tela
        const newCount = Math.min(50, Math.max(20, Math.floor(window.innerWidth * window.innerHeight / 20000)));
        
        if (newCount !== this.particleCount) {
            this.particleCount = newCount;
            this.createParticles();
        }
    }

    bindThemeChange() {
        window.addEventListener('themeChanged', () => {
            this.updateColors();
        });
    }

    updateColors() {
        const colors = this.getCurrentColors();
        
        this.particles.forEach((particle, index) => {
            const color = colors[index % colors.length];
            particle.color = color;
            particle.element.style.background = color;
            
            // Ajustar opacidade para tema escuro
            const opacity = document.documentElement.getAttribute('data-theme') === 'dark' 
                ? Math.random() * 0.08 + 0.02
                : Math.random() * 0.1 + 0.05;
            
            particle.opacity = opacity;
            particle.element.style.opacity = opacity;
        });
    }

    // Métodos públicos
    addParticles(count = 5) {
        for (let i = 0; i < count; i++) {
            this.createParticle(this.particles.length);
        }
        this.particleCount += count;
    }

    removeParticles(count = 5) {
        for (let i = 0; i < count && this.particles.length > 0; i++) {
            const particle = this.particles.pop();
            particle.element.remove();
        }
        this.particleCount = Math.max(10, this.particleCount - count);
    }

    changeDensity(density) {
        // density: 0 a 1
        const newCount = Math.floor(50 * density);
        const difference = newCount - this.particleCount;
        
        if (difference > 0) {
            this.addParticles(difference);
        } else if (difference < 0) {
            this.removeParticles(-difference);
        }
    }

    destroy() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }
        this.container.innerHTML = '';
        this.particles = [];
    }
}

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    window.particleSystem = new ParticleSystem();
});