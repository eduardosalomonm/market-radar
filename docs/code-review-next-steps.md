# FolioShift review — 2026-09-04

## Corrections implemented

- Demo daily bars now respect requested dates and generate prices from absolute session indices. Previously each window restarted the same price path, producing identical closing values on different scan dates.
- Portfolio summaries disclose missing prices, missing comparison prices and incomplete cost basis. Incomplete comparisons no longer generate a reassuring all-clear message.
- Comparisons reject different providers and non-earlier sessions.
- Removed ideas no longer imply that the score necessarily dropped: technical plan rules and data coverage can also remove a plan.
- Completed and expired paper outcomes cannot be overwritten through the repository. The outcome updater skips these records, reducing repeated historical downloads.
- Holdings reject nonfinite quantities and costs before reaching SQLite.
- The interface explains that change uses current quantities at both saved closes. This is a holdings scenario, not transaction-based account performance.

## Next implementation priorities

1. **Transaction-based portfolio accounting.** Store buys, sells, cash flows, fees, dividends, currency and splits. Calculate performance from actual holdings on each date, with an explicit benchmark. This is necessary before presenting historical account returns.
2. **Frozen personal briefs.** Persist each daily brief with the positions, watchlist, input scan and formula version used to create it. Currently historical scans are combined with today's editable holdings, so this is not yet a personal historical record.
3. **Reliable private real-data deployment.** Add persistent storage, authentication and a separate scheduled worker. Keep the last usable scan visible, show its age, and run a credentialed end-to-end verification. Credentials are not currently configured locally.
4. **Notification delivery.** Alerts currently appear inside the app. Add an opt-in daily email digest with delivery records, retries and duplicate prevention. Do not claim email or push notifications are already implemented.
5. **Separate UI modules.** The Streamlit entry point contains navigation, CSS, initialization, charts and page bodies. Extract portfolio rendering and scan initialization first, preserving behavior, then split the other views. Avoid a framework rewrite before the accounting and persistence boundaries are settled.

## Remaining review concerns

- The synthetic calendar uses weekdays rather than exchange holidays; synthetic options pressure is largely ticker-dependent.
- Existing saved demo scans keep their original values; the improved generator affects new scans only.
- Options chains are latest snapshots, which cannot reliably reconstruct a missed historical session. Historical catch-up must explicitly distinguish unavailable options evidence from captured session evidence.
- A single shared SQLite portfolio is a personal application, not a multi-user account system.
- Sector concentration plus market risk appetite is a limited portfolio macro explanation. Company geography, currency exposure and verified upcoming earnings would add useful context.
- Watchlist-only users now reach the alert section, but the portfolio metrics still warrant a dedicated empty-state design.

These are implementation proposals based on this code review, not claims that the features exist today.
