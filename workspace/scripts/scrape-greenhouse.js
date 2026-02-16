// ===========================================================================
// GREENHOUSE JOB BOARD SCRAPER — Structured JSON Extraction
// ===========================================================================
// Runs via OpenClaw browser `evaluate` action in page context.
// Input: Any Greenhouse job board page (e.g., job-boards.greenhouse.io/anthropic)
// Output: JSON with all job listings, filtered by relevant keywords.
//
// Greenhouse embeds job data in multiple possible locations:
//   1. window.__remixContext.state.loaderData (Remix-based boards)
//   2. Script tags with JSON-LD or embedded data
//   3. DOM elements with .opening class (legacy boards)
// ===========================================================================

(function() {
  'use strict';

  const RELEVANT_KEYWORDS = /\b(ai|ml|machine.?learning|deep.?learning|research|scientist|engineer|founding|llm|nlp|computer.?vision|reinforcement|rl|post.?train|pre.?train|inference|data.?scientist|applied.?ai|generative|genai|multimodal|rlhf|alignment|safety)\b/i;

  const boardUrl = window.location.href;
  const company = document.title.replace(/\s*[-–|].*$/, '').replace(/\s*Jobs?\s*$/i, '').trim() || 'Unknown';

  // Strategy 1: Extract from Remix loaderData (modern Greenhouse)
  function extractFromRemixContext() {
    try {
      const ctx = window.__remixContext;
      if (!ctx) return null;

      // Navigate through the Remix loader data structure
      const loaderData = ctx.state && ctx.state.loaderData;
      if (!loaderData) return null;

      // Find the route that contains jobPosts
      for (const routeKey of Object.keys(loaderData)) {
        const route = loaderData[routeKey];
        if (!route) continue;

        let posts = null;
        if (route.jobPosts && route.jobPosts.data) {
          posts = route.jobPosts.data;
        } else if (route.jobPosts && Array.isArray(route.jobPosts)) {
          posts = route.jobPosts;
        } else if (Array.isArray(route.data)) {
          posts = route.data;
        }

        if (posts && posts.length > 0) {
          return posts.map(function(p) {
            return {
              title: p.title || '',
              department: (p.department && p.department.name) || p.departmentName || '',
              location: p.location || '',
              url: p.absolute_url || p.absoluteUrl || '',
              publishedAt: p.published_at || p.publishedAt || '',
              id: p.id || ''
            };
          });
        }
      }
    } catch (e) { /* ignore */ }
    return null;
  }

  // Strategy 2: Extract from embedded script tags
  function extractFromScriptTags() {
    try {
      var scripts = document.querySelectorAll('script');
      for (var i = 0; i < scripts.length; i++) {
        var text = scripts[i].textContent;
        if (!text) continue;

        // Look for jobPosts or jobs array in script content
        var patterns = [
          /"jobPosts"\s*:\s*\{[^}]*"data"\s*:\s*(\[[\s\S]*?\])\s*\}/,
          /"jobs"\s*:\s*(\[[\s\S]*?\])/,
          /jobPosts\s*=\s*(\[[\s\S]*?\]);/
        ];

        for (var j = 0; j < patterns.length; j++) {
          var match = text.match(patterns[j]);
          if (match && match[1]) {
            try {
              var data = JSON.parse(match[1]);
              if (Array.isArray(data) && data.length > 0 && data[0].title) {
                return data.map(function(p) {
                  return {
                    title: p.title || '',
                    department: (p.department && p.department.name) || '',
                    location: p.location || '',
                    url: p.absolute_url || '',
                    publishedAt: p.published_at || '',
                    id: p.id || ''
                  };
                });
              }
            } catch (e) { /* parse error, try next */ }
          }
        }
      }
    } catch (e) { /* ignore */ }
    return null;
  }

  // Strategy 3: Extract from DOM (legacy Greenhouse boards)
  function extractFromDOM() {
    var openings = document.querySelectorAll('.opening');
    if (openings.length === 0) return null;

    var jobs = [];
    var currentDept = '';

    // Check for department headers before openings
    var allElements = document.querySelectorAll('.opening, .department-name, h2, h3');
    for (var i = 0; i < allElements.length; i++) {
      var el = allElements[i];
      if (el.classList.contains('department-name') || el.tagName === 'H2' || el.tagName === 'H3') {
        if (!el.classList.contains('opening')) {
          currentDept = el.textContent.trim();
        }
      }
      if (el.classList.contains('opening')) {
        var link = el.querySelector('a');
        var locEl = el.querySelector('.location');
        if (link) {
          jobs.push({
            title: link.textContent.trim(),
            department: currentDept,
            location: locEl ? locEl.textContent.trim() : '',
            url: link.href || '',
            publishedAt: '',
            id: ''
          });
        }
      }
    }
    return jobs.length > 0 ? jobs : null;
  }

  // Try all strategies in order
  var allJobs = extractFromRemixContext() || extractFromScriptTags() || extractFromDOM();

  if (!allJobs) {
    return JSON.stringify({
      board: 'greenhouse',
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
    var searchText = (job.title + ' ' + job.department).toLowerCase();
    return RELEVANT_KEYWORDS.test(searchText);
  });

  return JSON.stringify({
    board: 'greenhouse',
    company: company,
    boardUrl: boardUrl,
    totalFound: allJobs.length,
    relevantFound: relevantJobs.length,
    jobs: relevantJobs
  });
})();
