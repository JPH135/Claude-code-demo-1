// ===== GAME STATE =====
const AVATARS = ['🏎️', '🚀', '⭐', '🎯'];
const AVATAR_COLORS = ['#45caff', '#ff6b9d', '#6bff8e', '#ffd93d'];
const ROUNDS_PER_PLAYER = 5;

const state = {
    players: [],
    currentPlayerIndex: 0,
    currentRound: 0,       // 0-indexed within the turn sequence
    totalTurns: 0,
    scores: [],            // scores[playerIdx][roundIdx]
    // Current puzzle
    targetNumber: 0,
    availableCards: [],
    usedCardIndices: new Set(),
    expression: [],        // array of {type:'number'|'operator', value, cardIndex?}
    // Timer
    timerInterval: null,
    timeLeft: 60,
    timerRunning: false,
    // Audio
    audioCtx: null,
};

// ===== DIFFICULTY CONFIG =====
function getDifficulty(age) {
    if (age <= 7) {
        return {
            cardCount: 4,
            numberPool: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            targetMin: 10,
            targetMax: 50,
            operators: ['+', '-'],
        };
    } else if (age <= 9) {
        return {
            cardCount: 5,
            numberPool: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 25, 50],
            targetMin: 50,
            targetMax: 200,
            operators: ['+', '-', '×'],
        };
    } else {
        return {
            cardCount: 6,
            numberPool: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 25, 50, 75, 100],
            targetMin: 200,
            targetMax: 999,
            operators: ['+', '-', '×', '÷', '(', ')'],
        };
    }
}

// ===== SCREEN MANAGEMENT =====
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(screenId).classList.add('active');
}

// ===== PLAYER MANAGEMENT =====
function addPlayer() {
    const nameInput = document.getElementById('player-name-input');
    const ageInput = document.getElementById('player-age-input');
    const errorEl = document.getElementById('setup-error');

    const name = nameInput.value.trim();
    const age = parseInt(ageInput.value);

    errorEl.textContent = '';

    if (!name) {
        errorEl.textContent = 'Please enter a name!';
        nameInput.focus();
        return;
    }
    if (!age) {
        errorEl.textContent = 'Please select an age!';
        return;
    }
    if (state.players.length >= 4) {
        errorEl.textContent = 'Maximum 4 players!';
        return;
    }
    if (state.players.some(p => p.name.toLowerCase() === name.toLowerCase())) {
        errorEl.textContent = 'That name is already taken!';
        return;
    }

    state.players.push({
        name,
        age,
        avatar: AVATARS[state.players.length],
        color: AVATAR_COLORS[state.players.length],
    });

    nameInput.value = '';
    ageInput.value = '';
    nameInput.focus();

    renderPlayerList();
    playSound('click');
}

function removePlayer(index) {
    state.players.splice(index, 1);
    // Reassign avatars
    state.players.forEach((p, i) => {
        p.avatar = AVATARS[i];
        p.color = AVATAR_COLORS[i];
    });
    renderPlayerList();
}

function renderPlayerList() {
    const list = document.getElementById('player-list');
    const startBtn = document.getElementById('start-race-btn');

    list.innerHTML = state.players.map((p, i) => `
        <div class="player-card" style="border-color: ${p.color}">
            <div class="avatar" style="background: ${p.color}22">${p.avatar}</div>
            <div class="player-info">
                <div class="pname" style="color: ${p.color}">${escapeHtml(p.name)}</div>
                <div class="page">Age ${p.age} · ${getDifficultyLabel(p.age)}</div>
            </div>
            <button class="remove-btn" onclick="removePlayer(${i})">✕</button>
        </div>
    `).join('');

    startBtn.disabled = state.players.length < 2;
}

function getDifficultyLabel(age) {
    if (age <= 7) return '🟢 Starter';
    if (age <= 9) return '🟡 Racer';
    return '🔴 Champion';
}

// ===== GAME START =====
function startGame() {
    if (state.players.length < 2) return;

    state.currentPlayerIndex = 0;
    state.totalTurns = 0;
    state.scores = state.players.map(() => []);

    startTurn();
}

function startTurn() {
    const player = state.players[state.currentPlayerIndex];
    const roundNum = state.scores[state.currentPlayerIndex].length + 1;

    // Show turn announcement
    showScreen('turn-screen');
    document.getElementById('turn-round-info').textContent = `Round ${roundNum} of ${ROUNDS_PER_PLAYER}`;
    document.getElementById('turn-player-name').textContent = player.name;
    document.getElementById('turn-player-name').style.color = player.color;
    document.getElementById('turn-player-avatar').textContent = player.avatar;

    // 3-2-1-GO countdown
    const countdownEl = document.getElementById('countdown-text');
    countdownEl.textContent = '';

    const steps = [
        { text: '3', cls: 'count-green', delay: 600 },
        { text: '2', cls: 'count-yellow', delay: 1400 },
        { text: '1', cls: 'count-red', delay: 2200 },
        { text: 'GO!', cls: 'count-go', delay: 3000 },
    ];

    steps.forEach(step => {
        setTimeout(() => {
            countdownEl.textContent = step.text;
            countdownEl.className = step.cls;
            if (step.text === 'GO!') {
                playSound('go');
            } else {
                playSound('beep');
            }
        }, step.delay);
    });

    setTimeout(() => {
        setupGameBoard(player);
        showScreen('game-screen');
        startTimer();
    }, 3800);
}

// ===== PUZZLE GENERATION =====
function setupGameBoard(player) {
    const diff = getDifficulty(player.age);

    // Generate number cards
    const cards = [];
    for (let i = 0; i < diff.cardCount; i++) {
        const val = diff.numberPool[Math.floor(Math.random() * diff.numberPool.length)];
        cards.push(val);
    }

    // Generate a solvable target
    const target = generateSolvableTarget(cards, diff);

    state.availableCards = cards;
    state.targetNumber = target;
    state.usedCardIndices = new Set();
    state.expression = [];

    // Update UI
    document.getElementById('current-player-label').innerHTML =
        `${player.avatar} <span style="color:${player.color}">${escapeHtml(player.name)}</span>`;
    document.getElementById('round-label').textContent =
        `Round ${state.scores[state.currentPlayerIndex].length + 1}/${ROUNDS_PER_PLAYER}`;
    document.getElementById('target-number').textContent = target;

    renderCards(diff);
    renderOperators(diff);
    renderExpression();
}

function generateSolvableTarget(cards, diff) {
    // Try random expressions with the cards to find reachable targets
    const reachable = new Set();
    const ops = diff.operators.filter(o => o !== '(' && o !== ')');
    const opChars = ops.map(o => o === '×' ? '*' : o === '÷' ? '/' : o);

    // Try many random 2-3 card combinations
    for (let attempt = 0; attempt < 500; attempt++) {
        // Pick 2-3 random card indices
        const count = 2 + Math.floor(Math.random() * Math.min(2, cards.length - 1));
        const indices = [];
        const available = [...Array(cards.length).keys()];
        for (let i = 0; i < count && available.length > 0; i++) {
            const pick = Math.floor(Math.random() * available.length);
            indices.push(available[pick]);
            available.splice(pick, 1);
        }

        const vals = indices.map(i => cards[i]);

        // Try different operator combinations between them
        const opCount = vals.length - 1;
        for (let oi = 0; oi < Math.pow(opChars.length, opCount); oi++) {
            let expr = String(vals[0]);
            let opIdx = oi;
            for (let j = 1; j < vals.length; j++) {
                const op = opChars[opIdx % opChars.length];
                opIdx = Math.floor(opIdx / opChars.length);
                expr += op + vals[j];
            }
            try {
                const result = safeEval(expr);
                if (result !== null && Number.isInteger(result) && result >= diff.targetMin && result <= diff.targetMax && result > 0) {
                    reachable.add(result);
                }
            } catch (e) { /* skip */ }
        }
    }

    if (reachable.size > 0) {
        const arr = [...reachable];
        return arr[Math.floor(Math.random() * arr.length)];
    }

    // Fallback: simple sum of first two cards, clamped
    const fallback = cards[0] + cards[1];
    return Math.max(diff.targetMin, Math.min(diff.targetMax, fallback));
}

// ===== SAFE EXPRESSION EVALUATION =====
function safeEval(exprStr) {
    // Replace display operators
    let sanitized = exprStr.replace(/×/g, '*').replace(/÷/g, '/');

    // Validate: only digits, operators, parens, spaces, dots
    if (!/^[\d+\-*/().  ]+$/.test(sanitized)) return null;

    // Prevent empty parens, consecutive operators, etc.
    if (/[+\-*/]{2,}/.test(sanitized.replace(/[() ]/g, ''))) return null;

    try {
        const result = Function('"use strict"; return (' + sanitized + ')')();
        if (typeof result !== 'number' || !isFinite(result)) return null;
        return Math.round(result * 1000) / 1000; // avoid floating point weirdness
    } catch (e) {
        return null;
    }
}

// ===== RENDER CARDS & OPERATORS =====
function renderCards(diff) {
    const container = document.getElementById('number-cards');
    container.innerHTML = state.availableCards.map((val, i) => `
        <div class="number-card ${state.usedCardIndices.has(i) ? 'used' : ''}"
             data-index="${i}"
             onclick="clickCard(${i})">
            ${val}
        </div>
    `).join('');
}

function renderOperators(diff) {
    const container = document.getElementById('operator-buttons');
    const allOps = ['+', '-', '×', '÷', '(', ')'];
    container.innerHTML = allOps.map(op => `
        <button class="op-btn ${diff.operators.includes(op) ? '' : 'disabled'}"
                onclick="clickOperator('${op}')"
                ${diff.operators.includes(op) ? '' : 'disabled'}>
            ${op}
        </button>
    `).join('');
}

// ===== EXPRESSION BUILDING =====
function clickCard(index) {
    if (state.usedCardIndices.has(index) || !state.timerRunning) return;

    state.usedCardIndices.add(index);
    state.expression.push({
        type: 'number',
        value: state.availableCards[index],
        cardIndex: index,
    });

    playSound('click');
    updateGameUI();
}

function clickOperator(op) {
    if (!state.timerRunning) return;

    state.expression.push({
        type: 'operator',
        value: op,
    });

    playSound('click');
    updateGameUI();
}

function undoLast() {
    if (state.expression.length === 0 || !state.timerRunning) return;

    const removed = state.expression.pop();
    if (removed.type === 'number' && removed.cardIndex !== undefined) {
        state.usedCardIndices.delete(removed.cardIndex);
    }

    playSound('click');
    updateGameUI();
}

function clearExpression() {
    if (!state.timerRunning) return;

    state.expression = [];
    state.usedCardIndices.clear();
    playSound('click');
    updateGameUI();
}

function removeExprToken(index) {
    if (!state.timerRunning) return;

    const removed = state.expression.splice(index, 1)[0];
    if (removed.type === 'number' && removed.cardIndex !== undefined) {
        state.usedCardIndices.delete(removed.cardIndex);
    }

    playSound('click');
    updateGameUI();
}

function updateGameUI() {
    const player = state.players[state.currentPlayerIndex];
    const diff = getDifficulty(player.age);
    renderCards(diff);
    renderExpression();
}

function renderExpression() {
    const area = document.getElementById('expression-area');
    const resultEl = document.getElementById('expression-result');

    if (state.expression.length === 0) {
        area.innerHTML = '<span class="placeholder-text">Click cards and operators to build your answer!</span>';
        resultEl.textContent = '';
        resultEl.className = 'expression-result';
        return;
    }

    area.innerHTML = state.expression.map((token, i) => `
        <span class="expr-token expr-${token.type}" onclick="removeExprToken(${i})" title="Click to remove">
            ${token.value}
        </span>
    `).join('');

    // Try to evaluate
    const exprStr = state.expression.map(t => t.value).join(' ');
    const result = safeEval(exprStr);

    if (result !== null) {
        const diff = Math.abs(result - state.targetNumber);
        if (diff === 0) {
            resultEl.textContent = `= ${result} ✨ PERFECT!`;
            resultEl.className = 'expression-result';
            resultEl.style.color = '#ffd93d';
        } else {
            resultEl.textContent = `= ${result} (${diff} away)`;
            resultEl.className = 'expression-result';
            resultEl.style.color = diff <= 10 ? '#6bff8e' : '#45caff';
        }
    } else {
        resultEl.textContent = 'Keep building...';
        resultEl.className = 'expression-result';
        resultEl.style.color = 'rgba(255,255,255,0.4)';
    }
}

// ===== TIMER & F1 CAR =====
function startTimer() {
    state.timeLeft = 60;
    state.timerRunning = true;

    const timerText = document.getElementById('timer-text');
    const trackStatus = document.getElementById('track-status');
    const f1Car = document.getElementById('f1-car');
    const trackPath = document.getElementById('track-path');

    // Get path length for animation
    const pathLength = trackPath.getTotalLength();

    timerText.textContent = '60';
    timerText.className = 'timer-text';
    trackStatus.textContent = '🟢 GO!';

    // Position car at start
    updateCarPosition(0, trackPath, f1Car, pathLength);

    const startTime = Date.now();
    const duration = 60000;

    state.timerInterval = setInterval(() => {
        const elapsed = Date.now() - startTime;
        const remaining = Math.max(0, Math.ceil((duration - elapsed) / 1000));
        const progress = Math.min(1, elapsed / duration);

        state.timeLeft = remaining;
        timerText.textContent = remaining;

        // Update car position
        updateCarPosition(progress, trackPath, f1Car, pathLength);

        // Color changes
        if (remaining <= 10) {
            timerText.className = 'timer-text danger';
            trackStatus.textContent = '🔴 HURRY!';
            if (remaining <= 5 && remaining > 0) {
                playSound('tick');
            }
        } else if (remaining <= 30) {
            timerText.className = 'timer-text warning';
            trackStatus.textContent = '🟡 HALFWAY!';
        }

        if (remaining <= 0) {
            stopTimer();
            playSound('timeup');
            trackStatus.textContent = '🏁 TIME!';
            submitAnswer(true);
        }
    }, 100);
}

function updateCarPosition(progress, path, car, pathLength) {
    const point = path.getPointAtLength(progress * pathLength);
    car.setAttribute('transform', `translate(${point.x}, ${point.y})`);
}

function stopTimer() {
    state.timerRunning = false;
    if (state.timerInterval) {
        clearInterval(state.timerInterval);
        state.timerInterval = null;
    }
}

// ===== SCORING =====
function calculateScore(target, result) {
    if (result === null) return 0;
    const diff = Math.abs(target - result);
    if (diff === 0) return 10;
    if (diff <= 5) return 7;
    if (diff <= 10) return 5;
    if (diff <= 20) return 3;
    if (diff <= 50) return 1;
    return 0;
}

function submitAnswer(timeExpired = false) {
    stopTimer();

    const exprStr = state.expression.map(t => t.value).join(' ');
    const result = safeEval(exprStr);
    const score = calculateScore(state.targetNumber, result);
    const playerIdx = state.currentPlayerIndex;

    state.scores[playerIdx].push(score);
    state.totalTurns++;

    // Show result
    showResultScreen(result, score, timeExpired);
}

function showResultScreen(result, score, timeExpired) {
    const feedbackEl = document.getElementById('result-feedback');
    const detailsEl = document.getElementById('result-details');

    let feedbackText, feedbackClass;
    if (score === 10) {
        feedbackText = '🌟 PERFECT! 🌟';
        feedbackClass = 'perfect';
        launchConfetti();
        playSound('perfect');
    } else if (score >= 7) {
        feedbackText = '🎉 AMAZING!';
        feedbackClass = 'great';
        launchConfetti();
        playSound('great');
    } else if (score >= 5) {
        feedbackText = '👏 GREAT JOB!';
        feedbackClass = 'great';
        playSound('good');
    } else if (score >= 3) {
        feedbackText = '👍 GOOD TRY!';
        feedbackClass = 'good';
        playSound('good');
    } else if (score >= 1) {
        feedbackText = '💪 NICE EFFORT!';
        feedbackClass = 'good';
        playSound('good');
    } else {
        feedbackText = '😅 KEEP TRYING!';
        feedbackClass = 'miss';
        playSound('miss');
    }

    feedbackEl.textContent = feedbackText;
    feedbackEl.className = `result-feedback ${feedbackClass}`;

    const targetStr = state.targetNumber;
    const resultStr = result !== null ? Math.round(result) : 'No answer';
    const diffStr = result !== null ? Math.abs(Math.round(result) - targetStr) : '-';

    detailsEl.innerHTML = `
        Target: <strong>${targetStr}</strong><br>
        Your answer: <strong>${resultStr}</strong>
        ${result !== null && result !== targetStr ? ` (${diffStr} away)` : ''}<br>
        ${timeExpired && state.expression.length > 0 ? '⏰ Time ran out!<br>' : ''}
        ${timeExpired && state.expression.length === 0 ? '⏰ No answer submitted!<br>' : ''}
        <span class="points-earned">+${score} points</span>
    `;

    renderScoreboard('scoreboard');
    showScreen('result-screen');

    // Check if game is over
    const allDone = state.scores.every(s => s.length >= ROUNDS_PER_PLAYER);
    const nextBtn = document.getElementById('next-turn-btn');
    if (allDone) {
        nextBtn.textContent = '🏆 See Final Results!';
        nextBtn.onclick = showWinner;
    } else {
        nextBtn.textContent = '➡️ Next Turn!';
        nextBtn.onclick = nextTurn;
    }
}

function renderScoreboard(containerId) {
    const container = document.getElementById(containerId);

    const rows = state.players.map((p, i) => {
        const total = state.scores[i].reduce((a, b) => a + b, 0);
        const roundScores = [];
        for (let r = 0; r < ROUNDS_PER_PLAYER; r++) {
            if (r < state.scores[i].length) {
                roundScores.push(`<span class="round-score earned">${state.scores[i][r]}</span>`);
            } else {
                roundScores.push(`<span class="round-score">-</span>`);
            }
        }

        const isCurrent = i === state.currentPlayerIndex;
        return `
            <div class="score-row ${isCurrent ? 'current-turn' : ''}">
                <span class="score-avatar">${p.avatar}</span>
                <span class="score-name" style="color: ${p.color}">${escapeHtml(p.name)}</span>
                <span class="score-rounds">${roundScores.join('')}</span>
                <span class="score-total">${total}</span>
            </div>
        `;
    });

    container.innerHTML = `
        <div class="scoreboard-title">📊 Scoreboard</div>
        ${rows.join('')}
    `;
}

// ===== TURN MANAGEMENT =====
function nextTurn() {
    // Find next player who hasn't completed all rounds
    let nextIdx = (state.currentPlayerIndex + 1) % state.players.length;
    let safety = 0;
    while (state.scores[nextIdx].length >= ROUNDS_PER_PLAYER && safety < state.players.length) {
        nextIdx = (nextIdx + 1) % state.players.length;
        safety++;
    }

    state.currentPlayerIndex = nextIdx;
    startTurn();
}

function showWinner() {
    // Sort players by total score descending
    const totals = state.players.map((p, i) => ({
        player: p,
        index: i,
        total: state.scores[i].reduce((a, b) => a + b, 0),
    }));
    totals.sort((a, b) => b.total - a.total);

    // Reorder state for display
    const sortedPlayers = totals.map(t => t.player);
    const sortedScores = totals.map(t => state.scores[t.index]);

    // Temporarily swap for scoreboard rendering
    const origPlayers = state.players;
    const origScores = state.scores;
    state.players = sortedPlayers;
    state.scores = sortedScores;
    renderScoreboard('final-scoreboard');
    state.players = origPlayers;
    state.scores = origScores;

    const winner = totals[0];
    const isTie = totals.length > 1 && totals[0].total === totals[1].total;

    const announcement = document.getElementById('winner-announcement');
    if (isTie) {
        const tiedPlayers = totals.filter(t => t.total === winner.total);
        announcement.innerHTML = `It's a TIE! 🤝<br>${tiedPlayers.map(t =>
            `<span class="winner-name">${escapeHtml(t.player.name)}</span>`
        ).join(' & ')} with <span class="winner-name">${winner.total} points!</span>`;
    } else {
        announcement.innerHTML = `
            ${winner.player.avatar}<br>
            <span class="winner-name">${escapeHtml(winner.player.name)}</span><br>
            wins with <span class="winner-name">${winner.total} points!</span>
        `;
    }

    showScreen('winner-screen');
    launchConfetti();
    playSound('winner');
}

function resetGame() {
    state.players = [];
    state.scores = [];
    state.totalTurns = 0;
    state.currentPlayerIndex = 0;
    renderPlayerList();
    showScreen('welcome-screen');
}

// ===== CONFETTI =====
function launchConfetti() {
    const canvas = document.getElementById('confetti-canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    const particles = [];
    const colors = ['#ff6b9d', '#45caff', '#ffd93d', '#6bff8e', '#b066ff', '#ff8c42'];

    for (let i = 0; i < 150; i++) {
        particles.push({
            x: canvas.width / 2 + (Math.random() - 0.5) * 200,
            y: canvas.height / 2,
            vx: (Math.random() - 0.5) * 15,
            vy: -Math.random() * 20 - 5,
            size: Math.random() * 8 + 4,
            color: colors[Math.floor(Math.random() * colors.length)],
            rotation: Math.random() * 360,
            rotSpeed: (Math.random() - 0.5) * 10,
            gravity: 0.3,
            life: 1,
        });
    }

    let animFrame;
    function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        let alive = false;

        particles.forEach(p => {
            if (p.life <= 0) return;
            alive = true;

            p.vy += p.gravity;
            p.x += p.vx;
            p.y += p.vy;
            p.rotation += p.rotSpeed;
            p.life -= 0.008;

            ctx.save();
            ctx.translate(p.x, p.y);
            ctx.rotate(p.rotation * Math.PI / 180);
            ctx.globalAlpha = p.life;
            ctx.fillStyle = p.color;
            ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
            ctx.restore();
        });

        if (alive) {
            animFrame = requestAnimationFrame(animate);
        } else {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            cancelAnimationFrame(animFrame);
        }
    }

    animate();
}

// ===== SOUND EFFECTS (Web Audio API) =====
function getAudioCtx() {
    if (!state.audioCtx) {
        state.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    return state.audioCtx;
}

function playSound(type) {
    try {
        const ctx = getAudioCtx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);

        const now = ctx.currentTime;
        gain.gain.setValueAtTime(0.15, now);

        switch (type) {
            case 'click':
                osc.frequency.setValueAtTime(800, now);
                osc.type = 'sine';
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.1);
                osc.start(now);
                osc.stop(now + 0.1);
                break;
            case 'beep':
                osc.frequency.setValueAtTime(600, now);
                osc.type = 'sine';
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
                osc.start(now);
                osc.stop(now + 0.2);
                break;
            case 'go':
                osc.frequency.setValueAtTime(880, now);
                osc.frequency.setValueAtTime(1100, now + 0.1);
                osc.type = 'square';
                gain.gain.setValueAtTime(0.2, now);
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
                osc.start(now);
                osc.stop(now + 0.4);
                break;
            case 'tick':
                osc.frequency.setValueAtTime(1000, now);
                osc.type = 'sine';
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);
                osc.start(now);
                osc.stop(now + 0.08);
                break;
            case 'timeup':
                osc.frequency.setValueAtTime(400, now);
                osc.frequency.linearRampToValueAtTime(200, now + 0.5);
                osc.type = 'sawtooth';
                gain.gain.setValueAtTime(0.2, now);
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.5);
                osc.start(now);
                osc.stop(now + 0.5);
                break;
            case 'perfect':
            case 'winner':
                // Victory fanfare - ascending notes
                [0, 0.15, 0.3, 0.45].forEach((delay, i) => {
                    const o = ctx.createOscillator();
                    const g = ctx.createGain();
                    o.connect(g);
                    g.connect(ctx.destination);
                    o.frequency.setValueAtTime([523, 659, 784, 1047][i], now + delay);
                    o.type = 'square';
                    g.gain.setValueAtTime(0.15, now + delay);
                    g.gain.exponentialRampToValueAtTime(0.001, now + delay + 0.2);
                    o.start(now + delay);
                    o.stop(now + delay + 0.2);
                });
                break;
            case 'great':
                osc.frequency.setValueAtTime(523, now);
                osc.frequency.setValueAtTime(784, now + 0.15);
                osc.type = 'square';
                gain.gain.setValueAtTime(0.15, now);
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
                osc.start(now);
                osc.stop(now + 0.3);
                break;
            case 'good':
                osc.frequency.setValueAtTime(523, now);
                osc.type = 'sine';
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
                osc.start(now);
                osc.stop(now + 0.25);
                break;
            case 'miss':
                osc.frequency.setValueAtTime(300, now);
                osc.frequency.linearRampToValueAtTime(200, now + 0.3);
                osc.type = 'sine';
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
                osc.start(now);
                osc.stop(now + 0.3);
                break;
        }
    } catch (e) {
        // Audio not available, fail silently
    }
}

// ===== UTILITY =====
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ===== KEYBOARD SUPPORT =====
document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        const activeScreen = document.querySelector('.screen.active');
        if (activeScreen.id === 'setup-screen') {
            const nameInput = document.getElementById('player-name-input');
            if (document.activeElement === nameInput || document.activeElement === document.getElementById('player-age-input')) {
                addPlayer();
            }
        }
    }

    // Game screen shortcuts
    if (document.getElementById('game-screen').classList.contains('active') && state.timerRunning) {
        if (e.key === 'Backspace') {
            e.preventDefault();
            undoLast();
        }
        if (e.key === 'Escape') {
            clearExpression();
        }
        if (e.key === 'Enter') {
            submitAnswer();
        }
    }
});

// Resize confetti canvas on window resize
window.addEventListener('resize', () => {
    const canvas = document.getElementById('confetti-canvas');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
});
