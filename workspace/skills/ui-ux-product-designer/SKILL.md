# UI/UX Product Designer

## Purpose
Evaluate and design user interfaces that are clear, usable, accessible, conversion-aware, and implementation-ready.

## Use When
- Reviewing an app, website, dashboard, form, or landing page
- Designing a new UI flow
- Improving onboarding, navigation, conversion, or retention
- Creating wireframes, UX audits, or design specs
- Translating product requirements into screens

## Safety Model
This is a local instruction skill only. No external UI libraries are installed. Recommendations are based on established usability and accessibility principles.

## Core UX Heuristics
Apply Nielsen Norman Group's 10 usability heuristics:
1. Visibility of system status
2. Match between system and real world
3. User control and freedom
4. Consistency and standards
5. Error prevention
6. Recognition rather than recall
7. Flexibility and efficiency of use
8. Aesthetic and minimalist design
9. Help users recognize, diagnose, and recover from errors
10. Help and documentation

## Design Review Checklist
- [ ] Primary user goal is obvious within 5 seconds
- [ ] Page hierarchy guides the eye: headline → key action → supporting detail
- [ ] CTA labels are specific and action-oriented
- [ ] Navigation matches user mental models
- [ ] Forms use clear labels, inline validation, helpful errors
- [ ] Empty/loading/error/success states exist
- [ ] Visual design is consistent: spacing, typography, color, iconography
- [ ] Content is concise and jargon-free
- [ ] Mobile/responsive behavior is specified
- [ ] Accessibility basics are covered: contrast, keyboard focus, labels, semantic structure

## Accessibility Defaults
- Use semantic HTML first
- Keep visible focus states
- Maintain contrast: at least WCAG AA as a baseline
- Do not rely on color alone to convey meaning
- Every input needs a persistent label
- Every icon-only button needs an accessible name
- Error messages should explain what happened and how to fix it

## UX Audit Output Format
1. Executive summary
2. Top 5 issues ranked by impact
3. Heuristic/accessibility findings
4. Concrete fixes with copy examples
5. Suggested layout/flow changes
6. Quick wins vs deeper redesign
7. Implementation notes for developers

## Design Spec Output Format
- User goal
- Screen list
- Information architecture
- Component inventory
- Interaction states
- Empty/loading/error states
- Responsive behavior
- Analytics events
- Acceptance criteria

## Vetted References
- Nielsen Norman Group: 10 Usability Heuristics for User Interface Design
- WCAG accessibility principles as baseline
