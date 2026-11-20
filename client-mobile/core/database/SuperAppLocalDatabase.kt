package co.superapp.core.database

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "cached_products")
data class CachedProductEntity(
    @PrimaryKey val id: String,
    val sku: String,
    val title: String,
    val description: String,
    val priceCents: Long,
    val stockQuantity: Int,
)

@Entity(tableName = "wardrobe_items")
data class WardrobeItemEntity(
    @PrimaryKey val id: String,
    val title: String,
    val category: String, // TOP, BOTTOM, OUTERWEAR, SHOES
    val imageUri: String,
    val colorHex: String,
    val linkedCommerceProductId: String? = null,
)

@Entity(tableName = "weekly_outfit_plans")
data class WeeklyOutfitPlanEntity(
    @PrimaryKey val dayOfWeek: String,
    val topItemId: String,
    val bottomItemId: String,
    val outerwearItemId: String? = null,
    val aiNote: String,
)

@Dao
interface CachedProductDao {
    @Query("SELECT * FROM cached_products ORDER BY title ASC")
    fun observeCatalog(): Flow<List<CachedProductEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(products: List<CachedProductEntity>)
}

@Dao
interface WardrobeDao {
    @Query("SELECT * FROM wardrobe_items ORDER BY title ASC")
    fun observeWardrobeItems(): Flow<List<WardrobeItemEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertWardrobeItem(item: WardrobeItemEntity)

    @Query("SELECT * FROM weekly_outfit_plans ORDER BY dayOfWeek ASC")
    fun observeWeeklyOutfitPlans(): Flow<List<WeeklyOutfitPlanEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertWeeklyOutfitPlans(plans: List<WeeklyOutfitPlanEntity>)
}

@Database(
    entities = [
        CachedProductEntity::class,
        WardrobeItemEntity::class,
        WeeklyOutfitPlanEntity::class,
    ],
    version = 3,
    exportSchema = false,
)
abstract class SuperAppLocalDatabase : RoomDatabase() {
    abstract fun cachedProductDao(): CachedProductDao
    abstract fun wardrobeDao(): WardrobeDao
}
