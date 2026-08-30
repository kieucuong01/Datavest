# DataVest modification notice

DataVest is a QuantDinger fork started on 2026-08-24 from QuantDinger backend source commit `366ea33c276b5307ce8428da6dcca160532635ea` and the paired QuantDinger-Vue source commit `6f9ce97fe4730355c39a72610f5dbda3f05d3db7`.

The fork applies DataVest branding and is planned as a research and paper-only product. Planned removals cover broker credentials, live orders and workers, live strategy deployment, agent trading scope, grid/copy trading, billing/credits, paid or hidden marketplace surfaces, and mobile surfaces. Those removals are not complete in this release line.

DataVest will add Smart Insights and Optimizer modules. The upstream is frozen for `datavest-quant-v1`; future upstream adoption requires an explicit reviewed pin update. Upstream licenses and required attribution are retained, including `Powered by QuantDinger`.

Write a reviewable inventory artifact without committing machine-specific paths:

```powershell
New-Item -ItemType Directory -Force -Path .\artifacts | Out-Null
.\backend_api_python\.venv\Scripts\python.exe .\backend_api_python\scripts\datavest_scope_inventory.py > .\artifacts\datavest-scope-inventory.json
```
