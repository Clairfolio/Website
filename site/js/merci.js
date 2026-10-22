/* Page de confirmation : le focus va sur le titre, pour que « C'est bien reçu. » soit lu sans qu'on ait à le chercher. */
(function () {
  var title = document.getElementById('titre');
  if (title) title.focus();
})();
