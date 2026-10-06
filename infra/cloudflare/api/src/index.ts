import { Container, getContainer } from "@cloudflare/containers";
import { env } from "cloudflare:workers";

export class KubanFyApiContainer extends Container {
  defaultPort = 8000;
  sleepAfter = "10m";
  enableInternet = true;
  pingEndpoint = "health/live";

  envVars = {
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
    R2_SIGNED_URL_EXPIRY_SECONDS: env.R2_SIGNED_URL_EXPIRY_SECONDS,
    CORS_ORIGINS: env.CORS_ORIGINS,
    ALLOWED_HOSTS: env.ALLOWED_HOSTS
  };
}

export default {
  async fetch(request: Request, workerEnv: typeof env) {
    return getContainer(workerEnv.KUBANFY_API_CONTAINER, "staging-api").fetch(request);
  }
};
