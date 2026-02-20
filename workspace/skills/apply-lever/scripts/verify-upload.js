// verify-upload.js — Post-upload verification and React event re-dispatch
// Run via browser tool:
// action="act", profile="<profile>", request={kind:"evaluate", fn:"<this file>"}
// Run AFTER the browser upload action to ensure React forms recognize the uploaded file.
() => {
  const results = { verified: false, errors: [], actions: [] };

  const fileInputs = document.querySelectorAll('input[type="file"]');
  if (!fileInputs.length) {
    results.errors.push('No file inputs found on page');
    return JSON.stringify(results, null, 2);
  }

  fileInputs.forEach(fi => {
    const group = fi.closest('[class*="field"], [class*="group"], fieldset, [role="group"]');
    const label = group
      ? (group.querySelector('label') || {}).textContent?.trim() || 'file'
      : 'file';

    if (!fi.files || fi.files.length === 0) {
      results.errors.push(label + ': file input has no files after upload');
      return;
    }

    const fileName = fi.files[0].name;
    results.actions.push(label + ': found "' + fileName + '", re-dispatching events');

    // 1. Dispatch standard DOM events (bubbling) — covers vanilla JS listeners
    fi.dispatchEvent(new Event('input', { bubbles: true }));
    fi.dispatchEvent(new Event('change', { bubbles: true }));
    fi.dispatchEvent(new Event('blur', { bubbles: true }));

    // 2. Try to trigger React's onChange directly via __reactProps (React 17+)
    try {
      const propsKey = Object.keys(fi).find(k => k.startsWith('__reactProps'));
      if (propsKey && fi[propsKey] && typeof fi[propsKey].onChange === 'function') {
        fi[propsKey].onChange({
          target: fi,
          currentTarget: fi,
          type: 'change',
          nativeEvent: new Event('change'),
          preventDefault: function() {},
          stopPropagation: function() {},
          bubbles: true,
        });
        results.actions.push(label + ': React onChange triggered via __reactProps');
      }
    } catch (e) {
      results.actions.push(label + ': __reactProps error: ' + e.message);
    }

    // 3. Walk React fiber tree to find and trigger onChange handlers
    try {
      const fiberKey = Object.keys(fi).find(k =>
        k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance')
      );
      if (fiberKey) {
        let fiber = fi[fiberKey];
        let depth = 0;
        while (fiber && depth < 20) {
          const props = fiber.memoizedProps || fiber.pendingProps;
          if (props && typeof props.onChange === 'function') {
            props.onChange({
              target: fi,
              currentTarget: fi,
              type: 'change',
              nativeEvent: new Event('change'),
              preventDefault: function() {},
              stopPropagation: function() {},
              bubbles: true,
            });
            results.actions.push(label + ': React onChange triggered via fiber tree (depth ' + depth + ')');
            break;
          }
          fiber = fiber.return;
          depth++;
        }
        if (!fiber) {
          results.actions.push(label + ': No React onChange found in fiber tree');
        }
      } else {
        results.actions.push(label + ': No React fiber found (non-React or different framework)');
      }
    } catch (e) {
      results.actions.push(label + ': Fiber walk error: ' + e.message);
    }

    // 4. Dispatch additional events some frameworks listen for
    try {
      // Some upload libraries use 'drop' events
      const dt = new DataTransfer();
      dt.items.add(fi.files[0]);
      fi.dispatchEvent(new DragEvent('drop', { bubbles: true, dataTransfer: dt }));
      results.actions.push(label + ': drop event dispatched');
    } catch (e) {
      // DataTransfer constructor may not support adding existing files in all browsers
      results.actions.push(label + ': drop event skipped: ' + e.message);
    }

    results.verified = true;
  });

  // Check for upload-related validation errors still visible
  const errorEls = document.querySelectorAll(
    '[class*="error"], [class*="invalid"], [role="alert"], .error-message, [class*="validation"]'
  );
  errorEls.forEach(el => {
    const text = el.textContent.trim();
    if (text && /resume|file|attach|upload/i.test(text) && el.offsetParent !== null) {
      results.errors.push('Validation still showing: "' + text.substring(0, 100) + '"');
      results.verified = false;
    }
  });

  return JSON.stringify(results, null, 2);
}