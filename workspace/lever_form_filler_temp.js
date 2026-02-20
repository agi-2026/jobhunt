(function() {
  'use strict';

  const PROFILE = {
    firstName: 'Howard',
    lastName: 'Cheng',
    fullName: 'Howard Cheng',
    email: 'cheng.howard1@gmail.com',
    phone: '+19493397424',
    phoneFormatted: '+1 (949) 339-7424',
    phonePlain: '9493397424',
    phoneDashes: '949-339-7424',
    phoneLocal: '(949) 339-7424',
    linkedin: 'https://www.linkedin.com/in/howard-cheng1',
    location: 'Chicago, IL',
    fullAddress: '340 E North Water St, Unit 4707, Chicago, IL 60611',
    city: 'Chicago',
    state: 'Illinois',
    stateAbbr: 'IL',
    zip: '60611',
    country: 'United States',
    website: '',
    github: '',
    authorized: true,
    needsSponsorship: true,
    visaStatus: 'F1-OPT',
    currentTitle: 'Staff Researcher / Technical Advisor',
    currentCompany: 'Lenovo',
    yearsExperience: '4',
    yearsExperiencePlus: '5+',
    school1: 'University of Chicago',
    degree1: 'M.S. Computer Science',
    gradYear1: '2025',
    school2: 'Northeastern University',
    degree2: 'B.S. Mathematics & Business Administration',
    gradYear2: '2022',
    salary: '180000',
    salaryFormatted: '$180,000',
    salaryRange: '$180,000 - $250,000',
    salaryRangeNegotiable: '$180,000 - $250,000 (negotiable with equity)',
    startDate: 'Immediately',
    startDateISO: (() => {
      const d = new Date();
      d.setDate(d.getDate() + 14);
      while (d.getDay() !== 1) d.setDate(d.getDate() + 1);
      return d.toISOString().split('T')[0];
    })(),
    willingToRelocate: true,
    remotePreference: 'Open to remote, hybrid, or on-site',
    gender: 'Decline to self-identify',
    race: 'Decline to self-identify',
    veteran: 'I am not a protected veteran',
    disability: 'I do not wish to answer',
    howHeard: 'Company careers page',
    referral: '',
    deadlineNote: 'Yes — my F1-OPT visa requires H-1B sponsorship. The H-1B registration window closes mid-March 2026, so timing is critical. I would greatly appreciate expedited consideration.',
  };

  function detectATS() {
    return 'lever';
  }

  const nativeInputSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
  const nativeTextareaSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
  const nativeSelectSetter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value')?.set;

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

  function getFieldLabel(el) {
    const ariaLabel = el.getAttribute('aria-label');
    if (ariaLabel && ariaLabel.length > 1) return ariaLabel.toLowerCase().trim();

    const labelledBy = el.getAttribute('aria-labelledby');
    if (labelledBy) {
      const parts = labelledBy.split(/\s+/).map(id => {
        const ref = document.getElementById(id);
        return ref ? ref.textContent.trim() : '';
      }).filter(Boolean);
      if (parts.length) return parts.join(' ').toLowerCase().trim();
    }

    const id = el.id;
    if (id) {
      const label = document.querySelector(`label[for="${CSS.escape(id)}"]`);
      if (label) return label.textContent.toLowerCase().trim();
    }

    const parentLabel = el.closest('label');
    if (parentLabel) return parentLabel.textContent.toLowerCase().trim();

    const container = el.closest('[class*="field"], [class*="group"], [class*="question"], fieldset, [role="group"], li');
    if (container) {
      const labelCandidates = container.querySelectorAll('label, legend, [class*="label"]:not([class*="error"]), [class*="Label"]:not([class*="Error"])');
      for (const lc of labelCandidates) {
        if (!lc.contains(el) && lc.textContent.trim().length > 1 && lc.textContent.trim().length < 200) {
          return lc.textContent.toLowerCase().trim();
        }
      }
      for (const child of container.children) {
        if (child === el || child.contains(el)) break;
        const text = child.textContent.trim();
        if (text.length > 1 && text.length < 200 && !child.querySelector('input, textarea, select')) {
          return text.toLowerCase().trim();
        }
      }
    }

    const placeholder = el.getAttribute('placeholder');
    if (placeholder) return placeholder.toLowerCase().trim();

    const name = el.getAttribute('name');
    if (name) return name.toLowerCase().replace(/[\[\]]/g, ' ').trim();

    const prev = el.previousElementSibling;
    if (prev && (prev.tagName === 'LABEL' || prev.tagName === 'SPAN' || prev.tagName === 'DIV')) {
      const text = prev.textContent.trim();
      if (text.length > 1 && text.length < 200) return text.toLowerCase().trim();
    }

    const testId = el.getAttribute('data-testid') || el.getAttribute('data-qa');
    if (testId) return testId.toLowerCase().replace(/[-_]/g, ' ').trim();

    return '';
  }

  function getFieldContext(el) {
    const containers = [
      el.closest('[class*="field"], [class*="group"], [class*="question"], fieldset, [role="group"], li'),
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

  function getFullQuestionText(el) {
    const container = el.closest('[class*="field"], [class*="group"], [class*="question"], fieldset, [role="group"], li');
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

  const FIELD_MATCHERS = [
    { patterns: [/^first[\s_-]*name/, /given[\s_-]*name/, /^first$/], value: () => PROFILE.firstName },
    { patterns: [/^last[\s_-]*name/, /family[\s_-]*name/, /surname/, /^last$/], value: () => PROFILE.lastName },
    { patterns: [/^full[\s_-]*name/, /^name\*?$/, /^your[\s_-]*name/, /^candidate[\s_-]*name/], value: () => PROFILE.fullName },
    { patterns: [/e[\s_-]*mail/, /email[\s_-]*address/], value: () => PROFILE.email },
    { patterns: [/phone\*?$/, /mobile/, /cell/, /telephone/, /contact[\s_-]*number/, /phone[\s_-]*number/], value: () => PROFILE.phoneLocal },
    { patterns: [/linkedin/, /linked[\s_-]*in/], value: () => PROFILE.linkedin },
    { patterns: [/^website/, /portfolio/, /personal[\s_-]*url/, /personal[\s_-]*site/], value: () => PROFILE.website || '' },
    { patterns: [/github/, /git[\s_-]*hub/], value: () => PROFILE.github || '' },
    { patterns: [/address.*(?:work|plan|commut)/, /where.*plan.*work/], value: () => PROFILE.fullAddress },
    { patterns: [/^location/, /current[\s_-]*location/, /where.*located/], value: () => PROFILE.location, needsPlaywright: true },
    { patterns: [/^address/], value: () => PROFILE.fullAddress },
    { patterns: [/current[\s_-]*title/, /job[\s_-]*title/, /current[\s_-]*role/, /most[\s_-]*recent[\s_-]*title/], value: () => PROFILE.currentTitle },
    { patterns: [/current[\s_-]*company/, /current[\s_-]*employer/, /most[\s_-]*recent[\s_-]*company/, /company[\s_-]*name/], value: () => PROFILE.currentCompany },
    { patterns: [/years[\s_-]*(?:of[\s_-]*)?experience/, /total[\s_-]*experience/, /how[\s_-]*many[\s_-]*years/], value: () => PROFILE.yearsExperience },
    { patterns: [/school/, /university/, /college/, /alma[\s_-]*mater/, /institution/], value: () => PROFILE.school1 },
    { patterns: [/degree/, /education[\s_-]*level/, /highest[\s_-]*degree/], value: () => PROFILE.degree1 },
    { patterns: [/graduation[\s_-]*year/, /grad[\s_-]*year/], value: () => PROFILE.gradYear1 },
    { patterns: [/salary/, /compensation/, /pay[\s_-]*expect/, /desired[\s_-]*(?:salary|pay|compensation)/, /expected[\s_-]*(?:salary|compensation)/], value: () => PROFILE.salaryRange },
    { patterns: [/(?:earliest|when).*(?:start|want to start|begin|join)/, /start[\s_-]*date/, /available[\s_-]*(?:start|date)/, /when[\s_-]*can[\s_-]*you[\s_-]*start/, /date[\s_-]*available/], value: () => PROFILE.startDate },
    { patterns: [/deadline/, /timeline[\s_-]*consideration/, /time[\s_-]*(?:constraint|sensitive)/], value: () => PROFILE.deadlineNote },
    { patterns: [/how[\s_-]*(?:did[\s_-]*you[\s_-]*)?hear/, /referral[\s_-]*source/, /where[\s_-]*(?:did[\s_-]*you[\s_-]*)?(?:hear|find|learn|discover)/, /how.*find.*(?:us|position|role|job)/], value: () => PROFILE.howHeard },
    { patterns: [/pronounce.*name/, /pronunciation/], value: () => 'Howard Cheng (How-erd Cheng)' },
    { patterns: [/personal[\s_-]*preference/, /pronoun/], value: () => 'he/him' },
  ];

  const YES_NO_MATCHERS = [
    { patterns: [/authorized[\s_-]*to[\s_-]*work/, /legally[\s_-]*authorized/, /legal[\s_-]*right[\s_-]*to[\s_-]*work/, /eligible[\s_-]*to[\s_-]*work/, /right[\s_-]*to[\s_-]*work/], answer: 'yes' },
    { patterns: [/require[\s_-]*(?:visa[\s_-]*)?sponsorship/, /need[\s_-]*(?:visa[\s_-]*)?sponsorship/, /immigration[\s_-]*sponsorship/, /will[\s_-]*you[\s_-]*(?:now[\s_-]*or[\s_-]*in[\s_-]*the[\s_-]*future[\s_-]*)?require[\s_-]*(?:sponsorship|visa|employment visa)/, /visa[\s_-]*sponsorship/], answer: 'yes' },
    { patterns: [/(?:willing|open)[\s_-]*to[\s_-]*relocat/, /relocat/], answer: 'yes' },
    { patterns: [/(?:comfortable|willing|able|open)[\s_-]*(?:to[\s_-]*)?(?:work|working)[\s_-]*(?:in[\s_-]*)?(?:person|office|on[\s_-]*site|hybrid)/, /office[\s_-]*\d+/, /\d+[\s_-]*(?:%|percent|days).*(?:office|on[\s_-]*site|in[\s_-]*person)/, /in[\s_-]*person.*\d+[\s_-]*(?:%|percent)/, /25%[\s_-]*of[\s_-]*the[\s_-]*time/], answer: 'yes' },
    { patterns: [/(?:able|willing)[\s_-]*to[\s_-]*work[\s_-]*(?:remote|from[\s_-]*home)/], answer: 'yes' },
    { patterns: [/background[\s_-]*check/, /consent[\s_-]*to[\s_-]*background/], answer: 'yes' },
    { patterns: [/18[\s_-]*(?:years|or[\s_-]*older)/, /legal[\s_-]*age/], answer: 'yes' },
    { patterns: [/drug[\s_-]*(?:test|screen)/, /pre[\s_-]*employment[\s_-]*(?:test|screen)/], answer: 'yes' },
    { patterns: [/ai[\s_-]*policy/, /ai[\s_-]*(?:usage|use)[\s_-]*(?:policy|guideline)/, /candidate[\s_-]*ai/], answer: 'yes' },
    { patterns: [/non[\s_-]*compete/, /non[\s_-]*solicitation/, /restrictive[\s_-]*covenant/], answer: 'no' },
    { patterns: [/previously[\s_-]*(?:applied|interview)/, /(?:applied|interview)[\s_-]*(?:before|previously)/, /have[\s_-]*you[\s_-]*(?:ever[\s_-]*)?(?:applied|interview)/], answer: 'no' },
    { patterns: [/previously[\s_-]*employed/, /(?:have[\s_-]*you[\s_-]*)?(?:worked|employed)[\s_-]*(?:at|for|with)/], answer: 'no' },
  ];

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
      kind: 'include',
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
      preferOptions: ['master', "master's", 'ms', 'm.s.', 'graduate'],
    },
  };

  const CHECKBOX_MATCHERS = [
    { patterns: [/agree/, /terms/, /privacy/, /consent/, /acknowledge/], check: true },
    { patterns: [/subscribe/, /newsletter/, /marketing/, /promotional/], check: false },
  ];

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
    comboboxFields: [],
    playwrightFields: [],
  };

  function fillTextField(el, label, context) {
    const combined = (label + ' ' + context).trim();
    for (const matcher of FIELD_MATCHERS) {
      for (const pattern of matcher.patterns) {
        if (pattern.test(label) || pattern.test(combined)) {
          const value = matcher.value();
          if (value === undefined || value === null) continue;
          if (el.value && el.value.trim() !== '' && el.value !== value) {
            results.skipped.push({ field: label, reason: 'already filled with different value', currentValue: el.value.substring(0, 50) });
            return true;
          }
          if (el.value === value) {
            results.skipped.push({ field: label, reason: 'already filled' });
            return true;
          }
          if (value === '') {
            results.skipped.push({ field: label, reason: 'matched but no value configured' });
            return true;
          }
          setNativeValue(el, value);
          results.filled.push({ field: label, value: value.substring(0, 80), ref: el.id || el.name || '' });
          if (matcher.needsPlaywright) {
            results.playwrightFields.push({
              field: label,
              value: value,
              ref: el.id || el.name || '',
              selector: el.id ? '#' + CSS.escape(el.id) : (el.name ? '[name="' + CSS.escape(el.name) + '"]' : ''),
              note: 'JS value may not persist. Use Playwright type action to re-fill.',
            });
          }
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

  function isCustomQuestion(label, context) {
    const combined = label + ' ' + context;
    const customPatterns = [
      /why[\s_-]*(?:do[\s_-]*you[\s_-]*)?want|are[\s_-]*you[\s_-]*interested|this[\s_-]*(?:role|position|company)|anthropic|openai|perplexity|scale|google/,
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

  function detectFileUploads() {
    const fileInputs = Array.from(document.querySelectorAll('input[type="file"]'));
    fileInputs.forEach((fi, idx) => {
      results.fileUploadFound = true;
      const label = getFieldLabel(fi) || 'file upload';
      let selector;
      if (fi.id) {
        selector = '#' + CSS.escape(fi.id);
      } else if (fi.name) {
        selector = 'input[type="file"][name="' + CSS.escape(fi.name) + '"]';
      } else if (fileInputs.length === 1) {
        selector = 'input[type="file"]';
      } else {
        selector = 'input[type="file"]:nth-of-type(' + (idx + 1) + ')';
      }
      results.fileUploadSelectors.push({
        label: label,
        selector: selector,
        ref: fi.id || '',
        inputElement: selector,
      });
    });

    const uploadButtons = document.querySelectorAll('button');
    uploadButtons.forEach(btn => {
      const text = btn.textContent.toLowerCase().trim();
      if (text === 'attach' || text === 'upload' || text === 'upload resume' || text === 'choose file') {
        const group = btn.closest('[class*="field"], [class*="group"], fieldset, [role="group"]');
        const label = group ? getFieldLabel(group) || '' : '';
        if (/resume|cv|cover/i.test(label) || /resume|cv|cover/i.test(text)) {
          let hiddenInput = null;
          let searchEl = btn.parentElement;
          for (let i = 0; i < 4 && searchEl && !hiddenInput; i++) {
            hiddenInput = searchEl.querySelector('input[type="file"]');
            searchEl = searchEl.parentElement;
          }
          let inputSelector = null;
          if (hiddenInput) {
            if (hiddenInput.id) {
              inputSelector = '#' + CSS.escape(hiddenInput.id);
            } else if (hiddenInput.name) {
              inputSelector = 'input[type="file"][name="' + CSS.escape(hiddenInput.name) + '"]';
            } else {
              inputSelector = 'input[type="file"]';
            }
          }
          results.fileUploadFound = true;
          results.fileUploadSelectors.push({
            label: label || text,
            type: 'button-trigger',
            buttonText: text,
            inputElement: inputSelector,
            note: inputSelector ? 'Hidden file input found.' : 'No hidden input found.',
          });
        }
      }
    });

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

    const removeButtons = document.querySelectorAll('button');
    removeButtons.forEach(btn => {
      const text = btn.textContent.toLowerCase().trim();
      const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
      if (text === 'remove file' || ariaLabel === 'remove file' || text.includes('remove')) {
        const group = btn.closest('[class*="field"], [class*="group"], fieldset, [role="group"]');
        if (group) {
          const label = getFieldLabel(group) || 'file';
          const fileName = group.querySelector('p, span');
          if (fileName) {
            results.skipped.push({ field: label, reason: 'file already uploaded: ' + fileName.textContent.trim() });
          }
        }
      }
    });
  }

  function fillAllNativeFields() {
    const inputs = document.querySelectorAll(
      'input:not([type="hidden"]):not([type="file"]):not([type="submit"]):not([type="button"]):not([type="image"]), textarea, select'
    );
    const processedRadioGroups = new Set();

    inputs.forEach(el => {
      if (!el.offsetParent && !el.closest('[role="group"]') && el.type !== 'hidden') return;
      results.totalFields++;

      const label = getFieldLabel(el);
      const context = getFieldContext(el);

      if (el.getAttribute('role') === 'combobox' || el.getAttribute('aria-haspopup') === 'listbox') {
        return;
      }

      if (results.filled.some(f => f.ref === (el.id || el.name) && f.ref !== '')) return;

      if (el.type === 'radio') {
        const name = el.name;
        if (processedRadioGroups.has(name)) return;
        processedRadioGroups.add(name);
        const radios = Array.from(document.querySelectorAll('input[type="radio"][name="' + CSS.escape(name) + '"]'));
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

      if (el.type === 'checkbox') {
        if (!fillCheckbox(el, label, context)) {
          results.skipped.push({ field: label || '(checkbox)', reason: 'unknown checkbox' });
        }
        return;
      }

      if (el.tagName === 'SELECT') {
        if (!fillSelectField(el, label, context)) {
          const options = Array.from(el.options).map(o => o.textContent.trim()).filter(Boolean);
          if (isCustomQuestion(label, context)) {
            results.customQuestions.push({ field: label, context: context, type: 'select', options: options });
          } else if (label) {
            results.skipped.push({ field: label, reason: 'no matching select option', options: options.slice(0, 10) });
          }
        }
        return;
      }

      if (el.type === 'date') {
        const combined = label + ' ' + context;
        if (/start|available|earliest|begin|join/.test(combined)) {
          setNativeValue(el, PROFILE.startDateISO);
          results.filled.push({ field: label, value: PROFILE.startDateISO, ref: el.id || el.name || '' });
          return;
        }
      }

      if (el.value && el.value.trim() !== '') {
        results.skipped.push({ field: label || '(has value)', reason: 'already filled', currentValue: el.value.substring(0, 50) });
        return;
      }

      if (isCustomQuestion(label, context) || (el.tagName === 'TEXTAREA' && !fillTextField(el, label, context))) {
        if (el.tagName === 'TEXTAREA') {
          results.customQuestions.push({
            field: label || context || '(essay)',
            context: getFullQuestionText(el) || context,
            type: 'textarea',
            maxLength: el.getAttribute('maxlength') || '',
            placeholder: el.getAttribute('placeholder') || '',
            selector: el.id ? '#' + CSS.escape(el.id) : (el.name ? '[name="' + CSS.escape(el.name) + '"]' : ''),
          });
          return;
        }
        if (isCustomQuestion(label, context)) {
          if (!fillTextField(el, label, context)) {
            results.customQuestions.push({
              field: label || context,
              context: getFullQuestionText(el) || context,
              type: 'text',
              placeholder: el.getAttribute('placeholder') || '',
              selector: el.id ? '#' + CSS.escape(el.id) : (el.name ? '[name="' + CSS.escape(el.name) + '"]' : ''),
            });
          }
          return;
        }
      }

      if (!fillTextField(el, label, context)) {
        if (label) {
          results.skipped.push({ field: label, reason: 'no matcher found', context: context.substring(0, 80) });
        }
      }
    });
  }

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
      } catch (e) {}
    }
    return { found: false };
  }

  try {
    results.ats = detectATS();

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

    fillAllNativeFields();
    detectFileUploads();
    findSubmitButton();

    results.summary = {
      ats: results.ats,
      totalFields: results.totalFields,
      totalFilled: results.filled.length,
      totalSkipped: results.skipped.length,
      customQuestionsCount: results.customQuestions.length,
      comboboxCount: results.comboboxFields.length,
      fileUploadFound: results.fileUploadFound,
      hasSubmitButton: !!results.submitButtonRef,
      submitDisabled: results.submitButtonDisabled || false,
      playwrightFieldCount: results.playwrightFields.length,
      needsPlaywrightAction: results.comboboxFields.length > 0 || results.playwrightFields.length > 0,
      message: results.playwrightFields.length > 0
        ? `${results.playwrightFields.length} field(s) need Playwright type action (see playwrightFields). JS value may not persist.`
        : 'All fillable fields handled. Check customQuestions for essay/text responses needed.',
    };

  } catch (err) {
    results.errors.push({ message: err.message, stack: err.stack });
  }

  return results;
})();