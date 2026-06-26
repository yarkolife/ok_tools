/* Visual region picker for CoverOverlay admin.
 *
 * Shows the overlay image (saved or freshly chosen) and lets the operator
 * drag/resize two zones on it:
 *   - the TEXT area (magenta) -> the text_area JSON field (with align/color and
 *     a live sample title),
 *   - the LOGO area (green) -> the logo_area JSON field (position + width).
 * Coordinates are stored in native pixels (default 1280x720).
 */
(function () {
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function toHex(c) {
    if (c && /^#?[0-9a-fA-F]{6}$/.test(c)) return c[0] === '#' ? c : '#' + c;
    return '#ffffff';
  }
  function parse(field) {
    var d;
    try { d = JSON.parse(field.value || '{}'); } catch (e) { d = {}; }
    return (typeof d === 'object' && d !== null) ? d : {};
  }

  function setupZone(stage, field, opts, getScale) {
    var data = parse(field);
    var rect = document.createElement('div');
    rect.className = 'crp-rect';
    rect.style.borderColor = opts.color;
    rect.style.background = opts.fill;
    var label = document.createElement('div');
    label.className = 'crp-text';
    label.textContent = opts.label;
    var handle = document.createElement('div');
    handle.className = 'crp-handle';
    handle.style.background = opts.color;
    rect.appendChild(label);
    rect.appendChild(handle);
    stage.appendChild(rect);

    function applyDefaults() {
      var d = opts.defaults;
      if (data.x == null) data.x = d.x;
      if (data.y == null) data.y = d.y;
      if (data.w == null) data.w = d.w;
      if (data.h == null) data.h = d.h;
      if (opts.isText) {
        if (!data.align) data.align = 'left';
        if (!data.color) data.color = '#FFFFFF';
      }
    }
    function sync() { field.value = JSON.stringify(data); }
    function renderLabel() {
      if (opts.isText) {
        label.style.color = data.color;
        label.style.justifyContent =
          data.align === 'center' ? 'center' : (data.align === 'right' ? 'flex-end' : 'flex-start');
        label.style.fontSize = Math.max(10, (data.h / getScale()) * 0.34) + 'px';
      } else {
        label.style.color = opts.color;
        label.style.fontSize = '13px';
      }
    }
    function place() {
      var s = getScale();
      rect.style.left = (data.x / s) + 'px';
      rect.style.top = (data.y / s) + 'px';
      rect.style.width = (data.w / s) + 'px';
      rect.style.height = (data.h / s) + 'px';
      renderLabel();
    }

    var drag = null;
    rect.addEventListener('mousedown', function (e) {
      if (e.target === handle) return;
      drag = { mode: 'move', sx: e.clientX, sy: e.clientY, x: data.x, y: data.y };
      e.preventDefault();
    });
    handle.addEventListener('mousedown', function (e) {
      drag = { mode: 'resize', sx: e.clientX, sy: e.clientY, w: data.w, h: data.h };
      e.preventDefault(); e.stopPropagation();
    });
    document.addEventListener('mousemove', function (e) {
      if (!drag) return;
      var s = getScale();
      var dx = (e.clientX - drag.sx) * s, dy = (e.clientY - drag.sy) * s;
      if (drag.mode === 'move') {
        data.x = clamp(Math.round(drag.x + dx), 0, opts.nativeW - data.w);
        data.y = clamp(Math.round(drag.y + dy), 0, opts.nativeH - data.h);
      } else {
        data.w = clamp(Math.round(drag.w + dx), 30, opts.nativeW - data.x);
        data.h = clamp(Math.round(drag.h + dy), 24, opts.nativeH - data.y);
      }
      place(); sync();
    });
    document.addEventListener('mouseup', function () { drag = null; });

    return {
      data: data, place: place, applyDefaults: applyDefaults, sync: sync,
      renderLabel: renderLabel,
    };
  }

  function init(picker) {
    var textField = picker.querySelector('textarea, input');
    if (!textField) return;
    var nativeW = parseInt(picker.dataset.nativeW, 10) || 1280;
    var nativeH = parseInt(picker.dataset.nativeH, 10) || 720;
    textField.classList.add('crp-json');

    var stage = document.createElement('div');
    stage.className = 'crp-stage';
    var img = document.createElement('img');
    img.className = 'crp-img';
    stage.appendChild(img);

    var note = document.createElement('div');
    note.className = 'crp-note';
    note.textContent = 'Bild auswählen oder speichern, um die Bereiche zu markieren.';

    var ctrl = document.createElement('div');
    ctrl.className = 'crp-ctrl';
    ctrl.innerHTML =
      '<span style="color:#e6007e;font-weight:bold;">■</span> Text · Ausrichtung: ' +
      '<select class="crp-align"><option value="left">links</option>' +
      '<option value="center">zentriert</option><option value="right">rechts</option></select>' +
      ' Farbe: <input type="color" class="crp-color">' +
      ' &nbsp; <span style="color:#2e8b2e;font-weight:bold;">■</span> Logo';

    picker.insertBefore(note, textField);
    picker.insertBefore(stage, textField);
    picker.insertBefore(ctrl, textField);
    var alignSel = ctrl.querySelector('.crp-align');
    var colorInp = ctrl.querySelector('.crp-color');

    var scale = 1;
    function getScale() { return scale; }

    var textZone = setupZone(stage, textField, {
      color: '#e6007e', fill: 'rgba(230,0,126,0.18)', label: 'Titel-Vorschau',
      isText: true, nativeW: nativeW, nativeH: nativeH,
      defaults: {
        x: Math.round(nativeW * 0.06), y: Math.round(nativeH * 0.70),
        w: Math.round(nativeW * 0.88), h: Math.round(nativeH * 0.22),
      },
    }, getScale);

    var logoField = document.getElementById('id_logo_area');
    var logoZone = null;
    if (logoField) {
      logoZone = setupZone(stage, logoField, {
        color: '#2e8b2e', fill: 'rgba(46,139,46,0.18)', label: 'LOGO',
        isText: false, nativeW: nativeW, nativeH: nativeH,
        defaults: {
          x: Math.round(nativeW * 0.74), y: Math.round(nativeH * 0.05),
          w: Math.round(nativeW * 0.20), h: Math.round(nativeH * 0.12),
        },
      }, getScale);

      // One-click corner presets for the logo zone.
      var presets = document.createElement('span');
      presets.style.marginLeft = '6px';
      presets.innerHTML = ' Ecke: ';
      var margin = 40;
      [['↖', 'l', 't'], ['↗', 'r', 't'],
       ['↙', 'l', 'b'], ['↘', 'r', 'b']].forEach(function (c) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.textContent = c[0];
        btn.title = 'Logo in diese Ecke';
        btn.style.margin = '0 2px';
        btn.addEventListener('click', function () {
          var d = logoZone.data;
          d.x = c[1] === 'l' ? margin : (nativeW - d.w - margin);
          d.y = c[2] === 't' ? margin : (nativeH - d.h - margin);
          logoZone.place();
          logoZone.sync();
        });
        presets.appendChild(btn);
      });
      ctrl.appendChild(presets);
    }

    function ready() {
      if (!img.clientWidth) return;
      scale = nativeW / img.clientWidth;
      textZone.applyDefaults(); textZone.place(); textZone.sync();
      if (logoZone) { logoZone.applyDefaults(); logoZone.place(); logoZone.sync(); }
      alignSel.value = textZone.data.align;
      colorInp.value = toHex(textZone.data.color);
      stage.style.display = ''; ctrl.style.display = ''; note.style.display = 'none';
    }
    img.addEventListener('load', ready);

    function showImage(src) {
      if (!src) { stage.style.display = 'none'; ctrl.style.display = 'none'; return; }
      img.src = src;
    }
    var initialUrl = picker.dataset.imageUrl;
    if (initialUrl) showImage(initialUrl);
    else { stage.style.display = 'none'; ctrl.style.display = 'none'; }

    var fileInput = document.getElementById('id_image');
    if (fileInput) {
      fileInput.addEventListener('change', function () {
        var file = fileInput.files && fileInput.files[0];
        if (!file) return;
        var fr = new FileReader();
        fr.onload = function () { showImage(fr.result); };
        fr.readAsDataURL(file);
      });
    }

    alignSel.addEventListener('change', function () {
      textZone.data.align = alignSel.value; textZone.renderLabel(); textZone.sync();
    });
    colorInp.addEventListener('input', function () {
      textZone.data.color = colorInp.value.toUpperCase(); textZone.renderLabel(); textZone.sync();
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.cover-region-picker').forEach(init);
  });
})();
