import { Container } from "@cloudflare/containers";

interface Env {
  KUBANFY_API_CONTAINER: DurableObjectNamespace<KubanFyApiContainer>;
  ENVIRONMENT: string;
  DEBUG: string;
  DATABASE_URL: string;
  DATABASE_URL_SYNC?: string;
  REDIS_URL?: string;
  JWT_SECRET_KEY?: string;
  KBY_MASTER_KEY?: string;
  OFFLINE_LICENSE_PRIVATE_KEY?: string;
  OFFLINE_LICENSE_PUBLIC_KEY?: string;
  SUPER_ADMIN_EMAIL?: string;
  SUPER_ADMIN_PASSWORD?: string;
  DEFAULT_COUNTRY: string;
  RATE_LIMIT_FAIL_OPEN?: string;
  LOG_LEVEL?: string;
  LOG_FORMAT?: string;
  FEATURE_MONETIZATION?: string;
  FEATURE_GOOGLE_PLAY?: string;
  FEATURE_PROVIDER_YOUTUBE?: string;
  R2_ENDPOINT?: string;
  R2_ACCESS_KEY_ID?: string;
  R2_SECRET_ACCESS_KEY?: string;
  R2_CACHE_BUCKET?: string;
  R2_PERMANENT_BUCKET?: string;
  R2_REGION?: string;
  R2_SIGNED_URL_EXPIRY_SECONDS?: string;
  CORS_ORIGINS?: string;
  ALLOWED_HOSTS?: string;
}

function containerEnvironment(env: Env): Record<string, string> {
  const values: Record<string, string | undefined> = {
    ENVIRONMENT: env.ENVIRONMENT,
    DEBUG: env.DEBUG,
    DATABASE_URL: env.DATABASE_URL,
    DATABASE_URL_SYNC: env.DATABASE_URL_SYNC,
    REDIS_URL: env.REDIS_URL,
    JWT_SECRET_KEY: env.JWT_SECRET_KEY,
    KBY_MASTER_KEY: env.KBY_MASTER_KEY,
    OFFLINE_LICENSE_PRIVATE_KEY: env.OFFLINE_LICENSE_PRIVATE_KEY,
    OFFLINE_LICENSE_PUBLIC_KEY: env.OFFLINE_LICENSE_PUBLIC_KEY,
    SUPER_ADMIN_EMAIL: env.SUPER_ADMIN_EMAIL,
    SUPER_ADMIN_PASSWORD: env.SUPER_ADMIN_PASSWORD,
    DEFAULT_COUNTRY: env.DEFAULT_COUNTRY,
    RATE_LIMIT_FAIL_OPEN: env.RATE_LIMIT_FAIL_OPEN,
    LOG_LEVEL: env.LOG_LEVEL,
    LOG_FORMAT: env.LOG_FORMAT,
    FEATURE_MONETIZATION: env.FEATURE_MONETIZATION,
    FEATURE_GOOGLE_PLAY: env.FEATURE_GOOGLE_PLAY,
    FEATURE_PROVIDER_YOUTUBE: env.FEATURE_PROVIDER_YOUTUBE,
    R2_ENDPOINT: env.R2_ENDPOINT,
    R2_ACCESS_KEY_ID: env.R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY: env.R2_SECRET_ACCESS_KEY,
    R2_CACHE_BUCKET: env.R2_CACHE_BUCKET,
    R2_PERMANENT_BUCKET: env.R2_PERMANENT_BUCKET,
    R2_REGION: env.R2_REGION,
    R2_SIGNED_URL_EXPIRY_SECONDS: env.R2_SIGNED_URL_EXPIRY_SECONDS ?? "900",
    CORS_ORIGINS: env.CORS_ORIGINS,
    ALLOWED_HOSTS: env.ALLOWED_HOSTS,
  };

  // Wrangler/Worker bindings can accidentally contain the literal string
  // "undefined". Never pass that string into Pydantic as a real setting.
  return Object.fromEntries(
    Object.entries(values).filter(([, value]) => {
      if (typeof value !== "string") return false;
      const normalized = value.trim().toLowerCase();
      return normalized !== "" && normalized !== "undefined" && normalized !== "null";
    }),
  ) as Record<string, string>;
}

export class KubanFyApiContainer extends Container<Env> {
  defaultPort = 8000;
  sleepAfter = "10m";
  enableInternet = true;
  pingEndpoint = "health/live";

  envVars = containerEnvironment(this.env);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const id = env.KUBANFY_API_CONTAINER.idFromName("staging-api");
    const container = env.KUBANFY_API_CONTAINER.get(id);
    return container.fetch(request);
  },
};
