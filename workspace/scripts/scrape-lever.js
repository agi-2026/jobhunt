// ===========================================================================
// LEVER JOB BOARD SCRAPER — Structured Extraction
// ===========================================================================
// Runs via OpenClaw browser `evaluate` action in page context.
// Input: Any Lever job board page (e.g., jobs.lever.co/anyscale)
// Output: JSON with all job listings, filtered by relevant keywords.
//
// Lever uses traditional HTML with .postings-group and .posting elements.
// Also has a JSON API at /company?mode=json as fallback.
// ===========================================================================

(function() {
  'use strict';

  const RELEVANT_KEYWORDS = /\b(ai|ml|machine.?learning|deep.?learning|research|scientist|engineer|founding|llm|nlp|computer.?vision|reinforcement|rl|post.?train|pre.?train|inference|data.?scientist|applied.?ai|generative|genai|multimodal|rlhf|alignment|safety)\b/i;

  const boardUrl = window.location.href;
  const slug = window.location.pathname.replace(/^\//, '').split('/')[0] || '';
  const company = document.querySelector('.main-header-text h1, .company-name, title')
    ? (document.querySelector('.main-header-text h1, .company-name') || {}).textContent || document.title.replace(/\s*[-–|].*$/, '').trim()
    : slug;

  // Strategy 1: Extract from DOM (.posting elements)
  function extractFromDOM() {
    var postings = document.querySelectorAll('.posting');
    if (postings.length === 0) return null;

    var jobs = [];
    for (var i = 0; i < postings.length; i++) {
      var p = postings[i];

      var titleEl = p.querySelector('.posting-title h5, .posting-title a, a[data-qa="posting-name"]');
      var title = titleEl ? titleEl.textContent.trim() : '';

      var linkEl = p.querySelector('a.posting-title, a[data-qa="posting-name"], a[href*="/jobs/"]') || p.querySelector('a');
      var url = linkEl ? linkEl.href : '';

      // Categories: location, team, commitment
      var locationEl = p.querySelector('.posting-categories .location, [class*="location"], .workplaceTypes');
      var teamEl = p.querySelector('.posting-categories .team, [class*="department"], [class*="team"]');
      var commitEl = p.querySelector('.posting-categories .commitment, [class*="commitment"]');

      if (title) {
        jobs.push({
          title: title,
          team: teamEl ? teamEl.textContent.trim() : '',
          location: locationEl ? locationEl.textContent.trim() : '',
          commitment: commitEl ? commitEl.textContent.trim() : '',
          url: url,
          id: ''
        });
      }
    }
    return jobs.length > 0 ? jobs : null;
  }

  // Strategy 2: Extract from postings-group structure
  function extractFromGroups() {
    var groups = document.querySelectorAll('.postings-group');
    if (groups.length === 0) return null;

    var jobs = [];
    for (var g = 0; g < groups.length; g++) {
      var group = groups[g];
      var teamName = '';
      var teamHeader = group.querySelector('.posting-category-title, .large-category-header');
      if (teamHeader) teamName = teamHeader.textContent.trim();

      var items = group.querySelectorAll('.posting');
      for (var i = 0; i < items.length; i++) {
        var p = items[i];
        var titleEl = p.querySelector('h5, a');
        var title = titleEl ? titleEl.textContent.trim() : '';
        var linkEl = p.querySelector('a[href]');
        var url = linkEl ? linkEl.href : '';
        var locEl = p.querySelector('.location, .workplaceTypes');

        if (title) {
          jobs.push({
            title: title,
            team: teamName,
            location: locEl ? locEl.textContent.trim() : '',
            commitment: '',
            url: url,
            id: ''
          });
        }
      }
    }
    return jobs.length > 0 ? jobs : null;
  }

  // Strategy 3: Extract from any anchor links to lever jobs
  function extractFromLinks() {
    var links = document.querySelectorAll('a[href*="jobs.lever.co/' + slug + '/"]');
    if (links.length === 0) return null;

    var seen = {};
    var jobs = [];
    for (var i = 0; i < links.length; i++) {
      var a = links[i];
      var href = a.href;
      // Skip apply links and duplicates
      if (!href || seen[href] || /\/apply$/.test(href)) continue;
      seen[href] = true;

      var title = a.textContent.trim();
      if (title && title.length < 200) {
        jobs.push({
          title: title,
          team: '',
          location: '',
          commitment: '',
          url: href,
          id: ''
        });
      }
    }
    return jobs.length > 0 ? jobs : null;
  }

  var allJobs = extractFromDOM() || extractFromGroups() || extractFromLinks();

  if (!allJobs) {
    return JSON.stringify({
      board: 'lever',
      company: company,
      boardUrl: boardUrl,
      error: 'Could not extract job data from page',
      jobs: [],
      totalFound: 0,
      relevantFound: 0
    });
  }

  // Filter to relevant AI/ML roles
  var relevantJobs = allJobs.filter(function(job) {
    var searchText = (job.title + ' ' + job.team).toLowerCase();
    return RELEVANT_KEYWORDS.test(searchText);
  });

  return JSON.stringify({
    board: 'lever',
    company: company,
    boardUrl: boardUrl,
    totalFound: allJobs.length,
    relevantFound: relevantJobs.length,
    jobs: relevantJobs
  });
})();
