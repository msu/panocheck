# GitHub Pages

- The MSU org has a free plan, so Pages needs a public repo. This is not tested.
- Environment rules can block deploys from tags. Use a manual workflow run on `main` if a tag deploy fails.
- `vite` uses `base: './'`, so the app works under `/panocheck/`.
- The build adds the CSP only in production, because the dev server needs a websocket.
