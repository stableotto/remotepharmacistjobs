// Google Analytics (gtag.js) — loaded site-wide from a single source.
// Referenced by every page as: <script async src="/analytics.js"></script>
// To change the property, update GA_ID here only.
(function () {
  var GA_ID = 'G-C0EB4GHJS3';

  var loader = document.createElement('script');
  loader.async = true;
  loader.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA_ID;
  document.head.appendChild(loader);

  window.dataLayer = window.dataLayer || [];
  function gtag(){ dataLayer.push(arguments); }
  window.gtag = gtag;
  gtag('js', new Date());
  gtag('config', GA_ID);
})();
