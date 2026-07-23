/* Shared photo lightbox for rental pages (calendars and other server-rendered
 * views). Exposes window.openImageLightbox(url) and also enlarges any element
 * carrying a data-lightbox attribute on click.
 *
 * The image keeps its aspect ratio and is capped at the viewport, so portrait
 * and landscape photos both fit without cropping. Click anywhere or press Esc
 * to close.
 */
(function () {
  'use strict';

  var overlay = null;

  function close() {
    if (!overlay) return;
    overlay.remove();
    overlay = null;
    document.removeEventListener('keydown', onKey);
  }

  function onKey(event) {
    if (event.key === 'Escape') close();
  }

  function open(url) {
    if (!url) return;
    close();
    overlay = document.createElement('div');
    overlay.style.cssText =
      'position:fixed;inset:0;background:rgba(0,0,0,.8);display:flex;' +
      'align-items:center;justify-content:center;z-index:20000;' +
      'cursor:zoom-out;padding:24px;';
    var img = document.createElement('img');
    img.src = url;
    img.style.cssText =
      'max-width:92vw;max-height:92vh;width:auto;height:auto;' +
      'object-fit:contain;border-radius:8px;box-shadow:0 8px 40px rgba(0,0,0,.5);';
    overlay.appendChild(img);
    overlay.addEventListener('click', close);
    document.addEventListener('keydown', onKey);
    document.body.appendChild(overlay);
  }

  window.openImageLightbox = open;

  document.addEventListener('click', function (event) {
    var el = event.target.closest('[data-lightbox]');
    if (!el) return;
    event.preventDefault();
    event.stopPropagation();
    open(el.getAttribute('data-lightbox') || el.getAttribute('src'));
  });
})();
