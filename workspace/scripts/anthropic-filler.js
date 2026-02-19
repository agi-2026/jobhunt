
const form = {
  "first_name": "Howard",
  "last_name": "Cheng",
  "email": "cheng.howard1@gmail.com",
  "phone": "312-536-1936",
  "resume_url": "/Users/howard/.openclaw/workspace/resume/Howard_Cheng_AI_Engineer_2026.pdf",
  "linkedin": "https://www.linkedin.com/in/howard-cheng-ai/",
  "website": "https://howardcheng.ai",
  "questions": [
    {
      "label": "Are you open to working in-person in one of our offices 25% of the time?",
      "value": "Yes"
    },
    {
      "label": "When is the earliest you would want to start working with us?",
      "value": "Immediately"
    },
    {
      "label": "Do you have any deadlines or timeline considerations we should be aware of?",
      "value": "I am on an F1-OPT visa expiring May 2026 and would need an H-1B registration in the March 2026 lottery window."
    },
    {
      "label": "AI Policy for Application",
      "value": "Yes"
    },
    {
      "label": "Why Anthropic?",
      "value": "I am deeply inspired by Anthropic’s commitment to building reliable, interpretable, and steerable AI systems. As an AI engineer who has spent the last 18 months architecting autonomous agents and on-device intelligence at Lenovo, I have seen firsthand the gap between raw LLM capabilities and reliable, production-ready systems. My work on Perception Engine—a cross-device ambient intelligence system—and an RL-based autonomous agent with four-layer memory aligns perfectly with Anthropic's mission of making AI safe and beneficial through rigorous engineering. I’ve led 15-person teams, shipped 0-to-1 products in 4 months, and optimized sub-400M parameter models for on-device use. I want to bring this 'builder' mentality to the Startups team, helping technical founders navigate the complexities of agent design and evaluation frameworks on Claude. I thrive in high-growth environments where I can wear multiple hats, and I am eager to help the next generation of AI-native startups scale their impact using Anthropic’s frontier models."
    },
    {
      "label": "Do you require visa sponsorship?",
      "value": "Yes"
    },
    {
      "label": "Will you now or will you in the future require employment visa sponsorship to work in the country in which the job you're applying for is located?",
      "value": "Yes"
    },
    {
      "label": "Are you open to relocation for this role?",
      "value": "Yes"
    },
    {
      "label": "What is the address from which you plan on working? If you would need to relocate, please type \"relocating\".",
      "value": "Relocating"
    },
    {
      "label": "Have you ever interviewed at Anthropic before?",
      "value": "No"
    },
    {
      "label": "Gender",
      "value": "Male"
    },
    {
      "label": "Are you Hispanic/Latino?",
      "value": "No"
    },
    {
      "label": "Veteran Status",
      "value": "I am not a protected veteran"
    },
    {
      "label": "Disability Status",
      "value": "I do not wish to answer"
    }
  ]
};

async function fillGreenhouse() {
  const inputs = document.querySelectorAll('input[type="text"], input[type="email"], input[type="tel"], textarea');
  
  for (const input of inputs) {
    const label = input.closest('div')?.querySelector('label')?.innerText || "";
    if (label.includes("First Name")) {
      input.value = form.first_name;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    } else if (label.includes("Last Name")) {
      input.value = form.last_name;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    } else if (label.includes("Email")) {
      input.value = form.email;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    } else if (label.includes("Phone")) {
      input.value = form.phone;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    } else if (label.includes("LinkedIn Profile")) {
      input.value = form.linkedin;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    } else if (label.includes("Website")) {
      input.value = form.website;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    } else if (label.includes("Why Anthropic")) {
      input.value = form.questions.find(q => q.label === "Why Anthropic?")?.value || "";
      input.dispatchEvent(new Event('input', { bubbles: true }));
    } else if (label.includes("start working")) {
      input.value = form.questions.find(q => q.label === "When is the earliest you would want to start working with us?")?.value || "";
      input.dispatchEvent(new Event('input', { bubbles: true }));
    } else if (label.includes("deadlines or timeline")) {
      input.value = form.questions.find(q => q.label === "Do you have any deadlines or timeline considerations we should be aware of?")?.value || "";
      input.dispatchEvent(new Event('input', { bubbles: true }));
    } else if (label.includes("address from which you plan on working")) {
      input.value = form.questions.find(q => q.label === "What is the address from which you plan on working? If you would need to relocate, please type \"relocating\".")?.value || "";
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  // Handle Comboboxes
  const comboboxes = document.querySelectorAll('div[role="combobox"]');
  for (const combo of comboboxes) {
    const label = combo.closest('div[role="group"]')?.querySelector('label')?.innerText || 
                  combo.closest('div')?.parentElement?.querySelector('label')?.innerText || "";
    
    let targetValue = "";
    if (label.includes("in-person")) targetValue = "Yes";
    else if (label.includes("AI Policy")) targetValue = "Yes";
    else if (label.includes("visa sponsorship")) targetValue = "Yes";
    else if (label.includes("future require employment visa sponsorship")) targetValue = "Yes";
    else if (label.includes("relocation")) targetValue = "Yes";
    else if (label.includes("interviewed at Anthropic before")) targetValue = "No";
    else if (label.includes("Gender")) targetValue = "Male";
    else if (label.includes("Hispanic/Latino")) targetValue = "No";
    else if (label.includes("Veteran Status")) targetValue = "I am not a protected veteran";
    else if (label.includes("Disability Status")) targetValue = "I do not wish to answer";

    if (targetValue) {
      combo.click();
      await new Promise(r => setTimeout(r, 500));
      const options = document.querySelectorAll('div[role="option"]');
      for (const opt of options) {
        if (opt.innerText.trim() === targetValue) {
          opt.click();
          break;
        }
      }
      await new Promise(r => setTimeout(r, 500));
    }
  }
}

fillGreenhouse();
