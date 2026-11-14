import { Container, getContainer } from "@cloudflare/containers";

interface Env {
  AUTH_CONTAINER: DurableObjectNamespace<KubanFyAuthContainer>;
  DATABASE_URL: string;
  CORS_ORIGINS?: string;
  TERMS_VERSION?: string;
}

export class KubanFyAuthContainer extends Container {
  defaultPort = 8000;
  sleepAfter = "10m";
  pingEndpoint = "localhost/health/live";

  constructor(ctx: DurableObjectState<{}>, env: Env) {
    super(ctx, env);
    this.envVars = {
      DATABASE_URL: env.DATABASE_URL,
      ENVIRONMENT: "production",
      COOKIE_SECURE: "true",
      TRUST_CLOUDFLARE_HEADERS: "true",
      CORS_ORIGINS: env.CORS_ORIGINS ?? "http://localhost:5173",
      TERMS_VERSION: env.TERMS_VERSION ?? "draft-pending-v1"
    };
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const container = getContainer(env.AUTH_CONTAINER, "kubanfy-auth-v2");
    const headers = new Headers(request.headers);
    const country = request.cf?.country;
    if (typeof country === "string") headers.set("CF-IPCountry", country);
    return container.fetch(new Request(request, { headers }));
  }
};
