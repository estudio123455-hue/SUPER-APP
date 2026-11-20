package co.superapp.features.feat_studio.application

import co.superapp.features.feat_studio.domain.ScheduledStudioPost
import co.superapp.features.feat_studio.domain.StudioContentNiche
import co.superapp.features.feat_studio.domain.StudioJobType
import co.superapp.features.feat_studio.domain.StudioMediaJob
import co.superapp.features.feat_studio.domain.StudioNicheAnalyticsSummary
import co.superapp.features.feat_studio.domain.StudioPublishingSlot
import co.superapp.features.feat_studio.domain.StudioRepository

class StudioJobsUseCase(
    private val repository: StudioRepository,
) {
    suspend fun launchAsyncJob(
        jobType: StudioJobType,
        contentNiche: StudioContentNiche = StudioContentNiche.DESK_SETUP_UGC,
        sourceUrlOrPrompt: String,
        linkedProductId: String? = null,
    ): Result<StudioMediaJob> {
        require(sourceUrlOrPrompt.isNotBlank()) { "El prompt o URL de origen no puede estar vacío." }
        return repository.enqueueJob(
            jobType = jobType,
            contentNiche = contentNiche,
            sourceUrlOrPrompt = sourceUrlOrPrompt.trim(),
            linkedProductId = linkedProductId,
        )
    }

    suspend fun loadMyJobs(): Result<List<StudioMediaJob>> = repository.listCreatorJobs()

    suspend fun scheduleVideoInSlot(
        jobId: String,
        slot: StudioPublishingSlot,
    ): Result<ScheduledStudioPost> = repository.scheduleJobSlot(jobId, slot)

    suspend fun loadPublishingSchedule(): Result<List<ScheduledStudioPost>> =
        repository.getPublishingSchedule()

    suspend fun loadNichePerformanceAnalytics(): Result<StudioNicheAnalyticsSummary> =
        repository.getNichePerformanceAnalytics()
}
