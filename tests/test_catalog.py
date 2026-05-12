import unittest

from material_eval.catalog import Catalog


class CatalogTest(unittest.TestCase):
    def test_loads_legacy_seed_catalog(self):
        catalog = Catalog()

        self.assertEqual(len(catalog.domains), 8)
        self.assertEqual(len(catalog.parts), 17)
        self.assertEqual(len(catalog.mvp_parts()), 3)

    def test_get_part(self):
        catalog = Catalog()

        part = catalog.get_part("人形机器人核心骨架", "下肢大扭矩管状连杆")

        self.assertEqual(part.topology, "BEAM")
        self.assertTrue(part.geometry_inputs)


if __name__ == "__main__":
    unittest.main()
