// detect-hcaptcha.js — Detect hCaptcha challenge and return metadata
// Run via browser tool:
// action="act", profile="lever", request={kind:"evaluate", fn:"<this>"}
//
// Returns JSON:
// { detected: true/false, prompt: "...", gridSize: "3x3", iframeRect: {...} }

function () {
  const result = {
    detected: false,
    prompt: null,
    gridSize: null,
    iframeRect: null,
    checkboxVisible: false
  };

  // Method 1: Check for hCaptcha iframe (challenge modal)
  const iframes = document.querySelectorAll('iframe[src*="hcaptcha"], iframe[data-hcaptcha-widget-id]');
  for (const iframe of iframes) {
    const rect = iframe.getBoundingClientRect();
    // Challenge iframe is large (>200px wide), checkbox iframe is small (~300x75)
    if (rect.width > 200 && rect.height > 200) {
      result.detected = true;
      result.iframeRect = {
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height)
      };
    } else if (rect.width > 0) {
      result.checkboxVisible = true;
    }
  }

  // Method 2: Check for hCaptcha overlay/container divs
  if (!result.detected) {
    const overlays = document.querySelectorAll(
      '[class*="hcaptcha"], [id*="hcaptcha"], [class*="h-captcha"], [id*="h-captcha"]'
    );
    for (const el of overlays) {
      const rect = el.getBoundingClientRect();
      if (rect.width > 200 && rect.height > 200) {
        result.detected = true;
        result.iframeRect = {
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          width: Math.round(rect.width),
          height: Math.round(rect.height)
        };
        break;
      }
    }
  }

  // Method 3: Check for challenge popup (separate window/overlay)
  // hCaptcha sometimes opens as a centered modal over the page
  if (!result.detected) {
    const allIframes = document.querySelectorAll('iframe');
    for (const iframe of allIframes) {
      const src = iframe.src || '';
      if (src.includes('hcaptcha.com') || src.includes('newassets.hcaptcha')) {
        const rect = iframe.getBoundingClientRect();
        if (rect.width > 200 && rect.height > 200) {
          result.detected = true;
          result.iframeRect = {
            x: Math.round(rect.x),
            y: Math.round(rect.y),
            width: Math.round(rect.width),
            height: Math.round(rect.height)
          };
          break;
        }
      }
    }
  }

  // Try to extract prompt text from accessible elements
  // (hCaptcha prompt is inside the iframe, so this may not work due to cross-origin)
  // But we try anyway in case the page has a same-origin wrapper
  try {
    const promptEls = document.querySelectorAll('.prompt-text, [class*="prompt"], .challenge-prompt');
    for (const el of promptEls) {
      if (el.textContent && el.textContent.trim().length > 5) {
        result.prompt = el.textContent.trim();
        break;
      }
    }
  } catch (e) {
    // Cross-origin, expected
  }

  return JSON.stringify(result);
}