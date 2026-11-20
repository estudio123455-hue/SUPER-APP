package co.superapp.features.feat_shop

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import co.superapp.features.feat_shop.presentation.ShopRoute
import co.superapp.features.feat_shop.presentation.ShopViewModel

/**
 * Public API surface for feat_shop (Law 1).
 */
@Composable
fun FeatShopEntryPoint(
    viewModel: ShopViewModel,
    onOpenWhatsAppUrl: (String) -> Unit = {},
    modifier: Modifier = Modifier,
) {
    ShopRoute(
        viewModel = viewModel,
        onOpenWhatsAppUrl = onOpenWhatsAppUrl,
        modifier = modifier,
    )
}
