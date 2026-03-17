// =====================================================
// PLAYER DE ESTIRAMIENTOS - JAVASCRIPT MEJORADO
// =====================================================

class StretchPlayer {
    constructor(config) {
        this.steps = config.steps;
        this.transition = config.transition;
        this.planId = config.planId;
        this.totalSteps = this.steps.length;

        // Estado del player
        this.state = {
            currentIndex: 0,
            mode: 'WORK', // WORK | TRANSITION | DONE
            timeRemaining: this.steps[0].duration,
            transitionRemaining: this.transition,
            isPaused: false,
            totalElapsedTime: 0,
            breathIndicatorEnabled: true,
            fullscreenEnabled: false,
            durationAdjustment: 0 // Ajuste de duración en segundos
        };

        this.intervalId = null;
        this.wakeLock = null;

        // Touch gestures
        this.touchStartX = 0;
        this.touchEndX = 0;

        // Elementos DOM
        this.elements = {};

        // Bind methods
        this.tick = this.tick.bind(this);
        this.handleKeydown = this.handleKeydown.bind(this);
        this.handleTouchStart = this.handleTouchStart.bind(this);
        this.handleTouchEnd = this.handleTouchEnd.bind(this);
    }

    // =====================================================
    // INICIALIZACIÓN
    // =====================================================
    init() {
        try {
            console.log('🎯 Inicializando StretchPlayer...');
            console.log('📊 Datos:', { steps: this.steps.length, transition: this.transition, planId: this.planId });

            this.cacheElements();
            console.log('✅ Elementos cacheados');

            this.attachEventListeners();
            console.log('✅ Event listeners adjuntados');

            this.loadProgress();
            console.log('✅ Progreso cargado');

            this.requestWakeLock();
            console.log('✅ Wake Lock solicitado');

            this.render();
            console.log('✅ Primera renderización completada');

            this.start();
            console.log('✅ Timer iniciado');

            this.showToast('Sesión iniciada. ¡Buena suerte!', 'success');
            console.log('🎉 StretchPlayer inicializado correctamente');
        } catch (error) {
            console.error('❌ Error al inicializar StretchPlayer:', error);
            alert('Error al inicializar el player: ' + error.message);
        }
    }

    cacheElements() {
        const $ = (id) => document.getElementById(id);

        this.elements = {
            currentStep: $('currentStep'),
            totalSteps: $('totalSteps'),
            globalProgress: $('globalProgress'),
            exerciseImage: $('exerciseImage'),
            noImagePlaceholder: $('noImagePlaceholder'),
            placeholderText: $('placeholderText'),
            transitionScreen: $('transitionScreen'),
            transitionNextName: $('transitionNextName'),
            timerSeconds: $('timerSeconds'),
            timerLabel: $('timerLabel'),
            progressRing: $('progressRing'),
            exerciseName: $('exerciseName'),
            exerciseMuscle: $('exerciseMuscle'),
            exerciseDescription: $('exerciseDescription'),
            nextExerciseName: $('nextExerciseName'),
            btnPause: $('btnPause'),
            pauseLabel: $('pauseLabel'),
            btnSkip: $('btnSkip'),
            btnRestart: $('btnRestart'),
            completedOverlay: $('completedOverlay'),
            statExercises: $('statExercises'),
            statTime: $('statTime'),
            btnRestartFinal: $('btnRestartFinal'),
            breathIndicator: $('breathIndicator'),
            btnBreath: $('btnBreath'),
            btnFullscreen: $('btnFullscreen'),
            durationDisplay: $('durationDisplay'),
            btnDurationMinus: $('btnDurationMinus'),
            btnDurationPlus: $('btnDurationPlus'),
            toast: $('toast')
        };
    }

    attachEventListeners() {
        // Controles principales - verificar que existan
        if (this.elements.btnPause) {
            this.elements.btnPause.addEventListener('click', () => this.togglePause());
        }
        if (this.elements.btnSkip) {
            this.elements.btnSkip.addEventListener('click', () => this.skip());
        }
        if (this.elements.btnRestart) {
            this.elements.btnRestart.addEventListener('click', () => this.restart());
        }
        if (this.elements.btnRestartFinal) {
            this.elements.btnRestartFinal.addEventListener('click', () => this.restart());
        }

        // Controles adicionales
        if (this.elements.btnBreath) {
            this.elements.btnBreath.addEventListener('click', () => this.toggleBreathIndicator());
        }

        if (this.elements.btnFullscreen) {
            this.elements.btnFullscreen.addEventListener('click', () => this.toggleFullscreen());
        }

        // Ajuste de duración
        if (this.elements.btnDurationMinus) {
            this.elements.btnDurationMinus.addEventListener('click', () => this.adjustDuration(-5));
        }

        if (this.elements.btnDurationPlus) {
            this.elements.btnDurationPlus.addEventListener('click', () => this.adjustDuration(5));
        }

        // Teclado
        document.addEventListener('keydown', this.handleKeydown);

        // Touch gestures
        document.addEventListener('touchstart', this.handleTouchStart, { passive: true });
        document.addEventListener('touchend', this.handleTouchEnd, { passive: true });

        // Fullscreen change
        document.addEventListener('fullscreenchange', () => {
            this.state.fullscreenEnabled = !!document.fullscreenElement;
            this.updateFullscreenButton();
        });

        // Prevenir cierre accidental
        window.addEventListener('beforeunload', (e) => {
            if (this.state.mode !== 'DONE' && this.state.totalElapsedTime > 10) {
                e.preventDefault();
                e.returnValue = '';
            }
        });
    }

    // =====================================================
    // GESTIÓN DE ESTADO
    // =====================================================
    setState(newState) {
        this.state = { ...this.state, ...newState };
        this.saveProgress();
    }

    saveProgress() {
        const progress = {
            planId: this.planId,
            currentIndex: this.state.currentIndex,
            mode: this.state.mode,
            timeRemaining: this.state.timeRemaining,
            totalElapsedTime: this.state.totalElapsedTime,
            timestamp: Date.now()
        };
        localStorage.setItem('stretchProgress', JSON.stringify(progress));
    }

    loadProgress() {
        try {
            const saved = localStorage.getItem('stretchProgress');
            if (!saved) return;

            const progress = JSON.parse(saved);

            // Solo cargar si es del mismo plan y no ha pasado más de 1 hora
            const oneHour = 60 * 60 * 1000;
            if (progress.planId === this.planId &&
                Date.now() - progress.timestamp < oneHour &&
                progress.mode !== 'DONE') {

                if (confirm('¿Deseas continuar donde lo dejaste?')) {
                    this.state.currentIndex = progress.currentIndex;
                    this.state.mode = progress.mode;
                    this.state.timeRemaining = progress.timeRemaining;
                    this.state.totalElapsedTime = progress.totalElapsedTime;
                    this.showToast('Progreso restaurado', 'success');
                }
            }
        } catch (e) {
            console.error('Error loading progress:', e);
        }
    }

    clearProgress() {
        localStorage.removeItem('stretchProgress');
    }

    // =====================================================
    // RENDERIZADO
    // =====================================================
    render() {
        try {
            const step = this.steps[this.state.currentIndex];

            // Actualizar progreso global
            const progressPercent = ((this.state.currentIndex) / this.totalSteps) * 100;
            if (this.elements.globalProgress) {
                this.elements.globalProgress.style.width = `${progressPercent}%`;
            }
            if (this.elements.currentStep) {
                this.elements.currentStep.textContent = this.state.currentIndex + 1;
            }

            // Precargar siguiente imagen
            this.preloadNextImage();

            // Imagen
            if (step.image) {
                if (this.elements.exerciseImage) {
                    this.elements.exerciseImage.src = step.image;
                    this.elements.exerciseImage.classList.add('visible');
                }
                if (this.elements.noImagePlaceholder) {
                    this.elements.noImagePlaceholder.style.display = 'none';
                }
            } else {
                if (this.elements.exerciseImage) {
                    this.elements.exerciseImage.classList.remove('visible');
                }
                if (this.elements.noImagePlaceholder) {
                    this.elements.noImagePlaceholder.style.display = 'flex';
                }
                if (this.elements.placeholderText) {
                    this.elements.placeholderText.textContent = step.name;
                }
            }

            // Info del ejercicio
            if (this.elements.exerciseName) {
                this.elements.exerciseName.textContent = step.name;
            }
            if (this.elements.exerciseMuscle) {
                const muscleSpan = this.elements.exerciseMuscle.querySelector('span');
                if (muscleSpan) {
                    muscleSpan.textContent = step.muscle || 'General';
                }
            }
            if (this.elements.exerciseDescription) {
                this.elements.exerciseDescription.textContent = step.note || 'Mantén la posición y respira profundamente.';
            }

            // Siguiente ejercicio
            if (this.elements.nextExerciseName) {
                if (this.state.currentIndex + 1 < this.totalSteps) {
                    this.elements.nextExerciseName.textContent = this.steps[this.state.currentIndex + 1].name;
                } else {
                    this.elements.nextExerciseName.textContent = '¡Fin!';
                }
            }

            // Timer y modo
            if (this.state.mode === 'WORK') {
                this.renderWorkMode(step);
            } else if (this.state.mode === 'TRANSITION') {
                this.renderTransitionMode();
            } else if (this.state.mode === 'DONE') {
                this.showCompleted();
            }

            // Actualizar indicador de respiración
            this.updateBreathIndicator();
        } catch (error) {
            console.error('❌ Error en render():', error);
        }
    }

    renderWorkMode(step) {
        const adjustedDuration = step.duration + this.state.durationAdjustment;

        if (this.elements.timerSeconds) {
            this.elements.timerSeconds.textContent = this.formatTime(this.state.timeRemaining);

            // Warning en últimos 5 segundos
            if (this.state.timeRemaining <= 5) {
                this.elements.timerSeconds.classList.add('warning');
            } else {
                this.elements.timerSeconds.classList.remove('warning');
            }
            this.elements.timerSeconds.classList.remove('transition-mode');
        }

        if (this.elements.timerLabel) {
            this.elements.timerLabel.textContent = 'Estirando';
        }

        if (this.elements.progressRing) {
            this.elements.progressRing.classList.remove('transition-mode');

            // Progress ring
            const circumference = 264; // 2 * PI * 42
            const progress = this.state.timeRemaining / adjustedDuration;
            const offset = circumference * (1 - progress);
            this.elements.progressRing.style.strokeDashoffset = offset;
        }

        if (this.elements.transitionScreen) {
            this.elements.transitionScreen.classList.remove('visible');
        }
    }

    renderTransitionMode() {
        this.elements.timerSeconds.textContent = this.formatTime(this.state.transitionRemaining);
        this.elements.timerLabel.textContent = 'Preparando';
        this.elements.timerSeconds.classList.remove('warning');
        this.elements.timerSeconds.classList.add('transition-mode');
        this.elements.progressRing.classList.add('transition-mode');

        // Mostrar pantalla de transición
        this.elements.transitionScreen.classList.add('visible');
        if (this.state.currentIndex + 1 < this.totalSteps) {
            this.elements.transitionNextName.textContent = this.steps[this.state.currentIndex + 1].name;
        }

        // Progress ring para transición
        const circumference = 264;
        const progress = this.state.transitionRemaining / this.transition;
        const offset = circumference * (1 - progress);
        this.elements.progressRing.style.strokeDashoffset = offset;
    }

    // =====================================================
    // LÓGICA DEL TIMER
    // =====================================================
    tick() {
        if (this.state.isPaused) return;

        this.setState({ totalElapsedTime: this.state.totalElapsedTime + 1 });

        if (this.state.mode === 'WORK') {
            this.setState({ timeRemaining: this.state.timeRemaining - 1 });

            if (this.state.timeRemaining <= 3 && this.state.timeRemaining > 0) {
                this.playBeep(440, 80);
                this.vibrate(50);
            }

            if (this.state.timeRemaining <= 0) {
                this.playBeep(880, 150);
                this.vibrate(100);

                if (this.transition > 0) {
                    this.setState({
                        mode: 'TRANSITION',
                        transitionRemaining: this.transition
                    });
                } else {
                    this.goToNextStep();
                    return;
                }
            }

        } else if (this.state.mode === 'TRANSITION') {
            this.setState({ transitionRemaining: this.state.transitionRemaining - 1 });

            if (this.state.transitionRemaining <= 0) {
                this.goToNextStep();
                return;
            }
        }

        this.render();
    }

    goToNextStep() {
        const newIndex = this.state.currentIndex + 1;

        if (newIndex >= this.totalSteps) {
            this.setState({ mode: 'DONE' });
            this.stop();
            this.render();
            this.clearProgress();
            this.releaseWakeLock();
            return;
        }

        const adjustedDuration = this.steps[newIndex].duration + this.state.durationAdjustment;

        this.setState({
            currentIndex: newIndex,
            mode: 'WORK',
            timeRemaining: adjustedDuration,
            transitionRemaining: this.transition
        });

        this.playBeep(660, 100);
        this.vibrate(80);

        this.render();
    }

    start() {
        if (this.intervalId) return;
        this.intervalId = setInterval(this.tick, 1000);
    }

    stop() {
        if (!this.intervalId) return;
        clearInterval(this.intervalId);
        this.intervalId = null;
    }

    // =====================================================
    // CONTROLES
    // =====================================================
    togglePause() {
        this.setState({ isPaused: !this.state.isPaused });

        if (this.state.isPaused) {
            this.elements.btnPause.innerHTML = '<i class="fas fa-play"></i>';
            this.elements.btnPause.classList.add('paused');
            this.elements.pauseLabel.textContent = 'Reanudar';
            this.elements.pauseLabel.classList.add('paused-label');
            this.showToast('Pausado', 'warning');
        } else {
            this.elements.btnPause.innerHTML = '<i class="fas fa-pause"></i>';
            this.elements.btnPause.classList.remove('paused');
            this.elements.pauseLabel.textContent = 'Pausar';
            this.elements.pauseLabel.classList.remove('paused-label');
            this.showToast('Reanudado', 'success');
        }
    }

    skip() {
        if (this.state.mode === 'DONE') return;
        this.playBeep(550, 80);
        this.showToast('Ejercicio saltado', 'warning');
        this.goToNextStep();
    }

    restart() {
        this.stop();

        this.state = {
            currentIndex: 0,
            mode: 'WORK',
            timeRemaining: this.steps[0].duration + this.state.durationAdjustment,
            transitionRemaining: this.transition,
            isPaused: false,
            totalElapsedTime: 0,
            breathIndicatorEnabled: this.state.breathIndicatorEnabled,
            fullscreenEnabled: this.state.fullscreenEnabled,
            durationAdjustment: this.state.durationAdjustment
        };

        this.elements.btnPause.innerHTML = '<i class="fas fa-pause"></i>';
        this.elements.btnPause.classList.remove('paused');
        this.elements.pauseLabel.textContent = 'Pausar';
        this.elements.pauseLabel.classList.remove('paused-label');
        this.elements.completedOverlay.classList.remove('visible');

        this.clearProgress();
        this.render();
        this.start();
        this.showToast('Sesión reiniciada', 'success');
    }

    // =====================================================
    // NUEVAS FUNCIONALIDADES UX
    // =====================================================
    toggleBreathIndicator() {
        this.setState({ breathIndicatorEnabled: !this.state.breathIndicatorEnabled });
        this.updateBreathIndicator();

        if (this.elements.btnBreath) {
            if (this.state.breathIndicatorEnabled) {
                this.elements.btnBreath.classList.add('active');
                this.showToast('Indicador de respiración activado', 'success');
            } else {
                this.elements.btnBreath.classList.remove('active');
                this.showToast('Indicador de respiración desactivado', 'warning');
            }
        }
    }

    updateBreathIndicator() {
        if (!this.elements.breathIndicator) return;

        if (this.state.breathIndicatorEnabled && this.state.mode === 'WORK' && !this.state.isPaused) {
            this.elements.breathIndicator.classList.add('active');
        } else {
            this.elements.breathIndicator.classList.remove('active');
        }
    }

    async toggleFullscreen() {
        try {
            if (!document.fullscreenElement) {
                await document.documentElement.requestFullscreen();
                this.showToast('Modo pantalla completa', 'success');
            } else {
                await document.exitFullscreen();
                this.showToast('Pantalla completa desactivada', 'warning');
            }
        } catch (err) {
            console.error('Fullscreen error:', err);
            this.showToast('Pantalla completa no disponible', 'warning');
        }
    }

    updateFullscreenButton() {
        if (!this.elements.btnFullscreen) return;

        if (this.state.fullscreenEnabled) {
            this.elements.btnFullscreen.classList.add('active');
            this.elements.btnFullscreen.innerHTML = '<i class="fas fa-compress"></i>';
        } else {
            this.elements.btnFullscreen.classList.remove('active');
            this.elements.btnFullscreen.innerHTML = '<i class="fas fa-expand"></i>';
        }
    }

    adjustDuration(seconds) {
        this.state.durationAdjustment += seconds;

        // Limitar ajuste entre -15 y +15 segundos
        this.state.durationAdjustment = Math.max(-15, Math.min(15, this.state.durationAdjustment));

        // Actualizar duración actual si estamos en modo WORK
        if (this.state.mode === 'WORK') {
            const step = this.steps[this.state.currentIndex];
            const newDuration = step.duration + this.state.durationAdjustment;

            // Ajustar tiempo restante proporcionalmente
            const progress = this.state.timeRemaining / (step.duration + (this.state.durationAdjustment - seconds));
            this.state.timeRemaining = Math.round(newDuration * progress);
        }

        this.updateDurationDisplay();
        this.render();

        const sign = this.state.durationAdjustment >= 0 ? '+' : '';
        this.showToast(`Duración ajustada: ${sign}${this.state.durationAdjustment}s`, 'success');
    }

    updateDurationDisplay() {
        if (!this.elements.durationDisplay) return;

        const sign = this.state.durationAdjustment > 0 ? '+' : '';
        this.elements.durationDisplay.textContent = this.state.durationAdjustment === 0
            ? 'Normal'
            : `${sign}${this.state.durationAdjustment}s`;
    }

    // =====================================================
    // WAKE LOCK (Prevenir bloqueo de pantalla)
    // =====================================================
    async requestWakeLock() {
        if (!('wakeLock' in navigator)) return;

        try {
            this.wakeLock = await navigator.wakeLock.request('screen');
            console.log('Wake Lock activado');
        } catch (err) {
            console.log('Wake Lock no disponible:', err);
        }
    }

    async releaseWakeLock() {
        if (this.wakeLock) {
            await this.wakeLock.release();
            this.wakeLock = null;
            console.log('Wake Lock liberado');
        }
    }

    // =====================================================
    // GESTOS TÁCTILES
    // =====================================================
    handleTouchStart(e) {
        this.touchStartX = e.changedTouches[0].screenX;
    }

    handleTouchEnd(e) {
        this.touchEndX = e.changedTouches[0].screenX;
        this.handleSwipe();
    }

    handleSwipe() {
        const swipeThreshold = 50;
        const diff = this.touchEndX - this.touchStartX;

        if (Math.abs(diff) < swipeThreshold) return;

        if (diff < 0) {
            // Swipe left - Skip
            this.skip();
        } else {
            // Swipe right - Previous (restart current)
            if (this.state.timeRemaining < this.steps[this.state.currentIndex].duration - 5) {
                this.state.timeRemaining = this.steps[this.state.currentIndex].duration + this.state.durationAdjustment;
                this.render();
                this.showToast('Ejercicio reiniciado', 'warning');
            }
        }
    }

    // =====================================================
    // ATAJOS DE TECLADO
    // =====================================================
    handleKeydown(e) {
        if (e.code === 'Space') {
            e.preventDefault();
            this.togglePause();
        } else if (e.code === 'ArrowRight') {
            this.skip();
        } else if (e.code === 'ArrowLeft') {
            if (this.state.currentIndex > 0) {
                this.state.currentIndex--;
                this.state.mode = 'WORK';
                this.state.timeRemaining = this.steps[this.state.currentIndex].duration + this.state.durationAdjustment;
                this.render();
            }
        } else if (e.code === 'KeyR') {
            this.restart();
        } else if (e.code === 'KeyF') {
            this.toggleFullscreen();
        } else if (e.code === 'KeyB') {
            this.toggleBreathIndicator();
        }
    }

    // =====================================================
    // PANTALLA DE COMPLETADO
    // =====================================================
    showCompleted() {
        this.elements.statExercises.textContent = this.totalSteps;
        this.elements.statTime.textContent = this.formatTime(this.state.totalElapsedTime);
        this.elements.completedOverlay.classList.add('visible');

        // Secuencia de sonidos de celebración
        this.playBeep(523, 200);
        setTimeout(() => this.playBeep(659, 200), 200);
        setTimeout(() => this.playBeep(784, 300), 400);
        this.vibrate([100, 50, 100, 50, 200]);

        this.showToast('¡Sesión completada! 🎉', 'success');
    }

    // =====================================================
    // TOAST NOTIFICATIONS
    // =====================================================
    showToast(message, type = 'success') {
        if (!this.elements.toast) return;

        this.elements.toast.textContent = message;
        this.elements.toast.className = 'toast visible ' + type;

        setTimeout(() => {
            this.elements.toast.classList.remove('visible');
        }, 3000);
    }

    // =====================================================
    // UTILIDADES
    // =====================================================
    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        if (mins > 0) {
            return `${mins}:${String(secs).padStart(2, '0')}`;
        }
        return String(secs);
    }

    playBeep(frequency = 880, duration = 120) {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = ctx.createOscillator();
            const gain = ctx.createGain();

            oscillator.type = 'sine';
            oscillator.frequency.value = frequency;
            gain.gain.value = 0.1;

            oscillator.connect(gain);
            gain.connect(ctx.destination);

            oscillator.start();
            setTimeout(() => {
                oscillator.stop();
                ctx.close();
            }, duration);
        } catch (e) {
            console.log('Audio not available');
        }
    }

    vibrate(pattern = 100) {
        if (navigator.vibrate) {
            navigator.vibrate(pattern);
        }
    }

    preloadNextImage() {
        if (this.state.currentIndex + 1 < this.totalSteps) {
            const nextStep = this.steps[this.state.currentIndex + 1];
            if (nextStep.image) {
                const img = new Image();
                img.src = nextStep.image;
            }
        }
    }
}

// =====================================================
// EXPORTAR PARA USO GLOBAL
// =====================================================
window.StretchPlayer = StretchPlayer;
