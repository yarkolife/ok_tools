/* Double-submit guard for the admin.
 *
 * A slow page invites a second click on the same button, which sends the
 * form twice (two encodes of one video, two copies of a record). After the
 * first submit, every submit button of that form is shown as busy and a
 * second submit is swallowed until the page answers.
 *
 * - Only POST forms: search and filter forms (GET) stay untouched.
 * - Forms whose submit is cancelled by another script (validation, confirm(),
 *   fetch) are not locked: the guard runs after them and checks
 *   defaultPrevented.
 * - A submit that opens a new tab (formtarget/target "_blank", e.g. print)
 *   or a download leaves this page in place, so the lock is released after
 *   a few seconds.
 * - Pages restored from the back/forward cache are unlocked.
 * - <form data-allow-resubmit> opts out.
 */
(function () {
    'use strict';

    var NEW_TAB_RELEASE_MS = 3000;
    var FALLBACK_RELEASE_MS = 20000;
    var BUSY_CLASS = 'ok-submitting';

    function submitControls(form) {
        var controls = Array.prototype.slice.call(form.querySelectorAll(
            'button:not([type]), button[type="submit"], input[type="submit"], input[type="image"]'));
        if (form.id) {
            var outside = document.querySelectorAll(
                'button[form="' + form.id + '"], input[type="submit"][form="' + form.id + '"]');
            Array.prototype.forEach.call(outside, function (control) {
                if (controls.indexOf(control) === -1 && (control.type === 'submit' || control.tagName === 'BUTTON')) {
                    controls.push(control);
                }
            });
        }
        return controls;
    }

    function lock(form) {
        form.dataset.okSubmitting = '1';
        submitControls(form).forEach(function (control) {
            control.classList.add(BUSY_CLASS);
            control.setAttribute('aria-disabled', 'true');
        });
    }

    function release(form) {
        delete form.dataset.okSubmitting;
        submitControls(form).forEach(function (control) {
            control.classList.remove(BUSY_CLASS);
            control.removeAttribute('aria-disabled');
        });
    }

    document.addEventListener('submit', function (event) {
        var form = event.target;
        if (!(form instanceof HTMLFormElement) || form.hasAttribute('data-allow-resubmit')) {
            return;
        }
        if ((form.getAttribute('method') || 'get').toLowerCase() !== 'post') {
            return;
        }
        if (form.dataset.okSubmitting === '1') {
            event.preventDefault();
            event.stopImmediatePropagation();
            return;
        }
        if (event.defaultPrevented) {
            return;
        }
        var submitter = event.submitter;
        var target = (submitter && submitter.getAttribute('formtarget')) || form.getAttribute('target') || '';
        // Lock after the browser has collected the form data, so the clicked
        // button still sends its name.
        window.setTimeout(function () { lock(form); }, 0);
        window.setTimeout(function () { release(form); },
            target === '_blank' ? NEW_TAB_RELEASE_MS : FALLBACK_RELEASE_MS);
    });

    window.addEventListener('pageshow', function (event) {
        if (!event.persisted) {
            return;
        }
        Array.prototype.forEach.call(document.querySelectorAll('form[data-ok-submitting]'), release);
    });
})();
