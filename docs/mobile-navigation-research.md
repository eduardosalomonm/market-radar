# Mobile primary navigation research

## Decision

Use a persistent mobile header with the product name on the left and a clearly
visible control labelled exactly **Menu** on the right. Opening it should reveal
the app's primary destinations in a full-width panel. Show the current section
with both a strong visual treatment and programmatic state. Do not depend on the
Streamlit utility sidebar for primary navigation.

This pattern directly addresses the current discoverability problem: the user
sees “Menu” in the conventional header location before interacting, and can see
where they are after opening it.

## Evidence and actionable requirements

1. **Use the visible label “Menu.”** The US Web Design System reference header
   uses a mobile button whose text is `Menu`; the GOV.UK Service Navigation
   component does the same and connects that control to the navigation through
   `aria-controls`. This is clearer than product-specific wording such as
   “Dashboard menu” or “Explore dashboard.”
   [USWDS Header](https://designsystem.digital.gov/components/header/),
   [GOV.UK Service Navigation](https://design-system.service.gov.uk/components/service-navigation/)

2. **Keep primary navigation in the persistent header, not only in a collapsible
   sidebar.** USWDS describes header navigation as a visible, familiar way to
   reach a site's main sections. Streamlit now supports top navigation directly
   through `st.navigation(..., position="top")`; if the app remains a single
   script, a custom top menu should reproduce that placement.
   [USWDS Header](https://designsystem.digital.gov/components/header/),
   [Streamlit `st.navigation`](https://docs.streamlit.io/develop/api-reference/navigation/st.navigation)

3. **Identify the current section.** Give the selected destination a visible
   active treatment that does not rely on color alone, and expose it as the
   current item. W3C recommends `aria-current="page"`; USWDS explicitly says to
   highlight the current section, and GOV.UK's component demonstrates an active
   item with `aria-current`.
   [W3C Menu Structure](https://www.w3.org/WAI/tutorials/menus/structure/),
   [USWDS Header](https://designsystem.digital.gov/components/header/),
   [GOV.UK Service Navigation](https://design-system.service.gov.uk/components/service-navigation/)

4. **Make the relationship between the control and the menu explicit.** Use a
   real button, reflect its state with `aria-expanded`, and associate it with the
   revealed menu using `aria-controls`. The button must open with Enter and
   Space, not touch alone. WAI's Menu Button Pattern documents these semantics
   and keyboard interactions.
   [WAI-ARIA Menu Button Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/menu-button/)

5. **Keep mobile and desktop navigation consistent.** Use the same destination
   names, order, and destinations at every breakpoint. W3C allows items to be
   collapsed on small screens but says the items that remain should retain the
   same order, wording, and destination.
   [W3C Menu Structure](https://www.w3.org/WAI/tutorials/menus/structure/)

6. **Use touch-friendly rows and controls.** Target at least 44 by 44 CSS pixels
   for the Menu button, close button, and destination rows, with space between
   adjacent controls. WCAG 2.2 requires at least 24 by 24 CSS pixels or sufficient
   spacing at Level AA; Apple recommends 44 by 44 points for easy selection.
   [WCAG 2.2 Target Size (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum),
   [Apple Buttons](https://developer.apple.com/design/human-interface-guidelines/buttons)

7. **Keep the open menu contained and dismissible.** The menu should fit within
   the viewport, close on selection and Escape, preserve a visible focus
   indicator, and prevent keyboard focus from disappearing into obscured page
   content while open. USWDS explicitly tests reflow, keyboard access, visible
   focus, and contained focus for mobile navigation.
   [USWDS Header accessibility tests](https://designsystem.digital.gov/components/header/accessibility-tests/)

## Recommended Market Radar pattern

- Header, always visible: `Market Radar` | `Menu`
- Under the header or inside the open panel: `Current: Stock Explorer`
- Open state: a full-width vertical list with one destination per 44-pixel-or-
  taller row; the selected row gets a left accent/bar plus bold text or a check
  mark, not color alone.
- Destination labels: remove numeric prefixes and use short names such as
  `Brief`, `Market Map`, `Ideas`, `Stock Explorer`, `Watchlist`, `History`, and
  `Method` if those labels remain unambiguous after usability testing.
- Sidebar: retain only optional filters, scan metadata, and advanced settings.
- Test at 320, 375, 390, and 430 CSS-pixel widths, at 200% text zoom, with
  keyboard-only input, and with VoiceOver or TalkBack.

## Streamlit implementation note

The cleanest long-term implementation is a multipage entry point using
`st.navigation(position="top")`, which makes primary navigation part of the app
header. If that refactor is too large for the current release, keep the existing
single-page router but replace its exposed selector with a persistent top
**Menu** control and an in-content navigation panel. In either version, primary
navigation must remain usable when Streamlit automatically collapses its sidebar.

