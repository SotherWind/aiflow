/* aiflow 组件对照：把样式包画的组件和真实组件库渲染的同一组件逐个比较，列出尺寸、颜色、字号、文字位置不一样的地方。
   样式包是照组件库仿出来的，仿错一处，所有原型和设计稿都跟着错；前端用真组件库实现，页面就和设计稿对不上。
   用法（Playwright 等浏览器工具，两个页面都要用 http 打开）：
   1. 打开 kit.html?preset=element-plus，注入本文件，A = aiflowParityMeasure('kit')
   2. 打开 element-plus.html，等 window.__ready 为 true，注入本文件，B = aiflowParityMeasure('element-plus')
   3. aiflowParityCompare(A, B) 返回差异列表，空列表表示两边一致。
   差异怎么处理见 references/design-system.md「样式包和组件库对照」。 */
(function () {
  var CLEAR = 'rgba(0, 0, 0, 0)';
  var BOX = ['height', 'radius', 'bg', 'edge', 'shadow', 'fontSize', 'weight', 'color', 'left', 'top'];
  var BOX_W = BOX.concat('width');
  var TEXT = ['fontSize', 'weight', 'color', 'lineHeight'];
  var FIELD = ['height', 'radius', 'bg', 'edge', 'shadow', 'fontSize', 'color', 'left'];
  // 名称、所在的 [data-pair] 容器、样式包一侧的选择器、比较项
  var PAIRS = [
    ['btn', 'btn', '.btn', BOX_W], ['btn-pri', 'btn-pri', '.btn', BOX_W], ['btn-lg', 'btn-lg', '.btn', BOX_W],
    ['btn-sm', 'btn-sm', '.btn', BOX_W], ['btn-danger', 'btn-danger', '.btn', BOX_W],
    ['btn-link', 'btn-link', '.btn', ['height', 'bg', 'edge', 'fontSize', 'weight', 'color']],
    ['input', 'input', '.inp', FIELD], ['input-lg', 'input-lg', '.inp', FIELD],
    ['textarea', 'textarea', '.inp', ['radius', 'bg', 'edge', 'shadow', 'fontSize', 'color', 'left', 'top']],
    ['select', 'select', '.inp', FIELD],
    ['label', 'label', 'label', TEXT], ['label-star', 'label', 'label::before', ['color', 'marginRight']],
    ['ferr', 'ferr', '.ferr', TEXT],
    ['tag', 'tag', '.tag', BOX_W], ['tag-info', 'tag-info', '.tag', BOX_W],
    ['badge', 'badge', '.badge', BOX_W], ['avatar', 'avatar', '.avatar', BOX_W],
    ['alert', 'alert', '.alert', ['height', 'radius', 'bg', 'edge', 'shadow', 'left', 'top']], ['alert-text', 'alert', '.alert > div', TEXT],
    ['msg', 'msg', '.msg', ['height', 'radius', 'bg', 'edge', 'shadow', 'left', 'top']], ['msg-text', 'msg', '.msg', TEXT],
    ['pager', 'pager', '.pg.on', BOX_W], ['pager-item', 'pager', '.pg:not(.on)', BOX_W],
    ['tl-dot', 'timeline', '.tl li::before', ['height', 'width', 'radius', 'bg']],
    ['tl-text', 'timeline', '.tl li', TEXT], ['tl-time', 'timeline', '.tl .t', TEXT],
    ['result-icon', 'result', '.result .ic', ['height', 'width']],
    ['result-title', 'result', '.result h3', TEXT], ['result-sub', 'result', '.result p', TEXT],
    ['card', 'card', '.card', ['radius', 'bg', 'edge', 'shadow']],
    ['card-hd', 'card', '.card-hd', ['height', 'edge', 'fontSize', 'weight', 'color', 'left', 'top']],
    ['card-bd', 'card', '.card-bd', ['fontSize', 'color', 'left', 'top']],
    ['th', 'table', '.tbl th', ['height', 'bg', 'edge', 'fontSize', 'weight', 'color', 'left', 'top']],
    ['td', 'table', '.tbl td', ['height', 'bg', 'edge', 'fontSize', 'weight', 'color', 'left', 'top']],
    ['dialog', 'dialog', '.modal', ['width', 'height', 'radius', 'bg', 'shadow', 'left', 'top']], ['dialog-title', 'dialog', '.modal h4', TEXT],
    ['dialog-x', 'dialog', '.modal::after', ['width', 'height']], ['dialog-gap', 'dialog', '.modal .ft .btn', ['gap']],
    ['btn-dis', 'btn-dis', '.btn', BOX_W], ['btn-gap', 'btn-gap', '.btn', ['gap']],
    ['input-focus', 'input-focus', '.inp', ['edge', 'shadow']], ['input-err', 'ferr', '.inp', ['edge']], ['fi', 'label', '.fi', ['marginBottom']],
    ['menu-on', 'menu', '.menu-item.on', ['height', 'fontSize', 'weight', 'color', 'bg', 'edge', 'left']],
    ['menu-item', 'menu', '.menu-item:not(.on)', ['height', 'fontSize', 'weight', 'color', 'bg', 'edge', 'left']],
    ['crumb', 'crumb', '.crumb', TEXT.concat('height')], ['crumb-sep', 'crumb', '.crumb .sep', ['fontSize', 'weight', 'color', 'marginRight']],
    ['crumb-last', 'crumb', '.crumb b', TEXT], ['crumb-link', 'crumb-link', '.crumb a', TEXT],
    ['chk-box', 'chk', '.chk::before', ['height', 'width', 'radius', 'bg', 'edge']], ['chk-text', 'chk', '.chk', TEXT],
    ['tab-on', 'tabs', '.tabs .on', ['height', 'fontSize', 'weight', 'color']], ['tab', 'tabs', '.tabs span:not(.on)', ['height', 'fontSize', 'weight', 'color']],
    ['tab-gap', 'tabs', '.tabs span', ['textGap']],
    ['desc-label', 'desc', '.desc dt', TEXT.concat('pitch')], ['desc-content', 'desc', '.desc dd', TEXT],
    ['empty', 'empty', '.empty', ['padding']], ['empty-img', 'empty', '.empty .box', ['height', 'width']], ['empty-text', 'empty', '.empty', TEXT],
    ['skel', 'skel', '.skel', ['height', 'radius', 'pitch']],
    ['step-done', 'steps', '.step.done .dot', ['height', 'width', 'radius', 'bg', 'edge', 'color']],
    ['step-cur', 'steps', '.step.cur .dot', ['height', 'width', 'radius', 'bg', 'edge', 'color']],
    ['step-wait', 'steps', '.step:not(.done):not(.cur) .dot', ['height', 'width', 'radius', 'bg', 'edge', 'color']],
    ['step-title-done', 'steps', '.step.done .tt', TEXT], ['step-title-cur', 'steps', '.step.cur .tt', TEXT],
    ['step-title-wait', 'steps', '.step:not(.done):not(.cur) .tt', TEXT], ['step-line', 'steps', '.step.cur::after', ['height', 'bg']],
    ['pop', 'pop', '.pop', ['radius', 'bg', 'edge', 'shadow']],
    ['result-box', 'result', '.result', ['height', 'padding']], ['tl-pitch', 'timeline', '.tl li', ['pitch']]
  ];
  // 组件库一侧的选择器；@ 开头表示组件库把它挂到了 body 上，在整个页面里找。加一个组件库就在这里加一组
  var LIBS = {
    'element-plus': {
      btn: '.el-button', 'btn-pri': '.el-button', 'btn-lg': '.el-button', 'btn-sm': '.el-button', 'btn-danger': '.el-button', 'btn-link': '.el-button',
      input: '.el-input__wrapper', 'input-lg': '.el-input__wrapper', textarea: '.el-textarea__inner', select: '.el-select__wrapper',
      label: '.el-form-item__label', 'label-star': '.el-form-item__label::before', ferr: '.el-form-item__error',
      tag: '.el-tag', 'tag-info': '.el-tag', badge: '.el-badge__content', avatar: '.el-avatar',
      alert: '.el-alert', 'alert-text': '.el-alert__title', msg: '@.el-message', 'msg-text': '@.el-message__content',
      pager: '.el-pager li.is-active', 'pager-item': '.el-pager li:not(.is-active)',
      'tl-dot': '.el-timeline-item__node', 'tl-text': '.el-timeline-item__content', 'tl-time': '.el-timeline-item__timestamp',
      'result-icon': '.el-result__icon svg', 'result-title': '.el-result__title p', 'result-sub': '.el-result__subtitle p',
      card: '.el-card', 'card-hd': '.el-card__header', 'card-bd': '.el-card__body',
      th: '.el-table th.el-table__cell', td: '.el-table td.el-table__cell', dialog: '@.el-dialog', 'dialog-title': '@.el-dialog__title',
      'dialog-x': '@.el-dialog__headerbtn', 'dialog-gap': '@.el-dialog__footer .el-button',
      'btn-dis': '.el-button', 'btn-gap': '.el-button', 'input-focus': '.el-input__wrapper', 'input-err': '.el-input__wrapper', fi: '.el-form-item',
      'menu-on': '.el-menu-item.is-active', 'menu-item': '.el-menu-item:not(.is-active)',
      crumb: '.el-breadcrumb', 'crumb-sep': '.el-breadcrumb__separator', 'crumb-last': '.el-breadcrumb__item:last-child .el-breadcrumb__inner',
      'crumb-link': '.el-breadcrumb__inner.is-link',
      'chk-box': '.el-checkbox__inner', 'chk-text': '.el-checkbox__label',
      'tab-on': '.el-tabs__item.is-active', tab: '.el-tabs__item:not(.is-active)', 'tab-gap': '.el-tabs__item',
      'desc-label': '.el-descriptions__label', 'desc-content': '.el-descriptions__content',
      empty: '.el-empty', 'empty-img': '.el-empty__image', 'empty-text': '.el-empty__description p', skel: '.el-skeleton__item',
      'step-done': '.el-step__head.is-finish .el-step__icon', 'step-cur': '.el-step__head.is-process .el-step__icon',
      'step-wait': '.el-step__head.is-wait .el-step__icon', 'step-title-done': '.el-step__title.is-finish',
      'step-title-cur': '.el-step__title.is-process', 'step-title-wait': '.el-step__title.is-wait', 'step-line': '.el-step:nth-child(3) .el-step__line',
      pop: '@.el-popover', 'result-box': '.el-result', 'tl-pitch': '.el-timeline-item'
    }
  };
  var NAMES = { height: '高', width: '宽', radius: '圆角', bg: '背景色', edge: '边框', shadow: '阴影', fontSize: '字号', weight: '字重',
                color: '文字颜色', lineHeight: '行高', left: '文字距左边', top: '文字距上边', marginRight: '右外边距', marginBottom: '下外边距',
                padding: '内边距', gap: '和下一个的间距', textGap: '和下一个的文字间距', pitch: '到下一个的距离' };
  var TOL = { height: 0.75, width: 1.5, radius: 0.5, fontSize: 0.25, lineHeight: 0.75, left: 1.5, top: 1.5, marginRight: 0.5, marginBottom: 0.5,
              gap: 1, textGap: 1.5, pitch: 1 };

  function px(v) { return parseFloat(v) || 0; }
  // 系统缩放 125%、150% 时 1px 边框被画成 0.8px、0.67px；按整像素补回来，两边才可比
  function borderFix(s, a, b) {
    return [a, b].reduce(function (sum, side) { var w = px(s['border' + side + 'Width']); return sum + (w > 0 ? Math.max(1, Math.round(w)) - w : 0); }, 0);
  }
  // 边框统一成「哪几边、多宽、什么颜色」；Element Plus 输入框用内阴影画边框，也算边框；边框加内阴影时两样都列出来
  function ring(s) {
    var m = /(rgba?\([^)]*\))\s+0px\s+0px\s+0px\s+([\d.]+)px\s+inset/.exec(s.boxShadow || '');
    return m && m[1] !== CLEAR ? Math.max(1, Math.round(px(m[2]))) + 'px ' + m[1] : '';
  }
  function edge(s) {
    var sides = ['Top', 'Right', 'Bottom', 'Left'].map(function (side) {
      var w = px(s['border' + side + 'Width']), c = s['border' + side + 'Color'];
      return w > 0 && s['border' + side + 'Style'] !== 'none' && c !== CLEAR ? Math.max(1, Math.round(w)) + 'px ' + c : '';
    });
    var r = ring(s);
    if (sides.join('')) {
      var base = sides.every(function (x) { return x === sides[0]; }) ? '四边 ' + sides[0]
        : sides.map(function (x, i) { return x ? ['上', '右', '下', '左'][i] + ' ' + x : ''; }).filter(Boolean).join('，');
      return r ? base + ' + 内描边 ' + r : base;
    }
    return r ? '四边 ' + r : '无';
  }
  function shadow(s) {
    if (!s.boxShadow || s.boxShadow === 'none') return '无';
    var parts = s.boxShadow.split(/,(?![^(]*\))/).map(function (x) { return x.trim(); }).filter(function (x) {
      return !/0px\s+0px\s+0px\s+[\d.]+px\s+inset/.test(x) && !/^rgba\(0, 0, 0, 0\)/.test(x);
    });
    return parts.length ? parts.join(', ') : '无';
  }
  function shape(s, w, h) {
    var short = Math.min(w, h), raw = s.borderTopLeftRadius, r = px(raw);
    if (raw.indexOf('%') > 0) r = r / 100 * short;
    return { height: h + borderFix(s, 'Top', 'Bottom'), width: w + borderFix(s, 'Left', 'Right'),
             radius: r > 0 && r >= short / 2 - 0.5 ? '圆' : Math.round(r * 10) / 10, bg: s.backgroundColor, edge: edge(s), shadow: shadow(s),
             padding: s.padding, marginBottom: px(s.marginBottom), marginRight: px(s.marginRight) };
  }
  function font(m, s) {
    m.fontSize = px(s.fontSize); m.weight = s.fontWeight; m.color = s.color;
    m.lineHeight = s.lineHeight === 'normal' ? 'normal' : px(s.lineHeight);
  }
  function firstText(el) {
    var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (var n = walker.nextNode(); n; n = walker.nextNode()) if (n.textContent.trim()) return n;
    return null;
  }
  function textRect(el) {
    var t = firstText(el);
    if (!t) return null;
    var range = document.createRange(); range.selectNodeContents(t);
    return range.getBoundingClientRect();
  }
  function metrics(el) {
    var s = getComputedStyle(el), r = el.getBoundingClientRect(), m = shape(s, r.width, r.height), t = firstText(el);
    if (t) {
      var range = document.createRange(); range.selectNodeContents(t);
      var tr = range.getBoundingClientRect();
      font(m, getComputedStyle(t.parentElement));
      m.left = tr.left - r.left; m.top = tr.top - r.top;
      return m;
    }
    // 没有文字节点时取输入框的占位文字：颜色、字号取 ::placeholder，位置按输入框的内边距算
    var field = el.matches('input, textarea') ? el : el.querySelector('input, textarea');
    if (field) {
      var fs = getComputedStyle(field), fr = field.getBoundingClientRect(), probe = document.createElement('span');
      font(m, getComputedStyle(field, '::placeholder'));
      // 字形高度用文字范围量，不能用 span 的盒子：绝对定位的 span 会按行高撑开
      probe.textContent = '字'; probe.style.cssText = 'position:absolute;visibility:hidden';
      probe.style.fontFamily = fs.fontFamily; probe.style.fontSize = fs.fontSize; document.body.appendChild(probe);
      var glyph = textRect(probe).height; probe.remove();
      var line = fs.lineHeight === 'normal' ? glyph : px(fs.lineHeight);
      m.left = fr.left + px(fs.borderLeftWidth) + px(fs.paddingLeft) - r.left;
      m.top = fr.top + px(fs.borderTopWidth) + px(fs.paddingTop) + (line - glyph) / 2 - r.top;
    }
    return m;
  }
  function pseudoMetrics(el, which) {
    var s = getComputedStyle(el, which);
    if (!s.content || s.content === 'none' || s.content === 'normal') return null;
    var w = px(s.width), h = px(s.height);
    if (s.boxSizing !== 'border-box') {
      w += px(s.paddingLeft) + px(s.paddingRight) + px(s.borderLeftWidth) + px(s.borderRightWidth);
      h += px(s.paddingTop) + px(s.paddingBottom) + px(s.borderTopWidth) + px(s.borderBottomWidth);
    }
    var m = shape(s, w, h);
    font(m, s);
    m.marginRight = px(s.marginRight);
    return m;
  }
  function find(container, sel) {
    var pseudo = /::?(before|after)$/.exec(sel), doc = sel.charAt(0) === '@';
    if (pseudo) sel = sel.slice(0, pseudo.index);
    if (doc) sel = sel.slice(1);
    var scope = doc ? document : document.querySelector('[data-pair="' + container + '"]');
    var els = scope ? [].slice.call(scope.querySelectorAll(sel)) : [];
    if (!els.length) return null;
    if (pseudo) return pseudoMetrics(els[0], '::' + pseudo[1]);
    var m = metrics(els[0]);
    // 有两个以上时再量它和下一个的距离：按钮间距、页签文字间距、行距
    if (els[1]) {
      var a = els[0].getBoundingClientRect(), b = els[1].getBoundingClientRect(), ta = textRect(els[0]), tb = textRect(els[1]);
      m.gap = b.left - a.right; m.pitch = b.top - a.top;
      if (ta && tb) m.textGap = tb.left - ta.right;
    }
    return m;
  }
  window.aiflowParityMeasure = function (side) {
    var lib = side === 'kit' ? null : LIBS[side];
    if (side !== 'kit' && !lib) throw new Error('parity.js 没有组件库 ' + side + ' 的选择器，可用：' + Object.keys(LIBS).join('、'));
    var result = { side: side === 'kit' ? '样式包' : (window.__lib || side), pairs: {} };
    PAIRS.forEach(function (p) { result.pairs[p[0]] = find(p[1], side === 'kit' ? p[2] : lib[p[0]]); });
    return result;
  };
  function show(v) { return typeof v === 'number' ? Math.round(v * 10) / 10 + 'px' : v; }
  window.aiflowParityCompare = function (kit, lib) {
    var out = [];
    PAIRS.forEach(function (p) {
      var a = kit.pairs[p[0]], b = lib.pairs[p[0]];
      if (!a || !b) { out.push(p[0] + '：' + (a ? lib.side : kit.side) + '一侧没找到元素'); return; }
      p[3].forEach(function (k) {
        var x = a[k], y = b[k];
        if (x === undefined && y === undefined) return;
        var same = typeof x === 'number' && typeof y === 'number' ? Math.abs(x - y) <= TOL[k] : x === y;
        if (!same) out.push(p[0] + ' · ' + NAMES[k] + '：' + kit.side + ' ' + show(x) + '，' + lib.side + ' ' + show(y));
      });
    });
    return out;
  };
})();
