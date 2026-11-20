"""Seeds the local development database with demo users, wallet balance, products (with COGS), and AI jobs."""

import asyncio
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import (  # noqa: E402
    engine,
    ensure_sqlite_columns_up_to_date,
    get_session_factory,
)
from app.core.event_bus import event_bus  # noqa: E402
from app.modules.commerce.application.dtos import (  # noqa: E402
    CreateProductCommand,
    CreatePromoCouponCommand,
)
from app.modules.commerce.application.use_cases import (  # noqa: E402
    CreateProductUseCase,
    CreatePromoCouponUseCase,
)
from app.modules.commerce.domain.entities import Product, ProductVariant  # noqa: E402
from app.modules.commerce.infrastructure.models import CommerceBase  # noqa: E402
from app.modules.commerce.infrastructure.repositories import (  # noqa: E402
    SqlAlchemyProductRepository,
    SqlAlchemyPromoCouponRepository,
)
from app.modules.identity.application.dtos import RegisterUserCommand  # noqa: E402
from app.modules.identity.application.use_cases import RegisterUserUseCase  # noqa: E402
from app.modules.identity.domain.entities import UserRole  # noqa: E402
from app.modules.identity.infrastructure.models import IdentityBase  # noqa: E402
from app.modules.identity.infrastructure.repositories import (  # noqa: E402
    SqlAlchemyUserRepository,
)
from app.modules.identity.infrastructure.security import BcryptPasswordHasher  # noqa: E402
from app.modules.media_ai.application.dtos import EnqueueMediaJobCommand  # noqa: E402
from app.modules.media_ai.application.handlers import (  # noqa: E402
    register_media_ai_event_handlers,
)
from app.modules.media_ai.application.use_cases import (  # noqa: E402
    EnqueueMediaJobUseCase,
    ExecuteMediaJobUseCase,
)
from app.modules.media_ai.domain.entities import JobType  # noqa: E402
from app.modules.media_ai.infrastructure.models import MediaAiBase  # noqa: E402
from app.modules.media_ai.infrastructure.repositories import (  # noqa: E402
    PublicApiCatalogLookupAdapter,
    SqlAlchemyMediaJobRepository,
    artifact_generator,
)
from app.modules.wallet.application.dtos import (  # noqa: E402
    CreateWalletCommand,
    ProcessTransactionCommand,
)
from app.modules.wallet.application.handlers import (  # noqa: E402
    register_wallet_event_handlers,
)
from app.modules.wallet.application.use_cases import (  # noqa: E402
    CreateWalletUseCase,
    ProcessTransactionUseCase,
)
from app.modules.wallet.domain.entities import TransactionType  # noqa: E402
from app.modules.wallet.infrastructure.models import WalletBase  # noqa: E402
from app.modules.wallet.infrastructure.repositories import (  # noqa: E402
    SqlAlchemyWalletRepository,
)


class _NoOpJobDispatcher:
    """Synchronous seed helper so ExecuteMediaJobUseCase can be run deterministically."""

    def dispatch(self, job_id: object) -> None:
        pass


async def seed_demo_data() -> None:
    """Initializes all 4 bounded-context schemas and populates idempotent demo records."""
    async with engine.begin() as conn:
        await conn.run_sync(IdentityBase.metadata.create_all)
        await conn.run_sync(WalletBase.metadata.create_all)
        await conn.run_sync(CommerceBase.metadata.create_all)
        await conn.run_sync(MediaAiBase.metadata.create_all)

    await ensure_sqlite_columns_up_to_date(engine)

    event_bus.clear()
    register_wallet_event_handlers(event_bus)
    register_media_ai_event_handlers(event_bus)

    session_factory = get_session_factory()
    async with session_factory() as session:
        user_repo = SqlAlchemyUserRepository(session)
        wallet_repo = SqlAlchemyWalletRepository(session)
        product_repo = SqlAlchemyProductRepository(session)
        media_repo = SqlAlchemyMediaJobRepository(session)
        catalog_lookup = PublicApiCatalogLookupAdapter(session)

        # 1. Demo User: demo@superapp.co / SuperApp2026!
        existing_user = await user_repo.get_by_email("demo@superapp.co")
        if existing_user is None:
            reg_uc = RegisterUserUseCase(
                repository=user_repo,
                password_hasher=BcryptPasswordHasher(),
                event_bus=event_bus,
            )
            user_dto = await reg_uc.execute(
                RegisterUserCommand(
                    email="demo@superapp.co",
                    password="SuperApp2026!",
                    full_name="Valentina Creadora & Merchant",
                    roles={UserRole.USER, UserRole.CREATOR, UserRole.MERCHANT},
                )
            )
            demo_user_id = user_dto.id
        else:
            demo_user_id = existing_user.id

        # 2. Ensure COP Wallet & Top-up $250,000 COP (25_000_000 cents)
        await CreateWalletUseCase(wallet_repo).execute(
            CreateWalletCommand(user_id=demo_user_id, currency="COP")
        )
        existing_topup = await wallet_repo.get_ledger_by_key("seed-demo-topup-250k")
        if existing_topup is None:
            await ProcessTransactionUseCase(wallet_repo, event_bus).execute(
                ProcessTransactionCommand(
                    user_id=demo_user_id,
                    amount_cents=25_000_000,
                    transaction_type=TransactionType.CREDIT,
                    reference="Recarga Inicial Demo PSE ($250,000 COP)",
                    idempotency_key="seed-demo-topup-250k",
                )
            )

        # 3. Create 2 active catalog products in Commerce with realistic COGS + SUPER10 coupon
        coupon_repo = SqlAlchemyPromoCouponRepository(session)
        await CreatePromoCouponUseCase(coupon_repo).execute(
            CreatePromoCouponCommand(
                code="SUPER10",
                discount_percentage=10,
                max_uses=None,
            )
        )
        create_prod_uc = CreateProductUseCase(product_repo, event_bus)

        combo_product = await product_repo.get_by_sku("COMBO-SETUP-ERGO")
        if combo_product is None:
            combo_dto = await create_prod_uc.execute(
                CreateProductCommand(
                    merchant_id=demo_user_id,
                    sku="COMBO-SETUP-ERGO",
                    title="Combo Setup Ergonómico: Lámpara Monitor + Soporte Laptop",
                    description=(
                        "Lámpara LED asimétrica antirreflejo para monitor + soporte "
                        "plegable de aluminio anodizado para portátil."
                    ),
                    price_cents=9_500_000,  # $95,000 COP
                    unit_cost_cents=4_200_000,  # COGS $42,000 COP
                    stock_quantity=20,
                )
            )
            combo_product_id = combo_dto.id
        else:
            if combo_product.unit_cost_cents == 0:
                await product_repo.save(
                    Product(
                        id=combo_product.id,
                        merchant_id=combo_product.merchant_id,
                        sku=combo_product.sku,
                        title=combo_product.title,
                        description=combo_product.description,
                        price_cents=combo_product.price_cents,
                        unit_cost_cents=4_200_000,
                        stock_quantity=combo_product.stock_quantity,
                        is_active=combo_product.is_active,
                        created_at=combo_product.created_at,
                    )
                )
            combo_product_id = combo_product.id

        jacket_product = await product_repo.get_by_sku("CHAQUETA-RBR-EDITION")
        jacket_variants = (
            ProductVariant(
                variant_sku="RBR-JKT-M-BLK",
                size="M",
                color="Negro",
                stock_quantity=4,
            ),
            ProductVariant(
                variant_sku="RBR-JKT-L-BLK",
                size="L",
                color="Negro",
                stock_quantity=3,
            ),
        )
        if jacket_product is None:
            await create_prod_uc.execute(
                CreateProductCommand(
                    merchant_id=demo_user_id,
                    sku="CHAQUETA-RBR-EDITION",
                    title="Chaqueta Oversize RBR Edition",
                    description=(
                        "Chaqueta streetwear edición especial repelente al agua con "
                        "bordado de alta densidad."
                    ),
                    price_cents=18_000_000,  # $180,000 COP
                    unit_cost_cents=7_500_000,  # COGS $75,000 COP
                    stock_quantity=7,
                    variants=jacket_variants,
                    category_tag="MENSWEAR",
                    complement_tags=("MENSWEAR",),
                )
            )
        else:
            await product_repo.save(
                Product(
                    id=jacket_product.id,
                    merchant_id=jacket_product.merchant_id,
                    sku=jacket_product.sku,
                    title=jacket_product.title,
                    description=jacket_product.description,
                    price_cents=jacket_product.price_cents,
                    unit_cost_cents=7_500_000,
                    stock_quantity=7,
                    variants=jacket_variants,
                    category_tag="MENSWEAR",
                    complement_tags=("MENSWEAR",),
                    is_active=jacket_product.is_active,
                    created_at=jacket_product.created_at,
                )
            )

        # 3b. Add Pantalón Cargo Techwear RBR (Cross-Selling Complement)
        cargo_product = await product_repo.get_by_sku("PANTALON-CARGO-RBR")
        cargo_variants = (
            ProductVariant(
                variant_sku="RBR-CRG-30-BLK",
                size="30",
                color="Negro",
                stock_quantity=2,
            ),
            ProductVariant(
                variant_sku="RBR-CRG-32-BLK",
                size="32",
                color="Negro",
                stock_quantity=2,
            ),
            ProductVariant(
                variant_sku="RBR-CRG-34-BLK",
                size="34",
                color="Negro",
                stock_quantity=2,
            ),
        )
        if cargo_product is None:
            await create_prod_uc.execute(
                CreateProductCommand(
                    merchant_id=demo_user_id,
                    sku="PANTALON-CARGO-RBR",
                    title="Pantalón Cargo Techwear RBR",
                    description=(
                        "Pantalón táctico urbano con bolsillos modulares y tejido "
                        "ripstop impermeable de alta resistencia."
                    ),
                    price_cents=14_500_000,  # $145,000 COP
                    unit_cost_cents=6_000_000,  # COGS $60,000 COP
                    stock_quantity=6,
                    variants=cargo_variants,
                    category_tag="MENSWEAR",
                    complement_tags=("MENSWEAR",),
                )
            )
        else:
            await product_repo.save(
                Product(
                    id=cargo_product.id,
                    merchant_id=cargo_product.merchant_id,
                    sku=cargo_product.sku,
                    title=cargo_product.title,
                    description=cargo_product.description,
                    price_cents=cargo_product.price_cents,
                    unit_cost_cents=6_000_000,
                    stock_quantity=6,
                    variants=cargo_variants,
                    category_tag="MENSWEAR",
                    complement_tags=("MENSWEAR",),
                    is_active=cargo_product.is_active,
                    created_at=cargo_product.created_at,
                )
            )

        # 4. Create 2 completed AI / Video jobs in Media AI
        existing_jobs = await media_repo.list_by_creator(demo_user_id)
        if not existing_jobs:
            enqueue_uc = EnqueueMediaJobUseCase(
                repository=media_repo,
                catalog_lookup=catalog_lookup,
                dispatcher=_NoOpJobDispatcher(),
                event_bus=event_bus,
            )
            execute_uc = ExecuteMediaJobUseCase(
                repository=media_repo,
                catalog_lookup=catalog_lookup,
                event_bus=event_bus,
                artifact_generator=artifact_generator,
            )

            showcase_job = await enqueue_uc.execute(
                EnqueueMediaJobCommand(
                    creator_id=demo_user_id,
                    job_type=JobType.PRODUCT_SHOWCASE_VIDEO,
                    source_url_or_prompt="https://storage.superapp.io/demo/setup_ergo_raw.mp4",
                    linked_product_id=combo_product_id,
                )
            )
            await execute_uc.execute(showcase_job.id)

            outfit_job = await enqueue_uc.execute(
                EnqueueMediaJobCommand(
                    creator_id=demo_user_id,
                    job_type=JobType.AI_OUTFIT_RECOMMENDATION,
                    source_url_or_prompt="Look urbano nocturno en Bogotá con Chaqueta Oversize RBR",
                    linked_product_id=None,
                )
            )
            await execute_uc.execute(outfit_job.id)

    await engine.dispose()
    print("Seed completed successfully: demo@superapp.co / SuperApp2026!")


if __name__ == "__main__":
    asyncio.run(seed_demo_data())
