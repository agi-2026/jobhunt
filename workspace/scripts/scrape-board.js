// ===========================================================================
// UNIVERSAL JOB BOARD SCRAPER — Auto-Detecting ATS Type
// ===========================================================================
// Runs via OpenClaw browser `evaluate` action in page context.
// Auto-detects: Greenhouse, Ashby, Lever, LinkedIn, Work at a Startup
// Returns structured JSON regardless of ATS type.
//
// Usage: navigate to ANY job board page, then run this via evaluate.
// ===========================================================================

(function() {
  'use strict';

  var boardUrl = window.location.href;
  var hostname = window.location.hostname;

  var RELEVANT_KEYWORDS = /\b(ai|ml|machine.?learning|deep.?learning|research|scientist|engineer|founding|llm|nlp|computer.?vision|reinforcement|rl|post.?train|pre.?train|inference|data.?scientist|applied.?ai|generative|genai|multimodal|rlhf|alignment|safety)\b/i;

  // =========================================================================
  // GREENHOUSE
  // =========================================================================
  function scrapeGreenhouse() {
    // Strategy 1: Remix loaderData
    try {
      var ctx = window.__remixContext;
      if (ctx && ctx.state && ctx.state.loaderData) {
        var ld = ctx.state.loaderData;
        for (var rk of Object.keys(ld)) {
          var route = ld[rk];
          if (!route) continue;
          var posts = (route.jobPosts && route.jobPosts.data) || (Array.isArray(route.jobPosts) ? route.jobPosts : null);
          if (posts && posts.length > 0) {
            return posts.map(function(p) {
              return {
                title: p.title || '', department: (p.department && p.department.name) || '',
                location: p.location || '', url: p.absolute_url || p.absoluteUrl || '',
                publishedAt: p.published_at || ''
              };
            });
          }
        }
      }
    } catch(e) {}

    // Strategy 2: DOM
    var openings = document.querySelectorAll('.opening');
    if (openings.length > 0) {
      var jobs = [], dept = '';
      var els = document.querySelectorAll('.opening, .department-name, h2, h3');
      for (var i = 0; i < els.length; i++) {
        var el = els[i];
        if (!el.classList.contains('opening')) { dept = el.textContent.trim(); continue; }
        var a = el.querySelector('a'), loc = el.querySelector('.location');
        if (a) jobs.push({ title: a.textContent.trim(), department: dept, location: loc ? loc.textContent.trim() : '', url: a.href });
      }
      if (jobs.length > 0) return jobs;
    }
    return null;
  }

  // =========================================================================
  // ASHBY
  // =========================================================================
  function scrapeAshby() {
    var slug = window.location.pathname.replace(/^\//, '').split('/')[0] || '';
    // Strategy 1: window.__appData
    try {
      var ad = window.__appData;
      if (ad && ad.jobBoard && ad.jobBoard.jobPostings) {
        return ad.jobBoard.jobPostings.filter(function(p) { return p.isListed !== false; }).map(function(p) {
          return {
            title: p.title || '', department: p.departmentName || p.teamName || '',
            location: p.locationName || '', url: 'https://jobs.ashbyhq.com/' + slug + '/' + (p.id || ''),
            compensation: p.compensation || p.compensationTierSummary || '',
            workplaceType: p.workplaceType || '', publishedDate: p.publishedDate || ''
          };
        });
      }
    } catch(e) {}

    // Strategy 2: script tags
    try {
      var scripts = document.querySelectorAll('script');
      for (var i = 0; i < scripts.length; i++) {
        var t = scripts[i].textContent;
        if (!t || t.length < 100) continue;
        var m = t.match(/window\.__appData\s*=\s*(\{[\s\S]*\})\s*;?\s*$/);
        if (m && m[1]) {
          var d = JSON.parse(m[1]);
          if (d.jobBoard && d.jobBoard.jobPostings) {
            return d.jobBoard.jobPostings.filter(function(p) { return p.isListed !== false; }).map(function(p) {
              return {
                title: p.title || '', department: p.departmentName || p.teamName || '',
                location: p.locationName || '', url: 'https://jobs.ashbyhq.com/' + slug + '/' + (p.id || ''),
                compensation: p.compensation || '', publishedDate: p.publishedDate || ''
              };
            });
          }
        }
      }
    } catch(e) {}
    return null;
  }

  // =========================================================================
  // LEVER
  // =========================================================================
  function scrapeLever() {
    var postings = document.querySelectorAll('.posting');
    if (postings.length === 0) return null;
    var jobs = [];
    for (var i = 0; i < postings.length; i++) {
      var p = postings[i];
      var tEl = p.querySelector('.posting-title h5, .posting-title a, a[data-qa="posting-name"]');
      var lnk = p.querySelector('a.posting-title, a[data-qa="posting-name"], a[href*="/jobs/"]') || p.querySelector('a');
      var loc = p.querySelector('.posting-categories .location, [class*="location"]');
      var team = p.querySelector('.posting-categories .team, [class*="department"]');
      if (tEl) jobs.push({
        title: tEl.textContent.trim(), team: team ? team.textContent.trim() : '',
        location: loc ? loc.textContent.trim() : '', url: lnk ? lnk.href : ''
      });
    }
    return jobs.length > 0 ? jobs : null;
  }

  // =========================================================================
  // LINKEDIN
  // =========================================================================
  function scrapeLinkedIn() {
    var cards = document.querySelectorAll('.job-card-container, .jobs-search-results__list-item, .scaffold-layout__list-item, [data-occludable-job-id]');
    if (cards.length === 0) {
      // Try public/unauthenticated
      cards = document.querySelectorAll('.base-card, .job-search-card, .base-search-card');
    }
    if (cards.length === 0) return null;

    var jobs = [];
    for (var i = 0; i < cards.length; i++) {
      var c = cards[i];
      // Title
      var tEl = c.querySelector('.job-card-list__title, a[class*="job-card-list__title"], .artdeco-entity-lockup__title a');
      if (!tEl) { var fl = c.querySelector('a[href*="/jobs/view/"]'); tEl = fl ? (fl.querySelector('strong') || fl) : null; }
      if (!tEl) tEl = c.querySelector('.base-search-card__title, h3');
      var title = '';
      if (tEl) {
        var cl = tEl.cloneNode(true);
        var hid = cl.querySelectorAll('.visually-hidden, .sr-only, [aria-hidden="true"]');
        for (var h = 0; h < hid.length; h++) hid[h].remove();
        title = cl.textContent.trim().replace(/\s+/g, ' ').replace(/with verification$/i, '').replace(/(.{5,}?)\1+$/, '$1').trim();
      }
      // Company
      var coEl = c.querySelector('.job-card-container__primary-description, .artdeco-entity-lockup__subtitle, .base-search-card__subtitle');
      // Location
      var loEl = c.querySelector('.job-card-container__metadata-item, .artdeco-entity-lockup__caption, .job-search-card__location, [class*="location"]');
      // URL
      var lnk = c.querySelector('a[href*="/jobs/view/"]');
      var url = lnk ? lnk.href : '';
      if (!url) { var jid = c.getAttribute('data-occludable-job-id'); if (jid) url = 'https://www.linkedin.com/jobs/view/' + jid + '/'; }
      if (url) url = url.replace(/[?&](refId|trackingId|trk|currentJobId|position|eBP)=[^&]*/g, '').replace(/\?$/, '');
      // Salary
      var salEl = c.querySelector('.job-card-container__salary-info, [class*="salary"]');
      // Posted
      var tmEl = c.querySelector('time, [datetime]');
      var posted = tmEl ? (tmEl.getAttribute('datetime') || tmEl.textContent.trim()) : '';
      posted = posted.replace(/\s+/g, ' ').replace(/\s*(Within|Reposted|Viewed).*$/i, '').trim();

      if (title && url) jobs.push({
        title: title, company: coEl ? coEl.textContent.trim() : '',
        location: loEl ? loEl.textContent.trim() : '', url: url,
        salary: salEl ? salEl.textContent.trim() : '', posted: posted,
        easyApply: !!c.querySelector('[class*="easy-apply"]'),
        jobId: c.getAttribute('data-occludable-job-id') || ''
      });
    }
    return jobs.length > 0 ? jobs : null;
  }

  // =========================================================================
  // WORK AT A STARTUP (YC)
  // =========================================================================
  function scrapeWaaS() {
    var links = document.querySelectorAll('a[href*="signup_job_id"]');
    if (links.length === 0) return null;
    var seen = {}, jobs = [];
    for (var i = 0; i < links.length; i++) {
      var el = links[i], href = el.href || '';
      var jm = href.match(/signup_job_id=(\d+)/);
      var jid = jm ? jm[1] : '';
      if (jid && seen[jid]) continue;
      if (jid) seen[jid] = true;
      var text = el.textContent.trim().replace(/\s+/g, ' ');
      // Basic extraction from card text
      jobs.push({ title: text.substring(0, 200), company: '', location: '', url: href, jobId: jid });
    }
    return jobs.length > 0 ? jobs : null;
  }

  // =========================================================================
  // AUTO-DETECT AND RUN
  // =========================================================================
  var board = 'unknown';
  var allJobs = null;
  var company = document.title.replace(/\s*[-–|].*$/, '').replace(/\s*Jobs?\s*$/i, '').trim();

  if (hostname.indexOf('greenhouse.io') > -1) {
    board = 'greenhouse';
    allJobs = scrapeGreenhouse();
  } else if (hostname.indexOf('ashbyhq.com') > -1) {
    board = 'ashby';
    allJobs = scrapeAshby();
    try { company = window.__appData.jobBoard.organizationName || company; } catch(e) {}
  } else if (hostname.indexOf('lever.co') > -1) {
    board = 'lever';
    allJobs = scrapeLever();
  } else if (hostname.indexOf('linkedin.com') > -1) {
    board = 'linkedin';
    allJobs = scrapeLinkedIn();
    var qm = boardUrl.match(/[?&]keywords=([^&]*)/);
    company = qm ? decodeURIComponent(qm[1].replace(/\+/g, ' ')) : 'LinkedIn Search';
  } else if (hostname.indexOf('workatastartup.com') > -1) {
    board = 'workatastartup';
    allJobs = scrapeWaaS();
    company = 'YC Startups';
  } else {
    // Try all strategies as fallback
    allJobs = scrapeGreenhouse() || scrapeAshby() || scrapeLever();
  }

  if (!allJobs || allJobs.length === 0) {
    return JSON.stringify({
      board: board, company: company, boardUrl: boardUrl,
      error: 'Could not extract jobs. Page may need more load time.',
      jobs: [], totalFound: 0, relevantFound: 0
    });
  }

  // Filter relevant
  var relevant = allJobs.filter(function(j) {
    return RELEVANT_KEYWORDS.test((j.title || '') + ' ' + (j.department || '') + ' ' + (j.team || ''));
  });

  return JSON.stringify({
    board: board, company: company, boardUrl: boardUrl,
    totalFound: allJobs.length, relevantFound: relevant.length,
    jobs: relevant
  });
})();
