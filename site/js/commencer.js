/*
  Formulaire « Commencer » (guide Voix, UX et microtexte, « Formulaire »).
  - Sans JavaScript, le formulaire fonctionne : validation du navigateur, envoi par Netlify Forms, redirection vers /commencer/merci.
  - Avec JavaScript : pré-remplissage depuis l'adresse (?site=non, ?forfait=recommande), contrôle à l'envoi puis champ par champ
    après un premier essai (jamais pendant la frappe), résumé des erreurs en haut avec le focus sur son titre, réponses jamais effacées,
    états de l'envoi (« Envoi en cours… », échec avec « Réessayer l'envoi »).
*/
(function () {
  'use strict';

  var form = document.getElementById('formulaire');
  if (!form) return;
  form.noValidate = true;   // les messages sont les nôtres ; sans JS, le navigateur valide

  var summary = document.getElementById('resume-erreurs');
  var summaryTitle = document.getElementById('resume-titre');
  var summaryText = document.getElementById('resume-texte');
  var summaryList = document.getElementById('resume-liste');
  var failure = document.getElementById('echec');
  var failureTitle = document.getElementById('echec-titre');
  var retry = document.getElementById('reessayer');
  var button = document.getElementById('envoyer');
  var attempted = false;
  var sending = false;
  var NBSP = '\u00a0';

  /* Pré-remplissage : « Créer mon portfolio » coche « Non, je pars de zéro », « Choisir Recommandé » coche le forfait */
  var params = new URLSearchParams(window.location.search);
  var prefill = { site: 'deja-un-site', forfait: 'forfait' };   // paramètre d'adresse -> nom du champ
  Object.keys(prefill).forEach(function (param) {
    var key = params.get(param);
    if (!key || !/^[a-z-]+$/.test(key)) return;   // un paramètre inattendu est ignoré
    var radio = form.querySelector('input[name="' + prefill[param] + '"][data-key="' + key + '"]');
    if (radio) radio.checked = true;
  });

  /* Une date passée n'est pas proposée */
  function today() {
    var d = new Date();
    function pad(n) { return (n < 10 ? '0' : '') + n; }
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
  }
  var dateInput = form.elements['date-mise-en-ligne'];
  if (dateInput) dateInput.min = today();

  function checked(name) { return form.querySelector('input[name="' + name + '"]:checked'); }
  function value(name) { return (form.elements[name].value || '').trim(); }

  /* Les champs, dans l'ordre de la page. validate() renvoie le message d'erreur, ou une chaîne vide. */
  var fields = [
    { key: 'prenom', validate: function () { return value('prenom') ? '' : 'Indiquez votre prénom.'; } },
    { key: 'nom', validate: function () { return value('nom') ? '' : 'Indiquez votre nom.'; } },
    { key: 'email', validate: function () {
        var v = value('email');
        if (!v) return 'Indiquez votre adresse e-mail.';
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) ? '' : 'Cette adresse e-mail semble incomplète. Exemple : prenom@exemple.fr';
      } },
    { key: 'deja-un-site', group: true, validate: function () { return checked('deja-un-site') ? '' : 'Indiquez si vous avez déjà un site.'; } },
    { key: 'adresse-site', validate: function () {
        var v = value('adresse-site');
        if (!v) return '';
        return /^(https?:\/\/)?[^\s\/.]+(\.[^\s\/.]+)+(\/\S*)?$/i.test(v) ? '' : 'Cette adresse semble incomplète. Exemple : monsite.fr';
      } },
    { key: 'forfait', group: true, validate: function () { return checked('forfait') ? '' : 'Choisissez un forfait, ou «' + NBSP + 'Je ne sais pas encore' + NBSP + '».'; } },
    { key: 'date-mise-en-ligne', validate: function () {
        var v = value('date-mise-en-ligne');
        return v && v < today() ? 'Cette date est déjà passée. Choisissez une date à venir.' : '';
      } }
  ];

  function box(f) { return document.getElementById('champ-' + f.key); }
  function firstControl(f) { return box(f).querySelector('input, textarea'); }

  /* aria-describedby : l'aide toujours, l'erreur seulement quand elle est affichée */
  function describe(f, withError) {
    var target = f.group ? box(f) : firstControl(f);
    var ids = [];
    var help = box(f).querySelector('.field-help');
    if (help) ids.push(help.id);
    if (withError) ids.push('erreur-' + f.key);
    if (ids.length) target.setAttribute('aria-describedby', ids.join(' '));
    else target.removeAttribute('aria-describedby');
  }

  function setError(f, message) {
    var err = document.getElementById('erreur-' + f.key);
    var inputs = box(f).querySelectorAll('input, textarea');
    if (message) {
      err.querySelector('.field-error__text').textContent = message;
      err.hidden = false;
      box(f).classList.add('field--error');
      for (var i = 0; i < inputs.length; i++) inputs[i].setAttribute('aria-invalid', 'true');
    } else {
      err.hidden = true;
      box(f).classList.remove('field--error');
      for (var j = 0; j < inputs.length; j++) inputs[j].removeAttribute('aria-invalid');
    }
    describe(f, !!message);
  }

  /* Résumé en haut : « Corrigez 2 champs… » puis un lien par erreur */
  function renderSummary(errors) {
    if (!errors.length) { summary.hidden = true; return; }
    var n = errors.length;
    summaryText.textContent = 'Corrigez ' + n + NBSP + 'champ' + (n > 1 ? 's' : '') + ' pour envoyer votre demande.';
    summaryList.textContent = '';
    errors.forEach(function (e) {
      var li = document.createElement('li');
      var a = document.createElement('a');
      a.href = '#' + firstControl(e.field).id;
      a.textContent = e.message;
      li.appendChild(a);
      summaryList.appendChild(li);
    });
    summary.hidden = false;
  }

  function collect() {
    var errors = [];
    fields.forEach(function (f) {
      var m = f.validate();
      setError(f, m);
      if (m) errors.push({ field: f, message: m });
    });
    return errors;
  }

  /* Après un premier essai : champ par champ, à la sortie du champ (pas à la frappe) */
  function recheck(event) {
    if (!attempted) return;
    var wrapper = event.target.closest('.field');
    if (!wrapper) return;
    var f = fields.filter(function (x) { return box(x) === wrapper; })[0];
    if (!f) return;
    setError(f, f.validate());
    var errors = [];
    fields.forEach(function (x) { var m = x.validate(); if (m && !document.getElementById('erreur-' + x.key).hidden) errors.push({ field: x, message: m }); });
    renderSummary(errors);
  }
  form.addEventListener('change', recheck);
  form.addEventListener('focusout', recheck);

  function normalizeUrl() {
    var el = form.elements['adresse-site'];
    var v = (el.value || '').trim();
    if (v && !/^https?:\/\//i.test(v)) el.value = 'https://' + v;   // « monsite.fr » ne doit pas faire une erreur
  }

  function resetButton() {
    sending = false;
    button.disabled = false;
    button.textContent = 'Envoyer ma demande';
    button.removeAttribute('aria-busy');
  }

  function send() {
    normalizeUrl();
    failure.hidden = true;
    sending = true;
    button.disabled = true;
    button.textContent = 'Envoi en cours…';
    button.setAttribute('aria-busy', 'true');
    var action = form.getAttribute('action');
    fetch(action, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams(new FormData(form)).toString()
    }).then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      window.location.assign(action);   // la page de confirmation est une vraie page
    }).catch(function () {
      resetButton();
      failure.hidden = false;
      failureTitle.focus();             // les réponses restent dans le formulaire
    });
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    if (sending) return;
    attempted = true;
    failure.hidden = true;
    var errors = collect();
    renderSummary(errors);
    if (errors.length) { summaryTitle.focus(); return; }
    send();
  });

  if (retry) retry.addEventListener('click', function () { if (!sending) send(); });
})();
