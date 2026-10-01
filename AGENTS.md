<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

## Project decisions

- PayGuard AI is a frontend-only hackathon demo using mock data behind `src/lib/payguard-service.ts`, so it runs without FastAPI while preserving an API-ready seam.
- TanStack Router route files under `src/routes/app.*.tsx` provide real pages for every sidebar destination; the reusable UI lives in `src/components/payguard/`.
- The visual system uses the selected Frosted cockpit direction: Space Grotesk, Inter, JetBrains Mono, dark ink surfaces, lime/cyan/amber/rose signals, and semantic tokens in `src/styles.css`.
