# TODO

## Next up
- [ ] Redo every app screen to match the reference showcase (component list agreed in chat):
      soft shadow cards, heavier serif headings, pill view switcher, floating tab bar,
      corner-bracket scan frame, teardrop map pins, hero photo on pantry detail,
      clean sign-in / sign-up, settings with sign-out.
- [ ] Remaining art: onboarding cards, Ways-to-help art, megaphone, rescue bag,
      pantry storefront photos, item illustrations (bean cans etc.).

## Pantry staff
- [ ] **Depletion forecast**: predict when each category / item runs out from how fast
      stock leaves (distribute + discard rate from `inventory_transactions`), e.g.
      "Protein runs out in ~4 days at this week's pace". Use it to drive donor asks
      and restock alerts.
- [ ] **Stats page for the pantry owner**: intake vs. hand-outs over time, neighbors
      served, top categories, waste (discards / expired), robot vs. manual intake,
      donations received, rescue bags sold.

## Later
- [ ] Verify pantry claims (anyone can claim any pantry today).
- [ ] Real payments for donations and rescue bags (currently a mock checkout).
- [ ] Rename the Xcode project / bundle from PantrySort to Stash.
- [ ] **Storage capacity per category**: owners set how much they can hold (e.g. no
      freezer room). When a category is at capacity, show "Full: send something else"
      to donors, drop it from the Needs feed, and nudge toward categories with room.
