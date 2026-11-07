/* aiflow 版式检查：在浏览器里量按钮、标签、输入框的文字和图标是不是居中、有没有换行溢出。
   用法：用浏览器自动化工具（Playwright 等）把本文件注入页面，再执行 aiflowLayoutCheck()，返回问题列表；空列表表示没查出问题。
   可传根节点 aiflowLayoutCheck(root)，根控件和后代都会检查。
   阶段 2 / 3 交付原型和设计稿前、阶段 7 走查实现页面时都跑一次。查得出偏移、换行、溢出，查不出「好不好看」。
   重复打开同一页面时在地址后加 ?v=时间戳，避免读到浏览器缓存的旧页面。 */
(function () {
  var TOL = 1.5;
  // 文字要水平、垂直都居中的控件（含 Element Plus、Ant Design 的类名，走查实现页面时也能用）
  var CENTER = '.btn, .tag, .badge, .pg, .avatar, .el-button, .el-tag, .el-pager li, .el-badge__content, .ant-btn, .ant-tag, button';
  // 文字只要求垂直居中的控件（多行输入框的文字本来就靠上，不查）
  var VERTICAL = '.inp:not(.ta), .menu-item, .el-input__wrapper, .el-menu-item, .ant-input, .ant-menu-item, input';
  var ICON = '.i, svg, .el-icon, .anticon';
  var SKIP = '.mk, .dim';

  function visible(el) {
    var r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  }
  function content(el) {
    var parts = [], tops = [], walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (var node = walker.nextNode(); node; node = walker.nextNode()) {
      var parent = node.parentElement;
      if (!node.textContent.trim() || (parent && (parent.closest(SKIP) || getComputedStyle(parent).visibility !== 'visible'))) continue;
      var range = document.createRange(); range.selectNodeContents(node);
      [].forEach.call(range.getClientRects(), function (r) { if (r.width > 0) { parts.push(r); tops.push(r.top); } });
    }
    el.querySelectorAll(ICON).forEach(function (icon) {
      if (!icon.closest(SKIP) && visible(icon)) parts.push(icon.getBoundingClientRect());
    });
    if (!parts.length) return null;
    var box = { left: Infinity, right: -Infinity, top: Infinity, bottom: -Infinity, lines: tops.length ? 1 : 0 };
    parts.forEach(function (r) {
      box.left = Math.min(box.left, r.left); box.right = Math.max(box.right, r.right);
      box.top = Math.min(box.top, r.top); box.bottom = Math.max(box.bottom, r.bottom);
    });
    // 行数只按文字算：同一行的文字顶边相差不到 6px；图标和文字的高低差不算换行
    tops.sort(function (a, b) { return a - b; });
    for (var k = 1; k < tops.length; k++) if (tops[k] - tops[k - 1] > 6) box.lines++;
    return box;
  }
  function inner(el) {
    var r = el.getBoundingClientRect(), s = getComputedStyle(el), px = function (v) { return parseFloat(v) || 0; };
    return { left: r.left + px(s.borderLeftWidth) + px(s.paddingLeft), right: r.right - px(s.borderRightWidth) - px(s.paddingRight),
             top: r.top + px(s.borderTopWidth) + px(s.paddingTop), bottom: r.bottom - px(s.borderBottomWidth) - px(s.paddingBottom),
             width: r.width, height: r.height };
  }
  function label(el) {
    var frame = el.closest('.screen, .board, .state'), cap = frame && frame.querySelector('.screen-cap b, .frame-title, .cap');
    var name = el.tagName.toLowerCase() + '.' + [].slice.call(el.classList).filter(function (c) { return c !== 'an'; }).join('.');
    var text = (el.textContent || el.value || '').replace(/\s+/g, ' ').trim().slice(0, 16);
    return (cap ? cap.textContent.trim().slice(0, 20) + ' · ' : '') + name + '「' + text + '」';
  }
  function hasPseudo(el) {
    return ['::before', '::after'].some(function (p) { var c = getComputedStyle(el, p).content; return c && c !== 'none' && c !== 'normal'; });
  }
  function check(el, horizontal, issues) {
    if (!visible(el) || el.closest(SKIP)) return;
    var c = content(el); if (!c) return;
    var box = inner(el), name = label(el);
    var dy = (c.top + c.bottom) / 2 - (box.top + box.bottom) / 2;
    if (Math.abs(dy) > TOL) issues.push(name + '：内容' + (dy < 0 ? '偏上 ' : '偏下 ') + Math.abs(dy).toFixed(1) + 'px（控件高 ' + Math.round(box.height) + 'px）');
    if (horizontal && !hasPseudo(el)) {
      var dx = (c.left + c.right) / 2 - (box.left + box.right) / 2;
      if (Math.abs(dx) > TOL) issues.push(name + '：内容' + (dx < 0 ? '偏左 ' : '偏右 ') + Math.abs(dx).toFixed(1) + 'px');
    }
    if (horizontal && c.lines > 1) issues.push(name + '：文字换成了 ' + c.lines + ' 行');
    if (c.right > box.right + TOL + 1 || c.left < box.left - TOL - 1) issues.push(name + '：内容超出控件');
    var mid = (c.top + c.bottom) / 2;
    el.querySelectorAll(ICON).forEach(function (icon) {
      if (icon.closest(SKIP) || !visible(icon)) return;
      var r = icon.getBoundingClientRect(), off = (r.top + r.bottom) / 2 - mid;
      if (Math.abs(off) > TOL + 0.5) issues.push(name + '：图标和文字没对齐，图标' + (off < 0 ? '偏上 ' : '偏下 ') + Math.abs(off).toFixed(1) + 'px');
    });
  }
  window.aiflowLayoutCheck = function (root) {
    var scope = root || document, issues = [];
    if (scope.matches && scope.matches(CENTER)) check(scope, true, issues);
    if (scope.matches && scope.matches(VERTICAL)) check(scope, false, issues);
    scope.querySelectorAll(CENTER).forEach(function (el) { check(el, true, issues); });
    scope.querySelectorAll(VERTICAL).forEach(function (el) { check(el, false, issues); });
    return issues;
  };
})();
