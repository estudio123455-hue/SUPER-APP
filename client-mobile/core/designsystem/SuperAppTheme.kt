package co.superapp.core.designsystem

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.airbnb.lottie.compose.LottieAnimation
import com.airbnb.lottie.compose.LottieCompositionSpec
import com.airbnb.lottie.compose.LottieConstants
import com.airbnb.lottie.compose.rememberLottieComposition

private val SuperAppDarkColorScheme = darkColorScheme(
    primary = Color(0xFF00E5A3),
    onPrimary = Color(0xFF051F17),
    secondary = Color(0xFF7C4DFF),
    onSecondary = Color(0xFFFFFFFF),
    tertiary = Color(0xFFFFB300),
    background = Color(0xFF0B0F17),
    surface = Color(0xFF151C28),
    onBackground = Color(0xFFF3F6FC),
    onSurface = Color(0xFFE2E8F0),
)

@Composable
fun SuperAppTheme(
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = SuperAppDarkColorScheme,
        content = content,
    )
}

/**
 * Reusable header powered by Lottie Compose (com.airbnb.android:lottie-compose:6.4.1)
 * rendering pet_mascot.json from assets/ in an infinite loop.
 */
@Composable
fun SuperAppLottieHeader(
    title: String,
    subtitle: String,
    lottieAssetName: String = "pet_mascot.json",
    modifier: Modifier = Modifier,
) {
    val composition by rememberLottieComposition(
        LottieCompositionSpec.Asset(lottieAssetName)
    )

    Surface(
        color = MaterialTheme.colorScheme.surface,
        modifier = modifier.fillMaxWidth(),
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.padding(16.dp),
        ) {
            LottieAnimation(
                composition = composition,
                iterations = LottieConstants.IterateForever,
                modifier = Modifier.size(64.dp),
            )
            Text(
                text = title,
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.75f),
            )
        }
    }
}
