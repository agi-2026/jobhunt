// greenhouse-verify-code.js — Fill Greenhouse email verification code boxes
// Run via: browser act kind=evaluate fn="<this file>" profile="greenhouse"
// Pass the 8-character code as: fn="(function(){var CODE='ABCD1234'; ... })()"
// Or use the wrapper below that reads the code from the page URL hash or a global var.
//
// Usage:
//   1. Set window.__VERIFY_CODE = 'ABCD1234' via evaluate before running this script
//   2. Or pass the code inline: replace CODE_PLACEHOLDER below
//
// Why this exists:
//   Greenhouse email verification uses 8 separate <input> boxes with auto-advance.
//   Typing characters via Playwright one-at-a-time corrupts other form fields because
//   each keystroke triggers React re-renders. This script fills all 8 boxes atomically
//   via JS in a single evaluate call.
(() => {
  const CODE = window.__VERIFY_CODE || 'CODE_PLACEHOLDER';
  const results = { filled: false, error: null, boxes: 0 };

  if (!CODE || CODE === 'CODE_PLACEHOLDER' || CODE.length < 6) {
    results.error = 'No verification code set. Set window.__VERIFY_CODE first.';
    return JSON.stringify(results);
  }

  // Find the verification code input boxes
  // Greenhouse patterns: multiple single-char inputs in a row, or inputs with maxlength=1
  const codeInputs = [];

  // Pattern 1: inputs with maxlength=1 that are visible
  const maxLen1Inputs = document.querySelectorAll('input[maxlength="1"]');
  if (maxLen1Inputs.length >= 6) {
    maxLen1Inputs.forEach(inp => {
      if (inp.offsetParent !== null || inp.closest('[class*="verify"], [class*="code"], [class*="otp"]')) {
        codeInputs.push(inp);
      }
    });
  }

  // Pattern 2: inputs inside a verification/code container
  if (codeInputs.length < 6) {
    const containers = document.querySelectorAll('[class*="verify"], [class*="code"], [class*="otp"], [class*="pin"]');
    containers.forEach(container => {
      const inputs = container.querySelectorAll('input[type="text"], input[type="tel"], input:not([type])');
      if (inputs.length >= 6 && inputs.length <= 10) {
        codeInputs.length = 0;
        inputs.forEach(inp => codeInputs.push(inp));
      }
    });
  }

  // Pattern 3: consecutive single-char inputs (auto-advancing code boxes)
  if (codeInputs.length < 6) {
    const allInputs = document.querySelectorAll('input[type="text"], input[type="tel"], input:not([type])');
    const consecutive = [];
    let streak = [];
    allInputs.forEach(inp => {
      const ml = parseInt(inp.getAttribute('maxlength') || '999');
      const w = inp.offsetWidth;
      if ((ml === 1 || (w > 0 && w < 60)) && inp.offsetParent !== null) {
        streak.push(inp);
      } else {
        if (streak.length >= 6) consecutive.push(...streak);
        streak = [];
      }
    });
    if (streak.length >= 6) consecutive.push(...streak);
    if (consecutive.length >= 6) {
      codeInputs.length = 0;
      consecutive.forEach(inp => codeInputs.push(inp));
    }
  }

  results.boxes = codeInputs.length;

  if (codeInputs.length < 6) {
    results.error = 'Found only ' + codeInputs.length + ' code input boxes (need at least 6)';
    return JSON.stringify(results);
  }

  // Native value setter for React bypass
  const nativeSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, 'value'
  )?.set;

  // Fill each box with one character
  const chars = CODE.split('');
  for (let i = 0; i < Math.min(chars.length, codeInputs.length); i++) {
    const inp = codeInputs[i];
    if (nativeSetter) {
      nativeSetter.call(inp, chars[i]);
    } else {
      inp.value = chars[i];
    }
    // Dispatch full event sequence for React
    inp.dispatchEvent(new Event('focus', { bubbles: true }));
    inp.dispatchEvent(new Event('input', { bubbles: true }));
    inp.dispatchEvent(new Event('change', { bubbles: true }));
    inp.dispatchEvent(new KeyboardEvent('keydown', { key: chars[i], bubbles: true }));
    inp.dispatchEvent(new KeyboardEvent('keyup', { key: chars[i], bubbles: true }));
  }

  // Focus the last filled box (or the submit button if available)
  const lastFilled = codeInputs[Math.min(chars.length, codeInputs.length) - 1];
  if (lastFilled) {
    lastFilled.dispatchEvent(new Event('blur', { bubbles: true }));
  }

  results.filled = true;
  return JSON.stringify(results);
})();
