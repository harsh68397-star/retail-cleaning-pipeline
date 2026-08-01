# Pushing to GitHub - Step by Step

Once you are ready to publish this project, follow these exact steps.

## Option A: Using GitHub CLI (easier)

```bash
cd retail-cleaning-pipeline
git init
git add .
git commit -m "feat: initial retail cleaning pipeline with README and tests"
gh repo create retail-cleaning-pipeline --public --source=. --push
```

That is it. `gh` handles everything - creates the repo, links it,
and pushes your commit.

## Option B: Using the GitHub website

```bash
cd retail-cleaning-pipeline
git init
git add .
git commit -m "feat: initial retail cleaning pipeline with README and tests"
git branch -M main
```

Then:
1. Go to https://github.com/new
2. Repository name: `retail-cleaning-pipeline`
3. Visibility: Public
4. DO NOT initialize with README/license/gitignore (we already have them).
5. Click "Create repository"
6. Copy the "push an existing repository" command shown on screen.

## Recommended next commits

After the initial push, consider making these incremental commits:

```bash
git add .
git commit -m "docs: expand README with metrics and tech stack table"
git commit --allow-empty -m "test: add pandera schema validation tests"
git commit --allow-empty -m "feat: add great_expectations checkpoint (optional)"
git commit --allow-empty -m "docs: add screenshot of missing-value chart to README"
```

## Show it off

- LinkedIn post: "I built a reproducible data cleaning pipeline in
  Python. It takes a messy retail CSV with 7 different missing-value
  tokens, mixed date formats, and embedded duplicates, and produces
  a schema-validated clean CSV plus a markdown summary report."

- Resume bullet:
  > Built a 9-stage reproducible data cleaning pipeline in Python
  > (pandas + pandera) for retail sales data, reducing missing-cell
  > percentage and producing schema-validated output.

- Portfolio link: Add to your personal site under "Data Engineering".
