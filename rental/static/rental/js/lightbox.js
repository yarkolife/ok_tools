/* Shared photo lightbox with carousel navigation for rental pages and the
 * inventory admin. Enlarges a photo and, when several are given, lets the user
 * page through them with on-screen arrows or the Left/Right keys.
 *
 * Programmatic:  window.openImageLightbox(slides, startIndex)
 *   slides: a URL string, an array of URL strings, or an array of
 *           { src, full?, caption? } objects.
 *
 * Declarative: click any element carrying data-lightbox.
 *   - data-lightbox           single URL, or a JSON array (strings or objects)
 *   - data-lightbox-full      original-size URL for the "Original" link
 *   - data-lightbox-caption   caption text
 *   - data-lightbox-index     start index into the array (default 0)
 *   - data-lightbox-group     elements sharing a group form one carousel;
 *                             the clicked one becomes the start slide
 *   - data-lightbox-original-label  link text for the original (default "Original")
 */
(function () {
  'use strict';

  var overlay = null;
  var slides = [];
  var index = 0;
  var originalLabel = 'Original';

  function normalize(input) {
    var list = Array.isArray(input) ? input : [input];
    return list
      .map(function (entry) {
        if (!entry) return null;
        return typeof entry === 'string' ? { src: entry } : entry;
      })
      .filter(function (s) { return s && s.src; });
  }

  function close() {
    if (!overlay) return;
    overlay.remove();
    overlay = null;
    slides = [];
    document.removeEventListener('keydown', onKey);
  }

  function onKey(event) {
    if (event.key === 'Escape') close();
    else if (event.key === 'ArrowLeft') go(-1);
    else if (event.key === 'ArrowRight') go(1);
  }

  function go(delta) {
    if (slides.length < 2) return;
    index = (index + delta + slides.length) % slides.length;
    render();
  }

  function render() {
    if (!overlay) return;
    var slide = slides[index];
    overlay.querySelector('[data-lb-img]').src = slide.src;
    var counter = overlay.querySelector('[data-lb-counter]');
    counter.textContent = slides.length > 1
      ? (index + 1) + ' / ' + slides.length : '';
    var cap = overlay.querySelector('[data-lb-caption]');
    cap.textContent = slide.caption || '';
    var orig = overlay.querySelector('[data-lb-original]');
    if (slide.full) {
      orig.style.display = '';
      orig.href = slide.full;
    } else {
      orig.style.display = 'none';
    }
  }

  function navButton(dir) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.setAttribute('aria-label', dir < 0 ? 'Previous' : 'Next');
    btn.innerHTML = dir < 0 ? '&#8249;' : '&#8250;';
    btn.style.cssText =
      'position:absolute;top:50%;transform:translateY(-50%);' +
      (dir < 0 ? 'left:16px;' : 'right:16px;') +
      'width:48px;height:48px;border:none;border-radius:50%;' +
      'background:rgba(255,255,255,.15);color:#fff;font-size:30px;line-height:1;' +
      'cursor:pointer;display:flex;align-items:center;justify-content:center;';
    btn.addEventListener('click', function (e) { e.stopPropagation(); go(dir); });
    return btn;
  }

  function open(input, startIndex, opts) {
    slides = normalize(input);
    if (!slides.length) return;
    close();
    index = Math.min(Math.max(startIndex || 0, 0), slides.length - 1);
    originalLabel = (opts && opts.originalLabel) || 'Original';

    overlay = document.createElement('div');
    overlay.style.cssText =
      'position:fixed;inset:0;background:rgba(0,0,0,.85);display:flex;' +
      'flex-direction:column;align-items:center;justify-content:center;' +
      'gap:12px;z-index:20000;cursor:zoom-out;padding:24px;';

    var img = document.createElement('img');
    img.setAttribute('data-lb-img', '');
    img.style.cssText =
      'max-width:92vw;max-height:86vh;width:auto;height:auto;object-fit:contain;' +
      'border-radius:8px;box-shadow:0 8px 40px rgba(0,0,0,.5);cursor:default;';
    img.addEventListener('click', function (e) { e.stopPropagation(); });
    overlay.appendChild(img);

    var footer = document.createElement('div');
    footer.style.cssText =
      'display:flex;align-items:center;gap:16px;color:#fff;font-size:13px;max-width:92vw;';
    var counter = document.createElement('span');
    counter.setAttribute('data-lb-counter', '');
    counter.style.cssText = 'font-variant-numeric:tabular-nums;';
    var caption = document.createElement('span');
    caption.setAttribute('data-lb-caption', '');
    caption.style.cssText = 'word-break:break-all;';
    var original = document.createElement('a');
    original.setAttribute('data-lb-original', '');
    original.target = '_blank';
    original.rel = 'noopener';
    original.textContent = originalLabel;
    original.style.cssText = 'color:#fff;text-decoration:underline;white-space:nowrap;';
    original.addEventListener('click', function (e) { e.stopPropagation(); });
    footer.appendChild(counter);
    footer.appendChild(caption);
    footer.appendChild(original);
    overlay.appendChild(footer);

    if (slides.length > 1) {
      overlay.appendChild(navButton(-1));
      overlay.appendChild(navButton(1));
    }

    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.setAttribute('aria-label', 'Close');
    closeBtn.innerHTML = '&times;';
    closeBtn.style.cssText =
      'position:absolute;top:12px;right:20px;background:none;border:none;' +
      'color:#fff;font-size:34px;line-height:1;cursor:pointer;padding:4px;';
    closeBtn.addEventListener('click', close);
    overlay.appendChild(closeBtn);

    overlay.addEventListener('click', close);
    document.addEventListener('keydown', onKey);
    document.body.appendChild(overlay);
    render();
  }

  window.openImageLightbox = open;

  function parseSlides(raw) {
    if (!raw) return null;
    var trimmed = raw.trim();
    if (trimmed.charAt(0) === '[') {
      try { return JSON.parse(trimmed); } catch (e) { return [raw]; }
    }
    return [raw];
  }

  document.addEventListener('click', function (event) {
    var el = event.target.closest('[data-lightbox]');
    if (!el) return;
    // Let modifier / middle clicks on a real link open the original normally.
    if ((event.button && event.button !== 0) ||
        event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      if (el.tagName === 'A' && el.getAttribute('href')) return;
    }
    event.preventDefault();
    event.stopPropagation();

    var opts = { originalLabel: el.getAttribute('data-lightbox-original-label') };
    var group = el.getAttribute('data-lightbox-group');
    if (group) {
      var members = Array.prototype.slice.call(
        document.querySelectorAll('[data-lightbox-group="' + group + '"]'));
      var built = members.map(function (m) {
        return {
          src: m.getAttribute('data-lightbox'),
          full: m.getAttribute('data-lightbox-full') || undefined,
          caption: m.getAttribute('data-lightbox-caption') || undefined,
        };
      });
      open(built, members.indexOf(el), opts);
      return;
    }

    var parsed = parseSlides(el.getAttribute('data-lightbox'));
    // A bare single URL can still carry a full/caption from sibling attributes.
    if (parsed && parsed.length === 1 && typeof parsed[0] === 'string') {
      parsed = [{
        src: parsed[0],
        full: el.getAttribute('data-lightbox-full') || undefined,
        caption: el.getAttribute('data-lightbox-caption') || undefined,
      }];
    }
    open(parsed, parseInt(el.getAttribute('data-lightbox-index'), 10) || 0, opts);
  });
})();
