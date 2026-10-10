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

export class KubanFyApiContainer extends Container<Env> {
  defaultPort = 8000;
  sleepAfter = "10m";
  enableInternet = true;
  pingEndpoint = "health/live";

  envVars = Object.fromEntries(Object.entries({
    ENVIRONMENT: this.env.ENVIRONMENT,
    DEBUG: this.env.DEBUG,
    DATABASE_URL: this.env.DATABASE_URL,
    DATABASE_URL_SYNC: this.env.DATABASE_URL_SYNC,
    REDIS_URL: this.env.REDIS_URL,
    JWT_SECRET_KEY: this.env.JWT_SECRET_KEY,
    KBY_MASTER_KEY: this.env.KBY_MASTER_KEY,
    OFFLINE_LICENSE_PRIVATE_KEY: this.env.OFFLINE_LICENSE_PRIVATE_KEY,
    OFFLINE_LICENSE_PUBLIC_KEY: this.env.OFFLINE_LICENSE_PUBLIC_KEY,
    SUPER_ADMIN_EMAIL: this.env.SUPER_ADMIN_EMAIL,
    SUPER_ADMIN_PASSWORD: this.env.SUPER_ADMIN_PASSWORD,
    DEFAULT_COUNTRY: this.env.DEFAULT_COUNTRY,
    RATE_LIMIT_FAIL_OPEN: this.env.RATE_LIMIT_FAIL_OPEN,
    LOG_LEVEL: this.env.LOG_LEVEL,
    LOG_FORMAT: this.env.LOG_FORMAT,
    FEATURE_MONETIZATION: this.env.FEATURE_MONETIZATION,
    FEATURE_GOOGLE_PLAY: this.env.FEATURE_GOOGLE_PLAY,
    FEATURE_PROVIDER_YOUTUBE: this.env.FEATURE_PROVIDER_YOUTUBE,
    R2_ENDPOINT: this.env.R2_ENDPOINT,
    R2_ACCESS_KEY_ID: this.env.R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY: this.env.R2_SECRET_ACCESS_KEY,
    R2_CACHE_BUCKET: this.env.R2_CACHE_BUCKET,
    R2_PERMANENT_BUCKET: this.env.R2_PERMANENT_BUCKET,
    R2_REGION: this.env.R2_REGION,
    R2_SIGNED_URL_EXPIRY_SECONDS: this.env.R2_SIGNED_URL_EXPIRY_SECONDS,
    CORS_ORIGINS: this.env.CORS_ORIGINS,
    ALLOWED_HOSTS: this.env.ALLOWED_HOSTS
  }).filter(([, value]) => value !== undefined)) as Record<string, string>;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const id = env.KUBANFY_API_CONTAINER.idFromName("staging-api");
    const container = env.KUBANFY_API_CONTAINER.get(id);
    return container.fetch(request);
  }
};
