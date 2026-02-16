// ===========================================================================
// ASHBY JOB BOARD SCRAPER — Structured JSON Extraction
// ===========================================================================
// Runs via OpenClaw browser `evaluate` action in page context.
// Input: Any Ashby job board page (e.g., jobs.ashbyhq.com/openai)
// Output: JSON with all job listings, filtered by relevant keywords.
//
// Ashby embeds job data in window.__appData.jobBoard.jobPostings (React SPA).
// ===========================================================================

(function() {
  'use strict';

  const RELEVANT_KEYWORDS = /\b(ai|ml|machine.?learning|deep.?learning|research|scientist|engineer|founding|llm|nlp|computer.?vision|reinforcement|rl|post.?train|pre.?train|inference|data.?scientist|applied.?ai|generative|genai|multimodal|rlhf|alignment|safety)\b/i;

  const boardUrl = window.location.href;
  const slug = window.location.pathname.replace(/^\//, '').split('/')[0] || '';

  // Strategy 1: Extract from window.__appData (standard Ashby)
  function extractFromAppData() {
    try {
      var appData = window.__appData;
      if (!appData || !appData.jobBoard) return null;

      var board = appData.jobBoard;
      var company = (board.organizationName) || '';
      var postings = board.jobPostings;

      if (!Array.isArray(postings) || postings.length === 0) return null;

      return {
        company: company,
        jobs: postings
          .filter(function(p) { return p.isListed !== false; })
          .map(function(p) {
            return {
              title: p.title || '',
              department: p.departmentName || p.teamName || '',
              location: p.locationName || '',
              url: 'https://jobs.ashbyhq.com/' + slug + '/' + (p.id || p.jobId || ''),
              compensation: p.compensation || p.compensationTierSummary || '',
              workplaceType: p.workplaceType || '',
              employmentType: p.employmentType || '',
              publishedDate: p.publishedDate || '',
              id: p.id || p.jobId || ''
            };
          })
      };
    } catch (e) { /* ignore */ }
    return null;
  }

  // Strategy 2: Extract from script tags with embedded JSON
  function extractFromScripts() {
    try {
      var scripts = document.querySelectorAll('script');
      for (var i = 0; i < scripts.length; i++) {
        var text = scripts[i].textContent;
        if (!text || text.length < 100) continue;

        // Look for __appData assignment
        var match = text.match(/window\.__appData\s*=\s*(\{[\s\S]*\})\s*;?\s*$/);
        if (match && match[1]) {
          try {
            var data = JSON.parse(match[1]);
            if (data.jobBoard && data.jobBoard.jobPostings) {
              var board = data.jobBoard;
              return {
                company: board.organizationName || '',
                jobs: board.jobPostings
                  .filter(function(p) { return p.isListed !== false; })
                  .map(function(p) {
                    return {
                      title: p.title || '',
                      department: p.departmentName || p.teamName || '',
                      location: p.locationName || '',
                      url: 'https://jobs.ashbyhq.com/' + slug + '/' + (p.id || ''),
                      compensation: p.compensation || p.compensationTierSummary || '',
                      workplaceType: p.workplaceType || '',
                      employmentType: p.employmentType || '',
                      publishedDate: p.publishedDate || '',
                      id: p.id || ''
                    };
                  })
              };
            }
          } catch (e) { /* parse error */ }
        }
      }
    } catch (e) { /* ignore */ }
    return null;
  }

  // Strategy 3: Extract from rendered DOM (fallback)
  function extractFromDOM() {
    // Ashby renders job cards as links — look for common patterns
    var links = document.querySelectorAll('a[href*="/application"], a[href*="ashbyhq.com"]');
    if (links.length === 0) {
      links = document.querySelectorAll('[role="listitem"] a, [data-testid] a');
    }
    if (links.length === 0) return null;

    var seen = {};
    var jobs = [];
    for (var i = 0; i < links.length; i++) {
      var a = links[i];
      var href = a.href;
      if (!href || seen[href]) continue;
      seen[href] = true;

      // Try to get title from the link text or nearby heading
      var title = a.textContent.trim();
      if (title.length > 200) title = ''; // Not a title link

      // Try to find location nearby
      var parent = a.closest('[role="listitem"]') || a.parentElement;
      var locationEl = parent && parent.querySelector('[class*="location"], [class*="Location"]');

      if (title) {
        jobs.push({
          title: title,
          department: '',
          location: locationEl ? locationEl.textContent.trim() : '',
          url: href,
          compensation: '',
          workplaceType: '',
          employmentType: '',
          publishedDate: '',
          id: ''
        });
      }
    }
    return jobs.length > 0 ? { company: '', jobs: jobs } : null;
  }

  var result = extractFromAppData() || extractFromScripts() || extractFromDOM();

  if (!result) {
    return JSON.stringify({
      board: 'ashby',
      company: slug,
      boardUrl: boardUrl,
      error: 'Could not extract job data from page',
      jobs: [],
      totalFound: 0,
      relevantFound: 0
    });
  }

  var company = result.company || slug;
  var allJobs = result.jobs;

  // Filter to relevant AI/ML roles
  var relevantJobs = allJobs.filter(function(job) {
    var searchText = (job.title + ' ' + job.department).toLowerCase();
    return RELEVANT_KEYWORDS.test(searchText);
  });

  return JSON.stringify({
    board: 'ashby',
    company: company,
    boardUrl: boardUrl,
    totalFound: allJobs.length,
    relevantFound: relevantJobs.length,
    jobs: relevantJobs
  });
})();
