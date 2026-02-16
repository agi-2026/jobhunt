// ===========================================================================
// LINKEDIN JOB SEARCH SCRAPER — DOM Extraction (Authenticated)
// ===========================================================================
// Runs via OpenClaw browser `evaluate` action in page context.
// Input: LinkedIn job search results page (must be logged in)
//   e.g., https://www.linkedin.com/jobs/search/?keywords=AI+ML+Engineer&location=United+States&f_TPR=r86400
// Output: JSON with job listings from the search results.
//
// LinkedIn is a React SPA. Job cards are rendered in a scrollable list.
// This scraper extracts from the rendered DOM after the page loads.
// ===========================================================================

(function() {
  'use strict';

  const boardUrl = window.location.href;
  const queryMatch = boardUrl.match(/[?&]keywords=([^&]*)/);
  const query = queryMatch ? decodeURIComponent(queryMatch[1].replace(/\+/g, ' ')) : '';

  // Check if logged in
  const isLoggedIn = !!document.querySelector('.global-nav, nav[aria-label="Primary"], .feed-identity-module');
  if (!isLoggedIn) {
    // Check if on login page
    if (document.querySelector('#username, .login__form, .sign-in-form')) {
      return JSON.stringify({
        board: 'linkedin',
        query: query,
        error: 'Not logged in — LinkedIn login required. Navigate to linkedin.com/login first.',
        jobs: [],
        totalFound: 0
      });
    }
  }

  // Strategy 1: Extract from job search results list (authenticated view)
  function extractFromJobSearch() {
    // LinkedIn job search has a scaffold with job cards
    var cards = document.querySelectorAll(
      '.job-card-container, ' +
      '.jobs-search-results__list-item, ' +
      '.scaffold-layout__list-item, ' +
      'li[class*="jobs-search-results"], ' +
      '[data-occludable-job-id]'
    );

    if (cards.length === 0) return null;

    var jobs = [];
    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];

      // Title — extract carefully to avoid duplication and "with verification" badge
      var titleEl = card.querySelector(
        '.job-card-list__title, ' +
        'a[class*="job-card-list__title"], ' +
        '.artdeco-entity-lockup__title a, ' +
        'a[data-control-name="job_card_title"]'
      );
      if (!titleEl) {
        // Fallback: first <a> with /jobs/view/ link, use its strong or direct text
        var fallbackLink = card.querySelector('a[href*="/jobs/view/"]');
        if (fallbackLink) {
          var strongInLink = fallbackLink.querySelector('strong');
          titleEl = strongInLink || fallbackLink;
        }
      }
      var title = '';
      if (titleEl) {
        // Clone and remove visually-hidden/sr-only elements to get clean text
        var clone = titleEl.cloneNode(true);
        var hidden = clone.querySelectorAll('.visually-hidden, .sr-only, [aria-hidden="true"]');
        for (var h = 0; h < hidden.length; h++) hidden[h].remove();
        title = clone.textContent.trim()
          .replace(/\s+/g, ' ')                    // collapse whitespace
          .replace(/with verification$/i, '')       // strip verification badge
          .replace(/(.{5,}?)\1+$/, '$1')           // deduplicate repeated title text
          .trim();
      }

      // Company
      var companyEl = card.querySelector(
        '.job-card-container__primary-description, ' +
        '.artdeco-entity-lockup__subtitle, ' +
        '.job-card-container__company-name, ' +
        'a[data-control-name="job_card_company_link"], ' +
        '[class*="company"]'
      );
      var company = companyEl ? companyEl.textContent.trim() : '';

      // Location
      var locationEl = card.querySelector(
        '.job-card-container__metadata-item, ' +
        '.artdeco-entity-lockup__caption, ' +
        '[class*="location"], ' +
        '.job-card-container__metadata-wrapper li'
      );
      var location = locationEl ? locationEl.textContent.trim() : '';

      // URL — try multiple strategies
      var linkEl = card.querySelector('a[href*="/jobs/view/"]');
      if (!linkEl) linkEl = card.querySelector('a[href*="/jobs/"]');
      if (!linkEl) linkEl = card.tagName === 'A' ? card : null;
      var url = '';
      if (linkEl) {
        url = linkEl.href;
      } else {
        // Build URL from job ID
        var jid = card.getAttribute('data-occludable-job-id') || card.getAttribute('data-job-id');
        if (jid) url = 'https://www.linkedin.com/jobs/view/' + jid + '/';
      }
      if (url) {
        // Clean tracking parameters
        url = url.replace(/[?&](refId|trackingId|trk|currentJobId|position|eBP)=[^&]*/g, '');
        if (url.indexOf('?') === url.length - 1) url = url.slice(0, -1);
        if (url.startsWith('/')) url = 'https://www.linkedin.com' + url;
      }

      // Salary (if shown)
      var salaryEl = card.querySelector(
        '.job-card-container__salary-info, ' +
        '[class*="salary"], ' +
        '[class*="compensation"]'
      );
      var salary = salaryEl ? salaryEl.textContent.trim() : '';

      // Posted time
      var timeEl = card.querySelector(
        'time, ' +
        '.job-card-container__footer-item, ' +
        '[class*="listed-time"], ' +
        '[datetime]'
      );
      var posted = '';
      if (timeEl) {
        posted = timeEl.getAttribute('datetime') || timeEl.textContent.trim();
        // Clean up "9 minutes ago\n  Within the past 24 hours" → "9 minutes ago"
        posted = posted.replace(/\s+/g, ' ').replace(/\s*(Within|Reposted|Viewed).*$/i, '').trim();
      }

      // Easy Apply badge
      var easyApply = !!card.querySelector(
        '.job-card-container__apply-method, ' +
        '[class*="easy-apply"], ' +
        'svg[class*="easy-apply"]'
      );

      // Job ID from data attributes
      var jobId = card.getAttribute('data-occludable-job-id') ||
                  card.getAttribute('data-job-id') || '';

      if (title && url) {
        jobs.push({
          title: title,
          company: company,
          location: location,
          url: url,
          salary: salary,
          posted: posted,
          easyApply: easyApply,
          jobId: jobId
        });
      }
    }
    return jobs.length > 0 ? jobs : null;
  }

  // Strategy 2: Extract from unauthenticated/public job search
  function extractFromPublicSearch() {
    var cards = document.querySelectorAll(
      '.base-card, ' +
      '.job-search-card, ' +
      '.base-search-card, ' +
      '[class*="result-card"]'
    );

    if (cards.length === 0) return null;

    var jobs = [];
    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];

      var titleEl = card.querySelector('.base-search-card__title, h3, [class*="title"]');
      var companyEl = card.querySelector('.base-search-card__subtitle, h4, [class*="company"]');
      var locationEl = card.querySelector('.job-search-card__location, [class*="location"]');
      var linkEl = card.querySelector('a[href*="/jobs/view/"]');
      var timeEl = card.querySelector('time, [datetime]');

      var title = titleEl ? titleEl.textContent.trim() : '';
      var url = linkEl ? linkEl.href : '';

      if (title && url) {
        jobs.push({
          title: title,
          company: companyEl ? companyEl.textContent.trim() : '',
          location: locationEl ? locationEl.textContent.trim() : '',
          url: url.replace(/[?&](refId|trackingId|trk)=[^&]*/g, ''),
          salary: '',
          posted: timeEl ? (timeEl.getAttribute('datetime') || timeEl.textContent.trim()) : '',
          easyApply: false,
          jobId: ''
        });
      }
    }
    return jobs.length > 0 ? jobs : null;
  }

  var allJobs = extractFromJobSearch() || extractFromPublicSearch();

  if (!allJobs) {
    return JSON.stringify({
      board: 'linkedin',
      query: query,
      boardUrl: boardUrl,
      error: 'Could not extract job listings. Page may not have loaded fully — try scrolling first or check if logged in.',
      isLoggedIn: isLoggedIn,
      jobs: [],
      totalFound: 0
    });
  }

  // Deduplicate by URL
  var seen = {};
  var uniqueJobs = [];
  for (var i = 0; i < allJobs.length; i++) {
    var key = allJobs[i].url.replace(/[?#].*$/, '');
    if (!seen[key]) {
      seen[key] = true;
      uniqueJobs.push(allJobs[i]);
    }
  }

  return JSON.stringify({
    board: 'linkedin',
    query: query,
    boardUrl: boardUrl,
    isLoggedIn: isLoggedIn,
    totalFound: uniqueJobs.length,
    jobs: uniqueJobs
  });
})();
