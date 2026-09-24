plugins { id("com.android.application") }

android {
    namespace = "com.kubanfy.android"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.kubanfy.android"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }
    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
}
kotlin { jvmToolchain(17) }
