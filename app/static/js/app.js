// Shared across every page: toggle inline edit rows, confirm destructive
// actions, and auto-dismiss flash messages.
document.addEventListener('click', function (e) {
  const toggle = e.target.closest('[data-toggle]');
  if (toggle) {
    const target = document.getElementById(toggle.dataset.toggle);
    if (target) target.hidden = !target.hidden;
  }
});

document.addEventListener('submit', function (e) {
  const msg = e.target.dataset && e.target.dataset.confirm;
  if (msg && !window.confirm(msg)) e.preventDefault();
});

document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.flash').forEach(function (el, i) {
    setTimeout(function () { el.classList.add('flash-out'); }, 5000 + i * 150);
  });
});
