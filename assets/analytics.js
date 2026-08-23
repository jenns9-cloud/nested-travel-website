/* Nested Travel — marketing site analytics.
 *
 * Reports into the SAME Mixpanel project as the app, so every event is tagged
 * platform:'web', surface:'marketing-site', and prefixed 'Web:'. Filter on any
 * of those to keep site visitors out of app numbers — that matters, because app
 * metrics are read against a small real user base that anonymous web traffic
 * would otherwise swamp.
 *
 * The project token is a public, client-side credential by design (it already
 * ships inside the app bundle). It is not a secret.
 *
 * Loader notes — all verified against the live SDK on 2026-08-22:
 *   - Mixpanel's own cdn.mxpnl.com/libs/mixpanel-2-latest.min.js does NOT work
 *     standalone. It expects their inline snippet to have created a stub first
 *     and otherwise sets no global at all.
 *   - The module build's DEFAULT export is not a reliable singleton here:
 *     init(token, config) appeared to succeed but left a hollow client whose
 *     every method threw. Passing an instance NAME makes init return a real,
 *     self-contained client. Use the returned value; never the bare default.
 *   - The SDK posts to api-js.mixpanel.com, not api.mixpanel.com. Do not
 *     override api_host — the default is correct and an override broke it.
 */

const TOKEN = '1ff8234e791a39eab221d72771b654a0';
const SDK = 'https://cdn.jsdelivr.net/npm/mixpanel-browser@2.82.1/+esm';

/* App Store campaign attribution. Provider Token from App Store Connect. */
const APPLE_PROVIDER_TOKEN = '128414920';

const STORE = { apple: 'apps.apple.com', play: 'play.google.com' };

let client = null;

function pageName() {
  const p = location.pathname.replace(/\/+$/, '');
  if (p === '' || p === '/index.html') return 'Home';
  if (p.includes('privacy')) return 'Privacy';
  if (p.includes('terms')) return 'Terms';
  return p;
}

/* Which block a link sits in, so you can see which CTA actually works. */
function placementOf(el) {
  if (el.closest('.site-header')) return 'header';
  if (el.closest('.hero')) return 'hero';
  if (el.closest('.closing')) return 'closing';
  return 'other';
}

function storeOf(href) {
  if (href.includes(STORE.apple)) return 'App Store';
  if (href.includes(STORE.play)) return 'Google Play';
  return null;
}

/* Fallback tagging for links added later. The links in the markup are already
   tagged statically, so attribution survives even with scripts blocked; this
   no-ops on anything that already carries campaign parameters. */
function decorate() {
  document.querySelectorAll('a[href]').forEach((a) => {
    const href = a.getAttribute('href') || '';
    const campaign = 'site_' + placementOf(a);

    if (href.includes(STORE.play) && !href.includes('referrer=')) {
      const ref = encodeURIComponent(
        `utm_source=nestedtravel.com&utm_medium=website&utm_campaign=${campaign}`
      );
      a.setAttribute('href', `${href}&referrer=${ref}`);
    }

    if (href.includes(STORE.apple) && APPLE_PROVIDER_TOKEN && !href.includes('pt=')) {
      const sep = href.includes('?') ? '&' : '?';
      a.setAttribute('href',
        `${href}${sep}pt=${encodeURIComponent(APPLE_PROVIDER_TOKEN)}` +
        `&ct=${encodeURIComponent(campaign)}&mt=8`);
    }
  });
}

function wireClicks() {
  document.addEventListener('click', (e) => {
    const a = e.target.closest?.('a[href]');
    if (!a) return;
    const store = storeOf(a.getAttribute('href') || '');
    if (!store) return;
    // sendBeacon survives the navigation away to the store.
    client.track('Web: Store Click', {
      store,
      placement: placementOf(a),
      label: (a.textContent || '').trim().slice(0, 40),
      page: pageName()
    }, { transport: 'sendBeacon' });
  }, true);
}

/* How far people actually get. On a hero this tall a page view alone cannot
   tell you whether anyone ever saw the store buttons. */
function wireScrollDepth() {
  const marks = [25, 50, 75, 100];
  const hit = {};
  function onScroll() {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    if (max <= 0) return;
    const pct = Math.min(100, Math.round((window.scrollY / max) * 100));
    for (const m of marks) {
      if (pct >= m && !hit[m]) {
        hit[m] = true;
        client.track('Web: Scroll Depth', { depth: m, page: pageName() });
      }
    }
    if (hit[100]) window.removeEventListener('scroll', onScroll);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
}

function boot(mixpanel) {
  // The instance NAME is required — without it init returns undefined and the
  // default export stays hollow while appearing to work. See the header notes.
  client = mixpanel.init(TOKEN, {
    persistence: 'localStorage',  // no cookies
    ip: false,                    // -> /track/?ip=0, no IP geolocation
    track_pageview: false,        // we send our own, with better properties
    autocapture: false,
    batch_requests: false         // low volume; send immediately
  }, 'web');

  // Fail loudly into the status marker rather than pretending to track.
  client.get_distinct_id();

  client.register({ platform: 'web', surface: 'marketing-site' });

  const params = new URLSearchParams(location.search);
  client.track('Web: Page View', {
    page: pageName(),
    path: location.pathname,
    referrer: document.referrer || 'direct',
    utm_source: params.get('utm_source') || undefined,
    utm_medium: params.get('utm_medium') || undefined,
    utm_campaign: params.get('utm_campaign') || undefined
  });

  wireClicks();
  wireScrollDepth();
}

/* Decorate first — it must never depend on the SDK loading. */
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', decorate);
} else {
  decorate();
}

/* Status marker, so this is debuggable from the console on the live site:
   window.__ntAnalytics -> { loaded, tracking, error } */
window.__ntAnalytics = { loaded: false, tracking: false, error: null };

try {
  const mod = await import(SDK);
  const mixpanel = mod.default;
  window.__ntAnalytics.loaded = typeof mixpanel?.init === 'function';
  if (window.__ntAnalytics.loaded) {
    boot(mixpanel);
    window.__ntAnalytics.client = client;
    window.__ntAnalytics.tracking = true;
  }
} catch (e) {
  /* CDN blocked, offline, or SDK change — the site itself is unaffected. */
  window.__ntAnalytics.error = String(e?.message || e);
}
