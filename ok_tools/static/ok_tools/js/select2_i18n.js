/*
 * German texts for select2 dropdowns that Unfold initialises without
 * Django's i18n file (autocomplete filters of the change lists). Runs once
 * the page is parsed, before jQuery's ready handlers create the dropdowns,
 * and only defines the language module when no page script did.
 */
(function () {
    'use strict';
    var MESSAGES = {
        de: {
            errorLoading: function () { return 'Die Ergebnisse konnten nicht geladen werden.'; },
            inputTooLong: function (a) { return 'Bitte ' + (a.input.length - a.maximum) + ' Zeichen weniger eingeben'; },
            inputTooShort: function (a) { return 'Bitte ' + (a.minimum - a.input.length) + ' Zeichen mehr eingeben'; },
            loadingMore: function () { return 'Lade mehr Ergebnisse…'; },
            maximumSelected: function (a) {
                return 'Sie können nur ' + a.maximum + ' Element' + (a.maximum !== 1 ? 'e' : '') + ' auswählen';
            },
            noResults: function () { return 'Keine Übereinstimmungen gefunden'; },
            searching: function () { return 'Suche…'; },
            removeAllItems: function () { return 'Entferne alle Elemente'; }
        }
    };

    function register() {
        var jq = window.django && window.django.jQuery;
        var amd = jq && jq.fn && jq.fn.select2 && jq.fn.select2.amd;
        var lang = (document.documentElement.lang || '').toLowerCase().split('-')[0];
        if (!amd || !MESSAGES[lang]) return;
        var name = 'select2/i18n/' + lang;
        try {
            amd.require(name);          // Django's i18n file is on the page
        } catch (e) {
            amd.define(name, [], function () { return MESSAGES[lang]; });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', register);
    } else {
        register();
    }
})();
