/* ToxiGram — main.js */

// ── Like Button (AJAX) ───────────────────────────────────────────────────────
document.addEventListener('click', function(e) {
  const btn = e.target.closest('.like-btn');
  if (!btn) return;

  const postId = btn.dataset.postId;
  const countEl = document.getElementById(`like-count-${postId}`);
  const heartEl = btn.querySelector('.heart-icon');

  fetch(`/like/${postId}`, { method: 'POST' })
    .then(r => r.json())
    .then(data => {
      countEl.textContent = data.count;
      if (data.liked) {
        btn.classList.add('liked');
        heartEl.textContent = '❤️';
        // Quick pulse animation
        heartEl.style.transform = 'scale(1.4)';
        setTimeout(() => heartEl.style.transform = 'scale(1)', 200);
      } else {
        btn.classList.remove('liked');
        heartEl.textContent = '🤍';
      }
    });
});

// ── Comment Toggle ───────────────────────────────────────────────────────────
document.addEventListener('click', function(e) {
  const btn = e.target.closest('.comment-toggle-btn');
  if (!btn) return;
  const postId = btn.dataset.postId;
  const section = document.getElementById(`comments-${postId}`);
  if (!section) return;
  // Always visible on feed — but toggle on mobile or if needed
  section.style.display = section.style.display === 'none' ? 'block' : 'block';
});

// ── Live Toxicity Analysis (debounced) ───────────────────────────────────────
let debounceTimers = {};

function liveAnalyze(textarea, postId) {
  const text = textarea.value.trim();
  const meter = document.getElementById(`live-meter-${postId}`);
  const bar   = document.getElementById(`live-bar-${postId}`);
  const label = document.getElementById(`live-label-${postId}`);

  if (!text) {
    if (meter) meter.style.display = 'none';
    return;
  }

  if (meter) meter.style.display = 'flex';

  // Debounce 350ms
  clearTimeout(debounceTimers[postId]);
  debounceTimers[postId] = setTimeout(() => {
    fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    })
    .then(r => r.json())
    .then(data => {
      if (bar) {
        bar.style.width = data.toxicity_percent + '%';
        bar.style.background = data.color;
      }
      if (label) {
        label.textContent = `${data.label} · ${data.toxicity_percent}%`;
        label.style.color = data.color;
      }
    });
  }, 350);
}

// ── Auto-resize textarea ─────────────────────────────────────────────────────
document.addEventListener('input', function(e) {
  if (e.target.classList.contains('comment-input')) {
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  }
});

// ── Flash auto-dismiss ───────────────────────────────────────────────────────
setTimeout(() => {
  document.querySelectorAll('.flash').forEach(el => {
    el.style.transition = 'opacity .4s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 400);
  });
}, 3000);

// ── Animate toxicity bars on page load ───────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  // Animate all tox bars from 0 → value
  document.querySelectorAll('.tox-bar-fill, .sbar-fill').forEach(bar => {
    const target = bar.style.width;
    bar.style.width = '0';
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        bar.style.width = target;
      });
    });
  });
});
