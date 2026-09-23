# Load tests (plan §41)

## Requisitos

Instalar [k6](https://k6.io/docs/get-started/installation/).

## Smoke

Con el API en marcha (local o staging):

```bash
k6 run -e BASE_URL=http://127.0.0.1:8000 loadtests/k6_smoke.js
```

Carga más fuerte:

```bash
k6 run -e BASE_URL=http://127.0.0.1:8000 -e VUS=50 -e DURATION=2m loadtests/k6_smoke.js
```

## Umbrales

- `< 5%` requests fallidas
- p95 latencia `< 1.5s` en smoke

Añadir escenarios de login/download cuando existan usuarios de prueba en staging.
