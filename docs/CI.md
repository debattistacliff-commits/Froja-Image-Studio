# Continuous integration

Froja's release checks are intentionally available as ordinary commands so contributors can run them on Windows or Linux:

```bash
npm ci
python -m pip install -r requirements.txt
npm run lint
npx tsc --noEmit
npm test
```

Repository maintainers can later add a GitHub Actions workflow using Node.js 22 and Python 3.11 to execute the same commands on `windows-latest` and `ubuntu-latest`. Publishing workflow files requires a GitHub credential with the `workflow` scope.

Release packages can be produced locally on Windows with:

```powershell
.\scripts\build-packages.ps1
```
