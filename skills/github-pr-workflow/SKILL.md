---
name: github-pr-workflow
description: Ciclo de vida completo de Pull Requests en GitHub — crear branch, commits, abrir PR, CI, merge. Úsalo cuando el usuario quiera contribuir código, revisar un PR o gestionar branches.
---

# GitHub PR Workflow

Usa esta skill para guiar el ciclo completo de un Pull Request en GitHub.

## Flujo estándar

### 1. Crear branch
```bash
git checkout -b feat/nombre-descriptivo
# o para bugs:
git checkout -b fix/descripcion-del-bug
```

### 2. Hacer cambios y commits
```bash
git add <archivos>
git commit -m "feat: descripción corta en imperativo"
```

Formatos de commit:
- `feat:` nueva funcionalidad
- `fix:` corrección de bug
- `refactor:` mejora sin cambio de comportamiento
- `docs:` documentación
- `test:` tests
- `chore:` dependencias, config

### 3. Push y abrir PR
```bash
git push -u origin feat/nombre-descriptivo
gh pr create --title "Título corto" --body "## Qué hace\n- punto 1\n\n## Cómo probar\n- paso 1"
```

### 4. Revisión y CI
```bash
gh pr status          # ver estado
gh pr checks          # ver CI
gh pr view --web      # abrir en browser
```

### 5. Merge
```bash
gh pr merge --squash  # recomendado para features
gh pr merge --merge   # para mantener historial completo
```

## Buenas prácticas

- Un PR = una cosa. No mezcles features con refactors.
- Título en imperativo: "Agregar X", "Corregir Y".
- Si el PR es WIP, usa `gh pr create --draft`.
- Revisa `gh pr diff` antes de pedir review.
- Después del merge: `git checkout main && git pull && git branch -d feat/nombre`.
