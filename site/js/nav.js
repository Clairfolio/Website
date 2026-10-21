/*
  Menu de l'en-tête sur téléphone (guide Voix, UX et microtexte, « L'en-tête ») :
  bouton « Menu » qui devient « Fermer », la touche Échap ferme le menu et rend le focus au bouton.
  Sans JavaScript, la navigation reste visible (styles/no-js.css).
*/
(function () {
  var button = document.getElementById('menu-toggle');
  var nav = document.getElementById('site-nav');
  if (!button || !nav) return;
  var label = button.querySelector('.menu-toggle__label');

  function setOpen(open) {
    button.setAttribute('aria-expanded', open ? 'true' : 'false');
    label.textContent = open ? 'Fermer' : 'Menu';
    nav.classList.toggle('is-open', open);
  }

  button.addEventListener('click', function () {
    setOpen(button.getAttribute('aria-expanded') !== 'true');
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && button.getAttribute('aria-expanded') === 'true') {
      setOpen(false);
      button.focus();
    }
  });

  nav.addEventListener('click', function (event) {
    if (event.target.closest('a')) setOpen(false);
  });
})();
