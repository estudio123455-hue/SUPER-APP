"""Verifies live development endpoints GET /dashboard and GET /api/v1/commerce/products."""

import asyncio
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from httpx import ASGITransport, AsyncClient
from app.main import app


async def test_live_dev_endpoints() -> None:
    from app.core.database import ensure_sqlite_columns_up_to_date
    await ensure_sqlite_columns_up_to_date()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        # 1. Test GET /dashboard
        res_dash = await client.get("/dashboard")
        print(f"GET /dashboard -> status: {res_dash.status_code}, content-type: {res_dash.headers.get('content-type')}")
        assert res_dash.status_code == 200
        assert "✨ Sugerencia de Combo IA (Cross-Selling)" in res_dash.text

        # 2. Test GET /api/v1/commerce/products
        res_prod = await client.get("/api/v1/commerce/products")
        print(f"GET /api/v1/commerce/products -> status: {res_prod.status_code}")
        assert res_prod.status_code == 200
        products = res_prod.json()
        print(f"Returned {len(products)} active products:")
        for p in products:
            print(f"  • SKU: {p['sku']} | {p['title']} | Tallas: {len(p['variants'])} | Cat: {p['category_tag']}")

        # 3. Test GET /api/v1/commerce/products/{id}/cross-sell
        jacket = next((p for p in products if "CHAQUETA" in p["sku"]), products[0])
        res_cross = await client.get(f"/api/v1/commerce/products/{jacket['id']}/cross-sell")
        print(f"GET /api/v1/commerce/products/{jacket['id']}/cross-sell -> status: {res_cross.status_code}")
        assert res_cross.status_code == 200
        combo = res_cross.json()
        if combo:
            print(f"  • Combo: {combo['bundle_name']} | Ahorro: {combo['savings_cents']} cents ({combo['discount_percentage']}%)")

        print("\n✅ Verification SUCCESS: Both /dashboard and /products responded 200 OK without errors!")


if __name__ == "__main__":
    asyncio.run(test_live_dev_endpoints())
