(function () {
  const dataEl = document.getElementById('exercises-data');
  if (!dataEl) return;

  const exercises = JSON.parse(dataEl.textContent);
  const config = window.PLAYER_CONFIG || {};
  const stage = document.getElementById('player-stage');
  const checklistEl = document.getElementById('player-checklist');
  const progressFill = document.getElementById('progress-fill');
  const progressCount = document.getElementById('progress-count');
  const doneOverlay = document.getElementById('done-overlay');
  const doneSummary = document.getElementById('done-summary');
  const endEarlyBtn = document.getElementById('end-early-btn');

  const RING_CIRC = 2 * Math.PI * 90;

  let currentIndex = 0;
  let completedLog = [];
  const statuses = exercises.map(function () { return 'pending'; });

  // If this ever fires, the page rendered with zero exercises — that's a
  // data/caching problem, not a completed workout, so say so instead of
  // silently showing the celebration screen.
  if (!exercises.length) {
    stage.innerHTML =
      '<div class="exercise-stage-card"><h2 class="stage-name">No exercises loaded</h2>' +
      '<p class="stage-target">This session has nothing to play. Hard-refresh the page ' +
      '(Ctrl/Cmd+Shift+R) — if that doesn\'t fix it, this day may genuinely have no exercises.</p></div>';
    console.error('player.js: exercises array is empty — check the exercises-data script tag content.');
    return;
  }

  let timerInterval = null;
  let timeLeft = 0;
  let timerTotal = 0;
  let timerRunning = false;

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
  }

  function numOrNull(v) {
    if (v === '' || v === null || v === undefined) return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  function formatTime(s) {
    s = Math.max(0, Math.round(s));
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return String(m).padStart(2, '0') + ':' + String(sec).padStart(2, '0');
  }

  function stopTimer() {
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = null;
    timerRunning = false;
  }

  function beep() {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      const ctx = new Ctx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.001, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
      osc.start();
      osc.stop(ctx.currentTime + 0.4);
    } catch (e) { /* audio not available, ignore */ }
  }

  function updateProgress() {
    const doneCount = statuses.filter(function (s) { return s === 'done' || s === 'skipped'; }).length;
    progressCount.textContent = doneCount;
    progressFill.style.width = (exercises.length ? (doneCount / exercises.length * 100) : 0) + '%';
  }

  function renderChecklist() {
    checklistEl.innerHTML = '';
    exercises.forEach(function (ex, i) {
      const li = document.createElement('li');
      let cls = 'checklist-item status-' + statuses[i];
      if (i === currentIndex) cls += ' is-current';
      li.className = cls;
      const icon = statuses[i] === 'done' ? '✓' : statuses[i] === 'skipped' ? '–' : (i === currentIndex ? '▶' : '');
      li.innerHTML = '<span class="checklist-icon">' + icon + '</span><span class="checklist-name">' +
        escapeHtml(ex.exercise_name) + '</span>';
      checklistEl.appendChild(li);
    });
  }

  function updateRing() {
    const ring = document.getElementById('ring-fg');
    const timeEl = document.getElementById('timer-time');
    if (!ring) return;
    const fraction = timerTotal > 0 ? Math.max(0, Math.min(1, timeLeft / timerTotal)) : 0;
    ring.style.strokeDashoffset = String(RING_CIRC * (1 - fraction));
    ring.classList.toggle('timer-ring-fg-low', timerTotal > 0 && fraction <= 0.2);
    if (timeEl) timeEl.textContent = formatTime(timeLeft);
  }

  function toggleTimer() {
    const btn = document.getElementById('timer-toggle');
    if (!btn) return;
    if (timerRunning) {
      stopTimer();
      btn.textContent = '▶ Resume timer';
      btn.classList.remove('is-running');
      return;
    }
    timerRunning = true;
    btn.textContent = '⏸ Pause timer';
    btn.classList.add('is-running');
    timerInterval = setInterval(function () {
      timeLeft -= 1;
      updateRing();
      if (timeLeft <= 0) {
        stopTimer();
        beep();
        advance('done');
      }
    }, 1000);
  }

  function advance(status) {
    stopTimer();
    statuses[currentIndex] = status;
    if (status === 'done') {
      const ex = exercises[currentIndex];
      const setsEl = document.getElementById('actual-sets');
      const repsEl = document.getElementById('actual-reps');
      const weightEl = document.getElementById('actual-weight');
      completedLog.push({
        exercise_name: ex.exercise_name,
        sets: setsEl ? numOrNull(setsEl.value) : ex.sets,
        reps: repsEl ? numOrNull(repsEl.value) : ex.reps,
        weight: weightEl ? numOrNull(weightEl.value) : ex.weight,
        weight_unit: ex.weight_unit || 'kg',
        notes: ex.notes || null,
      });
    }
    currentIndex += 1;
    renderStage();
  }

  function renderStage() {
    stopTimer();

    if (currentIndex >= exercises.length) {
      finishSession();
      return;
    }

    const ex = exercises[currentIndex];
    statuses[currentIndex] = 'current';

    const targetParts = [];
    if (ex.sets && ex.reps) targetParts.push(ex.sets + ' × ' + ex.reps);
    else if (ex.sets) targetParts.push(ex.sets + ' sets');
    if (ex.weight) targetParts.push('@ ' + ex.weight + (ex.weight_unit || 'kg'));
    if (ex.work_seconds) targetParts.push(ex.work_seconds + 's hold');

    timerTotal = ex.work_seconds || ex.rest_seconds || 45;
    timeLeft = timerTotal;

    stage.innerHTML =
      '<div class="exercise-stage-card">' +
        '<div class="stage-index">Exercise ' + (currentIndex + 1) + ' of ' + exercises.length + '</div>' +
        '<h2 class="stage-name">' + escapeHtml(ex.exercise_name) + '</h2>' +
        '<div class="stage-target">' + escapeHtml(targetParts.join(' · ') || 'No target set — just go by feel') + '</div>' +
        '<div class="timer-ring-wrap">' +
          '<svg class="timer-ring" viewBox="0 0 200 200">' +
            '<circle class="timer-ring-bg" cx="100" cy="100" r="90"></circle>' +
            '<circle class="timer-ring-fg" id="ring-fg" cx="100" cy="100" r="90" ' +
              'stroke-dasharray="' + RING_CIRC + '" stroke-dashoffset="0"></circle>' +
          '</svg>' +
          '<div class="timer-ring-label">' +
            '<span class="timer-time" id="timer-time">' + formatTime(timeLeft) + '</span>' +
            '<span class="timer-caption">' + (ex.work_seconds ? 'hold' : 'rest timer') + '</span>' +
          '</div>' +
        '</div>' +
        '<div class="timer-controls">' +
          '<button type="button" id="timer-toggle" class="btn btn-ghost">▶ Start timer</button>' +
          '<button type="button" id="timer-add" class="btn btn-ghost">+15s</button>' +
        '</div>' +
        '<div class="actual-inputs">' +
          '<label>Sets<input type="number" id="actual-sets" value="' + (ex.sets != null ? ex.sets : '') + '"></label>' +
          '<label>Reps<input type="number" id="actual-reps" value="' + (ex.reps != null ? ex.reps : '') + '"></label>' +
          '<label>Weight<input type="number" step="0.5" id="actual-weight" value="' + (ex.weight != null ? ex.weight : '') + '"></label>' +
        '</div>' +
        '<div class="stage-actions">' +
          '<button type="button" id="skip-btn" class="btn btn-ghost">Skip</button>' +
          '<button type="button" id="done-btn" class="btn btn-play btn-lg">✓ Exercise done</button>' +
        '</div>' +
      '</div>';

    document.getElementById('timer-toggle').addEventListener('click', toggleTimer);
    document.getElementById('timer-add').addEventListener('click', function () {
      timeLeft += 15;
      timerTotal = Math.max(timerTotal, timeLeft);
      updateRing();
    });
    document.getElementById('skip-btn').addEventListener('click', function () { advance('skipped'); });
    document.getElementById('done-btn').addEventListener('click', function () { advance('done'); });

    updateRing();
    renderChecklist();
    updateProgress();
  }

  function finishSession() {
    stopTimer();
    stage.innerHTML = '<div class="exercise-stage-card stage-finishing"><p>Saving your session…</p></div>';
    renderChecklist();
    updateProgress();

    const tokenEl = document.querySelector('meta[name="csrf-token"]');
    fetch(config.finishUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': tokenEl ? tokenEl.content : '',
      },
      body: JSON.stringify({ completed: completedLog }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        const logged = data.logged || 0;
        doneSummary.textContent = logged + ' exercise' + (logged === 1 ? '' : 's') + ' logged for ' + config.dayName + '.';
        doneOverlay.hidden = false;
      })
      .catch(function () {
        doneSummary.textContent = "Couldn't save automatically — check your connection, your progress is shown above.";
        doneOverlay.hidden = false;
      });
  }

  if (endEarlyBtn) {
    endEarlyBtn.addEventListener('click', function () {
      if (!window.confirm('End this session now? Completed exercises will still be saved.')) return;
      currentIndex = exercises.length;
      finishSession();
    });
  }

  renderStage();
})();
