# DataVest Branding and Fork Policy

This policy describes the branding used by the DataVest distribution. It is
separate from the component code licenses and is not legal advice.

## 1) DataVest identity

DataVest is the primary product name, logo, and visual identity for this
distribution. Product UI, generated reports, notifications, documentation, and
deployment metadata should use DataVest consistently.

## 2) Source provenance

This distribution is based on upstream OpenByteInc source. Upstream repository
links, commit pins, copyright notices, and applicable license files are kept
where they document provenance or satisfy a component license. Those references
do not make the upstream project the product name of this distribution and do
not imply endorsement.

## 3) Derivative distributions

Derivative distributions may rebrand the product, replace product copy, and
use their own product identity, subject to the applicable upstream licenses.
They must not claim to be an official upstream release or suggest endorsement
by an upstream project or copyright holder.

## 4) Repository maintenance

New runtime-facing strings should use DataVest. Technical compatibility
identifiers, migration history, package/module paths, environment variable
names, metric names, and upstream URLs should not be renamed solely for
cosmetic reasons because doing so can break existing deployments or provenance
checks.
