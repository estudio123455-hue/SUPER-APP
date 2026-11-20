package co.superapp.app

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import co.superapp.core.designsystem.SuperAppTheme
import co.superapp.features.feat_auth.FeatAuthEntryPoint
import co.superapp.features.feat_auth.presentation.AuthViewModel
import co.superapp.features.feat_shop.FeatShopEntryPoint
import co.superapp.features.feat_shop.presentation.ShopViewModel
import co.superapp.features.feat_studio.FeatStudioEntryPoint
import co.superapp.features.feat_studio.presentation.StudioViewModel
import co.superapp.features.feat_wallet.FeatWalletEntryPoint
import co.superapp.features.feat_wallet.presentation.WalletViewModel

enum class SuperAppTab(val label: String) {
    STUDIO("Studio IA"),
    SHOP("Tienda"),
    WALLET("Billetera"),
    PROFILE("Perfil"),
}

/**
 * App Shell Navigation Scaffold assembling the 4 isolated Mini-Apps via their public_api entry points.
 */
@Composable
fun SuperAppMainScaffold(
    studioViewModel: StudioViewModel,
    shopViewModel: ShopViewModel,
    walletViewModel: WalletViewModel,
    authViewModel: AuthViewModel,
    onOpenWhatsAppUrl: (String) -> Unit = {},
) {
    var selectedTab by rememberSaveable { mutableStateOf(SuperAppTab.STUDIO) }

    SuperAppTheme {
        Scaffold(
            bottomBar = {
                NavigationBar {
                    SuperAppTab.entries.forEach { tab ->
                        NavigationBarItem(
                            selected = selectedTab == tab,
                            onClick = { selectedTab = tab },
                            icon = { Text(tab.label.take(2)) },
                            label = { Text(tab.label) },
                        )
                    }
                }
            },
        ) { innerPadding ->
            Box(modifier = Modifier.padding(innerPadding)) {
                when (selectedTab) {
                    SuperAppTab.STUDIO -> FeatStudioEntryPoint(viewModel = studioViewModel)
                    SuperAppTab.SHOP -> FeatShopEntryPoint(
                        viewModel = shopViewModel,
                        onOpenWhatsAppUrl = onOpenWhatsAppUrl,
                    )
                    SuperAppTab.WALLET -> FeatWalletEntryPoint(viewModel = walletViewModel)
                    SuperAppTab.PROFILE -> FeatAuthEntryPoint(viewModel = authViewModel)
                }
            }
        }
    }
}
