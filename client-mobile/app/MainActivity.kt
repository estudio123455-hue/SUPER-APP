package co.superapp.app

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import co.superapp.core.eventbus.ClientAppEvent
import co.superapp.core.eventbus.ClientEventBus
import co.superapp.core.network.AuthTokenProvider
import co.superapp.core.network.SuperAppApiClient
import co.superapp.features.feat_auth.application.LoginUserUseCase
import co.superapp.features.feat_auth.infrastructure.RemoteAuthRepository
import co.superapp.features.feat_auth.presentation.AuthViewModel
import co.superapp.features.feat_shop.application.ShopCatalogAndOrderUseCase
import co.superapp.features.feat_shop.infrastructure.RemoteShopRepository
import co.superapp.features.feat_shop.presentation.ShopViewModel
import co.superapp.features.feat_studio.application.StudioJobsUseCase
import co.superapp.features.feat_studio.infrastructure.RemoteStudioRepository
import co.superapp.features.feat_studio.presentation.StudioViewModel
import co.superapp.features.feat_wallet.application.ManageWalletUseCase
import co.superapp.features.feat_wallet.infrastructure.RemoteWalletFeatureRepository
import co.superapp.features.feat_wallet.presentation.WalletViewModel
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    @Volatile
    private var currentJwtToken: String? = null
    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val clientEventBus = ClientEventBus()
        appScope.launch {
            clientEventBus.events.collect { event ->
                if (event is ClientAppEvent.UserAuthenticated) {
                    currentJwtToken = event.accessToken
                }
            }
        }

        val tokenProvider = object : AuthTokenProvider {
            override fun currentAccessToken(): String? = currentJwtToken
        }

        val apiService = SuperAppApiClient.create(
            tokenProvider = tokenProvider,
        )

        val ioDispatcher = Dispatchers.IO

        val authViewModel = AuthViewModel(
            loginUserUseCase = LoginUserUseCase(RemoteAuthRepository(apiService, ioDispatcher)),
            eventBus = clientEventBus,
            dispatcher = ioDispatcher,
        )
        val walletViewModel = WalletViewModel(
            manageWalletUseCase = ManageWalletUseCase(RemoteWalletFeatureRepository(apiService, ioDispatcher)),
            eventBus = clientEventBus,
            dispatcher = ioDispatcher,
        )
        val shopViewModel = ShopViewModel(
            useCase = ShopCatalogAndOrderUseCase(RemoteShopRepository(apiService, ioDispatcher)),
            eventBus = clientEventBus,
            dispatcher = ioDispatcher,
        )
        val studioViewModel = StudioViewModel(
            useCase = StudioJobsUseCase(RemoteStudioRepository(apiService, ioDispatcher)),
            dispatcher = ioDispatcher,
        )

        setContent {
            SuperAppMainScaffold(
                studioViewModel = studioViewModel,
                shopViewModel = shopViewModel,
                walletViewModel = walletViewModel,
                authViewModel = authViewModel,
                onOpenWhatsAppUrl = { whatsappUrl ->
                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(whatsappUrl))
                    startActivity(intent)
                },
            )
        }
    }
}
