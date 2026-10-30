# Infrastructure: GitHub Pages

- `.github/workflows/pages.yml` builds `src/web` and deploys `src/web/dist`.
- The workflow runs on a `v*` tag or on a manual run.
- The site URL is https://msu.github.io/panocheck/.
- The Pages setting must be "GitHub Actions". The org plan requires a public repo for Pages.
- `.github/workflows/test.yml` runs the Python, web and LibreOffice jobs on each push to main and on each pull request.
