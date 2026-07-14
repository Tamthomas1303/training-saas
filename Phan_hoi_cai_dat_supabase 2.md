I've prepared everything possible without DB access — both commands are written and syntax-verified, the GitHub Actions schedule is in place, and I have a test CSV ready. I'm blocked on running makemigrations/migrate and the end-to-end tests until the Supabase password is fixed.

Summary of what's done:

sync\_cls (in cls\_sync app): ported faithfully from the real Apps Script (CLS\_Sync\_KetQuaHoc\_FIX.gs, CLS\_Sync\_KetQuaThi\_FIX.gs, ProbationService.gs) — I verified actual field shapes by hitting the live CLS API with the real secret key found in the old scripts. Handles Hội nhập/Level course filtering, the ≥80 eligibility rule, and the "lần 1 as-is / lần 2-3 best-of" exam attempt collapsing (candidate types NV/10N/15N/30N, configurable via .env).  
sync\_recruitment (in employees app): reads a CSV export (Google Sheet "Publish to web") since there's no real recruitment REST API in this codebase — only a Sheet-based flow. Restaurant inference ported from SnapshotService.gs's exact-then-brand-stripped name matching.  
.github/workflows/sync\_cls.yml for scheduled runs (every 6h) once you configure repo secrets; Windows Task Scheduler command documented in README for local runs.  
CourseResult gained a unique\_together so upserts work; migration is generated but not yet applied.  
Once you paste the corrected Supabase password/connection string, I'll apply the migration, run both commands against real data, and verify end-to-end before committing.