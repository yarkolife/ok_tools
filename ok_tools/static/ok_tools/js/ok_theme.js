/*
 * One light/dark setting for every page of OK Tools.
 *
 * The Unfold admin keeps the user's choice in localStorage under
 * "adminTheme" (Alpine $persist(...).as("adminTheme"), JSON: "light" | "dark" | "auto").
 * Pages outside the admin (rental, dashboard, ...) read the same key, so
 * switching the theme anywhere switches it everywhere.
 *
 * Effect on <html>: class "dark" (Unfold/Tailwind, ok_theme.css) and
 * data-bs-theme="light|dark" (Bootstrap 5.3).
 *
 * Load it in <head> without defer, so the page does not flash light first.
 */
(function () {
    'use strict';

    var KEY = 'adminTheme';
    var ORDER = ['light', 'dark', 'auto'];
    var root = document.documentElement;
    var media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

    function preference() {
        try {
            var value = JSON.parse(localStorage.getItem(KEY));
            if (ORDER.indexOf(value) !== -1) {
                return value;
            }
        } catch (e) { /* storage blocked or not JSON */ }
        return 'auto';
    }

    function resolve(pref) {
        if (pref === 'dark' || (pref === 'auto' && media && media.matches)) {
            return 'dark';
        }
        return 'light';
    }

    function syncBootstrap() {
        var mode = root.classList.contains('dark') ? 'dark' : 'light';
        if (root.getAttribute('data-bs-theme') !== mode) {
            root.setAttribute('data-bs-theme', mode);
        }
        root.style.colorScheme = mode;
    }

    function apply() {
        var mode = resolve(preference());
        root.classList.toggle('dark', mode === 'dark');
        syncBootstrap();
        document.dispatchEvent(new CustomEvent('ok:themechange', { detail: { mode: mode, preference: preference() } }));
    }

    function set(pref) {
        try {
            localStorage.setItem(KEY, JSON.stringify(pref));
        } catch (e) { /* keep it for this page only */ }
        apply();
    }

    apply();

    if (media) {
        media.addEventListener('change', apply);
    }
    window.addEventListener('storage', function (event) {
        if (event.key === KEY) {
            apply();
        }
    });
    // Unfold switches html.dark itself; keep Bootstrap in step with it.
    new MutationObserver(syncBootstrap).observe(root, { attributes: true, attributeFilter: ['class'] });

    window.okTheme = {
        preference: preference,
        mode: function () { return resolve(preference()); },
        set: set,
        cycle: function () {
            set(ORDER[(ORDER.indexOf(preference()) + 1) % ORDER.length]);
        },
    };

    // Buttons with [data-ok-theme-toggle] cycle light -> dark -> system.
    document.addEventListener('click', function (event) {
        var button = event.target.closest && event.target.closest('[data-ok-theme-toggle]');
        if (button) {
            event.preventDefault();
            window.okTheme.cycle();
        }
    });
    function label() {
        var pref = preference();
        var icons = { light: 'light_mode', dark: 'dark_mode', auto: 'contrast' };
        document.querySelectorAll('[data-ok-theme-toggle]').forEach(function (button) {
            button.setAttribute('data-pref', pref);
            var icon = button.querySelector('[data-ok-theme-icon]');
            if (icon) {
                icon.textContent = icons[pref];
            }
        });
    }
    document.addEventListener('ok:themechange', label);
    document.addEventListener('DOMContentLoaded', label);
})();
