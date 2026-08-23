/* Nested Travel — marketing site analytics.
 *
 * Reports into the SAME Mixpanel project as the app, so every event is tagged
 * platform:'web' and prefixed 'Web:' — filter on either to separate site
 * visitors from real app users. That separation matters: app metrics are read
 * against a small real user base, and anonymous web traffic will outnumber it.
 *
 * The project token is a public, client-side credential by design (it is
 * already shipped inside the app bundle). It is not a secret.
 */
(function () {
  'use strict';

  var TOKEN = '1ff8234e791a39eab221d72771b654a0';

  // App Store campaign attribution needs the Provider Token from
  // App Store Connect -> Payments and Financial Reports (the numeric ID in the
  // top-left picker). Until it is filled in we leave Apple's URLs untouched
  // rather than append parameters Apple will ignore.
  var APPLE_PROVIDER_TOKEN = '128414920';

  var STORE = {
    apple: 'apps.apple.com',
    play: 'play.google.com'
  };

  function pageName() {
    var p = location.pathname.replace(/\/+$/, '');
    if (p === '' || p === '/index.html') return 'Home';
    if (p.indexOf('privacy') !== -1) return 'Privacy';
    if (p.indexOf('terms') !== -1) return 'Terms';
    return p || 'Unknown';
  }

  /* Which block on the page a link lives in, so you can tell which CTA works. */
  function placementOf(el) {
    if (el.closest('.site-header')) return 'header';
    if (el.closest('.hero')) return 'hero';
    if (el.closest('.closing')) return 'closing';
    return 'other';
  }

  function campaignFor(placement) {
    return 'site_' + placement;
  }

  /* Decorate store links at runtime. If this script never runs the links still
   * work — they are plain hrefs — they just carry no campaign data. */
  function decorate() {
    var links = document.querySelectorAll('a[href]');
    Array.prototype.forEach.call(links, function (a) {
      var href = a.getAttribute('href') || '';
      var placement = placementOf(a);
      var campaign = campaignFor(placement);

      if (href.indexOf(STORE.play) !== -1 && href.indexOf('referrer=') === -1) {
        var referrer = encodeURIComponent(
          'utm_source=nestedtravel.com&utm_medium=website&utm_campaign=' + campaign
        );
        a.setAttribute('href', href + '&referrer=' + referrer);
      }

      if (href.indexOf(STORE.apple) !== -1 && APPLE_PROVIDER_TOKEN && href.indexOf('pt=') === -1) {
        a.setAttribute('href',
          href + '?pt=' + encodeURIComponent(APPLE_PROVIDER_TOKEN) +
          '&ct=' + encodeURIComponent(campaign) + '&mt=8');
      }
    });
  }

  function storeOf(href) {
    if (href.indexOf(STORE.apple) !== -1) return 'App Store';
    if (href.indexOf(STORE.play) !== -1) return 'Google Play';
    return null;
  }

  function wireClicks() {
    document.addEventListener('click', function (e) {
      var a = e.target.closest && e.target.closest('a[href]');
      if (!a) return;
      var store = storeOf(a.getAttribute('href') || '');
      if (!store) return;
      // sendBeacon survives the navigation away to the store.
      mixpanel.track('Web: Store Click', {
        store: store,
        placement: placementOf(a),
        label: (a.textContent || '').trim().slice(0, 40),
        page: pageName()
      }, { transport: 'sendBeacon' });
    }, true);
  }

  /* How far down the page people actually get — the redesign is a long scroll,
   * and a pageview alone cannot tell you if anyone saw the CTAs. */
  function wireScrollDepth() {
    var marks = [25, 50, 75, 100], hit = {};
    function onScroll() {
      var doc = document.documentElement;
      var max = doc.scrollHeight - window.innerHeight;
      if (max <= 0) return;
      var pct = Math.min(100, Math.round((window.scrollY / max) * 100));
      marks.forEach(function (m) {
        if (pct >= m && !hit[m]) {
          hit[m] = true;
          mixpanel.track('Web: Scroll Depth', { depth: m, page: pageName() });
        }
      });
      if (hit[100]) window.removeEventListener('scroll', onScroll);
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  function boot() {
    if (!window.mixpanel || !window.mixpanel.init) return;

    mixpanel.init(TOKEN, {
      api_host: 'https://api.mixpanel.com',
      persistence: 'localStorage',  // no cookies set
      ip: false,                    // do not geolocate; app-side geo is already unreliable
      track_pageview: false,        // we send our own, with better properties
      autocapture: false,
      batch_requests: true
    });

    // platform:'web' is the filter that keeps site visitors out of app numbers.
    mixpanel.register({ platform: 'web', surface: 'marketing-site' });

    var params = new URLSearchParams(location.search);
    mixpanel.track('Web: Page View', {
      page: pageName(),
      path: location.pathname,
      referrer: document.referrer || 'direct',
      utm_source: params.get('utm_source') || undefined,
      utm_medium: params.get('utm_medium') || undefined,
      utm_campaign: params.get('utm_campaign') || undefined
    });

    decorate();
    wireClicks();
    wireScrollDepth();
  }

  // Decorate the links even if Mixpanel is blocked, so store attribution still works.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', decorate);
  } else {
    decorate();
  }

  var s = document.createElement('script');
  s.async = true;
  s.src = 'https://cdn.mxpnl.com/libs/mixpanel-2-latest.min.js';
  s.onload = boot;
  s.onerror = function () { /* analytics blocked; the site is unaffected */ };
  document.head.appendChild(s);
})();
