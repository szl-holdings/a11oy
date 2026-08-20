/* =============================================================================
 * SZL Holdings — Canonical Mobile Controls  (szl-mobile-controls.js)
 * -----------------------------------------------------------------------------
 * Vanilla JS (zero deps). iOS-Safari-first touch layer for Three.js scenes.
 * ADDITIVE: never removes desktop WASD/pointer-lock. Mobile is an OR layer.
 *
 * Features:
 *   - Left thumb virtual joystick (40px radius) -> normalized {x,y} move vector
 *   - Right-half drag-anywhere -> camera yaw + pitch (look delta, consumed/frame)
 *   - Two-finger pinch -> FOV zoom delta
 *   - Tap "Enter" -> activate scene WITHOUT pointer lock; "Exit" -> leave
 *   - Mobile detect: ('ontouchstart' in window) || navigator.maxTouchPoints > 0
 *   - 100dvh / --vh CSS var fix for the iOS URL-bar viewport bug
 *   - prefers-reduced-motion honored (exposed flag)
 *   - aria-labels on every interactive control; -webkit-tap-highlight cleared
 *
 * Usage (in your app.js):
 *   import { SZLMobileControls } from './szl-mobile-controls.js';   // or window.SZLMobileControls if loaded via <script>
 *   const mc = new SZLMobileControls({
 *     onEnter(){ ... },          // called when user taps Enter (mobile) — do NOT pointer-lock
 *     onExit(){ ... },           // called when user taps Exit
 *     enterLabel: 'Enter (touch)'
 *   });
 *   // per-frame in your render loop:
 *   if (mc.isMobile && mc.active) {
 *     const m = mc.getMove();        // {x:-1..1 strafe, y:-1..1 forward(+)=back}
 *     const look = mc.consumeLook(); // {dx, dy} pixels since last frame (then resets)
 *     const fov  = mc.consumeFov();  // signed FOV delta from pinch (then resets)
 *     // apply: moveRight(m.x*speed*dt); moveForward(-m.y*speed*dt);
 *     // yaw -= look.dx*0.0022; pitch -= look.dy*0.0022;
 *     // camera.fov = clamp(camera.fov + fov); camera.updateProjectionMatrix();
 *   }
 *
 * Static helpers (work on desktop too):
 *   SZLMobileControls.isMobileDevice()      -> bool
 *   SZLMobileControls.prefersReducedMotion() -> bool
 *   SZLMobileControls.applyViewportVar()    -> sets --vh, re-binds on resize
 *   SZLMobileControls.rendererHints()       -> {antialias, powerPreference, pixelRatio}
 *   SZLMobileControls.particleScale()       -> 0.5 on mobile, 1 on desktop
 *
 * Sign: Yachay <yachay@szlholdings.dev>
 * ========================================================================== */
(function (global) {
  'use strict';

  function isMobileDevice() {
    return ('ontouchstart' in global) || (navigator.maxTouchPoints > 0);
  }
  function prefersReducedMotion() {
    return global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }
  // iOS URL-bar viewport bug: expose accurate --vh and provide 100dvh fallback.
  function applyViewportVar() {
    var set = function () {
      document.documentElement.style.setProperty('--vh', (global.innerHeight * 0.01) + 'px');
    };
    set();
    global.addEventListener('resize', set);
    global.addEventListener('orientationchange', set);
  }
  function rendererHints() {
    var mobile = isMobileDevice();
    return {
      antialias: !mobile,
      powerPreference: mobile ? 'low-power' : 'high-performance',
      pixelRatio: Math.min(global.devicePixelRatio || 1, mobile ? 1.5 : 2)
    };
  }
  function particleScale() {
    return isMobileDevice() ? 0.5 : 1;
  }

  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

  function SZLMobileControls(opts) {
    opts = opts || {};
    this.isMobile = isMobileDevice();
    this.reducedMotion = prefersReducedMotion();
    this.active = false;
    this._move = { x: 0, y: 0 };
    this._look = { dx: 0, dy: 0 };
    this._fov = 0;
    this._opts = opts;
    this._joyId = null;
    this._lookId = null;
    this._lookLast = null;
    this._pinchDist = null;

    applyViewportVar();
    this._injectStyle();

    if (this.isMobile) {
      this._buildTouchUI();
    } else {
      this._buildDesktopHint(opts.desktopHint);
    }
  }

  SZLMobileControls.isMobileDevice = isMobileDevice;
  SZLMobileControls.prefersReducedMotion = prefersReducedMotion;
  SZLMobileControls.applyViewportVar = applyViewportVar;
  SZLMobileControls.rendererHints = rendererHints;
  SZLMobileControls.particleScale = particleScale;

  SZLMobileControls.prototype.getMove = function () { return this._move; };
  SZLMobileControls.prototype.consumeLook = function () {
    var l = { dx: this._look.dx, dy: this._look.dy };
    this._look.dx = 0; this._look.dy = 0;
    return l;
  };
  SZLMobileControls.prototype.consumeFov = function () {
    var f = this._fov; this._fov = 0; return f;
  };

  SZLMobileControls.prototype._injectStyle = function () {
    if (document.getElementById('szl-mc-style')) return;
    var s = document.createElement('style');
    s.id = 'szl-mc-style';
    s.textContent = [
      '.szl-mc, .szl-mc *{ -webkit-tap-highlight-color: transparent; }',
      '.szl-mc{ position:fixed; z-index:60; touch-action:none; user-select:none; -webkit-user-select:none; font-family:ui-monospace,Menlo,monospace; }',
      '#szl-joy{ left:18px; bottom:calc(24px + env(safe-area-inset-bottom)); width:120px; height:120px; border-radius:50%; background:rgba(20,28,40,.45); border:1px solid rgba(143,182,255,.35); display:none; }',
      '#szl-joy-knob{ position:absolute; left:50%; top:50%; width:54px; height:54px; margin:-27px 0 0 -27px; border-radius:50%; background:rgba(143,182,255,.5); border:1px solid rgba(255,255,255,.5); }',
      '#szl-look-hint{ right:18px; bottom:calc(24px + env(safe-area-inset-bottom)); padding:8px 12px; border-radius:10px; background:rgba(20,28,40,.45); border:1px solid rgba(143,182,255,.25); color:#c9d2df; font-size:12px; display:none; pointer-events:none; max-width:42vw; }',
      '#szl-enter{ left:50%; top:50%; transform:translate(-50%,-50%); min-width:160px; min-height:48px; padding:14px 22px; border-radius:12px; border:1px solid #cda64a; background:#cda64a; color:#1b1206; font-size:16px; font-weight:700; }',
      '#szl-exit{ right:14px; top:calc(14px + env(safe-area-inset-top)); min-width:64px; min-height:44px; padding:10px 16px; border-radius:10px; border:1px solid rgba(143,182,255,.4); background:rgba(20,28,40,.7); color:#c9d2df; font-size:14px; display:none; }',
      '#szl-desktop-hint{ left:50%; bottom:14px; transform:translateX(-50%); padding:6px 12px; border-radius:8px; background:rgba(20,28,40,.55); color:#76859b; font-size:11px; pointer-events:none; }'
    ].join('\n');
    document.head.appendChild(s);
  };

  SZLMobileControls.prototype._buildDesktopHint = function (txt) {
    var d = document.createElement('div');
    d.className = 'szl-mc'; d.id = 'szl-desktop-hint';
    d.textContent = txt || 'Click to enter · WASD move · mouse look · Esc release';
    d.setAttribute('aria-hidden', 'true');
    document.body.appendChild(d);
    this._desktopHint = d;
  };

  SZLMobileControls.prototype._buildTouchUI = function () {
    var self = this;

    // Enter button (no pointer lock).
    var enter = document.createElement('button');
    enter.className = 'szl-mc'; enter.id = 'szl-enter';
    enter.textContent = this._opts.enterLabel || 'Enter (touch)';
    enter.setAttribute('aria-label', 'Enter scene with touch controls');
    document.body.appendChild(enter);
    this._enterBtn = enter;

    // Exit button.
    var exit = document.createElement('button');
    exit.className = 'szl-mc'; exit.id = 'szl-exit';
    exit.textContent = 'Exit';
    exit.setAttribute('aria-label', 'Exit scene');
    document.body.appendChild(exit);
    this._exitBtn = exit;

    // Joystick.
    var joy = document.createElement('div');
    joy.className = 'szl-mc'; joy.id = 'szl-joy';
    joy.setAttribute('aria-label', 'Movement joystick — drag to walk');
    joy.setAttribute('role', 'application');
    var knob = document.createElement('div'); knob.id = 'szl-joy-knob';
    joy.appendChild(knob);
    document.body.appendChild(joy);
    this._joy = joy; this._knob = knob;

    // Look hint.
    var look = document.createElement('div');
    look.className = 'szl-mc'; look.id = 'szl-look-hint';
    look.textContent = 'drag right side to look · pinch to zoom';
    document.body.appendChild(look);
    this._lookHint = look;

    enter.addEventListener('click', function () { self.enter(); });
    exit.addEventListener('click', function () { self.exit(); });

    this._bindTouch();
  };

  SZLMobileControls.prototype.enter = function () {
    this.active = true;
    if (this._enterBtn) this._enterBtn.style.display = 'none';
    if (this._exitBtn) this._exitBtn.style.display = 'block';
    if (this._joy) this._joy.style.display = 'block';
    if (this._lookHint) this._lookHint.style.display = 'block';
    if (typeof this._opts.onEnter === 'function') this._opts.onEnter();
  };

  SZLMobileControls.prototype.exit = function () {
    this.active = false;
    this._move.x = 0; this._move.y = 0;
    if (this._enterBtn) this._enterBtn.style.display = 'block';
    if (this._exitBtn) this._exitBtn.style.display = 'none';
    if (this._joy) this._joy.style.display = 'none';
    if (this._lookHint) this._lookHint.style.display = 'none';
    if (typeof this._opts.onExit === 'function') this._opts.onExit();
  };

  SZLMobileControls.prototype._bindTouch = function () {
    var self = this;
    var R = 40; // joystick radius (px) for normalization

    function joyCenter() {
      var r = self._joy.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    }
    function inJoy(t) {
      var r = self._joy.getBoundingClientRect();
      return t.clientX >= r.left - 30 && t.clientX <= r.right + 30 &&
             t.clientY >= r.top - 30 && t.clientY <= r.bottom + 30;
    }

    document.addEventListener('touchstart', function (e) {
      if (!self.active) return;
      for (var i = 0; i < e.changedTouches.length; i++) {
        var t = e.changedTouches[i];
        if (self._joyId === null && inJoy(t)) {
          self._joyId = t.identifier;
        } else if (t.clientX > global.innerWidth / 2 && self._lookId === null) {
          self._lookId = t.identifier;
          self._lookLast = { x: t.clientX, y: t.clientY };
        }
      }
      // pinch
      if (e.touches.length === 2) {
        var a = e.touches[0], b = e.touches[1];
        self._pinchDist = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
      }
    }, { passive: false });

    document.addEventListener('touchmove', function (e) {
      if (!self.active) return;
      for (var i = 0; i < e.changedTouches.length; i++) {
        var t = e.changedTouches[i];
        if (t.identifier === self._joyId) {
          var c = joyCenter();
          var dx = t.clientX - c.x, dy = t.clientY - c.y;
          var dist = Math.hypot(dx, dy);
          var cl = Math.min(dist, R);
          var nx = dist ? (dx / dist) * cl : 0;
          var ny = dist ? (dy / dist) * cl : 0;
          self._knob.style.transform = 'translate(' + nx + 'px,' + ny + 'px)';
          self._move.x = nx / R;          // strafe
          self._move.y = ny / R;          // +y = pull back toward user = backward
          e.preventDefault();
        } else if (t.identifier === self._lookId && self._lookLast) {
          self._look.dx += (t.clientX - self._lookLast.x);
          self._look.dy += (t.clientY - self._lookLast.y);
          self._lookLast = { x: t.clientX, y: t.clientY };
          e.preventDefault();
        }
      }
      if (e.touches.length === 2 && self._pinchDist !== null) {
        var a = e.touches[0], b = e.touches[1];
        var d = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
        self._fov += (self._pinchDist - d) * 0.05; // pinch in => zoom in (fov down)
        self._pinchDist = d;
        e.preventDefault();
      }
    }, { passive: false });

    function end(e) {
      for (var i = 0; i < e.changedTouches.length; i++) {
        var t = e.changedTouches[i];
        if (t.identifier === self._joyId) {
          self._joyId = null;
          self._move.x = 0; self._move.y = 0;
          self._knob.style.transform = 'translate(0,0)';
        } else if (t.identifier === self._lookId) {
          self._lookId = null; self._lookLast = null;
        }
      }
      if (e.touches.length < 2) self._pinchDist = null;
    }
    document.addEventListener('touchend', end, { passive: false });
    document.addEventListener('touchcancel', end, { passive: false });
  };

  global.SZLMobileControls = SZLMobileControls;
  if (typeof module !== 'undefined' && module.exports) module.exports = { SZLMobileControls: SZLMobileControls };
})(typeof window !== 'undefined' ? window : this);

/* ES-module re-export so scenes using importmaps can `import { SZLMobileControls }`. */
export const SZLMobileControls = (typeof window !== 'undefined' ? window.SZLMobileControls : undefined);
