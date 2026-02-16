// ===========================================================================
// WORK AT A STARTUP (YC) JOB BOARD SCRAPER
// ===========================================================================
// Runs via OpenClaw browser `evaluate` action in page context.
// Input: https://www.workatastartup.com/jobs?query=machine+learning&demographic=any
// Output: JSON with YC startup job listings.
//
// WaaS uses anchor elements with signup_job_id parameters.
// Job cards contain company logo, name, batch, title, type, location.
// ===========================================================================

(function() {
  'use strict';

  const RELEVANT_KEYWORDS = /\b(ai|ml|machine.?learning|deep.?learning|research|scientist|engineer|founding|llm|nlp|computer.?vision|reinforcement|rl|post.?train|pre.?train|inference|data.?scientist|applied.?ai|generative|genai|multimodal|rlhf|alignment|safety)\b/i;

  const boardUrl = window.location.href;

  // Strategy 1: Extract from React-rendered job cards
  function extractFromDOM() {
    // WaaS renders job listings as card-like elements
    // Each job posting is typically an <a> tag with job details inside
    var jobLinks = document.querySelectorAll('a[href*="signup_job_id"]');
    if (jobLinks.length === 0) {
      // Try alternative selectors
      jobLinks = document.querySelectorAll('[class*="job-listing"], [class*="JobListing"], [data-job-id]');
    }

    if (jobLinks.length === 0) return null;

    var seen = {};
    var jobs = [];

    for (var i = 0; i < jobLinks.length; i++) {
      var el = jobLinks[i];
      var href = el.href || '';

      // Extract job ID from URL
      var jobIdMatch = href.match(/signup_job_id=(\d+)/);
      var jobId = jobIdMatch ? jobIdMatch[1] : '';

      // Skip duplicates
      if (jobId && seen[jobId]) continue;
      if (jobId) seen[jobId] = true;

      // Parse the card content
      var text = el.textContent || '';
      var lines = text.split('\n').map(function(l) { return l.trim(); }).filter(Boolean);

      // Try to identify structured elements
      var imgs = el.querySelectorAll('img');
      var companyName = '';
      var batch = '';
      var title = '';
      var jobType = '';
      var location = '';
      var description = '';

      // Look for structured child elements
      var children = el.children;
      for (var j = 0; j < children.length; j++) {
        var child = children[j];
        var childText = child.textContent.trim();

        // Company logos are in img tags
        if (child.tagName === 'IMG' || child.querySelector('img')) {
          var img = child.tagName === 'IMG' ? child : child.querySelector('img');
          if (img && img.alt) companyName = img.alt;
        }
      }

      // Parse text content for job details
      for (var k = 0; k < lines.length; k++) {
        var line = lines[k];

        // Batch format: S24, W25, etc.
        if (/^[SWF]\d{2}$/.test(line)) {
          batch = line;
          continue;
        }

        // Job type
        if (/^(fulltime|intern|contract|part.?time)$/i.test(line)) {
          jobType = line;
          continue;
        }

        // Location patterns (City, State or Remote)
        if (/^(remote|Remote|.+,\s*[A-Z]{2})/.test(line) && !title) {
          location = line;
          continue;
        }

        // Posted time
        if (/\(\d+\s+(days?|months?|hours?)\s+ago\)/.test(line)) {
          continue; // Skip, not needed
        }

        // Role category
        if (/^(Backend|Frontend|Full stack|DevOps|Data|Design|Mobile|Marketing|Sales|Operations)/i.test(line) && line.length < 30) {
          continue;
        }

        // First meaningful line without match is likely company name or title
        if (!companyName && line.length > 1 && line.length < 100) {
          companyName = line;
        } else if (companyName && !title && line.length > 5 && line.length < 200) {
          // Could be company description or job title
          // Job titles are usually shorter
          if (line.length < 80 && !/^(We|Our|A |The |Building)/.test(line)) {
            title = line;
          } else if (!description) {
            description = line;
          }
        } else if (!title && line.length > 5 && line.length < 80) {
          title = line;
        }
      }

      // If we still don't have a title, try alternative extraction
      if (!title) {
        // Look for elements that look like job titles
        var headings = el.querySelectorAll('h1, h2, h3, h4, strong, b, [class*="title"]');
        for (var h = 0; h < headings.length; h++) {
          var hText = headings[h].textContent.trim();
          if (hText.length > 5 && hText.length < 200) {
            title = hText;
            break;
          }
        }
      }

      if (title || companyName) {
        // Build application URL
        var applyUrl = href || '';
        if (!applyUrl && jobId) {
          applyUrl = 'https://www.workatastartup.com/jobs/' + jobId;
        }

        jobs.push({
          title: title || '(untitled)',
          company: companyName,
          batch: batch,
          location: location,
          jobType: jobType,
          url: applyUrl,
          jobId: jobId
        });
      }
    }
    return jobs.length > 0 ? jobs : null;
  }

  // Strategy 2: Extract from page's embedded data (if available)
  function extractFromPageData() {
    try {
      // Check for Next.js or similar data embedding
      var nextData = document.querySelector('#__NEXT_DATA__');
      if (nextData) {
        var data = JSON.parse(nextData.textContent);
        var props = data.props && data.props.pageProps;
        if (props && props.jobs) {
          return props.jobs.map(function(j) {
            return {
              title: j.title || j.role || '',
              company: (j.company && j.company.name) || j.companyName || '',
              batch: (j.company && j.company.batch) || j.batch || '',
              location: j.location || '',
              jobType: j.type || j.employmentType || '',
              url: j.url || ('https://www.workatastartup.com/jobs/' + j.id),
              jobId: String(j.id || '')
            };
          });
        }
      }
    } catch (e) { /* ignore */ }
    return null;
  }

  var allJobs = extractFromPageData() || extractFromDOM();

  if (!allJobs) {
    return JSON.stringify({
      board: 'workatastartup',
      boardUrl: boardUrl,
      error: 'Could not extract job data. Page may need to load fully.',
      jobs: [],
      totalFound: 0,
      relevantFound: 0
    });
  }

  // Filter to relevant AI/ML roles
  var relevantJobs = allJobs.filter(function(job) {
    var searchText = (job.title + ' ' + job.company).toLowerCase();
    return RELEVANT_KEYWORDS.test(searchText);
  });

  return JSON.stringify({
    board: 'workatastartup',
    boardUrl: boardUrl,
    totalFound: allJobs.length,
    relevantFound: relevantJobs.length,
    jobs: relevantJobs
  });
})();
