# Public portfolio showcase

The public My Portfolio view defaults to a fixed **EUR 62,384.71** synthetic example (eight holdings plus cash), dated 2026-09-04. Holdings, prices, histories, IV, quotes and earnings dates are fictional. Real company names are used only to make the UI familiar; this is not current market analysis.

`portfolio_showcase.populate_showcase` creates the same seeded fixture each time in a separate in-memory repository. It does not read the personal SQLite database, write into visitor storage, or fetch a live feed. The existing valuation and market-analysis functions calculate the visible results from that fixture, including risk contribution, daily change, movement estimates and protection pricing.

The example is read-only except for the review-threshold control. Select **My own portfolio** to enter the independent guest workspace. Switching modes does not copy or erase holdings. Guest-session persistence limitations still apply.

Synthetic provenance is visible above the portfolio, alongside market analysis, on individual price sources, and in exported market evidence. Simulated earnings are not labelled verified and have no official-source links. The example's dates do not roll forward and its historical series is illustrative, not an exchange trading calendar.
