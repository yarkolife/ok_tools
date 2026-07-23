/* Photo lightbox for the inventory admin.
 *
 * Any link marked with data-photo-lightbox opens its target in an overlay
 * instead of a new tab. The image keeps its aspect ratio and is capped at the
 * viewport, so portrait and landscape photos both fit without cropping.
 * Used by the photo column in the change list and by the gallery on the form.
 */
(function () {
  'use strict';

  var overlay = null;

  function close() {
    if (!overlay) return;
    overlay.remove();
    overlay = null;
    document.removeEventListener('keydown', onKeyDown);
  }

  function onKeyDown(event) {
    if (event.key === 'Escape') close();
  }

  function open(src, caption, originalUrl, originalLabel) {
    close();

    overlay = document.createElement('div');
    overlay.className = 'inventory-photo-lightbox';
    overlay.style.cssText = [
      'position:fixed', 'inset:0', 'z-index:2000',
      'background:rgba(0,0,0,.8)',
      'display:flex', 'flex-direction:column',
      'align-items:center', 'justify-content:center',
      'gap:12px', 'padding:24px', 'cursor:zoom-out'
    ].join(';');

    var img = document.createElement('img');
    img.src = src;
    img.alt = caption || '';
    img.style.cssText = [
      'max-width:92vw', 'max-height:88vh',
      'width:auto', 'height:auto', 'object-fit:contain',
      'border-radius:6px', 'box-shadow:0 8px 40px rgba(0,0,0,.5)',
      'background:#fff', 'cursor:default'
    ].join(';');
    // Clicking the photo itself should not dismiss the overlay.
    img.addEventListener('click', function (event) { event.stopPropagation(); });
    overlay.appendChild(img);

    var footer = document.createElement('div');
    footer.style.cssText = 'display:flex;align-items:center;gap:16px;color:#fff;font-size:13px;max-width:92vw;';

    if (caption) {
      var label = document.createElement('span');
      label.textContent = caption;
      label.style.cssText = 'word-break:break-all;';
      footer.appendChild(label);
    }

    // A way out to the untouched original for anyone who needs full resolution.
    if (originalUrl) {
      var full = document.createElement('a');
      full.href = originalUrl;
      full.target = '_blank';
      full.rel = 'noopener';
      full.textContent = originalLabel || 'Original';
      full.style.cssText = 'color:#fff;text-decoration:underline;white-space:nowrap;';
      full.addEventListener('click', function (event) { event.stopPropagation(); });
      footer.appendChild(full);
    }

    if (footer.childNodes.length) overlay.appendChild(footer);

    var closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.setAttribute('aria-label', 'Close');
    closeButton.innerHTML = '&times;';
    closeButton.style.cssText = [
      'position:absolute', 'top:12px', 'right:20px',
      'background:none', 'border:none', 'color:#fff',
      'font-size:34px', 'line-height:1', 'cursor:pointer', 'padding:4px'
    ].join(';');
    closeButton.addEventListener('click', close);
    overlay.appendChild(closeButton);

    overlay.addEventListener('click', close);
    document.addEventListener('keydown', onKeyDown);
    document.body.appendChild(overlay);
  }

  document.addEventListener('click', function (event) {
    var link = event.target.closest('a[data-photo-lightbox]');
    if (!link) return;
    // Let modifier / middle clicks through: the browser then opens the link
    // target (the full original) in a new tab, as the user expects.
    if (event.defaultPrevented || event.button !== 0 ||
        event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }
    event.preventDefault();
    // Prefer the lightweight preview named in the attribute; fall back to the
    // link target (the full original) when no preview URL is given.
    var preview = link.getAttribute('data-photo-lightbox');
    var original = link.getAttribute('href');
    open(preview || original, link.getAttribute('title'), original,
         link.getAttribute('data-original-label'));
  });
})();
