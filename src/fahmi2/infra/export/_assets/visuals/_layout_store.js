/* Persistance des positions de nœuds en localStorage (HTML autonome, file://).
   Bas niveau : sonde de disponibilité au démarrage + read/write/remove, tout
   enveloppé dans try/catch — sous Safari/file://, navigation privée ou cookies
   bloqués, l'ACCÈS lui-même à localStorage peut lever (MDN : comportement file://
   « undefined »). L'intégration Cytoscape (événements, restauration) reste chez le
   consommateur. Partagé par knowledge_map.js et diagram_board.js. */
(function () {
  "use strict";

  function probe() {
    try {
      var k = "fahmi2:probe";
      window.localStorage.setItem(k, "1");
      window.localStorage.removeItem(k);
      return true;
    } catch (e) {
      return false;
    }
  }

  var AVAILABLE = probe();

  window.__fahmi2LayoutStore = {
    // Vrai si localStorage est utilisable (sinon persistance silencieusement désactivée).
    available: AVAILABLE,
    // Lit une map {id: {x, y}} sauvegardée, ou null (absente/indisponible/illisible).
    read: function (key) {
      if (!AVAILABLE) { return null; }
      try {
        var raw = window.localStorage.getItem(key);
        return raw ? JSON.parse(raw) : null;
      } catch (e) {
        return null;
      }
    },
    // Écrit une map {id: {x, y}} (silencieux en cas de quota/sécurité).
    write: function (key, map) {
      if (!AVAILABLE) { return; }
      try {
        window.localStorage.setItem(key, JSON.stringify(map));
      } catch (e) {
        /* quota dépassé / sécurité : on ignore */
      }
    },
    // Efface la disposition sauvegardée (revient au layout calculé au prochain rendu).
    remove: function (key) {
      if (!AVAILABLE) { return; }
      try {
        window.localStorage.removeItem(key);
      } catch (e) {
        /* noop */
      }
    }
  };
})();
