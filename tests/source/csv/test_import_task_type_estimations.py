import datetime
import os
import tempfile

from tests.base import ApiDBTestCase

from zou.app.models.task import Task

from zou.app.services import comments_service


class ImportCsvTaskTypeEstimationsTestCase(ApiDBTestCase):
    def setUp(self):
        super(ImportCsvTaskTypeEstimationsTestCase, self).setUp()

        # Creates sequence "S01", shot "P01" and an Animation task on it,
        # cascading the project, department, task type, person and assigner.
        self.generate_fixture_shot_task()
        self.task_type_id = self.task_type_animation.id
        self.path = self.estimations_path(self.task_type_id)

    def write_csv(self, content):
        """
        Write CSV content to a temporary file and return its path.
        """
        descriptor, file_path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return file_path

    def estimations_path(self, task_type_id):
        """
        Build the estimations import URL for the given task type.
        """
        return (
            f"/import/csv/projects/{self.project.id}"
            f"/task-types/{task_type_id}/estimations"
        )

    def import_csv(self, content, code=201, task_type_id=None):
        """
        Upload CSV content to the estimations import endpoint. Defaults to the
        Animation (Shot) task type; pass task_type_id to target another one.
        """
        path = (
            self.path
            if task_type_id is None
            else self.estimations_path(task_type_id)
        )
        return self.upload_file(path, self.write_csv(content), code)

    def assert_task_date(self, task, field, expected):
        """
        Assert that a task date column equals the expected YYYY-MM-DD string.
        """
        self.assertEqual(getattr(task, field).strftime("%Y-%m-%d"), expected)

    def test_import_matches_asset_entity(self):
        # For assets, a row is matched on its asset type ("Props") as Parent
        # and its asset name ("Tree") as Entity.
        self.generate_fixture_task()
        content = "Parent,Entity,Start date\nProps,Tree,2024-01-05\n"
        self.import_csv(content, task_type_id=self.task_type.id)

        task = Task.get(self.task.id)
        self.assert_task_date(task, "start_date", "2024-01-05")

    def test_import_real_dates(self):
        content = (
            "Parent,Entity,Estimation,Start date,Due date,Difficulty,"
            "WIP date,Feedback date,Approval date\n"
            "S01,P01,2,2024-01-01,2024-01-10,3,"
            "2024-01-05,2024-01-20,2024-01-25\n"
        )
        self.import_csv(content)

        task = Task.get(self.shot_task.id)
        # New real-date columns
        self.assert_task_date(task, "real_start_date", "2024-01-05")
        self.assert_task_date(task, "end_date", "2024-01-20")
        self.assert_task_date(task, "done_date", "2024-01-25")
        # Existing columns still work (backward compatibility)
        self.assert_task_date(task, "start_date", "2024-01-01")
        self.assert_task_date(task, "due_date", "2024-01-10")
        self.assertEqual(task.difficulty, 3)
        self.assertIsNotNone(task.estimation)

    def test_import_empty_real_dates_are_skipped(self):
        # Pre-set the real-date columns then import empty cells: empty cells
        # follow the existing convention (skip, do not null the field).
        self.shot_task.update(
            {
                "real_start_date": datetime.datetime(2023, 12, 1),
                "end_date": datetime.datetime(2023, 12, 2),
                "done_date": datetime.datetime(2023, 12, 3),
            }
        )
        content = (
            "Parent,Entity,WIP date,Feedback date,Approval date\n"
            "S01,P01,,,\n"
        )
        self.import_csv(content)

        task = Task.get(self.shot_task.id)
        self.assert_task_date(task, "real_start_date", "2023-12-01")
        self.assert_task_date(task, "end_date", "2023-12-02")
        self.assert_task_date(task, "done_date", "2023-12-03")

    def test_imported_real_start_date_survives_wip_transition(self):
        # An imported real_start_date (admin override) must not be overwritten
        # when the task later transitions to a WIP status, since the auto-set
        # only fills the field when it is null.
        content = "Parent,Entity,WIP date\nS01,P01,2024-01-05\n"
        self.import_csv(content)

        task_status_wip = self.generate_fixture_task_status_wip()
        comments_service.create_comment(
            self.person.id,
            str(self.shot_task.id),
            task_status_wip.id,
            "Moving to WIP",
        )

        task = Task.get(self.shot_task.id)
        self.assert_task_date(task, "real_start_date", "2024-01-05")
