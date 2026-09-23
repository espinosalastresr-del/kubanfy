# Publicar KubanFy en TU GitHub

Este monorepo se desarrolló en un **sandbox local**.  
**No está en tu GitHub todavía**: no hay `git remote` ni credenciales de tu cuenta.

## Por qué no lo ves en github.com

| Qué pasó | Detalle |
|----------|---------|
| Commits | Sí, ~15 en `main` **locales** |
| `git push` | **Nunca** se ejecutó hacia GitHub |
| Remote | **Ninguno** (`git remote -v` vacío) |
| Token | Este entorno **no** tiene acceso a tu cuenta |

Hasta que **tú** (o un token que configures) hagas push, el repo solo existe aquí.

## Cómo publicarlo (3 minutos)

### 1. Crea el repo vacío en GitHub
https://github.com/new → nombre `kubanfy` → **sin** README/LICENSE (ya los tenemos).

### 2. Conecta y sube

```bash
cd ruta/al/kubanfy

git remote add origin https://github.com/TU_USUARIO/kubanfy.git
# o: git remote add origin git@github.com:TU_USUARIO/kubanfy.git

git branch -M main
git push -u origin main
```

### 3. Comprueba
Abre `https://github.com/TU_USUARIO/kubanfy` — debes ver `apps/api`, `apps/mobile`, `.github/workflows`, etc.

### Alternativa: clonar desde git bundle
Si recibiste `kubanfy.bundle`:

```bash
git clone kubanfy.bundle kubanfy
cd kubanfy
git remote remove origin   # el bundle no es GitHub
git remote add origin https://github.com/TU_USUARIO/kubanfy.git
git push -u origin main
```

## Actions
Settings → Actions → permitir workflows. Secrets: ver `docs/CI_MOBILE.md`.

## Si quieres que se intente el push desde aquí
Necesitas proporcionar (en el entorno o como secret):
- URL del repo: `https://github.com/USER/kubanfy.git`
- Token con permiso `repo` (PAT) **o** SSH key

Sin eso, **nadie externo puede publicar en tu cuenta**.
