(function () {
  var BASE_URL = 'https://a11oy.szl-holdings.com';

  class A11oySpace extends HTMLElement {
    constructor() {
      super();
      this._iframe = null;
      this._connected = false;
    }

    connectedCallback() {
      var space = this.getAttribute('space') || '';
      var tenant = this.getAttribute('tenant') || 'szl';
      var height = this.getAttribute('height') || '400';

      var iframe = document.createElement('iframe');
      iframe.src = BASE_URL + '/a11oy/embed/' + encodeURIComponent(space) + '?tenant=' + encodeURIComponent(tenant);
      iframe.width = '100%';
      iframe.height = height;
      iframe.frameBorder = '0';
      iframe.allow = 'clipboard-read; clipboard-write';
      iframe.style.border = 'none';
      iframe.style.borderRadius = '10px';
      iframe.title = 'A11oy Atelier Space: ' + space;

      this._iframe = iframe;
      this.appendChild(iframe);

      var self = this;
      iframe.addEventListener('load', function () {
        iframe.contentWindow.postMessage(
          { type: 'a11oy-space-handshake', spaceSlug: space },
          BASE_URL
        );
      });

      window.addEventListener('message', function handler(e) {
        if (e.origin !== BASE_URL) return;
        if (e.data && e.data.type === 'a11oy-space-ack' && e.data.spaceSlug === space) {
          self._connected = true;
          self.dispatchEvent(new CustomEvent('a11oy-ready', { detail: e.data }));
        }
        if (e.data && e.data.type === 'a11oy-space-line') {
          self.dispatchEvent(new CustomEvent('a11oy-line', { detail: e.data }));
        }
        if (e.data && e.data.type === 'a11oy-space-done') {
          self.dispatchEvent(new CustomEvent('a11oy-done', { detail: e.data }));
        }
      });
    }

    run() {
      if (this._iframe && this._iframe.contentWindow) {
        var space = this.getAttribute('space') || '';
        this._iframe.contentWindow.postMessage(
          { type: 'a11oy-space-run', spaceSlug: space },
          BASE_URL
        );
      }
    }

    disconnectedCallback() {
      if (this._iframe) {
        this.removeChild(this._iframe);
        this._iframe = null;
      }
    }
  }

  if (!customElements.get('a11oy-space')) {
    customElements.define('a11oy-space', A11oySpace);
  }
})();
