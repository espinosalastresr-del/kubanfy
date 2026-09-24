plugins { id("com.android.application") }

android {
    buildFeatures { buildConfig = true }
    namespace = "com.kubanfy.android"
    compileSdk = 36
    defaultConfig {
        applicationId = "com.kubanfy.android"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
        buildConfigField("String", "KUBANFY_API_URL", "\"https://api.kubanfy.com/v1\"")
    }
    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
}
dependencies {
    implementation("androidx.media3:media3-exoplayer:1.11.1")
    implementation("androidx.media3:media3-session:1.11.1")
}

kotlin { jvmToolchain(17) }
