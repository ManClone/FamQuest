import unittest

from app.household_assignment import HouseholdChore, suggest_week


class HouseholdAssignmentTests(unittest.TestCase):
    def test_fixed_shopping_is_preserved(self):
        plan = suggest_week(
            [HouseholdChore(1, 60, "fixed", 10), HouseholdChore(2, 30)],
            [10, 20],
        )
        self.assertEqual(plan, {1: 10, 2: 20})

    def test_rotating_chore_changes_person(self):
        plan = suggest_week(
            [HouseholdChore(3, 20, "rotate")],
            [10, 20],
            previous_assignees={3: 10},
        )
        self.assertEqual(plan[3], 20)

    def test_previous_work_counts(self):
        plan = suggest_week(
            [HouseholdChore(5, 15)], [10, 20],
            previous_minutes={10: 90, 20: 10},
        )
        self.assertEqual(plan[5], 20)

    def test_invalid_fixed_member_is_rejected(self):
        with self.assertRaises(ValueError):
            suggest_week([HouseholdChore(1, 10, "fixed", 99)], [10, 20])

    def test_duplicate_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            suggest_week([HouseholdChore(1, 10), HouseholdChore(1, 20)], [10, 20])


if __name__ == "__main__":
    unittest.main()
