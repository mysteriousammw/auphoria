# Known issues

Outstanding known problems and limitations, grouped by analysis. To report a
**wrong result**, use the issue template
(`.github/ISSUE_TEMPLATE/wrong_result.md`): the acceptance for a fix is a
recorded cross-check against an independent reference.

{% include "../docs/validation/KNOWN_ISSUES.md" %}

## Report a wrong result

If an analysis produces a number that does not match an independent reference
(R, or a published worked example), report it with:

- the analysis id and the exact command,
- the expected value and its source,
- the value AUPHORIA produced,
- minimal data that reproduces it.

Fixes are validated by adding/updating the reference value in
`docs/validation/references.yaml` and regenerating the dashboard.