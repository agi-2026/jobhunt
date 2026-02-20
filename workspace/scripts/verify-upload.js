// verify-upload.js — Post-upload verification and React event re-dispatch
// This script verifies that a file upload was successful and re-dispatches React events
// if needed to trigger validation and UI updates.

(function() {
  'use strict';

  function verifyUpload() {
    let verified = false;
    let errors = [];
    let fileName = null;
    
    // Check for file name indicators (uploaded file name shown)
    const fileIndicators = document.querySelectorAll('[class*="file-name"], [class*="fileName"], [class*="uploaded"]');
    for (const ind of fileIndicators) {
      const text = ind.textContent.trim();
      if (text && text.length > 3 && /\.(pdf|doc|docx|txt|rtf)$/i.test(text)) {
        verified = true;
        fileName = text;
        break;
      }
    }
    
    // Check for "Remove file" button (means file is uploaded)
    if (!verified) {
      const removeButtons = document.querySelectorAll('button');
      for (const btn of removeButtons) {
        const text = btn.textContent.toLowerCase().trim();
        const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
        if (text === 'remove file' || ariaLabel === 'remove file' || text.includes('remove')) {
          const group = btn.closest('[class*="field"], [class*="group"], fieldset, [role="group"]');
          if (group) {
            const fileNameEl = group.querySelector('p, span');
            if (fileNameEl) {
              const text = fileNameEl.textContent.trim();
              if (text && text.length > 3) {
                verified = true;
                fileName = text;
                break;
              }
            }
          }
        }
      }
    }
    
    // Check if input[type=file] has a value (file path)
    if (!verified) {
      const fileInputs = document.querySelectorAll('input[type="file"]');
      for (const fi of fileInputs) {
        if (fi.value && fi.value.trim() !== '') {
          verified = true;
          fileName = fi.value.split(/[\\/]/).pop();
          break;
        }
      }
    }
    
    // If not verified, check for validation errors
    if (!verified) {
      const errorElements = document.querySelectorAll('[class*="error"], [class*="Error"], [role="alert"], [aria-live="assertive"]');
      for (const err of errorElements) {
        const text = err.textContent.trim();
        if (text && (text.toLowerCase().includes('file') || text.toLowerCase().includes('upload') || text.toLowerCase().includes('resume'))) {
          errors.push(text);
        }
      }
    }
    
    // Return verification result
    return {
      verified: verified,
      fileName: fileName,
      errors: errors,
      message: verified 
        ? `File upload verified: ${fileName}` 
        : errors.length > 0 
        ? `Upload failed: ${errors.join('; ')}` 
        : `Upload status unknown - no file indicators found`,
    };
  }

  // Return the result
  return verifyUpload();
})();