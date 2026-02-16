// ===========================================================================
// FILL CUSTOM ANSWERS — Companion to form-filler.js
// ===========================================================================
// Called AFTER AI generates answers for custom questions.
// Receives answers as a JSON string in the global __CUSTOM_ANSWERS__ variable.
//
// Usage: Set window.__CUSTOM_ANSWERS__ first via evaluate, then run this script.
// Or: Pass answers as a stringified JSON parameter.
//
// Expected format of __CUSTOM_ANSWERS__:
// [
//   { "selector": "#field_id", "value": "answer text", "type": "textarea|text|radio|select" },
//   ...
// ]
// ===========================================================================

(function() {
  'use strict';

  const nativeInputSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, 'value'
  )?.set;
  const nativeTextareaSetter = Object.getOwnPropertyDescriptor(
    window.HTMLTextAreaElement.prototype, 'value'
  )?.set;

  function setNativeValue(el, value) {
    if (el.tagName === 'TEXTAREA' && nativeTextareaSetter) {
      nativeTextareaSetter.call(el, value);
    } else if (nativeInputSetter) {
      nativeInputSetter.call(el, value);
    } else {
      el.value = value;
    }
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new Event('blur', { bubbles: true }));
  }

  const results = { filled: [], errors: [] };

  try {
    const answers = window.__CUSTOM_ANSWERS__;
    if (!answers || !Array.isArray(answers)) {
      results.errors.push({ message: 'No __CUSTOM_ANSWERS__ array found on window' });
      return results;
    }

    for (const answer of answers) {
      try {
        const { selector, value, type } = answer;

        if (type === 'radio') {
          // For radio buttons, find the option matching the value
          const radios = document.querySelectorAll(selector);
          let found = false;
          radios.forEach(radio => {
            if (radio.value === value || (radio.labels && radio.labels[0]?.textContent.toLowerCase().includes(value.toLowerCase()))) {
              radio.checked = true;
              radio.dispatchEvent(new Event('change', { bubbles: true }));
              radio.dispatchEvent(new Event('click', { bubbles: true }));
              found = true;
            }
          });
          if (found) {
            results.filled.push({ selector, value, type });
          } else {
            results.errors.push({ selector, value, message: 'radio option not found' });
          }
          continue;
        }

        if (type === 'select') {
          const el = document.querySelector(selector);
          if (!el) {
            results.errors.push({ selector, message: 'element not found' });
            continue;
          }
          // Find matching option
          const options = Array.from(el.options);
          const match = options.find(o =>
            o.value === value || o.textContent.toLowerCase().includes(value.toLowerCase())
          );
          if (match) {
            el.selectedIndex = options.indexOf(match);
            setNativeValue(el, match.value);
            results.filled.push({ selector, value: match.textContent.trim(), type });
          } else {
            results.errors.push({ selector, value, message: 'select option not found' });
          }
          continue;
        }

        // Text or textarea
        const el = document.querySelector(selector);
        if (!el) {
          results.errors.push({ selector, message: 'element not found' });
          continue;
        }
        setNativeValue(el, value);
        results.filled.push({ selector, value: value.substring(0, 50) + (value.length > 50 ? '...' : ''), type });

      } catch (err) {
        results.errors.push({ selector: answer.selector, message: err.message });
      }
    }
  } catch (err) {
    results.errors.push({ message: err.message, stack: err.stack });
  }

  return results;
})();
