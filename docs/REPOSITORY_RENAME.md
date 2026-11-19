# Repository naming

## Audit result

The build brief referred to an existing repository called `vibratex`. At build time:

* The working repository was **`hurjamies/ResonanceX`**, and it was empty: no commits, branches or files.
* No repository named `vibratex` was visible to the build session's GitHub access.

So no earlier code had to be preserved or migrated, and the codebase already uses the ResonanceX identity.
The internal namespace is `resonancex` (package `@resonancex/web`, env prefix `RESONANCEX_`).

## If a `vibratex` repository exists elsewhere

Renaming is a user decision; it is never automated. To fold it into this project:

1. Inspect it first and list anything worth keeping (code, designs, data).
2. Either port the useful parts into this repository in a normal reviewed PR, or rename the old repository
   on GitHub: **Settings → General → Repository name**. GitHub redirects the old URL, but update local
   remotes anyway:

   ```bash
   git remote set-url origin https://github.com/<owner>/<new-name>.git
   ```

3. Archive the old repository (**Settings → Danger Zone → Archive**) rather than deleting it.

## Optional: lowercase the repository name

The preferred repository spelling is `resonancex`. GitHub names are case-insensitive for URLs, but the
display name can be changed under **Settings → General → Repository name** (`ResonanceX` →
`resonancex`). Then update local remotes with `git remote set-url` as above. No code changes are needed.
