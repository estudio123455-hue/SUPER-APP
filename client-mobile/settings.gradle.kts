pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "super-app-client-mobile"

include(":app")
include(":core:network")
include(":core:database")
include(":core:designsystem")
include(":core:eventbus")
include(":features:feat_auth")
include(":features:feat_wallet")
include(":features:feat_shop")
include(":features:feat_studio")
