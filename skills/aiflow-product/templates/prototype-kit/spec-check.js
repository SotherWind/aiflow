/* aiflow 规范检查：在浏览器里量界面实际用到的颜色、字号、圆角、控件高度、字体，列出设计规范里没有的取值。
   用法：用浏览器自动化工具（Playwright 等）把本文件注入页面，再执行 aiflowSpecCheck()，返回问题列表；空列表表示没查出问题。
   取值范围从页面 :root 读：颜色是 :root 里的全部颜色变量（样式包、样式预设、design-system.md 令牌表、theme.css 合起来），
   字号、圆角、控件高度是 --check-* 变量，字体是 --font。只查界面层：.dframe、.canvas、.state > .mini 和 [data-check] 这些根节点及后代；
   标注层（.mk、.dim）、色块（.sw）和 [data-nocheck] 不查。阴影、间距不查，靠走查点和评审。
   查得出「用了规范外的取值」，查不出「该用 A 却用了 B」（比如该用警告色却用了错误色），后者靠走查点和独立评审。
   阶段 7 查实现页面：先在设计稿页面执行 JSON.stringify(aiflowSpecConfig()) 取出取值范围，
   再在实现页面注入本文件，执行 aiflowSpecCheck(取值范围, '#app')，第二个参数是实现页面的根节点选择器。 */
(function () {
  var SCOPE = '.dframe, .canvas, .state > .mini, [data-check]';
  var SKIP = '.mk, .dim, .sw, [data-nocheck]';
  // 图标字形（如结果页圆形图标里的 ✓）按图标尺寸画，不按字号查
  var GLYPH = '.result .ic';
  var CONTROLS = {
    btn: { name: '按钮', sel: '.btn:not(.link), .el-button:not(.is-link):not(.is-text), .ant-btn:not(.ant-btn-link):not(.ant-btn-text)' },
    input: { name: '输入框', sel: '.inp:not(.ta), .el-input__wrapper, .el-select__wrapper, .ant-input-affix-wrapper, .ant-select-selector, .ant-input:not(.ant-input-affix-wrapper *)' },
    tag: { name: '标签', sel: '.tag, .el-tag, .ant-tag' }
  };
  var CLEAR = 'rgba(0, 0, 0, 0)';
  var host = null;

  // 把任意写法的颜色换成浏览器的计算值（rgb / rgba），不是颜色时返回 null。探针继承一个不会用到的颜色，取到它说明值无效
  function norm(value) {
    if (!host) {
      host = document.createElement('div');
      host.style.cssText = 'position:absolute;left:-9999px;top:0;color:rgb(1, 2, 3)';
      host.appendChild(document.createElement('i'));
      document.body.appendChild(host);
    }
    var el = host.firstChild;
    el.style.color = '';
    el.style.color = value;
    if (!el.style.color) return null;
    var c = getComputedStyle(el).color;
    return c === 'rgb(1, 2, 3)' ? null : c;
  }
  function rootVars() {
    var names = {};
    function walk(rules) {
      [].forEach.call(rules, function (rule) {
        if (rule.cssRules && !rule.selectorText) { walk(rule.cssRules); return; }
        if (!rule.style || !/(^|,)\s*:root\s*(,|$)/.test(rule.selectorText || '')) return;
        for (var i = 0; i < rule.style.length; i++) if (rule.style[i].indexOf('--') === 0) names[rule.style[i]] = 1;
      });
    }
    [].forEach.call(document.styleSheets, function (sheet) {
      try { walk(sheet.cssRules); } catch (e) { /* 跨域样式表读不到，跳过 */ }
    });
    return Object.keys(names);
  }
  function nums(value) {
    return (value || '').trim().split(/[\s,]+/).map(parseFloat).filter(function (n) { return !isNaN(n); });
  }
  function fontOf(value) {
    if (!value) return '';
    var el = document.createElement('i');
    el.style.fontFamily = value;
    document.body.appendChild(el);
    var font = getComputedStyle(el).fontFamily;
    el.remove();
    return font;
  }
  window.aiflowSpecConfig = function () {
    var root = getComputedStyle(document.documentElement), colors = {};
    rootVars().forEach(function (name) {
      if (name.indexOf('--check-') === 0) return;
      var raw = root.getPropertyValue(name).trim(), c = raw && norm(raw);
      if (c && c !== CLEAR) (colors[c] = colors[c] || []).push(name);
    });
    if (host) { host.remove(); host = null; }
    return {
      colors: colors,
      fontSizes: nums(root.getPropertyValue('--check-font-sizes')),
      radii: nums(root.getPropertyValue('--check-radii')),
      heights: { btn: nums(root.getPropertyValue('--check-btn-heights')), input: nums(root.getPropertyValue('--check-input-heights')),
                 tag: nums(root.getPropertyValue('--check-tag-heights')) },
      font: fontOf(root.getPropertyValue('--font').trim())
    };
  };

  function visible(el) {
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
  }
  function ownText(el) {
    for (var n = el.firstChild; n; n = n.nextSibling) if (n.nodeType === 3 && n.textContent.trim()) return true;
    return (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') && !!(el.value || el.placeholder);
  }
  // 系统缩放 125%、150% 时浏览器把 1px 边框画成 0.8px、0.67px：写死高度的控件量出来不变，高度由内容撑开的（如标签）会少不到 1px。
  // 两种都算一遍，有一个落在规范里就算通过
  function heights(el) {
    var s = getComputedStyle(el), h = el.getBoundingClientRect().height, fixed = h;
    ['Top', 'Bottom'].forEach(function (side) {
      var w = parseFloat(s['border' + side + 'Width']);
      if (w > 0) fixed += Math.max(1, Math.round(w)) - w;
    });
    return [Math.round(h), Math.round(fixed)];
  }
  function near(v, list) { return list.some(function (x) { return Math.abs(x - v) < 0.6; }); }
  function fmt(v) { return Math.round(v * 10) / 10; }
  function signature(el) {
    return el.tagName.toLowerCase() + '.' + [].slice.call(el.classList).filter(function (c) { return c !== 'an'; }).sort().join('.');
  }
  function label(el) {
    var frame = el.closest('.screen, .board, .state, [data-check]');
    var cap = frame && frame.querySelector('.screen-cap b, .frame-title, .cap');
    var name = el.tagName.toLowerCase() + '.' + [].slice.call(el.classList).filter(function (c) { return c !== 'an'; }).join('.');
    var text = (el.textContent || el.value || '').replace(/\s+/g, ' ').trim().slice(0, 16);
    return (cap ? cap.textContent.trim().slice(0, 20) + ' · ' : '') + name + '「' + text + '」';
  }
  function color(el, value, what, config, report) {
    if (!value || value === CLEAR || value === 'transparent') return;
    if (!config.colors[value]) report(el, 'color' + what + value, what + ' ' + value + ' 不是规范里的颜色');
  }
  function inspect(el, config, report) {
    var s = getComputedStyle(el);
    if (ownText(el)) {
      color(el, s.color, '文字颜色', config, report);
      var size = parseFloat(s.fontSize);
      if (config.fontSizes.length && !near(size, config.fontSizes) && !el.matches(GLYPH))
        report(el, 'size' + size, '字号 ' + fmt(size) + 'px 不在规范字号里（' + config.fontSizes.join(' / ') + 'px）');
      if (config.font && s.fontFamily !== config.font) report(el, 'font' + s.fontFamily, '字体不是规范字体：' + s.fontFamily.slice(0, 48));
    }
    color(el, s.backgroundColor, '背景色', config, report);
    var borders = {};
    ['Top', 'Right', 'Bottom', 'Left'].forEach(function (side) {
      if (parseFloat(s['border' + side + 'Width']) > 0 && s['border' + side + 'Style'] !== 'none') borders[s['border' + side + 'Color']] = 1;
    });
    Object.keys(borders).forEach(function (c) { color(el, c, '边框色', config, report); });
    if (config.radii.length && (s.backgroundColor !== CLEAR || Object.keys(borders).length)) {
      var r = el.getBoundingClientRect(), short = Math.min(r.width, r.height), bad = {};
      ['TopLeft', 'TopRight', 'BottomRight', 'BottomLeft'].forEach(function (corner) {
        var raw = s['border' + corner + 'Radius'], v = parseFloat(raw);
        if (!v) return;
        if (raw.indexOf('%') > 0) { if (v >= 50) return; v = v / 100 * short; }
        if (v >= short / 2 - 0.5) return; // 圆形、胶囊形
        if (!near(v, config.radii)) bad[fmt(v)] = 1;
      });
      var values = Object.keys(bad);
      if (values.length) report(el, 'radius' + values.join(), '圆角 ' + values.join(' / ') + 'px 不在规范圆角里（' + config.radii.join(' / ') + 'px）');
    }
    Object.keys(CONTROLS).forEach(function (kind) {
      var list = (config.heights || {})[kind];
      if (!list || !list.length || !el.matches(CONTROLS[kind].sel)) return;
      var hs = heights(el);
      if (!hs.some(function (h) { return near(h, list); })) report(el, 'height' + hs[0], CONTROLS[kind].name + '高 ' + hs[0] + 'px，规范是 ' + list.join(' / ') + 'px');
    });
    ['::before', '::after'].forEach(function (p) {
      var ps = getComputedStyle(el, p);
      if (!ps.content || ps.content === 'none' || ps.content === 'normal' || ps.display === 'none') return;
      color(el, ps.backgroundColor, p + ' 背景色', config, report);
      if (ps.content !== '""') color(el, ps.color, p + ' 文字颜色', config, report);
    });
  }
  window.aiflowSpecCheck = function (config, scope) {
    config = config || window.aiflowSpecConfig();
    var roots = [].slice.call(document.querySelectorAll(scope || SCOPE));
    if (!roots.length) return ['页面上没有可查的界面区域（' + (scope || SCOPE) + '）。设计稿把画面放在 .dframe 或 .state > .mini 里，规范页的样张容器加 data-check；实现页面传根节点选择器，如 aiflowSpecCheck(取值范围, "#app")'];
    var seen = new Set(), groups = {}, order = [];
    function report(el, key, message) {
      var id = key + '|' + signature(el);
      if (!groups[id]) { groups[id] = { text: label(el) + '：' + message, count: 0 }; order.push(id); }
      groups[id].count++;
    }
    roots.forEach(function (root) {
      [root].concat([].slice.call(root.querySelectorAll('*'))).forEach(function (el) {
        if (seen.has(el)) return;
        seen.add(el);
        if (el.closest(SKIP) || !visible(el)) return;
        inspect(el, config, report);
      });
    });
    return order.map(function (id) { var g = groups[id]; return g.text + (g.count > 1 ? '（同类共 ' + g.count + ' 处）' : ''); });
  };
})();
