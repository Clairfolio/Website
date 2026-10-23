/*
  Menu de l'en-tête sur téléphone (guide Voix, UX et microtexte, « L'en-tête ») :
  bouton « Menu » qui devient « Fermer », la liste se déroule sous la barre ; la touche Échap ou un appui ailleurs
  ferme le menu (Échap rend le focus au bouton).
  Sans JavaScript, la navigation reste visible (styles/no-js.css).

  Retour d'appui des boutons-liens : sur téléphone, le :active du navigateur arrive après un court délai,
  un tap rapide ne le montre donc pas. Au clic, le bouton prend l'état « appuyé » (.is-pressed) jusqu'au
  changement de page ; au retour par l'historique, il est remis à l'état normal sans fondu.

  Ancres : si l'adresse (ou un lien de la page) vise un élément placé dans un volet replié (<details>), le volet
  s'ouvre, puis la page défile jusqu'à l'élément (cas-clara#rapports). Sans JavaScript, le volet reste fermé.
*/
(function () {
  document.addEventListener('click', function (event) {
    var link = event.target.closest('a.btn');
    if (!link || event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (link.target === '_blank' || link.hasAttribute('download')) return;
    if (!/^https?:$/.test(link.protocol)) return;   // mailto: ne change pas de page
    if (link.hash && link.pathname === location.pathname && link.search === location.search) return;   // ancre de la même page
    link.classList.add('is-pressed');
  });

  window.addEventListener('pageshow', function (event) {
    if (!event.persisted) return;
    var pressed = document.querySelectorAll('.btn.is-pressed');
    Array.prototype.forEach.call(pressed, function (el) {
      el.style.transition = 'none';
      el.classList.remove('is-pressed');
      void el.offsetWidth;
      el.style.transition = '';
    });
  });

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

  // Le menu se déroule par-dessus la page : toucher ailleurs le referme
  document.addEventListener('click', function (event) {
    if (button.getAttribute('aria-expanded') !== 'true') return;
    if (event.target.closest('#site-nav, #menu-toggle')) return;
    setOpen(false);
  });
})();

(function () {
  function revealTarget() {
    var id = decodeURIComponent(location.hash.slice(1));
    var target = id && document.getElementById(id);
    var panel = target && target.closest('details');
    if (!panel || panel.open) return;
    while (panel) {
      panel.open = true;
      panel = panel.parentElement && panel.parentElement.closest('details');
    }
    target.scrollIntoView();
  }

  window.addEventListener('hashchange', revealTarget);
  revealTarget();
})();
