package co.superapp.features.feat_studio

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import co.superapp.features.feat_studio.presentation.StudioRoute
import co.superapp.features.feat_studio.presentation.StudioViewModel

/**
 * Public API surface for feat_studio (Law 1).
 */
@Composable
fun FeatStudioEntryPoint(
    viewModel: StudioViewModel,
    modifier: Modifier = Modifier,
) {
    StudioRoute(viewModel = viewModel, modifier = modifier)
}
