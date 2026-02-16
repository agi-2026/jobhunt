// ===========================================================================
// DETERMINISTIC FORM FILLER — Autonomous Job Application Agent
// ===========================================================================
// v2.0 — Fixed: Greenhouse/Ashby custom React dropdowns, phone handling,
//         file upload detection, combobox interaction, better label detection
//
// Runs via OpenClaw browser `evaluate` action in page context.
// Returns: JSON with filled fields, unfilled fields, custom questions
//
// SETUP: Replace ALL values in PROFILE below with your own information.
// ===========================================================================

(function() {
  'use strict';

  // -------------------------------------------------------------------------
  // PROFILE DATA — ⚠️ CUSTOMIZE ALL VALUES BELOW ⚠️
  // -------------------------------------------------------------------------
  const PROFILE = {
    firstName: 'YOUR_FIRST_NAME',
    lastName: 'YOUR_LAST_NAME',
    fullName: 'YOUR FULL NAME',
    email: 'you@example.com',
    phone: '+15555555555',
    phoneFormatted: '+1 (555) 555-5555',
    phonePlain: '5555555555',
    phoneDashes: '555-555-5555',
    phoneLocal: '(555) 555-5555',
    linkedin: 'https://www.linkedin.com/in/your-profile',
    location: 'City, ST',
    fullAddress: '123 Main St, City, ST 00000',
    city: 'City',
    state: 'State',
    stateAbbr: 'ST',
    zip: '00000',
    country: 'United States',
    website: '',
    github: '',

    // Work authorization
    authorized: true,           // true if legally authorized to work in US
    needsSponsorship: false,    // true if you need visa sponsorship
    visaStatus: 'US Citizen',   // e.g. 'US Citizen', 'Green Card', 'F1-OPT', 'H-1B'

    // Current role
    currentTitle: 'Your Current Title',
    currentCompany: 'Your Company',
    yearsExperience: '5',
    yearsExperiencePlus: '5+',

    // Education
    school1: 'Your University',
    degree1: 'M.S. Computer Science',
    gradYear1: '2025',
    school2: '',                 // Leave empty if only one degree
    degree2: '',
    gradYear2: '',

    // Compensation
    salary: '150000',
    salaryFormatted: '$150,000',
    salaryRange: '$150,000 - $200,000',
    salaryRangeNegotiable: '$150,000 - $200,000 (negotiable with equity)',

    // Availability
    startDate: 'Immediately',
    startDateISO: (() => {
      const d = new Date();
      d.setDate(d.getDate() + 14);
      while (d.getDay() !== 1) d.setDate(d.getDate() + 1);
      return d.toISOString().split('T')[0];
    })(),
    willingToRelocate: true,
    remotePreference: 'Open to remote, hybrid, or on-site',

    // EEO / demographics (decline all — recommended)
    gender: 'Decline to self-identify',
    race: 'Decline to self-identify',
    veteran: 'I am not a protected veteran',
    disability: 'I do not wish to answer',

    // How heard
    howHeard: 'Company careers page',
    referral: '',

    // Optional: deadline/urgency note for sponsorship questions
    deadlineNote: '',
  };

  // -------------------------------------------------------------------------
  // ATS DETECTION
  // -------------------------------------------------------------------------
  function detectATS() {
    const hostname = window.location.hostname.toLowerCase();

    if (hostname.includes('ashbyhq.com') || hostname.includes('jobs.ashbyhq.com'))
      return 'ashby';
    if (hostname.includes('greenhouse.io') || hostname.includes('boards.greenhouse.io') || hostname.includes('job-boards.greenhouse.io'))
      return 'greenhouse';
    if (hostname.includes('lever.co') || hostname.includes('jobs.lever.co'))
      return 'lever';
    if (hostname.includes('myworkdayjobs.com') || hostname.includes('workday.com'))
      return 'workday';
    if (hostname.includes('gem.com'))
      return 'gem';
    if (hostname.includes('icims.com'))
      return 'icims';
    if (hostname.includes('bamboohr.com'))
      return 'bamboohr';
    if (hostname.includes('smartrecruiters.com'))
      return 'smartrecruiters';
    if (hostname.includes('jazz.co') || hostname.includes('applytojob.com'))
      return 'jazzhr';
    if (hostname.includes('breezy.hr'))
      return 'breezy';
    if (hostname.includes('rippling.com'))
      return 'rippling';

    return 'unknown';
  }

  // -------------------------------------------------------------------------
  // NATIVE INPUT VALUE SETTER (React bypass)
  // -------------------------------------------------------------------------
  const nativeInputSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, 'value'
  )?.set;
  const nativeTextareaSetter = Object.getOwnPropertyDescriptor(
    window.HTMLTextAreaElement.prototype, 'value'
  )?.set;
  const nativeSelectSetter = Object.getOwnPropertyDescriptor(
    window.HTMLSelectElement.prototype, 'value'
  )?.set;

  function setNativeValue(el, value) {
    if (el.tagName === 'TEXTAREA' && nativeTextareaSetter) {
      nativeTextareaSetter.call(el, value);
    } else if (el.tagName === 'SELECT' && nativeSelectSetter) {
      nativeSelectSetter.call(el, value);
    } else if (nativeInputSetter) {
      nativeInputSetter.call(el, value);
    } else {
      el.value = value;
    }
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new Event('blur', { bubbles: true }));
  }

  // -------------------------------------------------------------------------
  // ENHANCED LABEL DETECTION
  // -------------------------------------------------------------------------
  // Walk up the DOM tree to find the label/question text for any form element.
  // Handles: native labels, aria-label, parent containers with text, preceding
  // siblings, Greenhouse/Ashby wrapper divs, etc.
  function getFieldLabel(el) {
    // 1. aria-label directly on element
    const ariaLabel = el.getAttribute('aria-label');
    if (ariaLabel && ariaLabel.length > 1) return ariaLabel.toLowerCase().trim();

    // 2. aria-labelledby reference
    const labelledBy = el.getAttribute('aria-labelledby');
    if (labelledBy) {
      const parts = labelledBy.split(/\s+/).map(id => {
        const ref = document.getElementById(id);
        return ref ? ref.textContent.trim() : '';
      }).filter(Boolean);
      if (parts.length) return parts.join(' ').toLowerCase().trim();
    }

    // 3. Associated <label for="id">
    const id = el.id;
    if (id) {
      const label = document.querySelector(`label[for="${CSS.escape(id)}"]`);
      if (label) return label.textContent.toLowerCase().trim();
    }

    // 4. Parent <label> wrapping the element
    const parentLabel = el.closest('label');
    if (parentLabel) return parentLabel.textContent.toLowerCase().trim();

    // 5. Greenhouse/Ashby pattern: sibling or parent div with label text
    //    Structure: <div class="field-wrapper">
    //                 <div class="label">Label Text</div>
    //                 <div class="input-wrapper"><input/></div>
    //               </div>
    const container = el.closest('[class*="field"], [class*="group"], [class*="question"], fieldset, [role="group"]');
    if (container) {
      // Find label-like element that is NOT inside the input area
      const labelCandidates = container.querySelectorAll('label, legend, [class*="label"]:not([class*="error"]), [class*="Label"]:not([class*="Error"])');
      for (const lc of labelCandidates) {
        if (!lc.contains(el) && lc.textContent.trim().length > 1 && lc.textContent.trim().length < 200) {
          return lc.textContent.toLowerCase().trim();
        }
      }
      // Also check direct child div/span text before the input
      for (const child of container.children) {
        if (child === el || child.contains(el)) break;
        const text = child.textContent.trim();
        if (text.length > 1 && text.length < 200 && !child.querySelector('input, textarea, select')) {
          return text.toLowerCase().trim();
        }
      }
    }

    // 6. placeholder attribute
    const placeholder = el.getAttribute('placeholder');
    if (placeholder) return placeholder.toLowerCase().trim();

    // 7. name attribute (fallback)
    const name = el.getAttribute('name');
    if (name) return name.toLowerCase().replace(/[_\[\]]/g, ' ').trim();

    // 8. Preceding sibling text
    const prev = el.previousElementSibling;
    if (prev && (prev.tagName === 'LABEL' || prev.tagName === 'SPAN' || prev.tagName === 'DIV')) {
      const text = prev.textContent.trim();
      if (text.length > 1 && text.length < 200) return text.toLowerCase().trim();
    }

    // 9. data-testid or data-qa
    const testId = el.getAttribute('data-testid') || el.getAttribute('data-qa');
    if (testId) return testId.toLowerCase().replace(/[-_]/g, ' ').trim();

    return '';
  }

  function getFieldContext(el) {
    // Walk up to find the broadest container with question/context text
    const containers = [
      el.closest('[class*="field"], [class*="group"], [class*="question"], fieldset, [role="group"]'),
      el.closest('[class*="section"], [class*="block"]'),
    ].filter(Boolean);

    for (const container of containers) {
      const heading = container.querySelector('h1, h2, h3, h4, h5, h6, label, legend, [class*="label"], [class*="title"]');
      if (heading && heading.textContent.trim().length < 300) {
        return heading.textContent.toLowerCase().trim();
      }
    }
    return '';
  }

  // Get text from ALL label-like elements in the container (for question text that spans multiple elements)
  function getFullQuestionText(el) {
    const container = el.closest('[class*="field"], [class*="group"], [class*="question"], fieldset, [role="group"]');
    if (!container) return '';
    const texts = [];
    for (const child of container.children) {
      if (child === el || child.contains(el)) break;
      const text = child.textContent.trim();
      if (text.length > 1 && !child.querySelector('input, textarea, select, [role="combobox"]')) {
        texts.push(text);
      }
    }
    return texts.join(' ').toLowerCase().trim();
  }

  // -------------------------------------------------------------------------
  // FIELD MATCHING — maps label patterns to profile values
  // -------------------------------------------------------------------------
  const FIELD_MATCHERS = [
    // Name fields
    { patterns: [/^first[\s_-]*name/, /given[\s_-]*name/, /^first$/], value: () => PROFILE.firstName },
    { patterns: [/^last[\s_-]*name/, /family[\s_-]*name/, /surname/, /^last$/], value: () => PROFILE.lastName },
    { patterns: [/^full[\s_-]*name/, /^name\*?$/, /^your[\s_-]*name/, /^candidate[\s_-]*name/], value: () => PROFILE.fullName },

    // Contact
    { patterns: [/e[\s_-]*mail/, /email[\s_-]*address/], value: () => PROFILE.email },
    { patterns: [/phone\*?$/, /mobile/, /cell/, /telephone/, /contact[\s_-]*number/, /phone[\s_-]*number/], value: () => PROFILE.phoneLocal },

    // LinkedIn
    { patterns: [/linkedin/, /linked[\s_-]*in/], value: () => PROFILE.linkedin },

    // Website / portfolio / GitHub
    { patterns: [/^website/, /portfolio/, /personal[\s_-]*url/, /personal[\s_-]*site/], value: () => PROFILE.website || '' },
    { patterns: [/github/, /git[\s_-]*hub/], value: () => PROFILE.github || '' },

    // Location / address
    { patterns: [/^city\*?$/, /current[\s_-]*city/], value: () => PROFILE.city },
    { patterns: [/^state\*?$/, /^province$/], value: () => PROFILE.state },
    { patterns: [/^zip/, /postal[\s_-]*code/], value: () => PROFILE.zip },
    { patterns: [/^country\*?$/], value: () => PROFILE.country },
    { patterns: [/address.*(?:work|plan|commut)/, /where.*plan.*work/], value: () => PROFILE.fullAddress },
    { patterns: [/^location/, /current[\s_-]*location/, /where.*located/], value: () => PROFILE.location },
    { patterns: [/^address/], value: () => PROFILE.fullAddress },

    // Current role
    { patterns: [/current[\s_-]*title/, /job[\s_-]*title/, /current[\s_-]*role/, /most[\s_-]*recent[\s_-]*title/], value: () => PROFILE.currentTitle },
    { patterns: [/current[\s_-]*company/, /current[\s_-]*employer/, /most[\s_-]*recent[\s_-]*company/, /company[\s_-]*name/], value: () => PROFILE.currentCompany },

    // Experience
    { patterns: [/years[\s_-]*(?:of[\s_-]*)?experience/, /total[\s_-]*experience/, /how[\s_-]*many[\s_-]*years/], value: () => PROFILE.yearsExperience },

    // Education
    { patterns: [/school/, /university/, /college/, /alma[\s_-]*mater/, /institution/], value: () => PROFILE.school1 },
    { patterns: [/degree/, /education[\s_-]*level/, /highest[\s_-]*degree/], value: () => PROFILE.degree1 },
    { patterns: [/graduation[\s_-]*year/, /grad[\s_-]*year/], value: () => PROFILE.gradYear1 },

    // Salary
    { patterns: [/salary/, /compensation/, /pay[\s_-]*expect/, /desired[\s_-]*(?:salary|pay|compensation)/, /expected[\s_-]*(?:salary|pay|compensation)/], value: () => PROFILE.salaryRange },

    // Start date / availability
    { patterns: [/(?:earliest|when).*(?:start|want to start|begin|join)/, /start[\s_-]*date/, /available[\s_-]*(?:start|date)/, /when[\s_-]*can[\s_-]*you[\s_-]*start/, /date[\s_-]*available/], value: () => PROFILE.startDate },

    // Deadline / timeline
    { patterns: [/deadline/, /timeline[\s_-]*consideration/, /time[\s_-]*(?:constraint|sensitive)/], value: () => PROFILE.deadlineNote },

    // How did you hear
    { patterns: [/how[\s_-]*(?:did[\s_-]*you[\s_-]*)?hear/, /referral[\s_-]*source/, /where[\s_-]*(?:did[\s_-]*you[\s_-]*)?(?:hear|find|learn|discover)/, /how.*find.*(?:us|position|role|job)/], value: () => PROFILE.howHeard },

    // Pronounce name
    { patterns: [/pronounce.*name/, /pronunciation/], value: () => `${PROFILE.fullName}` }, // CUSTOMIZE: add pronunciation guide if needed

    // Personal preferences (optional)
    { patterns: [/personal[\s_-]*preference/, /pronoun/], value: () => 'he/him' },
  ];

  // -------------------------------------------------------------------------
  // YES/NO & SELECT FIELD MATCHING
  // -------------------------------------------------------------------------
  const YES_NO_MATCHERS = [
    // Work authorization — YES
    { patterns: [/authorized[\s_-]*to[\s_-]*work/, /legally[\s_-]*authorized/, /legal[\s_-]*right[\s_-]*to[\s_-]*work/, /eligible[\s_-]*to[\s_-]*work/, /right[\s_-]*to[\s_-]*work/], answer: 'yes' },

    // Sponsorship needed — YES
    { patterns: [/require[\s_-]*(?:visa[\s_-]*)?sponsorship/, /need[\s_-]*(?:visa[\s_-]*)?sponsorship/, /immigration[\s_-]*sponsorship/, /will[\s_-]*you[\s_-]*(?:now[\s_-]*or[\s_-]*in[\s_-]*the[\s_-]*future[\s_-]*)?require[\s_-]*(?:sponsorship|visa|employment visa)/, /visa[\s_-]*sponsorship/], answer: 'yes' },

    // Relocation — YES
    { patterns: [/(?:willing|open)[\s_-]*to[\s_-]*relocat/, /relocat/], answer: 'yes' },

    // In-person / office / on-site — YES
    { patterns: [/(?:comfortable|willing|able|open)[\s_-]*(?:to[\s_-]*)?(?:work|working)[\s_-]*(?:in[\s_-]*)?(?:person|office|on[\s_-]*site|hybrid)/, /office[\s_-]*\d+/, /\d+[\s_-]*(?:%|percent|days).*(?:office|on[\s_-]*site|in[\s_-]*person)/, /in[\s_-]*person.*\d+[\s_-]*(?:%|percent)/, /25%[\s_-]*of[\s_-]*the[\s_-]*time/], answer: 'yes' },

    // Remote work — YES
    { patterns: [/(?:able|willing)[\s_-]*to[\s_-]*work[\s_-]*(?:remote|from[\s_-]*home)/], answer: 'yes' },

    // Background check — YES
    { patterns: [/background[\s_-]*check/, /consent[\s_-]*to[\s_-]*background/], answer: 'yes' },

    // 18+ — YES
    { patterns: [/(?:are[\s_-]*you[\s_-]*)?(?:at[\s_-]*least[\s_-]*)?18[\s_-]*(?:years|or[\s_-]*older)/, /legal[\s_-]*age/], answer: 'yes' },

    // Drug test — YES
    { patterns: [/drug[\s_-]*(?:test|screen)/, /pre[\s_-]*employment[\s_-]*(?:test|screen)/], answer: 'yes' },

    // AI policy acknowledgment — YES
    { patterns: [/ai[\s_-]*policy/, /ai[\s_-]*(?:usage|use)[\s_-]*(?:policy|guideline)/, /candidate[\s_-]*ai/], answer: 'yes' },

    // Non-compete — NO
    { patterns: [/non[\s_-]*compete/, /non[\s_-]*solicitation/, /restrictive[\s_-]*covenant/], answer: 'no' },

    // Previously applied / interviewed — NO
    { patterns: [/previously[\s_-]*(?:applied|interview)/, /(?:applied|interview)[\s_-]*(?:before|previously)/, /have[\s_-]*you[\s_-]*(?:ever[\s_-]*)?(?:applied|interview)/], answer: 'no' },

    // Previously employed — NO
    { patterns: [/previously[\s_-]*employed/, /(?:have[\s_-]*you[\s_-]*)?(?:worked|employed)[\s_-]*(?:at|for|with)/], answer: 'no' },
  ];

  // Select/dropdown option matching
  const SELECT_MATCHERS = {
    authorization: {
      patterns: [/work[\s_-]*authorization/, /visa[\s_-]*status/, /immigration[\s_-]*status/],
      preferOptions: ['f-1', 'f1', 'opt', 'other', 'requires sponsorship', 'need sponsorship'],
      avoidOptions: ['citizen', 'permanent resident', 'green card', 'no sponsorship needed'],
    },
    gender: {
      patterns: [/gender/, /sex/],
      preferOptions: ['decline', 'prefer not', 'not to say', 'not disclose', 'choose not'],
    },
    race: {
      patterns: [/race/, /ethnicity/, /ethnic/, /hispanic/],
      preferOptions: ['decline', 'prefer not', 'not to say', 'not disclose', 'choose not'],
    },
    veteran: {
      patterns: [/veteran/],
      preferOptions: ['not a protected veteran', 'i am not', 'no', 'decline', 'prefer not'],
    },
    disability: {
      patterns: [/disability/, /disabled/],
      preferOptions: ['do not wish to answer', 'do not want to answer', 'decline', 'prefer not', 'no, i do not', 'no, i don'],
    },
    country: {
      patterns: [/^country\*?$/],
      preferOptions: ['united states', 'us', 'usa', 'u.s.'],
    },
    state: {
      patterns: [/^state\*?$/, /^province$/],
      preferOptions: ['illinois', 'il'],
    },
    heardAbout: {
      patterns: [/how[\s_-]*(?:did[\s_-]*you[\s_-]*)?hear/, /source/],
      preferOptions: ['company website', 'career page', 'careers page', 'website', 'other', 'job board'],
    },
    degree: {
      patterns: [/degree/, /education[\s_-]*level/],
      preferOptions: ["master", "master's", "ms", "m.s.", "graduate"],
    },
  };

  // -------------------------------------------------------------------------
  // CHECKBOX MATCHING
  // -------------------------------------------------------------------------
  const CHECKBOX_MATCHERS = [
    { patterns: [/agree/, /terms/, /privacy/, /consent/, /acknowledge/], check: true },
    { patterns: [/subscribe/, /newsletter/, /marketing/, /promotional/], check: false },
  ];

  // -------------------------------------------------------------------------
  // RESULTS OBJECT
  // -------------------------------------------------------------------------
  const results = {
    ats: 'unknown',
    url: window.location.href,
    totalFields: 0,
    filled: [],
    skipped: [],
    customQuestions: [],
    errors: [],
    fileUploadFound: false,
    fileUploadSelectors: [],
    submitButtonRef: null,
    // NEW: list of combobox/dropdown fields that need Playwright interaction
    comboboxFields: [],
  };

  // -------------------------------------------------------------------------
  // CORE FILL FUNCTIONS
  // -------------------------------------------------------------------------
  function fillTextField(el, label, context) {
    const combined = (label + ' ' + context).trim();
    for (const matcher of FIELD_MATCHERS) {
      for (const pattern of matcher.patterns) {
        if (pattern.test(label) || pattern.test(combined)) {
          const value = matcher.value();
          if (value === undefined || value === null) continue;
          // Don't overwrite non-empty values
          if (el.value && el.value.trim() !== '' && el.value !== value) {
            results.skipped.push({ field: label, reason: 'already filled with different value', currentValue: el.value.substring(0, 50) });
            return true;
          }
          if (el.value === value) {
            results.skipped.push({ field: label, reason: 'already filled' });
            return true;
          }
          if (value === '') {
            // Matched but value is empty (e.g., no github) — skip silently
            results.skipped.push({ field: label, reason: 'matched but no value configured' });
            return true;
          }
          setNativeValue(el, value);
          results.filled.push({ field: label, value: value.substring(0, 80), ref: el.id || el.name || '' });
          return true;
        }
      }
    }
    return false;
  }

  function fillSelectField(el, label, context) {
    const options = Array.from(el.options).map((opt, i) => ({
      index: i,
      value: opt.value,
      text: opt.textContent.toLowerCase().trim(),
    }));

    // Try select matchers
    for (const [, matcher] of Object.entries(SELECT_MATCHERS)) {
      const combined = label + ' ' + context;
      if (!matcher.patterns.some(p => p.test(label) || p.test(combined))) continue;

      for (const preferred of matcher.preferOptions) {
        const match = options.find(opt => opt.text.includes(preferred));
        if (match) {
          el.selectedIndex = match.index;
          setNativeValue(el, match.value);
          results.filled.push({ field: label, value: match.text, ref: el.id || el.name || '' });
          return true;
        }
      }

      if (matcher.avoidOptions) {
        const safeOptions = options.filter(opt =>
          !matcher.avoidOptions.some(avoid => opt.text.includes(avoid)) &&
          opt.value !== '' && opt.text !== '' && !opt.text.includes('select')
        );
        if (safeOptions.length > 0) {
          const pick = safeOptions[safeOptions.length - 1];
          el.selectedIndex = pick.index;
          setNativeValue(el, pick.value);
          results.filled.push({ field: label, value: pick.text, ref: el.id || el.name || '' });
          return true;
        }
      }
    }

    // For yes/no selects
    const yesNoOptions = options.filter(o => o.text === 'yes' || o.text === 'no');
    if (yesNoOptions.length >= 2) {
      for (const matcher of YES_NO_MATCHERS) {
        const combined = label + ' ' + context;
        for (const pattern of matcher.patterns) {
          if (pattern.test(label) || pattern.test(combined)) {
            const pick = options.find(o => o.text === matcher.answer);
            if (pick) {
              el.selectedIndex = pick.index;
              setNativeValue(el, pick.value);
              results.filled.push({ field: label, value: pick.text, ref: el.id || el.name || '' });
              return true;
            }
          }
        }
      }
    }

    return false;
  }

  function fillRadioGroup(radios, label, context) {
    const options = radios.map(r => ({
      el: r,
      value: r.value.toLowerCase(),
      text: (getFieldLabel(r) || r.value).toLowerCase(),
    }));

    for (const matcher of YES_NO_MATCHERS) {
      const combined = label + ' ' + context;
      for (const pattern of matcher.patterns) {
        if (pattern.test(label) || pattern.test(combined)) {
          const pick = options.find(o => o.text.includes(matcher.answer) || o.value === matcher.answer);
          if (pick) {
            pick.el.checked = true;
            pick.el.dispatchEvent(new Event('change', { bubbles: true }));
            pick.el.dispatchEvent(new Event('click', { bubbles: true }));
            results.filled.push({ field: label, value: matcher.answer, ref: pick.el.id || pick.el.name || '' });
            return true;
          }
        }
      }
    }

    for (const [, matcher] of Object.entries(SELECT_MATCHERS)) {
      const combined = label + ' ' + context;
      if (!matcher.patterns.some(p => p.test(label) || p.test(combined))) continue;

      for (const preferred of matcher.preferOptions) {
        const pick = options.find(o => o.text.includes(preferred) || o.value.includes(preferred));
        if (pick) {
          pick.el.checked = true;
          pick.el.dispatchEvent(new Event('change', { bubbles: true }));
          pick.el.dispatchEvent(new Event('click', { bubbles: true }));
          results.filled.push({ field: label, value: pick.text, ref: pick.el.id || pick.el.name || '' });
          return true;
        }
      }
    }

    return false;
  }

  function fillCheckbox(el, label, context) {
    for (const matcher of CHECKBOX_MATCHERS) {
      const combined = label + ' ' + context;
      for (const pattern of matcher.patterns) {
        if (pattern.test(label) || pattern.test(combined)) {
          if (el.checked !== matcher.check) {
            el.checked = matcher.check;
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.dispatchEvent(new Event('click', { bubbles: true }));
          }
          results.filled.push({ field: label, value: matcher.check ? 'checked' : 'unchecked', ref: el.id || el.name || '' });
          return true;
        }
      }
    }
    return false;
  }

  // -------------------------------------------------------------------------
  // CUSTOM QUESTION DETECTION
  // -------------------------------------------------------------------------
  function isCustomQuestion(label, context) {
    const combined = label + ' ' + context;
    const customPatterns = [
      /why[\s_-]*(?:do[\s_-]*you[\s_-]*want|are[\s_-]*you[\s_-]*interested|this[\s_-]*(?:role|position|company)|anthropic|openai|perplexity|scale|google)/,
      /tell[\s_-]*us[\s_-]*(?:about|why)/,
      /what[\s_-]*(?:excites|interests|motivates|draws)/,
      /describe[\s_-]*(?:your|a[\s_-]*time|a[\s_-]*project|an[\s_-]*experience)/,
      /cover[\s_-]*letter/,
      /additional[\s_-]*(?:info|information|comments|notes)/,
      /anything[\s_-]*else.*share/,
      /essay/,
      /what[\s_-]*(?:is|are)[\s_-]*your[\s_-]*(?:greatest|biggest|most[\s_-]*significant)/,
      /what[\s_-]*makes[\s_-]*you/,
      /how[\s_-]*would[\s_-]*you[\s_-]*(?:approach|solve|handle|improve)/,
      /what[\s_-]*(?:project|achievement|accomplishment)/,
      /research[\s_-]*(?:interest|direction|area)/,
      /technical[\s_-]*(?:challenge|problem)/,
      /exceptional[\s_-]*ability/,
    ];
    return customPatterns.some(p => p.test(combined));
  }

  function isLongTextField(el) {
    if (el.tagName === 'TEXTAREA') return true;
    if (el.getAttribute('type') === 'hidden') return false;
    const minLength = parseInt(el.getAttribute('minlength') || '0');
    if (minLength > 100) return true;
    const role = el.getAttribute('role');
    if (role === 'textbox' && el.getAttribute('contenteditable') === 'true') return true;
    return false;
  }

  // -------------------------------------------------------------------------
  // COMBOBOX / CUSTOM DROPDOWN DETECTION
  // -------------------------------------------------------------------------
  // Modern ATS (Greenhouse, Ashby) use React combobox components.
  // These CANNOT be filled with JS alone — they need Playwright click/type.
  // This function detects them and returns instructions for the agent.
  function detectComboboxFields() {
    const comboboxes = document.querySelectorAll('[role="combobox"], input[aria-haspopup="listbox"]');

    comboboxes.forEach(cb => {
      const label = getFieldLabel(cb) || getFieldContext(cb) || getFullQuestionText(cb);
      if (!label) return;

      // Skip if already filled (check if there's a selection shown)
      const container = cb.closest('[class*="field"], [class*="group"], [class*="question"], fieldset, [role="group"]');
      const hasSelection = container && (
        container.querySelector('[class*="singleValue"], [class*="selected"], [class*="chip"], [class*="tag"]') ||
        (cb.value && cb.value.trim() !== '' && cb.value.toLowerCase() !== 'select...')
      );

      // Check for "Clear selections" button — means something is already selected
      const clearBtn = container && container.querySelector('button[class*="clear"], [aria-label*="clear"], [aria-label*="Clear"]');
      if (clearBtn) {
        results.skipped.push({ field: label, reason: 'combobox already has selection' });
        return;
      }

      if (hasSelection) {
        results.skipped.push({ field: label, reason: 'combobox already has selection' });
        return;
      }

      // Determine what value this combobox should have
      let targetValue = null;
      let matchType = 'unknown';

      // Check YES_NO_MATCHERS
      for (const matcher of YES_NO_MATCHERS) {
        const combined = label;
        for (const pattern of matcher.patterns) {
          if (pattern.test(combined)) {
            targetValue = matcher.answer.charAt(0).toUpperCase() + matcher.answer.slice(1); // "Yes" or "No"
            matchType = 'yes_no';
            break;
          }
        }
        if (targetValue) break;
      }

      // Check SELECT_MATCHERS
      if (!targetValue) {
        for (const [key, matcher] of Object.entries(SELECT_MATCHERS)) {
          const combined = label;
          if (matcher.patterns.some(p => p.test(combined))) {
            targetValue = matcher.preferOptions[0]; // First preferred option
            matchType = key;
            break;
          }
        }
      }

      // Determine the element's aria ref or a unique selector for the agent
      const ariaRef = cb.getAttribute('aria-ref') || cb.id || '';
      const selector = cb.id ? `#${CSS.escape(cb.id)}` :
                       cb.getAttribute('name') ? `[name="${CSS.escape(cb.getAttribute('name'))}"]` :
                       cb.getAttribute('aria-label') ? `[aria-label="${CSS.escape(cb.getAttribute('aria-label'))}"]` :
                       '';

      results.comboboxFields.push({
        field: label,
        targetValue: targetValue,
        matchType: matchType,
        ariaRef: ariaRef,
        selector: selector,
        // Instructions for the agent:
        instruction: targetValue
          ? `Click combobox, type "${targetValue}", then press Enter to select`
          : `Custom dropdown — needs manual selection`,
      });
    });
  }

  // -------------------------------------------------------------------------
  // FILE UPLOAD DETECTION
  // -------------------------------------------------------------------------
  function detectFileUploads() {
    // Native file inputs
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(fi => {
      results.fileUploadFound = true;
      const label = getFieldLabel(fi) || 'file upload';
      results.fileUploadSelectors.push({
        label: label,
        selector: fi.id ? `#${CSS.escape(fi.id)}` : 'input[type="file"]',
        ref: fi.id || '',
      });
    });

    // Greenhouse/Ashby button-based uploads (no visible input[type=file])
    const uploadButtons = document.querySelectorAll('button');
    uploadButtons.forEach(btn => {
      const text = btn.textContent.toLowerCase().trim();
      if (text === 'attach' || text === 'upload' || text === 'upload resume' || text === 'choose file') {
        const group = btn.closest('[class*="field"], [class*="group"], fieldset, [role="group"]');
        const label = group ? getFieldLabel(group) || '' : '';
        if (/resume|cv|cover/i.test(label) || /resume|cv|cover/i.test(text)) {
          results.fileUploadFound = true;
          results.fileUploadSelectors.push({
            label: label || text,
            type: 'button-trigger',
            buttonText: text,
            note: 'Use browser upload action with ref, not click',
          });
        }
      }
    });

    // Check if resume is already uploaded (file name shown)
    const uploadedIndicators = document.querySelectorAll('[class*="file-name"], [class*="fileName"], [class*="uploaded"]');
    uploadedIndicators.forEach(ind => {
      const text = ind.textContent.trim();
      if (text && text.length > 3 && /\.(pdf|doc|docx|txt|rtf)$/i.test(text)) {
        results.fileUploadFound = true;
        const group = ind.closest('[class*="field"], [class*="group"], fieldset, [role="group"]');
        const label = group ? getFieldLabel(group) || 'resume' : 'resume';
        results.skipped.push({ field: label, reason: 'file already uploaded: ' + text });
      }
    });

    // Greenhouse specific: check for "Remove file" button (means file is already uploaded)
    const removeButtons = document.querySelectorAll('button');
    removeButtons.forEach(btn => {
      const text = btn.textContent.toLowerCase().trim();
      const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
      if (text === 'remove file' || ariaLabel === 'remove file' || text.includes('remove')) {
        const group = btn.closest('[class*="field"], [class*="group"], fieldset, [role="group"]');
        if (group) {
          const label = getFieldLabel(group) || 'file';
          // File is already uploaded
          const fileName = group.querySelector('p, span');
          if (fileName) {
            results.skipped.push({ field: label, reason: 'file already uploaded: ' + fileName.textContent.trim() });
          }
        }
      }
    });
  }

  // -------------------------------------------------------------------------
  // ASHBY TOGGLE BUTTON HANDLER
  // -------------------------------------------------------------------------
  function simulateRealClick(el) {
    const rect = el.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const eventInit = { bubbles: true, cancelable: true, view: window, clientX: cx, clientY: cy };

    el.dispatchEvent(new PointerEvent('pointerdown', { ...eventInit, pointerId: 1, pointerType: 'mouse' }));
    el.dispatchEvent(new MouseEvent('mousedown', eventInit));
    el.dispatchEvent(new PointerEvent('pointerup', { ...eventInit, pointerId: 1, pointerType: 'mouse' }));
    el.dispatchEvent(new MouseEvent('mouseup', eventInit));
    el.dispatchEvent(new MouseEvent('click', eventInit));
    el.focus();
    el.dispatchEvent(new FocusEvent('focus', { bubbles: true }));
  }

  function fillAshbyToggleButtons() {
    const allButtons = document.querySelectorAll('button[aria-pressed], [role="radio"], [role="option"]');
    const processedGroups = new Set();

    allButtons.forEach(btn => {
      const group = btn.parentElement;
      if (!group || processedGroups.has(group)) return;

      const siblings = Array.from(group.querySelectorAll('button[aria-pressed], [role="radio"], [role="option"]'));
      if (siblings.length < 2) return;

      const texts = siblings.map(s => s.textContent.trim().toLowerCase());
      if (!texts.includes('yes') || !texts.includes('no')) return;

      processedGroups.add(group);

      const container = group.closest('[class*="field"], [class*="question"], [class*="form"], [class*="group"], fieldset') || group.parentElement;
      let questionLabel = '';
      if (container) {
        const labelEl = container.querySelector('label, [class*="label"], [class*="title"], legend, h3, h4, h5, p');
        if (labelEl && !group.contains(labelEl)) {
          questionLabel = labelEl.textContent.toLowerCase().trim();
        }
      }

      const radioGroup = group.closest('[role="radiogroup"]') || group;
      const ariaLabel = radioGroup.getAttribute('aria-label') || radioGroup.getAttribute('aria-labelledby');
      if (ariaLabel && !questionLabel) {
        const labelledBy = document.getElementById(ariaLabel);
        questionLabel = labelledBy ? labelledBy.textContent.toLowerCase().trim() : ariaLabel.toLowerCase().trim();
      }

      if (!questionLabel) return;
      if (results.filled.some(f => f.field === questionLabel)) return;

      let matched = false;
      for (const matcher of YES_NO_MATCHERS) {
        for (const pattern of matcher.patterns) {
          if (pattern.test(questionLabel)) {
            const targetBtn = siblings.find(s => s.textContent.trim().toLowerCase() === matcher.answer);
            if (targetBtn) {
              const alreadySelected = targetBtn.getAttribute('aria-pressed') === 'true' ||
                                       targetBtn.getAttribute('aria-checked') === 'true';
              if (!alreadySelected) {
                simulateRealClick(targetBtn);
              }
              results.filled.push({
                field: questionLabel,
                value: matcher.answer,
                ref: targetBtn.id || 'ashby-toggle',
                method: 'ashby-toggle-click',
                note: 'Verify visually — React state may not persist from JS click',
              });
              matched = true;
            }
            break;
          }
        }
        if (matched) break;
      }

      if (!matched) {
        results.skipped.push({
          field: questionLabel,
          reason: 'ashby toggle — no matching pattern',
          type: 'ashby-toggle',
          options: texts,
        });
      }
    });
  }

  // -------------------------------------------------------------------------
  // GENERIC FIELD FILLER (works on any ATS)
  // -------------------------------------------------------------------------
  function fillAllNativeFields() {
    const inputs = document.querySelectorAll(
      'input:not([type="hidden"]):not([type="file"]):not([type="submit"]):not([type="button"]):not([type="image"]), textarea, select'
    );
    const processedRadioGroups = new Set();

    inputs.forEach(el => {
      // Skip invisible elements (but not off-screen ones used by some ATS)
      if (!el.offsetParent && !el.closest('[role="group"]') && el.type !== 'hidden') return;
      results.totalFields++;

      const label = getFieldLabel(el);
      const context = getFieldContext(el);

      // Skip combobox inputs — handled separately
      if (el.getAttribute('role') === 'combobox' || el.getAttribute('aria-haspopup') === 'listbox') {
        return;
      }

      // Skip if already filled by previous logic
      if (results.filled.some(f => f.ref === (el.id || el.name) && f.ref !== '')) return;

      // Radio buttons
      if (el.type === 'radio') {
        const name = el.name;
        if (processedRadioGroups.has(name)) return;
        processedRadioGroups.add(name);
        const radios = Array.from(document.querySelectorAll(`input[type="radio"][name="${CSS.escape(name)}"]`));
        if (!fillRadioGroup(radios, label, context)) {
          if (isCustomQuestion(label, context)) {
            results.customQuestions.push({
              field: label,
              context: context,
              type: 'radio',
              options: radios.map(r => ({ value: r.value, label: getFieldLabel(r) || r.value })),
            });
          } else {
            results.skipped.push({ field: label, reason: 'no matching radio option', context: context });
          }
        }
        return;
      }

      // Checkboxes
      if (el.type === 'checkbox') {
        if (!fillCheckbox(el, label, context)) {
          results.skipped.push({ field: label || '(checkbox)', reason: 'unknown checkbox' });
        }
        return;
      }

      // Native select dropdowns
      if (el.tagName === 'SELECT') {
        if (!fillSelectField(el, label, context)) {
          const options = Array.from(el.options).map(o => o.textContent.trim()).filter(Boolean);
          if (isCustomQuestion(label, context)) {
            results.customQuestions.push({ field: label, context: context, type: 'select', options: options });
          } else {
            results.skipped.push({ field: label, reason: 'no matching select option', options: options.slice(0, 10) });
          }
        }
        return;
      }

      // Date fields
      if (el.type === 'date') {
        const combined = label + ' ' + context;
        if (/start|available|earliest|begin|join/.test(combined)) {
          setNativeValue(el, PROFILE.startDateISO);
          results.filled.push({ field: label, value: PROFILE.startDateISO, ref: el.id || el.name || '' });
          return;
        }
      }

      // Text inputs and textareas
      // Skip if already has value
      if (el.value && el.value.trim() !== '') {
        results.skipped.push({ field: label || '(has value)', reason: 'already filled', currentValue: el.value.substring(0, 50) });
        return;
      }

      // Check if custom question (long text / essay)
      if (isCustomQuestion(label, context) || (el.tagName === 'TEXTAREA' && !fillTextField(el, label, context))) {
        if (el.tagName === 'TEXTAREA') {
          results.customQuestions.push({
            field: label || context || '(essay)',
            context: getFullQuestionText(el) || context,
            type: 'textarea',
            maxLength: el.getAttribute('maxlength') || '',
            placeholder: el.getAttribute('placeholder') || '',
            selector: el.id ? `#${CSS.escape(el.id)}` : (el.name ? `[name="${CSS.escape(el.name)}"]` : ''),
          });
          return;
        }
        // For regular inputs detected as custom questions
        if (isCustomQuestion(label, context)) {
          // But first try to fill with matchers (e.g., "start date" matches both custom and fill)
          if (!fillTextField(el, label, context)) {
            results.customQuestions.push({
              field: label || context,
              context: getFullQuestionText(el) || context,
              type: 'text',
              placeholder: el.getAttribute('placeholder') || '',
              selector: el.id ? `#${CSS.escape(el.id)}` : (el.name ? `[name="${CSS.escape(el.name)}"]` : ''),
            });
          }
          return;
        }
      }

      // Try to fill with text matchers
      if (!fillTextField(el, label, context)) {
        if (label) {
          results.skipped.push({ field: label, reason: 'no matcher found', context: context.substring(0, 80) });
        }
      }
    });
  }

  // -------------------------------------------------------------------------
  // FIND SUBMIT BUTTON
  // -------------------------------------------------------------------------
  function findSubmitButton() {
    const candidates = [
      ...document.querySelectorAll('button[type="submit"]'),
      ...document.querySelectorAll('input[type="submit"]'),
    ];

    for (const btn of candidates) {
      const text = (btn.textContent || btn.value || '').toLowerCase();
      if (/submit|apply|send/.test(text)) {
        results.submitButtonRef = btn.id || btn.getAttribute('aria-label') || text.trim();
        results.submitButtonDisabled = btn.disabled;
        return;
      }
    }

    // Fallback: any button with submit-like text
    const allButtons = document.querySelectorAll('button, [role="button"]');
    for (const btn of allButtons) {
      const text = (btn.textContent || '').toLowerCase().trim();
      if (/^submit[\s_-]*application$|^apply[\s_-]*(?:now|for|to)?$|^send[\s_-]*application$/.test(text)) {
        results.submitButtonRef = btn.id || btn.getAttribute('aria-label') || text;
        results.submitButtonDisabled = btn.disabled;
        return;
      }
    }
  }

  // -------------------------------------------------------------------------
  // IFRAME DETECTION
  // -------------------------------------------------------------------------
  const KNOWN_ATS_HOSTS = [
    'boards.greenhouse.io', 'job-boards.greenhouse.io',
    'jobs.ashbyhq.com',
    'jobs.lever.co',
    'jobs.smartrecruiters.com',
  ];

  function detectATSIframe() {
    const iframes = document.querySelectorAll('iframe');
    for (const iframe of iframes) {
      const src = iframe.src || iframe.getAttribute('src') || '';
      try {
        const url = new URL(src, window.location.href);
        const host = url.hostname.toLowerCase();
        for (const atsHost of KNOWN_ATS_HOSTS) {
          if (host === atsHost || host.endsWith('.' + atsHost)) {
            return {
              found: true,
              url: src,
              host: atsHost,
              ats: host.includes('greenhouse') ? 'greenhouse' : host.includes('ashby') ? 'ashby' : host.includes('lever') ? 'lever' : 'unknown',
            };
          }
        }
      } catch (e) { /* skip invalid URLs */ }
    }
    return { found: false };
  }

  // -------------------------------------------------------------------------
  // MAIN EXECUTION
  // -------------------------------------------------------------------------
  try {
    results.ats = detectATS();

    // Check for cross-origin iframe (company career page wrapping ATS)
    if (results.ats === 'unknown') {
      const iframeInfo = detectATSIframe();
      if (iframeInfo.found) {
        results.iframeDetected = true;
        results.iframeUrl = iframeInfo.url;
        results.iframeAts = iframeInfo.ats;
        results.summary = {
          ats: 'iframe-redirect',
          iframeUrl: iframeInfo.url,
          iframeAts: iframeInfo.ats,
          message: 'Form is inside a cross-origin iframe. Navigate to: ' + iframeInfo.url,
        };
        return results;
      }
    }

    // 1. Fill all native form fields (input, textarea, native select)
    fillAllNativeFields();

    // 2. Detect and catalog custom React combobox/dropdown fields
    //    These CANNOT be filled with JS — agent must use Playwright actions
    detectComboboxFields();

    // 3. Handle Ashby toggle buttons
    if (results.ats === 'ashby') {
      fillAshbyToggleButtons();
    }

    // 4. Detect file upload fields
    detectFileUploads();

    // 5. Find submit button
    findSubmitButton();

    // Summary
    results.summary = {
      ats: results.ats,
      totalFields: results.totalFields,
      filledCount: results.filled.length,
      skippedCount: results.skipped.length,
      customQuestionsCount: results.customQuestions.length,
      comboboxCount: results.comboboxFields.length,
      fileUploadFound: results.fileUploadFound,
      hasSubmitButton: !!results.submitButtonRef,
      submitDisabled: results.submitButtonDisabled || false,
      // Key insight for the agent:
      needsPlaywrightAction: results.comboboxFields.length > 0,
      message: results.comboboxFields.length > 0
        ? `Found ${results.comboboxFields.length} custom dropdown(s) that need Playwright interaction (click + type + Enter). See comboboxFields array.`
        : 'All fillable fields handled. Check customQuestions for essay/text responses needed.',
    };

  } catch (err) {
    results.errors.push({ message: err.message, stack: err.stack });
  }

  return results;
})();
