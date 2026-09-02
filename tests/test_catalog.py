import unittest
from pathlib import Path

from market_radar.catalog import load_company_catalog, search_company_catalog


class CompanyCatalogTest(unittest.TestCase):
    def test_expanded_catalog_finds_palantir_and_nu_by_familiar_company_names(self):
        project = Path(__file__).parents[1]
        catalog = load_company_catalog(
            project / "data" / "universe.csv",
            project / "data" / "symbol_catalog.csv",
        )

        palantir = search_company_catalog(catalog, "palantir")
        nu_bank = search_company_catalog(catalog, "nu bank")

        self.assertEqual(palantir[0].ticker, "PLTR")
        self.assertEqual(nu_bank[0].ticker, "NU")
        self.assertIn("Nu Holdings", nu_bank[0].name)
        self.assertEqual(palantir[0].sector, "Information Technology")
        self.assertEqual(nu_bank[0].sector_etf, "XLF")


if __name__ == "__main__":
    unittest.main()
