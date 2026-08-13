"""
day10_tasks.py

The 22 tasks agreed on for the microsite (raghavvohra.smartmfdpro.com).
Each task: goal (plain English) + acceptance_criteria (what should be
verifiably true afterward, checked via 'assert' - real evidence, not a
self-declared verdict).
"""

MICROSITE_URL = "https://raghavvohra.smartmfdpro.com/"

TASKS = [
    {
        "id": "contact-form-top",
        "start_url": MICROSITE_URL,
        "goal": "Fill and submit the top 'Contact Me Now' form with a valid test phone number",
        "acceptance_criteria": "A success or confirmation state appears after submission"
    },
    {
        "id": "contact-form-bottom",
        "start_url": MICROSITE_URL,
        "goal": "Fill and submit the bottom 'Contact Me Now' form (near the map/address section)",
        "acceptance_criteria": "A success or confirmation state appears after submission"
    },
    {
        "id": "whatsapp-cta",
        "start_url": MICROSITE_URL,
        "goal": "Open the WhatsApp CTA modal, fill in the message field, and submit via 'Share Message'",
        "acceptance_criteria": "The share/submit action completes without an error state"
    },
    {
        "id": "chatbot-cta",
        "start_url": MICROSITE_URL,
        "goal": "Open the CRMF chatbot widget",
        "acceptance_criteria": "The chatbot widget visibly opens/expands"
    },
    {
        "id": "chatbot-fill-details",
        "start_url": MICROSITE_URL,
        "goal": "Open the CRMF chatbot and progress its conversation by providing requested details",
        "acceptance_criteria": "The bot responds or advances after input is provided"
    },
    {
        "id": "content-filter-leaflet",
        "start_url": MICROSITE_URL,
        "goal": "Click the Content Type filter and select 'Leaflet'",
        "acceptance_criteria": "The content list updates to reflect the Leaflet filter"
    },
    {
        "id": "category-equity",
        "start_url": MICROSITE_URL,
        "goal": "Click the 'Equity Schemes' category filter",
        "acceptance_criteria": "The content list filters to Equity Schemes"
    },
    {
        "id": "category-hybrid",
        "start_url": MICROSITE_URL,
        "goal": "Click the 'Hybrid Schemes' category filter",
        "acceptance_criteria": "The content list filters to Hybrid Schemes"
    },
    {
        "id": "category-debt",
        "start_url": MICROSITE_URL,
        "goal": "Click the 'Debt Schemes' category filter",
        "acceptance_criteria": "The content list filters to Debt Schemes"
    },
    {
        "id": "achievements-visible",
        "start_url": MICROSITE_URL,
        "goal": "Verify the Achievements section is rendered on the page",
        "acceptance_criteria": "Achievement entries (e.g. 'Employee of the Year') are present"
    },
    {
        "id": "testimonials-visible",
        "start_url": MICROSITE_URL,
        "goal": "Verify the Testimonials section is rendered on the page",
        "acceptance_criteria": "Testimonial entries with names are present"
    },
    {
        "id": "content-click-navigation",
        "start_url": MICROSITE_URL,
        "goal": "Click on one content card and verify it navigates to a new URL",
        "acceptance_criteria": "Browser URL changes away from the microsite's own URL"
    },
    {
        "id": "logo-visible",
        "start_url": MICROSITE_URL,
        "goal": "Verify the site logo (smartMFDPro branding) is visible at the top of the page",
        "acceptance_criteria": "The logo image element is present and visible"
    },
    {
        "id": "header-contact-info",
        "start_url": MICROSITE_URL,
        "goal": "Verify the header shows a phone number and email address",
        "acceptance_criteria": "Phone number 7838281546 and email raghav.vohra@salespanda.com are both visible"
    },
    {
        "id": "social-links-redirect",
        "start_url": MICROSITE_URL,
        "goal": "Click the Facebook icon, verify it redirects to the correct profile; repeat for LinkedIn",
        "acceptance_criteria": "Facebook link leads to facebook.com/583196961554123; LinkedIn leads to linkedin.com/company/107425006"
    },
    {
        "id": "nav-home",
        "start_url": MICROSITE_URL,
        "goal": "Click the 'Home' nav link",
        "acceptance_criteria": "Current URL contains a bare '#' fragment (Home's link is unlike the other nav items - it has no named anchor like '#about')"
    },
    {
        "id": "nav-about",
        "start_url": MICROSITE_URL,
        "goal": "Click the 'About Us' nav link",
        "acceptance_criteria": "Page scrolls to the About section (anchor link, same page)"
    },
    {
        "id": "nav-content",
        "start_url": MICROSITE_URL,
        "goal": "Click the 'Content' nav link",
        "acceptance_criteria": "Page scrolls to the Content section (anchor link, same page)"
    },
    {
        "id": "nav-contact",
        "start_url": MICROSITE_URL,
        "goal": "Click the 'Contact Us' nav link",
        "acceptance_criteria": "Page scrolls to the Contact section (anchor link, same page)"
    },
    {
        "id": "contact-form-validation",
        "start_url": MICROSITE_URL,
        "goal": "Attempt to submit the top 'Contact Me Now' form with an empty or invalid phone number",
        "acceptance_criteria": "Form correctly blocks submission and shows a validation message, rather than silently failing or succeeding"
    },
    {
        "id": "sebi-disclosure-check",
        "start_url": MICROSITE_URL,
        "goal": "Verify the SEBI regulatory disclosure text is present on the page",
        "acceptance_criteria": "SEBI registration name and registration number text is visible"
    },
    {
        "id": "broken-image-check",
        "start_url": MICROSITE_URL,
        "goal": "Check that key images (logo, testimonial photos, achievement icons) actually load rather than being broken",
        "acceptance_criteria": "No broken/404 image is found among the checked images"
    },
]