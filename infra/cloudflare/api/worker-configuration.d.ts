declare namespace Cloudflare {
  interface Env {
    KUBANFY_API_CONTAINER: DurableObjectNamespace;
    ENVIRONMENT: string;
    DEBUG: string;
    DATABASE_URL: string;
    DATABASE_URL_SYNC: string;
    REDIS_URL: string;
    JWT_SECRET_KEY: string;
    KBY_MASTER_KEY: string;
    OFFLINE_LICENSE_PRIVATE_KEY: string;
    OFFLINE_LICENSE_PUBLIC_KEY: string;
    SUPER_ADMIN_EMAIL: string;
    SUPER_ADMIN_PASSWORD: string;
    DEFAULT_COUNTRY: string;
    RATE_LIMIT_FAIL_OPEN: string;
    LOG_LEVEL: string;
    LOG_FORMAT: string;
    FEATURE_MONETIZATION: string;
    FEATURE_GOOGLE_PLAY: string;
    FEATURE_PROVIDER_YOUTUBE: string;
    R2_ENDPOINT: string;
    R2_ACCESS_KEY_ID: string;
    R2_SECRET_ACCESS_KEY: string;
    R2_CACHE_BUCKET: string;
    R2_PERMANENT_BUCKET: string;
    R2_REGION: string;
    R2_SIGNED_URL_EXPIRY_SECONDS: string;
    CORS_ORIGINS: string;
    ALLOWED_HOSTS: string;
  }
}
declare const env: Cloudflare.Env;
